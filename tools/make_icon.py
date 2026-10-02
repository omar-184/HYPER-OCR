"""Make the desktop app's Windows icon from the interface's own app icon.

    python tools/make_icon.py        # writes packaging/windows/HYPER-OCR.ico

Each size is drawn from hyperocr/static/icon.svg on its own, so small sizes stay sharp.
Needs CairoSVG (pip install cairosvg; MuPDF draws no gradients). Run it again whenever
icon.svg changes: the icon is committed, so building the app doesn't need it.
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

import cairosvg
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SVG = ROOT / "hyperocr" / "static" / "icon.svg"
ICO = ROOT / "packaging" / "windows" / "HYPER-OCR.ico"
SIZES = (16, 20, 24, 32, 40, 48, 64, 96, 128, 256)


def render(size: int) -> Image.Image:
    png = cairosvg.svg2png(bytestring=SVG.read_bytes(), output_width=size, output_height=size)
    return Image.open(io.BytesIO(png)).convert("RGBA")


def build() -> bytes:
    images = [render(s) for s in SIZES]
    out = io.BytesIO()
    images[-1].save(out, format="ICO", sizes=[(s, s) for s in SIZES], append_images=images[:-1])
    return out.getvalue()


def main() -> int:
    ICO.parent.mkdir(parents=True, exist_ok=True)
    ICO.write_bytes(build())
    print("wrote %s" % ICO.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
