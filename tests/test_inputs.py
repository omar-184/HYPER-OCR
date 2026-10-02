"""Pictures as input: phone photos, rotation flags, HEIC, multi-page TIFF, combine or separate."""

import io

import pymupdf
import pytest
from PIL import Image

from conftest import FIXTURES, needs_tesseract
from hyperocr import inputs
from hyperocr.engines.base import Options
from hyperocr.pipeline import convert_job


def page_image(index: int, dpi: int = 150) -> Image.Image:
    page = pymupdf.open(FIXTURES / "scanned_english.pdf")[index]
    pix = page.get_pixmap(dpi=dpi, colorspace=pymupdf.csRGB)
    return Image.frombytes("RGB", (pix.w, pix.h), pix.samples)


def page_photo(index: int, fmt: str = "JPEG", sideways: bool = False) -> bytes:
    """A page as a phone would save it; `sideways` stores it rotated with an EXIF flag."""
    im = page_image(index)
    buf = io.BytesIO()
    if sideways:
        exif = Image.Exif()
        exif[0x0112] = 6                                   # "rotate 90° clockwise to view"
        im.rotate(90, expand=True).save(buf, fmt, exif=exif.tobytes(), quality=90)
    else:
        im.save(buf, fmt, **({"quality": 90} if fmt == "JPEG" else {}))
    return buf.getvalue()


def _upload(tmp_path, name, data):
    path = tmp_path / name
    path.write_bytes(data)
    kind = inputs.detect(path)
    assert kind is not None, name
    return inputs.Upload(name, path, kind)


def test_detect_by_content(tmp_path):
    assert _upload(tmp_path, "a.jpg", page_photo(0)).kind == "image"
    (tmp_path / "x.pdf").write_bytes(b"not really a pdf")
    assert inputs.detect(tmp_path / "x.pdf") is None
    assert inputs.detect(FIXTURES / "scanned_english.pdf") == "pdf"


def test_rotation_flag_is_applied(tmp_path):
    up = _upload(tmp_path, "sideways.jpg", page_photo(0, sideways=True))
    (data, w, h), = inputs.image_pages(up.path)
    assert h > w                                           # upright portrait page, not landscape
    assert abs(h - 11.69 * 72) < 1                         # sized like an A4 page


def test_unrotated_jpeg_is_kept_byte_for_byte(tmp_path):
    raw = page_photo(0)
    up = _upload(tmp_path, "plain.jpg", raw)
    (data, w, h), = inputs.image_pages(up.path)
    assert data == raw


def test_heic_and_multipage_tiff(tmp_path):
    # An iPhone-style HEIC (made once with an encoder; the app itself only decodes).
    up = _upload(tmp_path, "IMG_0001.HEIC", (FIXTURES / "iphone_photo.heic").read_bytes())
    assert up.kind == "image"
    (data, w, h), = inputs.image_pages(up.path)
    assert h > w and abs(h - 11.69 * 72) < 1
    tiff = io.BytesIO()
    a, b = page_image(0, 100).convert("L"), page_image(1, 100).convert("L")
    a.save(tiff, "TIFF", save_all=True, append_images=[b], dpi=(100, 100))
    up = _upload(tmp_path, "fax.tif", tiff.getvalue())
    pages = inputs.image_pages(up.path)
    assert len(pages) == 2 and abs(pages[0][1] - a.width * 72 / 100) < 0.5


def test_combine_keeps_the_given_order(tmp_path):
    ups = [_upload(tmp_path, "b.png", page_photo(1, "PNG")), _upload(tmp_path, "a.jpg", page_photo(0)),
           inputs.Upload("doc.pdf", FIXTURES / "scanned_arabic.pdf", "pdf")]
    docs = inputs.build(ups, "combine", tmp_path / "work")
    assert [d.name for d in docs] == ["b_combined"]
    assert inputs.page_count(docs[0]) == 3


def test_separate_names_are_unique(tmp_path):
    ups = [_upload(tmp_path, "scan.png", page_photo(0, "PNG")), _upload(tmp_path, "scan.jpg", page_photo(1))]
    docs = inputs.build(ups, "separate", tmp_path / "work")
    assert [d.name for d in docs] == ["scan", "scan (2)"]


@needs_tesseract
def test_photos_combined_end_to_end(tmp_path):
    ups = [_upload(tmp_path, "p1.jpg", page_photo(0, sideways=True)), _upload(tmp_path, "p2.png", page_photo(1, "PNG"))]
    seen = []
    out = convert_job(ups, "combine", tmp_path / "job", Options(engine="tesseract", languages=["eng"]), seen.append)
    assert len(out.documents) == 1 and out.documents[0].pages == 2
    pdf = out.documents[0].folder / out.documents[0].pdf_file
    assert pymupdf.open(pdf)[0].search_for("Mobilisation")    # the sideways photo was read upright
    reading = [s for s in seen if s["stage"] == "reading"]
    assert [s["page"] for s in reading] == [1, 2] and all(s["pages"] == 2 for s in reading)
    assert all((tmp_path / "job" / "_previews" / s["preview"]).is_file() for s in reading)


@needs_tesseract
def test_photos_separately_end_to_end(tmp_path):
    ups = [_upload(tmp_path, "p1.jpg", page_photo(0)), _upload(tmp_path, "p2.jpg", page_photo(1))]
    seen = []
    out = convert_job(ups, "separate", tmp_path / "job", Options(engine="tesseract", languages=["eng"]), seen.append)
    assert [d.name for d in out.documents] == ["p1", "p2"]
    assert out.zip_path.name == "HYPER-OCR_2-documents.zip"
    reading = [s for s in seen if s["stage"] == "reading"]
    assert [(s["doc"], s["page"], s["pages"]) for s in reading] == [(1, 1, 2), (2, 2, 2)]
    import zipfile

    names = zipfile.ZipFile(out.zip_path).namelist()
    assert "p1/p1_searchable.pdf" in names and "p2/p2.md" in names


def test_password_protected_file_is_named(tmp_path):
    src = pymupdf.open(FIXTURES / "scanned_english.pdf")
    locked = tmp_path / "locked.pdf"
    src.save(locked, encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw="secret", owner_pw="owner")
    with pytest.raises(Exception) as err:
        inputs.build([inputs.Upload("locked.pdf", locked, "pdf")], "separate", tmp_path / "w")
    assert err.value.key == "passwordProtected" and err.value.detail == "locked.pdf"
