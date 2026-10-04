"""One conversion: scanned PDF in; searchable PDF, Markdown, Images/ and Tables/ out."""

from __future__ import annotations

import re
import threading
import time
import unicodedata
import zipfile
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import numpy as np
import pymupdf

from . import __version__, engines
from .document import CAPTION, FIGURE, HEADING, TABLE, TITLE, Block, PageResult
from .engines import pdftext
from .engines.base import OUTPUTS, EngineError, Options
from .engines.tesseract_engine import PDF_TEXT
from .outputs import images as img_out
from .outputs.markdown import to_markdown
from .outputs.tables import write_table_docx
from .outputs.tablegrid import parse_table
from .outputs.textlayer import TextLayerWriter, page_text_kind, remove_invisible_text

MAX_SIDE_PX = 7000   # pages larger than this (posters, plans) are read at a lower resolution

Report = Callable[[dict], None]


class Cancelled(Exception):
    pass


@dataclass
class Output:
    """The results for one document."""

    folder: Path
    zip_path: Path
    pdf_file: str
    md_file: str
    title: str
    engine: str
    name: str = ""
    pages: int = 0
    words: int = 0
    images: list[str] = field(default_factory=list)
    tables: list[dict] = field(default_factory=list)
    warnings: list[dict] = field(default_factory=list)
    markdown: str = ""
    seconds: float = 0.0
    outputs: list[str] = field(default_factory=lambda: list(OUTPUTS))


@dataclass
class JobOutput:
    """Everything one conversion produced: one or more documents in one ZIP."""

    root: Path
    zip_path: Path
    engine: str
    documents: list[Output]
    warnings: list[dict] = field(default_factory=list)
    seconds: float = 0.0


def safe_stem(name: str) -> str:
    stem = Path(name).stem
    stem = unicodedata.normalize("NFC", stem)
    stem = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", stem).strip(" .")
    # Working folders (_uploads, _inputs, _previews) start with "_"; a result folder never does,
    # so a file called "_previews.pdf" can't have its results deleted with the previews.
    stem = stem.lstrip("_ ")
    return stem[:80] or "document"


def convert(pdf_path: Path, work: Path, options: Options, report: Report,
            cancel: threading.Event | None = None, original_name: str | None = None) -> Output:
    """Convert one PDF and zip its results (the original single-file entry point)."""
    started = time.time()
    cancel = cancel or threading.Event()
    name = original_name or pdf_path.name
    report({"stage": "opening"})
    engine, passed_over = engines.choose(options)
    engine.prepare(lambda stage: report({"stage": stage}))
    out = _convert_document(pdf_path, safe_stem(name), name, work, options, engine, report, cancel)
    if passed_over is not None:
        out.warnings.insert(0, _cpu_warning(passed_over))
    report({"stage": "packing"})
    _zip([out.folder], out.zip_path)
    out.seconds = round(time.time() - started, 1)
    report({"stage": "done"})
    return out


def convert_job(uploads: list, mode: str, work: Path, options: Options, report: Report,
                cancel: threading.Event | None = None) -> JobOutput:
    """Convert uploads (PDFs and pictures), combined into one document or one each."""
    from . import inputs

    started = time.time()
    cancel = cancel or threading.Event()
    report({"stage": "opening"})
    docs = inputs.build(uploads, mode, work / "_inputs")
    counts = [inputs.page_count(d) for d in docs]
    total = sum(counts)
    engine, passed_over = engines.choose(options)
    engine.prepare(lambda stage: report({"stage": stage}))
    previews = work / "_previews"
    previews.mkdir(parents=True, exist_ok=True)
    outputs: list[Output] = []
    done_pages = 0
    for d, doc in enumerate(docs):
        source = doc.name if len(uploads) > 1 and mode == "combine" else uploads[d].name

        def doc_report(data: dict, d=d, doc=doc, before=done_pages) -> None:
            if data.get("stage") == "reading":
                data = dict(data, doc=d + 1, docs=len(docs), name=doc.name, doc_page=data["page"],
                            doc_pages=data["pages"], page=before + data["page"], pages=total)
            report(data)

        outputs.append(_convert_document(doc.pdf, doc.name, source, work, options, engine, doc_report, cancel,
                                         previews=previews, preview_prefix="%03d" % (d + 1)))
        done_pages += counts[d]
    warnings = [_cpu_warning(passed_over)] if passed_over is not None else []
    if len(outputs) == 1:
        zip_path = work / (outputs[0].folder.name + "_HYPER-OCR.zip")
    else:
        zip_path = work / ("HYPER-OCR_%d-documents.zip" % len(outputs))
    report({"stage": "packing"})
    _zip([o.folder for o in outputs], zip_path)
    for o in outputs:
        o.zip_path = zip_path
    report({"stage": "done"})
    used = PDF_TEXT if all(o.engine == PDF_TEXT for o in outputs) else engine.id
    return JobOutput(work, zip_path, used, outputs, warnings, round(time.time() - started, 1))


def _cpu_warning(state) -> dict:
    return {"key": "usedCpu", "reason": state.reason, "detail": state.detail}


def _convert_document(pdf_path: Path, stem: str, name: str, work: Path, options: Options, engine,
                      report: Report, cancel: threading.Event, previews: Path | None = None,
                      preview_prefix: str = "") -> Output:
    """One PDF into its own folder: the files chosen in options.outputs, of searchable PDF,
    Markdown, Images/ and Tables/."""
    started = time.time()
    try:
        doc = pymupdf.open(pdf_path)
    except Exception as exc:
        raise EngineError("notPdf", name) from exc
    if doc.needs_pass and not doc.authenticate(""):
        raise EngineError("passwordProtected", name)
    if not doc.is_pdf:
        raise EngineError("notPdf", name)
    if doc.page_count == 0:
        raise EngineError("emptyPdf", name)

    wanted = set(options.outputs)
    out = Output(
        folder=work / stem, zip_path=work / (stem + "_HYPER-OCR.zip"),
        pdf_file=stem + "_searchable.pdf" if "pdf" in wanted else "",
        md_file=stem + ".md" if "markdown" in wanted else "",
        title=stem, engine=engine.id, name=stem, outputs=[o for o in OUTPUTS if o in wanted],
    )
    out.folder.mkdir(parents=True, exist_ok=True)
    if "images" in wanted:
        (out.folder / "Images").mkdir(exist_ok=True)
    if "tables" in wanted:
        (out.folder / "Tables").mkdir(exist_ok=True)

    writer = TextLayerWriter(doc)
    pages: list[PageResult] = []
    had_text: list[int] = []
    own_text: list[int] = []
    empty: list[int] = []
    turned: list[int] = []
    width = max(3, len(str(doc.page_count)))
    table_no = 0

    reader = _read_pages(doc, engine, options, cancel)
    try:
        for i, dpi, image, reading in reader:
            if cancel.is_set():
                raise Cancelled()
            update = {"stage": "reading", "page": i + 1, "pages": doc.page_count}
            if previews is not None:
                update["preview"] = _save_preview(image, previews, "%s-%04d.jpg" % (preview_prefix, i + 1))
            report(update)
            turn, image, result = reading.result()
            if cancel.is_set():
                raise Cancelled()
            page = doc[i]
            if turn:
                # Upside down or sideways: it was read upright; turn the page itself (its /Rotate;
                # the scan is untouched) so the searchable PDF shows it upright too.
                page.set_rotation((page.rotation + turn) % 360)
                turned.append(i + 1)
            if result.engine == PDF_TEXT:
                own_text.append(i + 1)
            table_no = _page_outputs(page, i, image, dpi, result, out, writer, name, width, table_no, options,
                                     had_text, empty, pages)
            del image
    finally:
        reader.close()          # stops reading ahead when the conversion stops early

    if turned:
        out.warnings.append({"key": "turned", "pages": turned})
    if own_text:
        out.warnings.append({"key": "ownText", "pages": own_text})
        if len(own_text) == doc.page_count:
            out.engine = PDF_TEXT                  # nothing was read by OCR
    had_text = [n for n in had_text if n not in set(own_text)]   # said already
    if had_text and "pdf" in wanted:
        out.warnings.append({"key": "keptText", "pages": had_text})
    if empty:
        out.warnings.append({"key": "noText", "pages": empty})

    out.pages = doc.page_count
    out.title = _title(pages, doc, stem)

    if out.pdf_file:
        report({"stage": "writing-pdf"})
        _bookmarks(doc, pages)
        meta = dict(doc.metadata or {})
        meta.update({"producer": "HYPER-OCR %s (offline OCR)" % __version__, "creator": meta.get("creator") or "HYPER-OCR"})
        if not meta.get("title"):
            meta["title"] = out.title
        doc.set_metadata({k: v for k, v in meta.items() if k in (
            "author", "producer", "creator", "title", "format", "encryption", "creationDate", "modDate", "subject",
            "keywords", "trapped")})
        doc.save(out.folder / out.pdf_file, garbage=3, deflate=True)
    doc.close()

    if out.md_file:
        report({"stage": "writing-markdown"})
        out.markdown = to_markdown(pages, out.title, options.skip_furniture, options.ui_lang)
        (out.folder / out.md_file).write_text(out.markdown, encoding="utf-8")
    out.seconds = round(time.time() - started, 1)
    return out


def _page_outputs(page: pymupdf.Page, i: int, image: np.ndarray, dpi: int, result: PageResult, out: Output,
                  writer: TextLayerWriter, name: str, width: int, table_no: int, options: Options,
                  had_text: list[int], empty: list[int], pages: list[PageResult]) -> int:
    """One page's pictures, tables and searchable text (those chosen); returns the number of
    tables so far."""
    wanted = set(options.outputs)
    # Images/
    scan_dpi = img_out.native_dpi(page)
    figure_no = 0
    for j, block in enumerate(result.blocks):
        if block.kind != FIGURE or "images" not in wanted:
            continue
        figure_no += 1
        picture = img_out.crop(page, image, block.box, dpi, scan_dpi)
        file = img_out.save(picture, out.folder / "Images", "page-%0*d_figure-%02d" % (width, i + 1, figure_no))
        block.figure_file = "Images/" + file
        caption = _caption(result.blocks, j)
        block.text = caption or "Figure %d, page %d" % (figure_no, i + 1)
        out.images.append(block.figure_file)

    # Tables/
    for j, block in enumerate(result.blocks):
        if block.kind != TABLE or not block.html or "tables" not in wanted:
            continue
        table_no += 1
        file = "Table-%02d_page-%0*d.docx" % (table_no, width, i + 1)
        # Always: the picture is what every number in the table must be checked against.
        snapshot = img_out.png_bytes(img_out.crop(page, image, _pad(block.box, dpi, image), dpi, 0))
        write_table_docx(
            out.folder / "Tables" / file, block.html, table_no, i + 1, name,
            caption=_caption(result.blocks, j), snapshot_png=snapshot, ui_lang=options.ui_lang,
        )
        block.table_file = "Tables/" + file
        grid = parse_table(block.html)
        out.tables.append({"file": block.table_file, "page": i + 1, "rows": grid.rows, "cols": grid.cols})

    # Searchable text layer
    existing = page_text_kind(page)
    if existing == "visible":
        had_text.append(i + 1)          # born-digital page: its own text is already searchable (warned)
    elif "pdf" in wanted:
        if existing == "invisible":
            remove_invisible_text(page)  # replace an older OCR layer
        writer.add(page, result)         # a stamped scan keeps its stamp and gets OCR like any scan
    if not result.lines:
        empty.append(i + 1)
    out.words += result.word_count
    pages.append(result)
    return table_no


class _Later:
    """A page read when its result is asked for: engines that read one page at a time."""

    def __init__(self, read, *args):
        self.read, self.args = read, args

    def result(self):
        return self.read(*self.args)


def _read_pages(doc: pymupdf.Document, engine, options: Options, cancel: threading.Event):
    """Every page in order, as (index, dpi, image as rendered, reading); reading.result() gives
    (turn, upright image, PageResult). A page made on a computer gets its words from the PDF
    (options.own_text; see engines/pdftext.py) instead of OCR. An engine that can read several pages at once (Tesseract:
    one per processor core) reads the next ones while a page is written. Pages are rendered
    here, on the conversion's own thread: PyMuPDF must not be used from several threads."""
    at_once = max(1, engine.pages_at_once())
    pool = ThreadPoolExecutor(at_once, thread_name_prefix="hyperocr-page") if at_once > 1 else None
    ahead: deque = deque()
    following = 0
    try:
        for _ in range(doc.page_count):
            # One more than are read at once, so a reader is never idle while a page is written.
            while following < doc.page_count and len(ahead) < (at_once + 1 if pool else 1):
                if cancel.is_set():
                    raise Cancelled()
                page = doc[following]
                dpi = _page_dpi(page, options.dpi)
                image = _render(page, dpi)
                own = pdftext.page_words(page, dpi) if options.own_text else None
                args = (engine, image, following, dpi, options, own)
                ahead.append((following, dpi, image, pool.submit(_read_page, *args) if pool else _Later(_read_page, *args)))
                following += 1
            yield ahead.popleft()
    finally:
        if pool is not None:
            pool.shutdown(wait=False, cancel_futures=True)


def _read_page(engine, image: np.ndarray, index: int, dpi: int, options: Options, own=None):
    if own is not None:
        # The page's own text: laid out like OCR words, nothing read (and upright as shown).
        return 0, image, engines.get("tesseract").lay_out(image, index, dpi, options, own)
    turn = engines.page_turn(image, dpi)
    if turn:
        image = np.ascontiguousarray(np.rot90(image, k=-(turn // 90)))   # turned clockwise
    return turn, image, engine.process(image, index, dpi, options)


def _save_preview(image: np.ndarray, folder: Path, name: str) -> str:
    """A small picture of the page being read, for the interface."""
    from PIL import Image

    im = Image.fromarray(image)
    im.thumbnail((560, 800))
    im.save(folder / name, "JPEG", quality=72)
    return name


def _render(page: pymupdf.Page, dpi: int) -> np.ndarray:
    pix = page.get_pixmap(dpi=dpi, colorspace=pymupdf.csRGB, alpha=False)
    return np.frombuffer(pix.samples, np.uint8).reshape(pix.h, pix.w, 3).copy()


def _page_dpi(page: pymupdf.Page, dpi: int) -> int:
    longest = max(page.rect.width, page.rect.height) / 72.0
    if longest * dpi > MAX_SIDE_PX:
        return max(72, int(MAX_SIDE_PX / longest))
    return dpi


def _pad(box, dpi, image):
    pad = dpi * 0.04
    h, w = image.shape[:2]
    return (max(0, box[0] - pad), max(0, box[1] - pad), min(w, box[2] + pad), min(h, box[3] + pad))


def _caption(blocks: list[Block], index: int) -> str:
    for j in (index + 1, index - 1):
        if 0 <= j < len(blocks) and blocks[j].kind == CAPTION:
            return blocks[j].text
    return ""


def _title(pages: list[PageResult], doc: pymupdf.Document, stem: str) -> str:
    for page in pages[:3]:
        for b in page.blocks:
            if b.kind == TITLE and b.text.strip():
                return b.text.strip()[:200]
    meta = (doc.metadata or {}).get("title") or ""
    return meta.strip() or stem


def _bookmarks(doc: pymupdf.Document, pages: list[PageResult]) -> None:
    """Headings become the PDF's bookmarks (unless it already has some)."""
    if doc.get_toc():
        return
    entries = []
    for page in pages:
        for b in page.blocks:
            if b.kind == TITLE or (b.kind == HEADING and b.level <= 3):
                text = " ".join(b.text.split())[:120]
                if text:
                    entries.append([1 if b.kind == TITLE else b.level, text, page.index + 1])
    if not entries:
        return
    top = min(e[0] for e in entries)
    prev = 0
    for e in entries:
        e[0] = min(e[0] - top + 1, prev + 1)
        prev = e[0]
    try:
        doc.set_toc(entries)
    except Exception:
        pass  # bookmarks are a convenience; never fail a conversion over them


def _zip(folders: list[Path], target: Path) -> None:
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for folder in folders:
            for sub in ("Images", "Tables"):
                if (folder / sub).is_dir():
                    z.writestr(folder.name + "/" + sub + "/", "")
            for f in sorted(folder.rglob("*")):
                if f.is_file():
                    z.write(f, Path(folder.name) / f.relative_to(folder))
