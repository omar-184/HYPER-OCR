"""The page model every OCR engine fills in and every exporter reads.

All boxes are (x0, y0, x1, y1) in pixels of the page image the engine saw,
origin at the top-left. The exporters convert them to PDF points themselves.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

Box = tuple[float, float, float, float]

# Block kinds. Engines map their own labels onto these.
TITLE = "title"          # document title (h1)
HEADING = "heading"      # section heading (h2 and below, see Block.level)
TEXT = "text"            # paragraph or list item
CAPTION = "caption"      # figure or table caption
TABLE = "table"          # a table; Block.html holds a <table>
FIGURE = "figure"        # a picture, chart or photo; saved to Images/
FORMULA = "formula"      # display formula; Block.text holds LaTeX
HEADER = "header"        # running page header
FOOTER = "footer"        # running page footer
PAGE_NUMBER = "page_number"

PAGE_FURNITURE = {HEADER, FOOTER, PAGE_NUMBER}


@dataclass
class Word:
    box: Box
    text: str
    conf: float = 100.0


@dataclass
class Line:
    """One visual line of text, used to place the invisible text layer."""

    box: Box
    text: str
    words: list[Word] = field(default_factory=list)


@dataclass
class Block:
    kind: str
    box: Box
    text: str = ""
    html: str = ""          # tables only
    level: int = 1          # headings: 1 = title, 2 = section, 3 = subsection
    figure_file: str = ""   # set by the image exporter, relative to the output root
    table_file: str = ""    # set by the table exporter, relative to the output root


@dataclass
class PageResult:
    index: int              # 0-based page number
    width: int              # page image size in pixels
    height: int
    dpi: float
    engine: str
    blocks: list[Block] = field(default_factory=list)
    lines: list[Line] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def word_count(self) -> int:
        return sum(len(line.text.split()) for line in self.lines)


# ---------------------------------------------------------------- text helpers

_RTL_RANGES = (
    (0x0590, 0x08FF),   # Hebrew, Arabic, Syriac, Thaana, NKo, Samaritan, Arabic Ext-A
    (0xFB1D, 0xFDFF),   # Hebrew and Arabic presentation forms A
    (0xFE70, 0xFEFF),   # Arabic presentation forms B
)


def is_rtl_char(ch: str) -> bool:
    o = ord(ch)
    return any(a <= o <= b for a, b in _RTL_RANGES)


def is_rtl(text: str) -> bool:
    """True when the first strongly directional character is right-to-left."""
    for ch in text:
        bidi = unicodedata.bidirectional(ch)
        if bidi in ("R", "AL"):
            return True
        if bidi == "L":
            return False
    return False


def mostly_rtl(text: str) -> bool:
    """True when most letters are right-to-left (Arabic, Hebrew, Persian, Urdu...)."""
    rtl = sum(1 for ch in text if is_rtl_char(ch))
    ltr = sum(1 for ch in text if ch.isalpha() and not is_rtl_char(ch))
    return rtl > ltr


_INVISIBLE = re.compile("[\u200e\u200f\u202a-\u202e\u2066-\u2069\ufeff]")


def clean_text(text: str) -> str:
    """Drop bidi control marks engines add, and normalise spacing."""
    text = _INVISIBLE.sub("", text)
    text = unicodedata.normalize("NFC", text)
    return re.sub(r"[ \t]+", " ", text).strip()


def union(boxes: list[Box]) -> Box:
    return (
        min(b[0] for b in boxes),
        min(b[1] for b in boxes),
        max(b[2] for b in boxes),
        max(b[3] for b in boxes),
    )


def area(b: Box) -> float:
    return max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])


def intersection(a: Box, b: Box) -> float:
    return area((max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])))


def overlap_ratio(inner: Box, outer: Box) -> float:
    """Share of `inner` that lies inside `outer` (0..1)."""
    a = area(inner)
    return intersection(inner, outer) / a if a else 0.0
