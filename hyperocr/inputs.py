"""What people upload: PDFs and pictures (phone photos, scans, iPhone HEIC).

Pictures become PDF pages, upright (the camera's rotation flag is applied)
and sized like a real page. Several files are either combined into one
document, in the order given, or kept as separate documents.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path

import pymupdf
from PIL import Image, ImageOps, ImageSequence

from .engines.base import EngineError

IMAGE_TYPES = (".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".webp", ".gif", ".heic", ".heif")
A4_LONG_INCHES = 11.69
Image.MAX_IMAGE_PIXELS = 300_000_000   # large scans are fine; this only guards against absurd files

try:  # iPhone photos. pi-heif only decodes, so it bundles no encoder (no GPL x265).
    import pi_heif as _heif
except ImportError:  # pragma: no cover - older installs had pillow-heif
    try:
        import pillow_heif as _heif
    except ImportError:
        _heif = None
if _heif is not None:
    _heif.register_heif_opener()
HEIC = _heif is not None


@dataclass
class Upload:
    name: str     # the name the person gave it
    path: Path    # where it was saved
    kind: str     # "pdf" or "image"


@dataclass
class Document:
    name: str     # used for the output folder and file names
    pdf: Path


def detect(path: Path) -> str | None:
    """'pdf', 'image' or None, from the file's bytes rather than its name."""
    with path.open("rb") as f:
        head = f.read(1024)
    if b"%PDF-" in head:
        return "pdf"
    try:
        with Image.open(path) as im:
            im.verify()
        return "image"
    except Exception:
        return None


def build(uploads: list[Upload], mode: str, work: Path) -> list[Document]:
    """The documents to convert. `mode` is 'combine' or 'separate'."""
    work.mkdir(parents=True, exist_ok=True)
    if not uploads:
        raise EngineError("noFile")
    if mode == "combine" and len(uploads) > 1:
        doc = pymupdf.open()
        for up in uploads:
            _append(doc, up)
        target = work / "combined.pdf"
        doc.save(target, garbage=3, deflate=True)
        doc.close()
        return [Document(_stem(uploads[0].name) + "_combined", target)]
    docs, used = [], set()
    for i, up in enumerate(uploads):
        name = _unique(_stem(up.name), used)
        if up.kind == "pdf":
            _check_pdf(up).close()
            docs.append(Document(name, up.path))
        else:
            doc = pymupdf.open()
            _append(doc, up)
            target = work / ("input-%03d.pdf" % (i + 1))
            doc.save(target, garbage=3, deflate=True)
            doc.close()
            docs.append(Document(name, target))
    return docs


def page_count(doc: Document) -> int:
    with pymupdf.open(doc.pdf) as d:
        if d.needs_pass:
            d.authenticate("")
        return d.page_count


# ---------------------------------------------------------------- internals


def _append(doc: pymupdf.Document, up: Upload) -> None:
    if up.kind == "pdf":
        src = _check_pdf(up)
        doc.insert_pdf(src)
        src.close()
    else:
        for data, w_pt, h_pt in image_pages(up.path, up.name):
            page = doc.new_page(width=w_pt, height=h_pt)
            page.insert_image(page.rect, stream=data)


def _check_pdf(up: Upload) -> pymupdf.Document:
    try:
        src = pymupdf.open(up.path)
    except Exception as exc:
        raise EngineError("notPdf", up.name) from exc
    if src.needs_pass and not src.authenticate(""):
        raise EngineError("passwordProtected", up.name)
    if src.page_count == 0:
        raise EngineError("emptyPdf", up.name)
    return src


def image_pages(path: Path, name: str = "") -> list[tuple[bytes, float, float]]:
    """Each frame of a picture as (encoded image, page width pt, page height pt)."""
    try:
        im = Image.open(path)
    except Exception as exc:
        raise EngineError("badImage", name or path.name) from exc
    source_format = (im.format or "").upper()
    raw = path.read_bytes() if source_format == "JPEG" else b""
    pages = []
    with im:
        frames = getattr(im, "n_frames", 1)
        for frame in ImageSequence.Iterator(im):
            upright = ImageOps.exif_transpose(frame) if frames == 1 else frame.copy()
            rotated = upright.size != frame.size or _orientation(frame) not in (None, 1)
            dpi = _dpi(frame, upright.size)
            w_pt, h_pt = upright.width * 72.0 / dpi, upright.height * 72.0 / dpi
            if raw and frames == 1 and not rotated and frame.mode in ("RGB", "L"):
                pages.append((raw, w_pt, h_pt))   # keep the camera's JPEG untouched
                continue
            pages.append((_encode(upright), w_pt, h_pt))
    if not pages:
        raise EngineError("badImage", name or path.name)
    return pages


def _orientation(im: Image.Image):
    try:
        return im.getexif().get(0x0112)
    except Exception:
        return None


def _dpi(im: Image.Image, size: tuple[int, int]) -> float:
    """The picture's own resolution when it looks real (a scanner's), otherwise
    whatever makes its longer side as long as an A4 page (a phone photo)."""
    dpi = im.info.get("dpi")
    try:
        value = float(dpi[0]) if dpi else 0.0
    except (TypeError, ValueError, IndexError):
        value = 0.0
    if 100 <= value <= 1200:
        return value
    return min(600.0, max(72.0, max(size) / A4_LONG_INCHES))


def _encode(im: Image.Image) -> bytes:
    """PNG for black-and-white and greyscale scans, JPEG for colour photographs."""
    buf = io.BytesIO()
    if im.mode == "1":
        im.save(buf, "PNG", optimize=True)
    elif im.mode in ("L", "LA", "P", "I;16", "I"):
        im.convert("L").save(buf, "PNG", optimize=True)
    else:
        im.convert("RGB").save(buf, "JPEG", quality=92, optimize=True)
    return buf.getvalue()


def _stem(name: str) -> str:
    from .pipeline import safe_stem

    return safe_stem(name)


def _unique(name: str, used: set[str]) -> str:
    candidate, n = name, 2
    while candidate.lower() in used:
        candidate = "%s (%d)" % (name, n)
        n += 1
    used.add(candidate.lower())
    return candidate
