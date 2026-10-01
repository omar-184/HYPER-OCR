"""Save figures as image files, at the scan's own resolution when that is sharper."""

from __future__ import annotations

import io
from pathlib import Path

import numpy as np
import pymupdf
from PIL import Image

from ..document import Box

MAX_DPI = 600
PNG_LIMIT = 1_500_000   # bytes; bigger photographs are stored as JPEG instead


def native_dpi(page: pymupdf.Page) -> float:
    """Resolution of the scan image that covers most of the page (0 if none)."""
    best = 0.0
    page_area = abs(page.rect)
    for info in page.get_image_info():
        bbox = pymupdf.Rect(info["bbox"])
        if bbox.is_empty or abs(bbox) < 0.5 * page_area:
            continue
        dpi = info["width"] / (bbox.width / 72.0)
        best = max(best, dpi)
    return best


def crop(page: pymupdf.Page, image: np.ndarray, box: Box, dpi: float, scan_dpi: float) -> Image.Image:
    """The region `box` (pixels of `image`, rendered at `dpi`) as a picture."""
    x0, y0, x1, y1 = (int(round(v)) for v in box)
    if scan_dpi > dpi * 1.2:
        # The scan holds more detail than our working render: render just this region again.
        scale = 72.0 / dpi
        clip = pymupdf.Rect(x0 * scale, y0 * scale, x1 * scale, y1 * scale) + (page.rect.x0, page.rect.y0) * 2
        target = min(scan_dpi, MAX_DPI)
        pix = page.get_pixmap(dpi=int(target), clip=clip, colorspace=pymupdf.csRGB, alpha=False)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        img.info["dpi"] = (target, target)
        return img
    img = Image.fromarray(image[max(0, y0): y1, max(0, x0): x1])
    img.info["dpi"] = (dpi, dpi)
    return img


def save(img: Image.Image, folder: Path, stem: str) -> str:
    """Write PNG, or JPEG for large photographs. Returns the file name."""
    folder.mkdir(parents=True, exist_ok=True)
    dpi = img.info.get("dpi", (300, 300))
    if _is_gray(img):
        img = img.convert("L")
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True, dpi=dpi)
    if buf.tell() <= PNG_LIMIT:
        name = stem + ".png"
        (folder / name).write_bytes(buf.getvalue())
        return name
    name = stem + ".jpg"
    img.convert("RGB" if img.mode != "L" else "L").save(folder / name, "JPEG", quality=90, dpi=dpi)
    return name


def png_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True, dpi=img.info.get("dpi", (300, 300)))
    return buf.getvalue()


def _is_gray(img: Image.Image) -> bool:
    if img.mode in ("L", "1"):
        return True
    small = np.asarray(img.convert("RGB").resize((64, 64)), dtype=np.int16)
    return int(np.abs(small - small.mean(axis=2, keepdims=True)).max()) <= 6
