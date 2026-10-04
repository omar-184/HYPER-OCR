"""A page's own text, for pages made on a computer: no OCR needed.

A PDF exported from Word or a publisher's typesetting holds its text exactly; reading it
from the page image is slower and less exact. Such a page's words are taken from the PDF
and placed on the rendered page image, where the usual layout analysis (headings, tables,
figures) works on them as it does on OCR words.

The PDF's text is not used, and the page is read by OCR as before, when it is:
- not the page's own (a scan, a scan with a stamp, an OCR layer of another program);
- in a right-to-left script: PDFs store Arabic in many orders (visual, logical, joined
  letter forms), and what comes out can be backwards;
- undecodable (fonts without a character map give replacement or private-use characters);
- mostly running sideways (a turned table): OCR turns such pages upright first.
"""

from __future__ import annotations

import unicodedata

import pymupdf

from ..document import is_rtl_char
from ..outputs.textlayer import born_digital
from .tesseract_engine import TWord

BAD_SHARE = 0.02        # more undecodable characters than this: the text is not used
RTL_SHARE = 0.05        # more right-to-left letters than this: the page is read by OCR
SIDEWAYS_SHARE = 0.2    # more characters on sideways lines than this: the page is read by OCR
# Ligatures (fi, fl) are given as their letters: no TEXT_PRESERVE_LIGATURES.
FLAGS = pymupdf.TEXT_MEDIABOX_CLIP | pymupdf.TEXT_PRESERVE_WHITESPACE


def page_words(page: pymupdf.Page, dpi: float) -> list[TWord] | None:
    """The page's own words, placed in the pixels of the page rendered at `dpi` (as it is
    shown, turned by its /Rotate), grouped into blocks, paragraphs and lines; None when
    the page should be read by OCR (see above)."""
    if not born_digital(page):
        return None
    raw = page.get_text("words", flags=FLAGS)   # (x0, y0, x1, y1, text, block, line, word)
    if not raw or not _usable("".join(w[4] for w in raw)) or _mostly_sideways(page):
        return None
    to_pixels = page.rotation_matrix * pymupdf.Matrix(dpi / 72.0, dpi / 72.0)
    words: list[TWord] = []
    for block, lines in _blocks(raw).items():
        for paragraph, line_no, line in _paragraphs(lines):
            for x0, y0, x1, y1, text, *_ in line:
                r = pymupdf.Rect(x0, y0, x1, y1) * to_pixels
                words.append(TWord((r.x0, r.y0, r.x1, r.y1), unicodedata.normalize("NFC", text), 100.0,
                                   (block + 1, paragraph, line_no), len(words)))
    return words or None


def _usable(text: str) -> bool:
    chars = [ch for ch in text if not ch.isspace()]
    if not chars:
        return False
    bad = sum(1 for ch in chars if ch == "�" or "" <= ch <= "" or unicodedata.category(ch) == "Cc")
    letters = [ch for ch in chars if ch.isalpha()]
    rtl = sum(1 for ch in letters if is_rtl_char(ch))
    return bad <= BAD_SHARE * len(chars) and rtl <= RTL_SHARE * max(1, len(letters))


def _mostly_sideways(page: pymupdf.Page) -> bool:
    total = sideways = 0
    for block in page.get_text("dict", flags=FLAGS)["blocks"]:
        for line in block.get("lines", ()):
            n = sum(len(span["text"]) for span in line["spans"])
            total += n
            if abs(line["dir"][1]) > 0.1:      # not left to right along the page
                sideways += n
    return total > 0 and sideways > SIDEWAYS_SHARE * total


def _blocks(raw: list) -> dict[int, list[list]]:
    """MuPDF's blocks, each a list of lines (lists of words), in the PDF's own order."""
    blocks: dict[int, dict[int, list]] = {}
    for w in raw:
        blocks.setdefault(w[5], {}).setdefault(w[6], []).append(w)
    return {b: list(lines.values()) for b, lines in blocks.items()}


def _paragraphs(lines: list[list]):
    """(paragraph, line, words) for each line of one block. A block can hold several
    paragraphs (a whole column of a book): a new one starts at an indented line, after a
    short line ending a sentence, or after a gap wider than the usual line spacing."""
    if not lines:
        return
    boxes = [(min(w[0] for w in l), min(w[1] for w in l), max(w[2] for w in l), max(w[3] for w in l)) for l in lines]
    left, right = min(b[0] for b in boxes), max(b[2] for b in boxes)
    height = sorted(b[3] - b[1] for b in boxes)[len(boxes) // 2]
    steps = sorted(boxes[i][1] - boxes[i - 1][1] for i in range(1, len(boxes)) if boxes[i][1] > boxes[i - 1][1])
    step = steps[len(steps) // 2] if steps else height
    paragraph = 1
    for i, line in enumerate(lines):
        if i:
            prev, box = boxes[i - 1], boxes[i]
            indented = box[0] - left > 0.6 * height and prev[0] - left <= 0.6 * height
            ended = prev[2] < right - 1.5 * height and lines[i - 1][-1][4].rstrip().endswith((".", "!", "?", ":", '"', "”"))
            gap = box[1] - prev[1] > 1.6 * step
            if indented or ended or gap:
                paragraph += 1
        yield paragraph, i + 1, line
