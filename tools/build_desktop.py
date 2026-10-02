"""Build the HYPER-OCR desktop app for Windows: HYPER-OCR.exe, then its installer.

    python tools/build_desktop.py tesseract DEST      # the pinned Tesseract and languages, checked, in DEST
    python tools/build_desktop.py app                 # dist/HYPER-OCR/ (Tesseract, languages, self-test)
    python tools/build_desktop.py app --installer     # ... and dist/HYPER-OCR-Setup-<version>.exe + .sha256

Needs (pip): requirements.txt, MarkItDown without its dependencies (as setup installs it),
and requirements-desktop.txt. On Windows, 7-Zip (to unpack Tesseract's installer) and
Inno Setup 6 (for --installer). GitHub builds it on every push: .github/workflows/desktop.yml.

Everything downloaded is pinned by SHA-256: the Tesseract build the tests pass on
(UB Mannheim's 5.4.0.20240606, the one Windows setup installs) and the language files.
The app then converts the test documents with its own Tesseract before it counts as built.
On Linux and macOS, `app` builds the same app for checking the recipe, with the system's
Tesseract (it has no Tesseract of its own there).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hyperocr.engines.tesseract_engine import TESTED_VERSION, WINGET_VERSION  # noqa: E402

CACHE = ROOT / "build" / "downloads"
DIST = ROOT / "dist"
APP = DIST / "HYPER-OCR"
EXE = APP / ("HYPER-OCR.exe" if sys.platform == "win32" else "HYPER-OCR")

TESSERACT = {
    "url": "https://github.com/UB-Mannheim/tesseract/releases/download/v%s/tesseract-ocr-w64-setup-%s.exe"
           % (WINGET_VERSION, WINGET_VERSION),
    "sha256": "c885fff6998e0608ba4bb8ab51436e1c6775c2bafc2559a19b423e18678b60c9",
}
# Tesseract's standard models (tesseract-ocr/tessdata), the ones setup downloads; every test
# passes on them with Tesseract 5.4.0 and 5.3.4.
TESSDATA_COMMIT = "ced78752cc61322fb554c280d13360b35b8684e4"
TESSDATA = {
    "eng": "daa0c97d651c19fba3b25e81317cd697e9908c8208090c94c3905381c23fc047",
    "ara": "2005976778bbc14fc56a4ea8d43c6080847aeee72fcc2201488f240daca15c5b",
    "osd": "e19f2ae860792fdf372cf48d8ce70ae5da3c4052962fe22e9de1f680c374bb0e",
}
TESSDATA_URL = "https://raw.githubusercontent.com/tesseract-ocr/tessdata/%s/%%s.traineddata" % TESSDATA_COMMIT


def fetch(url: str, sha256: str, name: str) -> Path:
    """A download, kept in build/downloads, refused unless it has the pinned SHA-256."""
    CACHE.mkdir(parents=True, exist_ok=True)
    dest = CACHE / name
    if not (dest.is_file() and _sha256(dest) == sha256):
        print("Downloading %s ..." % name, flush=True)
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "HYPER-OCR-build"}),
                                    timeout=300) as r:
            dest.with_suffix(".part").write_bytes(r.read())
        dest.with_suffix(".part").replace(dest)
    found = _sha256(dest)
    if found != sha256:
        dest.unlink()
        raise SystemExit("%s: SHA-256 %s, expected %s. Not used." % (name, found, sha256))
    return dest


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


def seven_zip() -> str:
    for c in (shutil.which("7z"), r"C:\Program Files\7-Zip\7z.exe", r"C:\Program Files (x86)\7-Zip\7z.exe"):
        if c and Path(c).is_file():
            return c
    raise SystemExit("7-Zip is needed to unpack Tesseract's installer.")


def needed_dlls(folder: Path, program: str = "tesseract.exe") -> set[str]:
    """The DLLs `program` loads, directly or through another DLL, among those in `folder`.
    UB Mannheim's build also carries those of Tesseract's training tools (GLib, Pango, cairo,
    ICU...): 25 files, 46 MB the app never loads."""
    import pefile

    present = {p.name.lower(): p for p in folder.iterdir()}
    needed: set[str] = set()
    todo = [program.lower()]
    while todo:
        name = todo.pop()
        if name in needed:
            continue
        needed.add(name)
        pe = pefile.PE(str(present[name]), fast_load=True)
        pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_IMPORT"],
                                               pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_DELAY_IMPORT"]])
        for entry in ("DIRECTORY_ENTRY_IMPORT", "DIRECTORY_ENTRY_DELAY_IMPORT"):
            for imported in getattr(pe, entry, []):
                dll = imported.dll.decode("ascii", "replace").lower()
                if dll in present:
                    todo.append(dll)        # system DLLs (KERNEL32, msvcrt...) aren't in the folder
    return {present[n].name for n in needed}


def add_tesseract(dest: Path) -> Path:
    """Tesseract's program and the libraries it loads (no training tools, no languages: those
    come next), with its licence, unpacked from the pinned installer."""
    setup = fetch(TESSERACT["url"], TESSERACT["sha256"], Path(TESSERACT["url"]).name)
    target = dest / "tesseract"
    if target.exists():
        shutil.rmtree(target)
    unpacked = CACHE / "tesseract-unpacked"
    if unpacked.exists():
        shutil.rmtree(unpacked)
    subprocess.run([seven_zip(), "x", "-y", "-o%s" % unpacked, str(setup), "tesseract.exe", "*.dll", "doc"],
                   check=True, stdout=subprocess.DEVNULL)
    target.mkdir(parents=True)
    for name in sorted(needed_dlls(unpacked)):
        shutil.copy2(unpacked / name, target / name)
    shutil.copytree(unpacked / "doc", target / "doc")
    return target / "tesseract.exe"


def add_languages(dest: Path) -> Path:
    target = dest / "tessdata"
    target.mkdir(parents=True, exist_ok=True)
    for code, sha256 in TESSDATA.items():
        shutil.copy2(fetch(TESSDATA_URL % code, sha256, "%s-%s.traineddata" % (code, TESSDATA_COMMIT[:8])),
                     target / ("%s.traineddata" % code))
    return target


def tesseract_command(argv: list[str]) -> int:
    """The pinned Tesseract and languages in DEST (for the Windows test run)."""
    dest = Path(argv[0]).resolve()
    exe = add_tesseract(dest)
    tessdata = add_languages(dest)
    print(json.dumps({"tesseract": str(exe), "tessdata": str(tessdata)}))
    return 0


def version() -> str:
    return re.search(r'__version__ = "([\d.]+)"', (ROOT / "hyperocr" / "__init__.py").read_text()).group(1)


def build_app() -> None:
    subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--distpath", str(DIST),
                    "--workpath", str(ROOT / "build" / "pyinstaller"), str(ROOT / "packaging" / "HYPER-OCR.spec")],
                   check=True, cwd=ROOT)
    if sys.platform == "win32":
        add_tesseract(APP)
    add_languages(APP)


def self_test() -> None:
    """The built app converts both test documents with its own Tesseract and languages."""
    checks = [
        ("scanned_english.pdf", "eng", ["# Effect of Early Mobilisation After Surgery", "| Day 2 | 88 | 57.9 | 5.3 |"]),
        ("scanned_arabic.pdf", "eng+ara", ["# تقرير المتابعة الطبية", "## نتائج التحاليل", "Amlodipine"]),
    ]
    for name, langs, expected in checks:
        out = ROOT / "build" / "self-test" / Path(name).stem
        if out.exists():
            shutil.rmtree(out)
        done = subprocess.run([str(EXE), "--self-test", str(ROOT / "tests" / "fixtures" / name), str(out),
                               "--lang", langs], cwd=APP, timeout=900)
        report_file = out / "self-test.json"
        if not report_file.is_file():
            raise SystemExit("self-test %s: no report (exit %s)" % (name, done.returncode))
        report = json.loads(report_file.read_text(encoding="utf-8"))
        problems = [] if done.returncode == 0 else ["exit %s: %s" % (done.returncode, report.get("error"))]
        problems += ["missing %r" % text for text in expected if text not in report.get("markdown", "")]
        if not report.get("frozen"):
            problems.append("not running as the built app")
        if sys.platform == "win32":
            if not str(report.get("tesseract", "")).startswith(str(APP)):
                problems.append("uses a Tesseract outside the app: %s" % report.get("tesseract"))
            if report.get("tesseract_version") != TESTED_VERSION:
                problems.append("Tesseract %s, not %s" % (report.get("tesseract_version"), TESTED_VERSION))
        if sorted(report.get("installed_languages", [])) != sorted(TESSDATA):
            problems.append("languages %s" % report.get("installed_languages"))
        if problems:
            raise SystemExit("self-test %s failed: %s" % (name, "; ".join(problems)))
        print("self-test %s: ok (%s pages, Tesseract %s)" % (name, report["pages"], report["tesseract_version"]))


def iscc() -> str:
    for c in (os.environ.get("ISCC"), shutil.which("iscc"), r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
              r"C:\Program Files\Inno Setup 6\ISCC.exe"):
        if c and Path(c).is_file():
            return c
    raise SystemExit("Inno Setup 6 (ISCC.exe) is needed for --installer.")


def build_installer() -> Path:
    v = version()
    subprocess.run([iscc(), "/Q", "/DAppVersion=%s" % v, "/DSourceDir=%s" % APP, "/DOutputDir=%s" % DIST,
                    str(ROOT / "packaging" / "windows" / "HYPER-OCR.iss")], check=True)
    setup = DIST / ("HYPER-OCR-Setup-%s.exe" % v)
    (DIST / (setup.name + ".sha256")).write_text("%s  %s\n" % (_sha256(setup), setup.name), encoding="ascii")
    print("Built %s (%d MB)" % (setup.relative_to(ROOT), setup.stat().st_size // 1_000_000))
    return setup


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("what", choices=["tesseract", "app"])
    parser.add_argument("dest", nargs="?")
    parser.add_argument("--installer", action="store_true")
    args = parser.parse_args(argv)
    if args.what == "tesseract":
        if not args.dest:
            parser.error("tesseract needs DEST")
        return tesseract_command([args.dest])
    build_app()
    self_test()
    if args.installer:
        if sys.platform != "win32":
            raise SystemExit("The installer is built on Windows.")
        build_installer()
    return 0


if __name__ == "__main__":
    sys.exit(main())
