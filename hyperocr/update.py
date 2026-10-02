"""Update HYPER-OCR in place from its GitHub repository.

    python -m hyperocr.update            # check, and update if a newer version exists
    python -m hyperocr.update --check    # only say whether there is one
    python -m hyperocr.update --yes      # update without asking

Only the app's own files are replaced. Python, the installed packages, Tesseract,
the language files and the Unlimited-OCR model stay as they are; packages are
reinstalled only when the new version's requirements differ. The previous
version is kept in .backup/<version>/ and restored automatically if anything
goes wrong while files are being replaced.

This runs as its own process, started by the app's "Check for Updates" button
(or the update-windows.bat / update.sh files). It is the only part of HYPER-OCR
that goes online, and only when asked.
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
import urllib.request
import zipfile
from pathlib import Path

from . import __version__

REPO = os.environ.get("HYPEROCR_UPDATE_REPO", "omar-184/HYPER-OCR")
API = os.environ.get("HYPEROCR_UPDATE_API", "https://api.github.com").rstrip("/")
ROOT = Path(os.environ.get("HYPEROCR_APP_ROOT", Path(__file__).resolve().parents[1]))
# Never touched by an update: the environment, models, languages, backups.
KEEP = {".venv", "venv", "models", "tessdata", "tesseract", ".backup", ".git", ".github"}
REQUIREMENTS = ("requirements.txt", "requirements-gpu.txt")


class UpdateError(RuntimeError):
    pass


def _get(url: str, accept: str = "application/vnd.github+json") -> bytes:
    req = urllib.request.Request(url, headers={"Accept": accept, "User-Agent": "HYPER-OCR-updater"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.read()
    except Exception as exc:
        raise UpdateError("network: %s" % exc) from exc


def parse_version(text: str) -> tuple[int, ...]:
    m = re.search(r'__version__\s*=\s*["\'](\d+(?:\.\d+)*)["\']', text) or re.fullmatch(r"(\d+(?:\.\d+)*)", text.strip())
    if not m:
        raise UpdateError("no version found")
    return tuple(int(p) for p in m.group(1).split("."))


def _fmt(v: tuple[int, ...]) -> str:
    return ".".join(str(p) for p in v)


def check() -> dict:
    info = json.loads(_get("%s/repos/%s" % (API, REPO)))
    branch = info.get("default_branch") or "main"
    text = _get("%s/repos/%s/contents/hyperocr/__init__.py?ref=%s" % (API, REPO, branch),
                accept="application/vnd.github.raw").decode("utf-8", "replace")
    latest = parse_version(text)
    current = parse_version(__version__)
    return {"current": _fmt(current), "latest": _fmt(latest), "available": latest > current, "branch": branch}


def apply(say=print) -> dict:
    state = check()
    if not state["available"]:
        say({"step": "upToDate", **state})
        return dict(state, updated=False)
    say({"step": "downloading", "version": state["latest"]})
    with tempfile.TemporaryDirectory(prefix="hyperocr-update-") as tmp:
        archive = Path(tmp) / "update.zip"
        archive.write_bytes(_get("%s/repos/%s/zipball/%s" % (API, REPO, state["branch"])))
        say({"step": "unpacking"})
        new_root = _unpack(archive, Path(tmp) / "new")
        found = parse_version((new_root / "hyperocr" / "__init__.py").read_text(encoding="utf-8"))
        if found <= parse_version(__version__):
            raise UpdateError("the download is not newer than this version")
        packages_changed = _req_hash(ROOT) != _req_hash(new_root)
        say({"step": "installing"})
        backup = ROOT / ".backup" / __version__
        _backup(backup)
        try:
            _replace(new_root)
        except Exception:
            _restore(backup)
            raise
    if packages_changed:
        say({"step": "packages"})
        _install_packages()
    result = dict(state, updated=True, packages=packages_changed)
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


def _backup(target: Path) -> None:
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    for p in _entries(ROOT):
        if p.is_dir():
            shutil.copytree(p, target / p.name, ignore=shutil.ignore_patterns("__pycache__"))
        else:
            shutil.copy2(p, target / p.name)


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


def _restore(backup: Path) -> None:
    for p in backup.iterdir():
        dst = ROOT / p.name
        if p.is_dir():
            _sync_dir(p, dst)
        else:
            shutil.copy2(p, dst)


def _req_hash(root: Path) -> str:
    h = hashlib.sha256()
    for name in REQUIREMENTS:
        f = root / name
        h.update(name.encode() + b"\0" + (f.read_bytes() if f.is_file() else b"") + b"\0")
    return h.hexdigest()


def _install_packages() -> None:
    pip = [sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "-q"]
    _run(pip + ["-r", str(ROOT / "requirements.txt")])
    _run(pip + ["--no-deps", "markitdown>=0.1.2,<0.2"])
    if os.environ.get("HYPEROCR_GPU", "").strip() != "1":
        return  # the experimental GPU engine is off: never download its packages
    try:
        import torch  # noqa: F401  (only people who installed GPU support get its updates)

        _run(pip + ["-r", str(ROOT / "requirements-gpu.txt")])
    except ImportError:
        pass


def _run(cmd: list[str]) -> None:
    done = subprocess.run(cmd, capture_output=True, text=True)
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
