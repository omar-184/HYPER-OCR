"""The invisible text layer: positions on rotated and cropped pages, and Arabic search."""

import pymupdf
import pytest

from hyperocr.document import Line, PageResult, Word
from hyperocr.outputs.textlayer import TextLayerWriter, page_text_kind, remove_invisible_text


def _page(rotation=0, crop=None):
    doc = pymupdf.open()
    page = doc.new_page(width=600, height=800)
    page.draw_rect(pymupdf.Rect(20, 20, 580, 780), color=(0, 0, 0))
    if crop:
        page.set_cropbox(pymupdf.Rect(*crop))
    page.set_rotation(rotation)
    return doc, page


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
@pytest.mark.parametrize("crop", [None, (50, 30, 550, 700)])
def test_words_land_where_the_engine_saw_them(rotation, crop):
    doc, page = _page(rotation, crop)
    w, h = page.rect.width * 2, page.rect.height * 2   # engine image at 144 dpi
    box = (0.1 * w, 0.2 * h, 0.5 * w, 0.2 * h + 40)
    result = PageResult(0, int(w), int(h), 144, "test", lines=[Line(box, "Hello world")])
    assert TextLayerWriter(doc).add(page, result) == 1
    reopened = pymupdf.open("pdf", doc.tobytes())[0]
    words = reopened.get_text("words")
    assert [x[4] for x in words] == ["Hello", "world"]
    got = pymupdf.Rect(words[0][:4]) * reopened.rotation_matrix
    assert abs(got.x0 - box[0] / 2) < 1.5 and abs(got.y0 - box[1] / 2) < 1.5 and abs(got.y1 - box[3] / 2) < 1.5


def test_arabic_word_layer_is_searchable_and_extracts_in_reading_order():
    doc, page = _page()
    words = [Word((700, 100, 900, 140), "مرحبا"), Word((450, 100, 680, 140), "بالعالم"), Word((250, 100, 430, 140), "الطبي")]
    result = PageResult(0, 1200, 1600, 144, "test", lines=[Line((250, 100, 900, 140), "مرحبا بالعالم الطبي", words)])
    TextLayerWriter(doc).add(page, result)
    p = pymupdf.open("pdf", doc.tobytes())[0]
    assert p.search_for("الطبي")
    assert p.get_text().split() == ["مرحبا", "بالعالم", "الطبي"]
    assert page_text_kind(p) == "invisible"


def test_old_ocr_layer_is_replaced_not_doubled():
    doc, page = _page()
    result = PageResult(0, 1200, 1600, 144, "test", lines=[Line((100, 100, 500, 140), "old words")])
    TextLayerWriter(doc).add(page, result)
    doc = pymupdf.open("pdf", doc.tobytes())
    page = doc[0]
    remove_invisible_text(page)
    TextLayerWriter(doc).add(page, PageResult(0, 1200, 1600, 144, "test", lines=[Line((100, 100, 500, 140), "new words")]))
    text = pymupdf.open("pdf", doc.tobytes())[0].get_text()
    assert "new" in text and "old" not in text
    assert page.get_drawings()  # the drawing survived


def test_visible_text_is_recognised():
    doc, page = _page()
    page.insert_text((50, 100), "This page was typed, not scanned, and has real text already.")
    assert page_text_kind(page) == "visible"


def _scan_page(doc, text=""):
    """A page that is one big picture, optionally with a little real text on top (a fax header)."""
    page = doc.new_page(width=595, height=842)
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 400, 560), False)
    pix.set_rect(pix.irect, (245, 245, 245))
    page.insert_image(page.rect, pixmap=pix)
    if text:
        page.insert_text((36, 20), text, fontsize=8)
    return page


def test_a_stamped_scan_is_not_mistaken_for_born_digital():
    doc = pymupdf.open()
    assert page_text_kind(_scan_page(doc, "FAX 02/10/2026 09:14 FROM CLINIC LAB  P.1")) == "stamped"
    assert page_text_kind(_scan_page(doc)) == "none"


def test_a_born_digital_page_with_a_background_picture_keeps_its_text():
    doc = pymupdf.open()
    page = _scan_page(doc)
    for k in range(40):
        page.insert_text((40, 60 + 18 * k), "Typed report text that already fills the page line after line, " * 2, fontsize=11)
    assert page_text_kind(page) == "visible"
