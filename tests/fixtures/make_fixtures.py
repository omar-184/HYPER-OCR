"""Build small "scanned" test PDFs (image-only pages) for the test suite.

Each page is laid out with PyMuPDF's HTML engine, rendered to a bitmap, lightly
degraded (rotation jitter, noise) and stored as an image-only PDF, so the files
behave like real scans: they carry no text layer at all.

    python tests/fixtures/make_fixtures.py
"""

from __future__ import annotations

import io
import random
from pathlib import Path

import pymupdf
from PIL import Image, ImageDraw, ImageFilter

HERE = Path(__file__).parent
DPI = 200

CSS = """
body { font-family: sans-serif; font-size: 11pt; }
h1 { font-size: 18pt; margin: 0 0 6pt 0; }
h2 { font-size: 13pt; margin: 10pt 0 4pt 0; }
p { margin: 0 0 6pt 0; line-height: 1.3; }
table { border-collapse: collapse; margin: 6pt 0; }
td, th { border: 1px solid black; padding: 3pt 6pt; font-size: 10pt; }
th { font-weight: bold; }
.cap { font-size: 9pt; font-style: italic; }
"""


def chart_png() -> bytes:
    """A simple bar chart, standing in for a figure in a paper."""
    img = Image.new("RGB", (900, 520), "white")
    d = ImageDraw.Draw(img)
    d.line((80, 460, 860, 460), fill="black", width=3)
    d.line((80, 40, 80, 460), fill="black", width=3)
    colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd"]
    for i, h in enumerate([300, 180, 380, 240, 140]):
        x = 130 + i * 145
        d.rectangle((x, 460 - h, x + 90, 459), fill=colors[i])
    for y in range(100, 460, 60):
        d.line((70, y, 80, y), fill="black", width=2)
    return _png(img)


def photo_png() -> bytes:
    """A smooth, photo-like gradient with a few shapes (an 'X-ray' stand-in)."""
    w, h = 700, 520
    img = Image.new("L", (w, h))
    px = img.load()
    for y in range(h):
        for x in range(w):
            dx, dy = (x - w / 2) / (w / 2), (y - h / 2) / (h / 2)
            px[x, y] = int(40 + 170 * max(0.0, 1 - (dx * dx + dy * dy) ** 0.5))
    d = ImageDraw.Draw(img)
    d.ellipse((250, 150, 450, 380), outline=230, width=12)
    img = img.filter(ImageFilter.GaussianBlur(3))
    return _png(img.convert("RGB"))


def _png(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def layout_page(doc: pymupdf.Document, html: str, images: dict[str, bytes] | None = None) -> None:
    """Flow `html` onto a new A4 page; `images` maps <img src> names to PNG bytes."""
    archive = pymupdf.Archive()
    for name, data in (images or {}).items():
        archive.add(data, name)
    page = doc.new_page(width=595, height=842)
    page.insert_htmlbox(pymupdf.Rect(50, 50, 545, 800), html, css=CSS, archive=archive)


def scan(src: pymupdf.Document, out: Path, seed: int) -> None:
    """Rasterise every page and degrade it slightly, like a flatbed scan."""
    rnd = random.Random(seed)
    dst = pymupdf.open()
    for page in src:
        pix = page.get_pixmap(dpi=DPI, colorspace=pymupdf.csGRAY)
        img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("L")
        img = img.rotate(rnd.uniform(-0.6, 0.6), resample=Image.BICUBIC, fillcolor=255)
        px = img.load()
        for _ in range(img.size[0] * img.size[1] // 400):  # salt-and-pepper specks
            x, y = rnd.randrange(img.size[0]), rnd.randrange(img.size[1])
            px[x, y] = rnd.choice((0, 255))
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=80)
        p = dst.new_page(width=page.rect.width, height=page.rect.height)
        p.insert_image(p.rect, stream=buf.getvalue())
    dst.save(out, garbage=3, deflate=True)


def english() -> pymupdf.Document:
    doc = pymupdf.open()
    layout_page(doc, """
<h1>Effect of Early Mobilisation After Surgery</h1>
<p>Background: early mobilisation is recommended after abdominal surgery, but the
evidence for its effect on length of stay is mixed. We reviewed 240 patients treated
between 2021 and 2023 at a single teaching hospital.</p>
<h2>Methods</h2>
<p>Patients were grouped by the day of first walk. The primary outcome was length of
hospital stay; secondary outcomes were readmission and pneumonia within 30 days.</p>
<p style="text-align:center"><img src="chart.png" width="330"></p>
<p class="cap">Figure 1. Mean length of stay by group.</p>
<h2>Results</h2>
<p>Patients who walked on day one went home sooner, with fewer complications.</p>
""", {"chart.png": chart_png()})
    layout_page(doc, """
<h2>Table 1. Baseline characteristics</h2>
<table>
<tr><th>Group</th><th>Patients</th><th>Mean age</th><th>Stay (days)</th></tr>
<tr><td>Day 1</td><td>96</td><td>54.2</td><td>4.1</td></tr>
<tr><td>Day 2</td><td>88</td><td>57.9</td><td>5.3</td></tr>
<tr><td>Day 3+</td><td>56</td><td>61.4</td><td>7.8</td></tr>
</table>
<p>Readmission was lowest in the day-one group. The difference in pneumonia rates
was not statistically significant (p = 0.08).</p>
<p style="text-align:center"><img src="xray.png" width="260"></p>
<p class="cap">Figure 2. Chest radiograph of a typical patient.</p>
<h2>Conclusion</h2>
<p>Walking on the first day after surgery is safe and shortens the hospital stay.</p>
""", {"xray.png": photo_png()})
    return doc


def arabic() -> pymupdf.Document:
    doc = pymupdf.open()
    layout_page(doc, """
<div dir="rtl" style="text-align:right">
<h1>تقرير المتابعة الطبية</h1>
<p>يعاني المريض من ارتفاع ضغط الدم منذ خمس سنوات، ويتناول العلاج بانتظام.
تمت مراجعة نتائج التحاليل في العيادة الخارجية.</p>
<h2>نتائج التحاليل</h2>
<table style="margin-left:auto">
<tr><th>المعدل الطبيعي</th><th>النتيجة</th><th>التحليل</th></tr>
<tr><td>70 - 100</td><td>110</td><td>السكر الصائم</td></tr>
<tr><td>0.6 - 1.2</td><td>1.1</td><td>الكرياتينين</td></tr>
<tr><td>13 - 17</td><td>13.5</td><td>الهيموجلوبين</td></tr>
</table>
<h2>التوصيات</h2>
<p>الاستمرار على العلاج الحالي مع متابعة الضغط يوميا، وتقليل الملح في الطعام،
والعودة للمراجعة بعد ثلاثة أشهر.</p>
<p>Amlodipine 5 mg مرة واحدة يوميا</p>
</div>
""")
    return doc


if __name__ == "__main__":
    scan(english(), HERE / "scanned_english.pdf", seed=1)
    scan(arabic(), HERE / "scanned_arabic.pdf", seed=2)
    for p in sorted(HERE.glob("*.pdf")):
        print(p.name, p.stat().st_size // 1024, "KB")
