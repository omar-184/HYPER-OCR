"""Markdown through Microsoft MarkItDown.

A scanned PDF has no text for MarkItDown to read, so the OCR result is first
assembled into an HTML document (headings, paragraphs, figures pointing at
Images/, tables, captions, formulas) and MarkItDown converts that to Markdown.
LaTeX and table pipes are swapped for tokens around the conversion so they
come out exactly as written.
"""

from __future__ import annotations

import html as htmllib
import re

from ..document import (
    CAPTION,
    FIGURE,
    FORMULA,
    HEADING,
    PAGE_FURNITURE,
    TABLE,
    TEXT,
    TITLE,
    PageResult,
    mostly_rtl,
)
from .tablegrid import flat_html

PIPE = "HOCRPIPEX"
INLINE_MATH = re.compile(r"\\\((.+?)\\\)", re.S)   # \( ... \), as Unlimited-OCR writes it


class _Tokens:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    def add(self, value: str) -> str:
        key = "HOCRTOKEN%05dX" % len(self.values)
        self.values[key] = value
        return key

    def restore(self, text: str) -> str:
        for key, value in self.values.items():
            text = text.replace(key, value)
        return text.replace(PIPE, "\\|")


TABLE_LINK = {"en": "Table {n} as a Word file", "ar": "الجدول {n} كملف Word"}


def build_html(pages: list[PageResult], title: str, skip_furniture: bool = True, ui_lang: str = "en") -> tuple[str, _Tokens]:
    tokens = _Tokens()
    parts = ['<html><head><meta charset="utf-8"><title>%s</title></head><body>' % htmllib.escape(title)]
    # Number heading levels consecutively from h2 (h1 is the title), whatever sizes were found.
    used = sorted({b.level for p in pages for b in p.blocks if b.kind == HEADING})
    level_of = {lvl: min(2 + i, 6) for i, lvl in enumerate(used)}
    table_no = 0
    for page in pages:
        for b in page.blocks:
            if skip_furniture and b.kind in PAGE_FURNITURE:
                continue
            if b.kind == TITLE:
                parts.append("<h1>%s</h1>" % _inline(b.text, tokens))
            elif b.kind == HEADING:
                level = level_of.get(b.level, 2)
                parts.append("<h%d>%s</h%d>" % (level, _inline(b.text, tokens), level))
            elif b.kind == CAPTION:
                parts.append("<p%s><em>%s</em></p>" % (_dir(b.text), _inline(b.text, tokens)))
            elif b.kind == FIGURE:
                if b.figure_file:
                    alt = b.text or "Figure"
                    parts.append('<p><img src="%s" alt="%s"></p>' % (htmllib.escape(b.figure_file), htmllib.escape(alt)))
            elif b.kind == TABLE:
                flat = flat_html(b.html, PIPE) if b.html else ""
                if flat:
                    parts.append(flat)
                if b.table_file:
                    table_no += 1
                    label = TABLE_LINK.get(ui_lang, TABLE_LINK["en"]).format(n=table_no)
                    parts.append('<p><a href="%s">%s</a></p>' % (htmllib.escape(b.table_file), label))
            elif b.kind == FORMULA:
                parts.append("<p>%s</p>" % tokens.add("$$\n%s\n$$" % b.text.strip()))
            elif b.kind in (TEXT,) or b.kind in PAGE_FURNITURE:
                parts.append("<p%s>%s</p>" % (_dir(b.text), _inline(b.text, tokens)))
    parts.append("</body></html>")
    return "".join(parts), tokens


def to_markdown(pages: list[PageResult], title: str, skip_furniture: bool = True, ui_lang: str = "en") -> str:
    # MarkItDown's own HTML converter, called directly: the input is always HTML, so
    # MarkItDown's file-type detector (a model run by ONNX Runtime, which carries
    # Microsoft telemetry) is never needed or loaded.
    from ..offline import quiet_libraries

    quiet_libraries()
    from markitdown.converters import HtmlConverter

    html, tokens = build_html(pages, title, skip_furniture, ui_lang)
    result = HtmlConverter().convert_string(html)
    md = getattr(result, "markdown", None) or getattr(result, "text_content", "") or ""
    md = tokens.restore(md)
    md = re.sub(r"\n{3,}", "\n\n", md).strip() + "\n"
    return md


def _inline(text: str, tokens: _Tokens) -> str:
    """Escape text for HTML, protecting inline math from Markdown escaping."""
    out, last = [], 0
    for m in INLINE_MATH.finditer(text):
        out.append(htmllib.escape(text[last:m.start()]))
        out.append(tokens.add("$%s$" % m.group(1).strip()))
        last = m.end()
    out.append(htmllib.escape(text[last:]))
    return "".join(out)


def _dir(text: str) -> str:
    return ' dir="rtl"' if mostly_rtl(text) else ""
