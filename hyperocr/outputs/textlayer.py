"""Invisible, searchable text over scanned pages.

The text is drawn in render mode 3 (invisible) with a "glyphless" font, the
same technique Tesseract and OCRmyPDF use: the embedded TrueType font has one
blank glyph, every character code is its own Unicode value (Identity-H with a
CIDToGIDMap that sends every code to that glyph), and a ToUnicode map that is
the identity. Copy, search and screen readers therefore get exactly the text
the OCR engine produced, in any script.

Right-to-left text (Arabic, Hebrew...) is written in *visual* order, the way
born-digital PDFs store it. Tested with MuPDF, Poppler, PDFium (Chrome, Edge)
and pdf.js (Firefox): every one of them finds single Arabic words, which a
logical-order layer does not achieve.
"""

from __future__ import annotations

from pathlib import Path

import pymupdf
from bidi import get_display

from ..document import Line, PageResult, is_rtl

FONT_FILE = Path(__file__).with_name("glyphless.ttf")
FONT_NAME = "HOCRGlyphless"
CHAR_WIDTH = 0.5   # every glyph advances half an em (/DW 500)

_TO_UNICODE = b"""/CIDInit /ProcSet findresource begin
12 dict begin
begincmap
/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def
/CMapName /Adobe-Identity-UCS def
/CMapType 2 def
1 begincodespacerange
<0000> <FFFF>
endcodespacerange
1 beginbfrange
<0000> <FFFF> <0000>
endbfrange
endcmap
CMapName currentdict /CMap defineresource pop
end
end
"""


class TextLayerWriter:
    """Adds invisible text to pages of one document; the font is embedded once."""

    def __init__(self, doc: pymupdf.Document):
        self.doc = doc
        self._font_xref = 0

    # ------------------------------------------------------------ public

    def add(self, page: pymupdf.Page, result: PageResult) -> int:
        """Write `result.lines` onto `page`. Returns the number of lines written."""
        ops: list[str] = []
        for line in result.lines:
            ops.extend(_line_ops(line))
        if not ops:
            return 0
        to_pdf = display_to_pdf_matrix(self.doc, page)
        # Engine pixels -> displayed page points -> PDF user space.
        m = pymupdf.Matrix(page.rect.width / result.width, page.rect.height / result.height) * to_pdf
        stream = (
            "q\n%s cm\nBT\n3 Tr\n%s\nET\nQ\n" % (_fmt_matrix(m), "\n".join(ops))
        ).encode("ascii")
        self._append_stream(page, stream)
        return len(result.lines)

    # ------------------------------------------------------------ internals

    def _font(self) -> int:
        if self._font_xref:
            return self._font_xref
        doc = self.doc
        font_bytes = FONT_FILE.read_bytes()
        font_file = _new_stream(doc, font_bytes, "/Length1 %d" % len(font_bytes))
        cid_to_gid = _new_stream(doc, b"\x00\x01" * 65536)
        to_unicode = _new_stream(doc, _TO_UNICODE)
        descriptor = _new_object(
            doc,
            "<</Type/FontDescriptor/FontName/%s/Flags 5/FontBBox[0 0 %d 1000]/ItalicAngle 0"
            "/Ascent 1000/Descent 0/CapHeight 1000/StemV 80/FontFile2 %d 0 R>>"
            % (FONT_NAME, CHAR_WIDTH * 1000, font_file),
        )
        cid_font = _new_object(
            doc,
            "<</Type/Font/Subtype/CIDFontType2/BaseFont/%s"
            "/CIDSystemInfo<</Registry(Adobe)/Ordering(Identity)/Supplement 0>>"
            "/FontDescriptor %d 0 R/CIDToGIDMap %d 0 R/DW %d>>"
            % (FONT_NAME, descriptor, cid_to_gid, CHAR_WIDTH * 1000),
        )
        self._font_xref = _new_object(
            doc,
            "<</Type/Font/Subtype/Type0/BaseFont/%s/Encoding/Identity-H"
            "/DescendantFonts[%d 0 R]/ToUnicode %d 0 R>>" % (FONT_NAME, cid_font, to_unicode),
        )
        return self._font_xref

    def _append_stream(self, page: pymupdf.Page, stream: bytes) -> None:
        doc = self.doc
        _set_font_resource(doc, page, "HOCR", self._font())
        kind, value = doc.xref_get_key(page.xref, "Contents")
        if kind in ("xref", "array") and not page.is_wrapped:
            page.wrap_contents()  # isolate the original drawing state from ours
            kind, value = doc.xref_get_key(page.xref, "Contents")
        new = _new_stream(doc, stream)
        if kind == "array":
            doc.xref_set_key(page.xref, "Contents", value[:-1] + " %d 0 R]" % new)
        elif kind == "xref":
            doc.xref_set_key(page.xref, "Contents", "[%s %d 0 R]" % (value, new))
        else:
            doc.xref_set_key(page.xref, "Contents", "%d 0 R" % new)


def _line_ops(line: Line) -> list[str]:
    """Text operators for one line, in engine pixel space (y grows downwards)."""
    x0, y0, x1, y1 = line.box
    size = y1 - y0
    if size <= 0 or not line.text.strip():
        return []
    rtl_line = is_rtl(line.text)
    words = [w for w in line.words if w.text.strip() and w.box[2] > w.box[0]]
    if words:
        runs = []
        for w in words:
            rtl = is_rtl(w.text) if w.text.strip() else rtl_line
            runs.append((w.box[0], w.box[2], w.text, rtl))
    else:
        runs = [(x0, x1, line.text, rtl_line)]
    ops = []
    for rx0, rx1, text, rtl in runs:
        visual = get_display(text, base_dir="R" if rtl else "L")
        # The space goes after the word in reading order: visually left of an RTL word.
        visual = " " + visual if rtl else visual + " "
        codes = _hex(visual)
        n = len(codes) // 4
        if n == 0:
            continue
        scale = 100.0 * (rx1 - rx0) / (size * CHAR_WIDTH * n)
        # Flip y back (the cm makes y point down) and put the baseline on the line's bottom.
        ops.append(
            "/HOCR %.2f Tf %.3f Tz 1 0 0 -1 %.2f %.2f Tm <%s> Tj"
            % (size, max(scale, 0.1), rx0, y1, codes)
        )
    return ops


def _hex(text: str) -> str:
    out = []
    for ch in text:
        o = ord(ch)
        if o < 0x20 or 0xD800 <= o <= 0xDFFF or o > 0xFFFF:
            continue  # control characters and astral-plane symbols have no code here
        out.append("%04X" % o)
    return "".join(out)


# ------------------------------------------------------------ PDF plumbing


def display_to_pdf_matrix(doc: pymupdf.Document, page: pymupdf.Page) -> pymupdf.Matrix:
    """Map displayed page coordinates (top-left origin, after /Rotate and /CropBox)
    to PDF user space. Verified pixel-exact for every rotation, with and without
    an offset crop box."""
    media = _page_box(doc, page, "MediaBox") or [0.0, 0.0, 612.0, 792.0]
    crop = _page_box(doc, page, "CropBox") or media
    crop = [max(crop[0], media[0]), max(crop[1], media[1]), min(crop[2], media[2]), min(crop[3], media[3])]
    x0, x1 = sorted((crop[0], crop[2]))
    y0, y1 = sorted((crop[1], crop[3]))
    w, h = x1 - x0, y1 - y0
    forward = pymupdf.Matrix(1, 0, 0, -1, -x0, y1)  # PDF -> unrotated, y down
    rotation = page.rotation % 360
    if rotation == 90:
        rotate = pymupdf.Matrix(0, 1, -1, 0, h, 0)
    elif rotation == 180:
        rotate = pymupdf.Matrix(-1, 0, 0, -1, w, h)
    elif rotation == 270:
        rotate = pymupdf.Matrix(0, -1, 1, 0, 0, w)
    else:
        rotate = pymupdf.Identity
    return ~(forward * rotate)


def _page_box(doc: pymupdf.Document, page: pymupdf.Page, key: str) -> list[float] | None:
    """A page box straight from the PDF, following inheritance from parent nodes."""
    xref, seen = page.xref, set()
    while xref and xref not in seen:
        seen.add(xref)
        kind, value = doc.xref_get_key(xref, key)
        if kind == "array":
            try:
                nums = [float(v) for v in value.strip("[]").split()]
            except ValueError:
                return None
            return nums if len(nums) == 4 else None
        kind, value = doc.xref_get_key(xref, "Parent")
        xref = int(value.split()[0]) if kind == "xref" else 0
    return None


def _fmt_matrix(m: pymupdf.Matrix) -> str:
    return " ".join("%.6f" % v for v in (m.a, m.b, m.c, m.d, m.e, m.f))


def _new_object(doc: pymupdf.Document, source: str) -> int:
    xref = doc.get_new_xref()
    doc.update_object(xref, source)
    return xref


def _new_stream(doc: pymupdf.Document, data: bytes, extra: str = "") -> int:
    xref = _new_object(doc, "<<%s>>" % extra)
    doc.update_stream(xref, data, compress=True)
    return xref


def _set_font_resource(doc: pymupdf.Document, page: pymupdf.Page, name: str, font_xref: int) -> None:
    """Register a font in the page's /Resources, wherever that dictionary lives."""
    owner, prefix = page.xref, "Resources/"
    kind, value = doc.xref_get_key(owner, "Resources")
    if kind == "xref":
        owner, prefix = int(value.split()[0]), ""
    elif kind == "null":
        # Inherited resources: copy them onto the page before extending them.
        inherited = _inherited(doc, page.xref, "Resources")
        doc.xref_set_key(owner, "Resources", inherited or "<<>>")
        kind, value = doc.xref_get_key(owner, "Resources")
        if kind == "xref":
            owner, prefix = int(value.split()[0]), ""
    kind, value = doc.xref_get_key(owner, prefix + "Font")
    if kind == "xref":
        doc.xref_set_key(int(value.split()[0]), name, "%d 0 R" % font_xref)
        return
    if kind == "null":
        doc.xref_set_key(owner, prefix + "Font", "<<>>")
    doc.xref_set_key(owner, prefix + "Font/" + name, "%d 0 R" % font_xref)


def _inherited(doc: pymupdf.Document, xref: int, key: str) -> str | None:
    seen = set()
    while xref and xref not in seen:
        seen.add(xref)
        kind, value = doc.xref_get_key(xref, key)
        if kind in ("dict", "xref"):
            return value
        kind, value = doc.xref_get_key(xref, "Parent")
        xref = int(value.split()[0]) if kind == "xref" else 0
    return None


# ------------------------------------------------------------ existing text


def page_text_kind(page: pymupdf.Page) -> str:
    """'none', 'invisible' (an old OCR layer) or 'visible' (born-digital text)."""
    visible = invisible = 0
    for span in page.get_texttrace():
        n = len(span.get("chars", ()))
        if span.get("type") == 3 or span.get("opacity", 1) == 0:
            invisible += n
        else:
            visible += n
    if visible > 20:
        return "visible"
    if invisible:
        return "invisible"
    return "none"


def remove_invisible_text(page: pymupdf.Page) -> None:
    """Delete an old OCR text layer, keeping images and drawings untouched."""
    page.add_redact_annot(page.rect)
    page.apply_redactions(
        images=pymupdf.PDF_REDACT_IMAGE_NONE,
        graphics=pymupdf.PDF_REDACT_LINE_ART_NONE,
        text=pymupdf.PDF_REDACT_TEXT_REMOVE,
    )
