"""Add Tesseract languages to HYPER-OCR's own language folder (./tessdata).

    python -m hyperocr.languages                 # list what is installed
    python -m hyperocr.languages add eng ara     # download (needs the internet once)
    python -m hyperocr.languages add fra deu --best

Codes are Tesseract's: eng English, ara Arabic, fra French, deu German,
spa Spanish, fas Persian, urd Urdu, tur Turkish, chi_sim Chinese... When this
folder holds any language, the app uses it instead of the system's.
"""

from __future__ import annotations

import os
import re
import sys
import urllib.request
from pathlib import Path

from .paths import APP_ROOT as ROOT   # the checkout, or the desktop app's folder

SOURCES = {
    "standard": "https://github.com/tesseract-ocr/tessdata/raw/main/%s.traineddata",
    "best": "https://github.com/tesseract-ocr/tessdata_best/raw/main/%s.traineddata",
}


def folder() -> Path:
    return Path(os.environ.get("HYPEROCR_TESSDATA", ROOT / "tessdata"))


def installed() -> list[str]:
    f = folder()
    return sorted(p.stem for p in f.glob("*.traineddata")) if f.is_dir() else []


def add(codes: list[str], best: bool = False) -> int:
    target = folder()
    target.mkdir(parents=True, exist_ok=True)
    failed = 0
    for code in codes:
        if not re.fullmatch(r"[a-z]{3}(_[a-z]+)?|osd", code):
            print("Skipping %r: not a Tesseract language code." % code)
            failed += 1
            continue
        url = SOURCES["best" if best else "standard"] % code
        dest = target / (code + ".traineddata")
        print("Downloading %s ..." % code, end=" ", flush=True)
        try:
            with urllib.request.urlopen(url, timeout=120) as r, open(dest.with_suffix(".part"), "wb") as f:
                while chunk := r.read(1 << 16):
                    f.write(chunk)
            dest.with_suffix(".part").replace(dest)
            print("done (%d MB)" % (dest.stat().st_size // 1_000_000))
        except Exception as exc:
            dest.with_suffix(".part").unlink(missing_ok=True)
            print("failed: %s" % exc)
            failed += 1
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if args[:1] == ["add"]:
        codes = [a for a in args[1:] if not a.startswith("--")]
        return add(codes, best="--best" in args)
    print("Language folder: %s" % folder())
    print("Installed: %s" % (", ".join(installed()) or "none (the system's Tesseract languages are used)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
