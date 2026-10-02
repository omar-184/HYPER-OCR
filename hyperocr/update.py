"""Update HYPER-OCR in place from its latest GitHub Release.

    python -m hyperocr.update            # check, and update if a newer release exists
    python -m hyperocr.update --check    # only say whether there is one
    python -m hyperocr.update --yes      # update without asking

Only a published GitHub Release is installed, never whatever happens to be on a
branch: the release must carry HYPER-OCR-<version>.zip and its .sha256, and the
download must match that checksum (made by tools/make_release.py).

Only the app's own files are replaced: the top-level files and folders the release
contains. Python, the installed packages, Tesseract, the language files, the model
and any folder of your own stay as they are. When the release needs different
packages they are installed first, before any file is touched: if that fails,
nothing changes. The replaced files are kept in .backup/<version>/ (only the last
update's) and put back automatically if anything goes wrong while copying.

The desktop app (HYPER-OCR.exe) is updated by its installer instead: the release's
HYPER-OCR-Setup-<version>.exe, checked against its .sha256 like the zip, is started
and replaces the whole app, Tesseract included; the app closes, and the installer
opens the new version. Windows installs it for the current user, so no
administrator prompt appears.

This runs as its own process, started by the app's "Check for Updates" button
(or the update-windows.bat / update.sh files; in the desktop app,
HYPER-OCR.exe --update). It is the only part of HYPER-OCR that goes online, and
only when asked.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

from . import __version__
from .paths import APP_ROOT, FROZEN, no_window

REPO = os.environ.get("HYPEROCR_UPDATE_REPO", "omar-184/HYPER-OCR")
API = os.environ.get("HYPEROCR_UPDATE_API", "https://api.github.com").rstrip("/")
ROOT = Path(os.environ.get("HYPEROCR_APP_ROOT", APP_ROOT))
# The desktop app updates through its installer; a checkout through the zip.
INSTALLER = FROZEN or os.environ.get("HYPEROCR_UPDATE_KIND") == "installer"
SETUP_FOLDER = "hyperocr-setup-"      # in the temporary folder; the previous update's is removed
# Never touched by an update: the environment, models, languages, backups.
KEEP = {".venv", "venv", "models", "tessdata", "tesseract", ".backup", ".git", ".github"}
REQUIREMENTS = ("requirements.txt", "requirements-gpu.txt")


class UpdateError(RuntimeError):
    pass


def _get(url: str, accept: str = "application/vnd.github+json") -> bytes:
    req = urllib.request.Request(url, headers={"Accept": accept, "User-Agent": "HYPER-OCR-updater"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.read()
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise NotFound(url) from exc
        raise UpdateError("network: %s" % exc) from exc
    except Exception as exc:
        raise UpdateError("network: %s" % exc) from exc


class NotFound(UpdateError):
    pass


def parse_version(text: str) -> tuple[int, ...]:
    m = re.search(r'__version__\s*=\s*["\'](\d+(?:\.\d+)*)["\']', text) or re.fullmatch(r"(\d+(?:\.\d+)*)", text.strip())
    if not m:
        raise UpdateError("no version found")
    return tuple(int(p) for p in m.group(1).split("."))


def _fmt(v: tuple[int, ...]) -> str:
    return ".".join(str(p) for p in v)


def _latest_release() -> dict | None:
    """GitHub's latest published release (drafts and pre-releases never count), or None."""
    try:
        return json.loads(_get("%s/repos/%s/releases/latest" % (API, REPO)))
    except NotFound:
        return None


def asset_name(version: str, installer: bool | None = None) -> str:
    installer = INSTALLER if installer is None else installer
    return ("HYPER-OCR-Setup-%s.exe" if installer else "HYPER-OCR-%s.zip") % version


def check() -> dict:
    current = parse_version(__version__)
    state = {"current": _fmt(current), "latest": _fmt(current), "available": False, "release": None}
    release = _latest_release()
    if release is None:
        return state                                  # nothing published yet
    latest = parse_version(str(release.get("tag_name", "")).lstrip("vV"))
    name = asset_name(_fmt(latest))
    assets = {a.get("name"): a for a in release.get("assets", [])}
    if name not in assets or name + ".sha256" not in assets:
        raise UpdateError("release %s has no %s with its .sha256" % (release.get("tag_name"), name))
    state.update(latest=_fmt(latest), available=latest > current, release=release.get("tag_name"),
                 download=assets[name]["browser_download_url"], sha256=assets[name + ".sha256"]["browser_download_url"])
    return state


def _verified(state: dict) -> bytes:
    """The release's file, refused unless it matches the SHA-256 published with it."""
    data = _get(state["download"], accept="application/octet-stream")
    expected = _get(state["sha256"], accept="application/octet-stream").decode("ascii", "replace").split()
    if not expected or expected[0].lower() != hashlib.sha256(data).hexdigest():
        raise UpdateError("the download does not match its published SHA-256: not installed")
    return data


def apply(say=print) -> dict:
    state = check()
    if not state["available"]:
        say({"step": "upToDate", **state})
        return dict(state, updated=False)
    say({"step": "downloading", "version": state["latest"]})
    if INSTALLER:
        return _run_installer(state, _verified(state), say)
    with tempfile.TemporaryDirectory(prefix="hyperocr-update-") as tmp:
        archive = Path(tmp) / "update.zip"
        archive.write_bytes(_verified(state))
        say({"step": "unpacking"})
        new_root = _unpack(archive, Path(tmp) / "new")
        found = parse_version((new_root / "hyperocr" / "__init__.py").read_text(encoding="utf-8"))
        if _fmt(found) != state["latest"]:
            raise UpdateError("the release %s contains version %s" % (state["release"], _fmt(found)))
        packages_changed = _req_hash(ROOT) != _req_hash(new_root)
        if packages_changed:
            say({"step": "packages"})
            _install_packages(new_root)              # before any file is replaced: a failure changes nothing
        say({"step": "installing"})
        names = [p.name for p in _entries(new_root)]
        backup = ROOT / ".backup" / __version__
        _backup(backup, names)
        try:
            _replace(new_root)
        except Exception:
            _restore(backup, names)
            raise
        _prune_backups(keep=backup)
    result = dict(state, updated=True, packages=packages_changed)
    say({"step": "done", **result})
    return result


def _run_installer(state: dict, data: bytes, say) -> dict:
    """Start the checked installer on its own and report done: the app then closes, the
    installer replaces it (its /CLOSEAPPLICATIONS closes it if it hasn't yet) and opens the
    new version. Only the previous update's installer is cleaned up, never this one: it is
    still running after this process ends."""
    tmp = Path(tempfile.gettempdir())
    for old in tmp.glob(SETUP_FOLDER + "*"):
        shutil.rmtree(old, ignore_errors=True)
    folder = Path(tempfile.mkdtemp(prefix=SETUP_FOLDER))
    setup = folder / asset_name(state["latest"], installer=True)
    setup.write_bytes(data)
    say({"step": "installing"})
    cmd = [str(setup), "/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CLOSEAPPLICATIONS"]
    if os.environ.get("HYPEROCR_UPDATE_DRY_RUN") == "1":      # tests: everything but starting it
        cmd = None
    elif sys.platform == "win32":
        detached = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
        subprocess.Popen(cmd, close_fds=True, creationflags=detached)
    else:
        raise UpdateError("the installer runs on Windows only")
    result = dict(state, updated=True, packages=False, installer=str(setup))
    say({"step": "done", **result})
    return result


def _unpack(archive: Path, dest: Path) -> Path:
    with zipfile.ZipFile(archive) as z:
        for member in z.namelist():
            target = (dest / member).resolve()
            if dest.resolve() not in target.parents and target != dest.resolve():
                raise UpdateError("unsafe path in download: %s" % member)
        z.extractall(dest)
    tops = [p for p in dest.iterdir() if p.is_dir()]
    root = tops[0] if len(tops) == 1 else dest   # GitHub wraps everything in owner-repo-sha/
    if not (root / "hyperocr" / "__init__.py").is_file():
        raise UpdateError("the download does not look like HYPER-OCR")
    return root


def _entries(root: Path):
    for p in sorted(root.iterdir()):
        if p.name in KEEP or p.name.startswith(".git") or p.name == "__pycache__":
            continue
        yield p


def _backup(target: Path, names: list[str]) -> None:
    """Copy what the update will replace: only the app's own top-level files and folders."""
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    for name in names:
        p = ROOT / name
        if p.is_dir():
            shutil.copytree(p, target / name, ignore=shutil.ignore_patterns("__pycache__"))
        elif p.is_file():
            shutil.copy2(p, target / name)


def _prune_backups(keep: Path) -> None:
    """Only the last update's backup is kept."""
    for old in (ROOT / ".backup").iterdir():
        if old != keep and old.is_dir():
            shutil.rmtree(old, ignore_errors=True)


def _replace(new_root: Path) -> None:
    """Copy the new version over the old one, then remove app files it no longer has.
    Files are overwritten rather than folders deleted, which works while the app runs."""
    for src in _entries(new_root):
        dst = ROOT / src.name
        if src.is_dir():
            _sync_dir(src, dst)
        else:
            if dst.is_dir():
                shutil.rmtree(dst)
            _copy_if_changed(src, dst)


def _sync_dir(src: Path, dst: Path) -> None:
    if dst.exists() and not dst.is_dir():
        dst.unlink()
    dst.mkdir(parents=True, exist_ok=True)
    wanted = set()
    for item in src.rglob("*"):
        rel = item.relative_to(src)
        if "__pycache__" in rel.parts:
            continue
        wanted.add(rel)
        target = dst / rel
        if item.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            _copy_if_changed(item, target)
    for item in sorted(dst.rglob("*"), reverse=True):
        rel = item.relative_to(dst)
        if "__pycache__" in rel.parts or rel in wanted:
            continue
        if item.is_dir():
            shutil.rmtree(item, ignore_errors=True)
        else:
            item.unlink(missing_ok=True)


def _copy_if_changed(src: Path, dst: Path) -> None:
    """Rewrite only files that changed (Windows re-reads a running .bat from disk)."""
    if dst.is_file() and dst.read_bytes() == src.read_bytes():
        return
    shutil.copy2(src, dst)
    _keep_executable(dst)


def _keep_executable(path: Path) -> None:
    if path.suffix in (".sh", ".command"):
        path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _restore(backup: Path, names: list[str]) -> None:
    for name in names:
        saved, dst = backup / name, ROOT / name
        if saved.is_dir():
            _sync_dir(saved, dst)
        elif saved.is_file():
            if dst.is_dir():
                shutil.rmtree(dst)
            shutil.copy2(saved, dst)
        elif dst.is_dir():                 # new in the failed version: remove it again
            shutil.rmtree(dst, ignore_errors=True)
        elif dst.exists():
            dst.unlink()


def _req_hash(root: Path) -> str:
    h = hashlib.sha256()
    for name in REQUIREMENTS:
        f = root / name
        h.update(name.encode() + b"\0" + (f.read_bytes() if f.is_file() else b"") + b"\0")
    return h.hexdigest()


def _install_packages(new_root: Path) -> None:
    """The new version's packages, into this app's Python, before its files are copied in."""
    pip = [sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "-q"]
    _run(pip + ["-r", str(new_root / "requirements.txt")])
    _run(pip + ["--no-deps", "markitdown>=0.1.2,<0.2"])
    if os.environ.get("HYPEROCR_GPU", "").strip() != "1":
        return  # the experimental GPU engine is off: never download its packages
    try:
        import torch  # noqa: F401  (only people who installed GPU support get its updates)

        _run(pip + ["-r", str(new_root / "requirements-gpu.txt")])
    except ImportError:
        pass


def _run(cmd: list[str]) -> None:
    done = subprocess.run(cmd, capture_output=True, text=True, **no_window())
    if done.returncode != 0:
        raise UpdateError("package install failed: %s" % (done.stderr.strip().splitlines() or ["?"])[-1])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Update HYPER-OCR from GitHub.")
    parser.add_argument("--check", action="store_true", help="only check for a newer version")
    parser.add_argument("--yes", action="store_true", help="update without asking")
    parser.add_argument("--json", action="store_true", help="machine-readable progress (used by the app)")
    args = parser.parse_args(argv)

    def say(event: dict) -> None:
        if args.json:
            print(json.dumps(event), flush=True)
        elif event.get("step") == "upToDate":
            print("HYPER-OCR %s is up to date." % event["current"])
        elif event.get("step") == "downloading":
            print("Downloading HYPER-OCR %s ..." % event["version"])
        elif event.get("step") == "packages":
            print("Installing updated packages ...")
        elif event.get("step") == "done":
            print("Updated to %s. Start HYPER-OCR again to use it." % event["latest"])

    try:
        if args.check:
            state = check()
            if args.json:
                print(json.dumps(state))
            elif state["available"]:
                print("HYPER-OCR %s is available (you have %s)." % (state["latest"], state["current"]))
            else:
                print("HYPER-OCR %s is up to date." % state["current"])
            return 0
        if not args.yes and not args.json:
            state = check()
            if not state["available"]:
                say({"step": "upToDate", **state})
                return 0
            answer = input("Update from %s to %s? [Y/n] " % (state["current"], state["latest"]))
            if answer.strip().lower().startswith("n"):
                return 0
        apply(say)
        return 0
    except UpdateError as exc:
        if args.json:
            print(json.dumps({"step": "failed", "error": str(exc)}), flush=True)
        else:
            print("The update did not finish: %s" % exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
