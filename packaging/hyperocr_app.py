"""Entry point of the HYPER-OCR desktop app (built by PyInstaller; see packaging/HYPER-OCR.spec)."""

import sys

from hyperocr.desktop import main

if __name__ == "__main__":
    sys.exit(main())
