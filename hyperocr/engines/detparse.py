"""Parse Unlimited-OCR's raw "document parsing" output into page blocks.

The model writes one block per line group, each introduced by a detection tag:

    <|det|>title [114, 508, 255, 525]<|/det|>5. Evaluation
    <|det|>text [113, 567, 884, 698]<|/det|>We select OmniDocBench \\( [23] \\) as ...
    <|det|>table [137, 192, 860, 593]<|/det|><table><tr><td>Model</td>...
    <|det|>list [139, 483, 884, 759]<|/det|>          (a container: no content)
    <PAGE>                                            (separates pages)

Coordinates are x0, y0, x1, y1 normalised to 0-1000 of the page image (the
paper: "The coordinates of each element are normalized to the range of
0-1000"). Labels follow PaddleOCR's layout classes, which the training data
was annotated with.
"""

from __future__ import annotations

import html as htmllib
import re

from ..document import (
    CAPTION,
    FIGURE,
    FOOTER,
    FORMULA,
    HEADER,
    HEADING,
    PAGE_NUMBER,
    TABLE,
    TEXT,
    TITLE,
    Block,
    clean_text,
)

DET_RE = re.compile(r"<\|det\|>\s*([^\[<]*?)\s*(\[[\[\]\d\s,.\-]*\])?\s*<\|/det\|>", re.S)
REF_RE = re.compile(r"<\|ref\|>(.*?)<\|/ref\|>", re.S)  # DeepSeek-OCR style, tolerated
PAGE_RE = re.compile(r"<\s*page\s*>", re.I)
SPECIAL_RE = re.compile(r"<\|[^|>]*\|>|<｜[^｜]*｜>")

LABELS = {
    TITLE: {"title", "doc_title", "document_title"},
    HEADING: {"paragraph_title", "section_title", "sub_title", "subtitle", "heading", "section_header", "header_title"},
    TEXT: {"text", "paragraph", "content", "abstract", "reference", "reference_content", "references",
           "footnote", "aside_text", "list_item", "list", "vision_footnote", "algorithm", "plain_text",
           "code", "code_txt", "text_block", "sidebar", "note"},
    CAPTION: {"caption", "figure_title", "table_title", "chart_title", "figure_caption", "table_caption",
              "image_caption", "figure_footnote", "table_footnote", "image_title"},
    TABLE: {"table"},
    FIGURE: {"image", "figure", "chart", "picture", "photo", "seal", "header_image", "footer_image",
             "graphic", "diagram", "image_body", "figure_body", "illustration", "logo"},
    FORMULA: {"formula", "equation", "display_formula", "interline_equation", "isolate_formula",
              "formula_number", "math"},
    HEADER: {"header", "page_header", "running_title"},
    FOOTER: {"footer", "page_footer"},
    PAGE_NUMBER: {"page_number", "number", "page_num", "pagenum"},
}
_KIND_BY_LABEL = {label: kind for kind, labels in LABELS.items() for label in labels}


def kind_for(label: str) -> str | None:
    label = label.strip().lower().replace(" ", "_").replace("-", "_")
    if label in _KIND_BY_LABEL:
        return _KIND_BY_LABEL[label]
    for key, kind in _KIND_BY_LABEL.items():  # e.g. "figure_1", "table_body"
        if label.startswith(key):
            return kind
    return None


def split_pages(raw: str) -> list[str]:
    return [p for p in PAGE_RE.split(raw)]


def parse(raw: str, width: int, height: int) -> list[Block]:
    """Blocks for one page, in the model's reading order."""
    raw = raw.replace("\r\n", "\n")
    raw = REF_RE.sub(lambda m: m.group(1) + " ", raw)
    matches = list(DET_RE.finditer(raw))
    blocks: list[Block] = []
    if not matches:
        text = _strip_special(raw).strip()
        if text:
            blocks.append(Block(TEXT, (0, 0, width, height), text=clean_text(text)))
        return blocks
    leading = _strip_special(raw[: matches[0].start()]).strip()
    if leading:
        blocks.append(Block(TEXT, (0, 0, width, height), text=clean_text(leading)))
    for i, m in enumerate(matches):
        label = (m.group(1) or "").strip()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(raw)
        content = _strip_special(raw[m.end():end]).strip()
        box = _box(m.group(2), width, height)
        kind = kind_for(label) if label else TEXT
        if kind is None:
            kind = TEXT
        if kind == FIGURE:
            if box:
                blocks.append(Block(FIGURE, box, text=clean_text(_plain(content))))
            continue
        if not content:
            continue  # a container (e.g. "list") whose items follow as their own blocks
        if box is None:
            box = blocks[-1].box if blocks else (0, 0, width, height)
        if kind == TABLE:
            table_html = table_to_html(content)
            if table_html:
                blocks.append(Block(TABLE, box, text=table_text(table_html), html=table_html))
            else:
                blocks.append(Block(TEXT, box, text=clean_text(content)))
            continue
        if kind == FORMULA:
            blocks.append(Block(FORMULA, box, text=_strip_math_delims(content)))
            continue
        level = 1 if kind == TITLE else 2
        if kind == HEADING and re.match(r"^\d+\.\d+", content):
            level = 3  # "5.1. Benchmark and Metrics"
        blocks.append(Block(kind, box, text=_tidy_text(content), level=level))
    return blocks


def _box(group: str | None, width: int, height: int):
    if not group:
        return None
    nums = [float(n) for n in re.findall(r"-?\d+(?:\.\d+)?", group)]
    if len(nums) < 4:
        return None
    x0, y0, x1, y1 = nums[:4]
    if max(nums[:4]) <= 1.0:      # 0-1 floats
        sx, sy = width, height
    elif max(nums[:4]) <= 1000.5:  # the documented 0-1000 grid
        sx, sy = width / 1000.0, height / 1000.0
    else:                          # already pixels
        sx = sy = 1.0
    x0, x1 = sorted((x0 * sx, x1 * sx))
    y0, y1 = sorted((y0 * sy, y1 * sy))
    x0, y0 = max(0.0, x0), max(0.0, y0)
    x1, y1 = min(float(width), x1), min(float(height), y1)
    if x1 - x0 < 2 or y1 - y0 < 2:
        return None
    return (x0, y0, x1, y1)


def _strip_special(text: str) -> str:
    return SPECIAL_RE.sub("", text)


def _tidy_text(text: str) -> str:
    # Keep the model's own line breaks inside a block as spaces; paragraphs are blocks.
    lines = [clean_text(t) for t in text.split("\n")]
    return " ".join(t for t in lines if t)


def _strip_math_delims(text: str) -> str:
    t = text.strip()
    for a, b in (("$$", "$$"), ("\\[", "\\]"), ("\\(", "\\)"), ("$", "$")):
        if t.startswith(a) and t.endswith(b) and len(t) > len(a) + len(b):
            return t[len(a): -len(b)].strip()
    return t


def _plain(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text)


# ---------------------------------------------------------------- tables


def table_to_html(content: str) -> str:
    """Normalise the model's table output to one clean <table>."""
    m = re.search(r"<table\b.*?</table\s*>", content, re.S | re.I)
    if m:
        return sanitize_table_html(m.group(0))
    if "<tr" in content.lower():
        return sanitize_table_html("<table>" + content + "</table>")
    rows = [r.strip() for r in content.strip().split("\n") if r.strip().startswith("|")]
    if len(rows) >= 2:
        return markdown_table_to_html(rows)
    return ""


def markdown_table_to_html(rows: list[str]) -> str:
    out = ["<table>"]
    for r in rows:
        cells = [c.strip() for c in r.strip().strip("|").split("|")]
        if all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
            continue
        out.append("<tr>" + "".join("<td>%s</td>" % htmllib.escape(c) for c in cells) + "</tr>")
    out.append("</table>")
    return "".join(out)


_ALLOWED_TAGS = {"table", "thead", "tbody", "tfoot", "tr", "td", "th", "br", "b", "strong", "i", "em", "sub", "sup"}


def sanitize_table_html(fragment: str) -> str:
    """Keep table structure (rowspan/colspan) and simple inline formatting; drop the rest."""

    def tag(m: re.Match) -> str:
        closing, name, attrs = m.group(1), m.group(2).lower(), m.group(3) or ""
        if name not in _ALLOWED_TAGS:
            return ""
        if closing:
            return "</%s>" % name
        keep = []
        for a, v in re.findall(r'\b(rowspan|colspan)\s*=\s*["\']?(\d+)', attrs, re.I):
            keep.append('%s="%d"' % (a.lower(), max(1, min(int(v), 1000))))
        return "<%s%s>" % (name, (" " + " ".join(keep)) if keep else "")

    cleaned = re.sub(r"<(/?)([A-Za-z][A-Za-z0-9]*)([^>]*)>", tag, fragment)
    cleaned = re.sub(r"<!--.*?-->", "", cleaned, flags=re.S)
    return cleaned.strip()


def table_text(table_html: str) -> str:
    """Cell texts, row by row, for search and word counts."""
    rows = []
    for row in re.findall(r"<tr\b.*?</tr>", table_html, re.S | re.I):
        cells = re.findall(r"<t[dh]\b[^>]*>(.*?)</t[dh]>", row, re.S | re.I)
        rows.append(" ".join(clean_text(htmllib.unescape(re.sub(r"<[^>]+>", " ", c))) for c in cells))
    return "\n".join(r for r in rows if r.strip())
