"""How often table cells come out right, read the way the app reads them.

    python tools/cell_benchmark.py
    HYPEROCR_TESSERACT=... HYPEROCR_TESSDATA=... python tools/cell_benchmark.py   # another setup

The two test documents' tables (28 cells) are read at 200, 300 and 400 dpi, straight and
tilted: 264 cells. It prints how many numbers and how many words came out exactly right, and
every one that didn't. It was used to choose how numbers in cells are read (NUMBER_HEIGHTS in
hyperocr/engines/tesseract_engine.py) and which language files the app installs.
"""

from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np
import pymupdf

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hyperocr.engines.base import Options  # noqa: E402
from hyperocr.engines.tesseract_engine import TesseractEngine, tesseract_version  # noqa: E402
from hyperocr.languages import folder, installed  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures"
# What each cell holds, row by row, columns left to right as printed.
ENGLISH = [["Group", "Patients", "Mean age", "Stay (days)"], ["Day 1", "96", "54.2", "4.1"],
           ["Day 2", "88", "57.9", "5.3"], ["Day 3+", "56", "61.4", "7.8"]]
ARABIC = [["المعدل الطبيعي", "النتيجة", "التحليل"], ["100-70", "110", "السكر الصائم"],
          ["1.2-0.6", "1.1", "الكرياتينين"], ["17-13", "13.5", "الهيموجلوبين"]]
DOCUMENTS = [("English", "scanned_english.pdf", 1, ENGLISH, ["eng"], (0.0, 1.0, -1.0, -2.0)),
             ("Arabic", "scanned_arabic.pdf", 0, ARABIC, ["eng", "ara"], (0.0, 1.0))]


def same(a: str, b: str) -> bool:
    return "".join(a.split()) == "".join(b.split())


def main() -> int:
    engine = TesseractEngine()
    print("Tesseract %s, languages from %s" % (tesseract_version() or "?", folder() if installed() else "the system"))
    read = TesseractEngine._read_cells
    results = []
    current = {}

    def recording(self, gray, grid, words, langs, dpi):
        read(self, gray, grid, words, langs, dpi)
        for c in grid.cells:
            truth = current["truth"]
            if c.row < len(truth) and c.col < len(truth[c.row]):
                results.append((current["name"], c.row, c.col, truth[c.row][c.col], c.text or ""))

    TesseractEngine._read_cells = recording
    for name, file, page_no, truth, langs, angles in DOCUMENTS:
        for dpi in (200, 300, 400):
            pix = pymupdf.open(FIXTURES / file)[page_no].get_pixmap(dpi=dpi)
            image = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, pix.n).copy()
            for angle in angles:
                page = image
                if angle:
                    m = cv2.getRotationMatrix2D((image.shape[1] / 2, image.shape[0] / 2), angle, 1.0)
                    page = cv2.warpAffine(image, m, (image.shape[1], image.shape[0]), borderValue=(255, 255, 255))
                current.update(name="%s %d dpi %+g°" % (name, dpi, angle), truth=truth)
                engine.process(page, 0, dpi, Options(engine="tesseract", languages=langs))
    numbers = [r for r in results if not any(ch.isalpha() for ch in r[3])]
    words = [r for r in results if any(ch.isalpha() for ch in r[3])]
    for label, group in (("numbers", numbers), ("words", words)):
        right = sum(same(r[4], r[3]) for r in group)
        print("%s: %d of %d right" % (label, right, len(group)))
        for page, row, col, truth, got in group:
            if not same(got, truth):
                print("   %-26s row %d col %d  %s -> %s" % (page, row, col, truth, got))
    return 0


if __name__ == "__main__":
    sys.exit(main())
