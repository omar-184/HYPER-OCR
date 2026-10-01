"""CPU engine: Tesseract for the text, OpenCV for tables and figures.

Runs on any computer. Quality notes:
* pages are denoised first (a 3x3 median removes scanner specks that
  Tesseract otherwise reads as Arabic diacritics);
* table borders are erased before OCR so cell text is read cleanly;
* with several languages selected, each word is read once with all of them
  together and again with each one alone, and the most confident reading
  wins, with a bonus for matching the script of its line. This fixes Arabic
  words that the combined model reads as Latin look-alikes ("bad" for ضغط).
"""

from __future__ import annotations

import os
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from ..document import (
    CAPTION,
    FIGURE,
    FOOTER,
    HEADER,
    HEADING,
    PAGE_NUMBER,
    TABLE,
    TEXT,
    TITLE,
    Block,
    Box,
    Line,
    PageResult,
    Word,
    clean_text,
    is_rtl,
    mostly_rtl,
    union,
)
from . import layout_cv as cv
from .base import Availability, Engine, Options

CAPTION_RE = re.compile(
    r"^\s*(fig(ure)?|table|tab|chart|graph|plate|exhibit|scheme|"
    r"شكل|الشكل|جدول|الجدول|صورة|الصورة|رسم|مخطط)\s*\.?\s*[\dIVX٠-٩]+",
    re.I,
)
SCRIPT_BONUS = 8.0
ORPHAN_BLOCK = 100000   # block numbers for text recovered outside Tesseract's own layout


def find_tesseract() -> str | None:
    """The tesseract executable: setting, PATH, then the usual install folders."""
    candidates = [os.environ.get("HYPEROCR_TESSERACT", "")]
    candidates.append(shutil.which("tesseract") or "")
    here = Path(__file__).resolve().parents[2]
    if sys.platform == "win32":
        candidates += [
            str(here / "tesseract" / "tesseract.exe"),
            os.path.expandvars(r"%ProgramFiles%\Tesseract-OCR\tesseract.exe"),
            os.path.expandvars(r"%ProgramFiles(x86)%\Tesseract-OCR\tesseract.exe"),
            os.path.expandvars(r"%LocalAppData%\Programs\Tesseract-OCR\tesseract.exe"),
        ]
    else:
        candidates += [str(here / "tesseract" / "tesseract"), "/opt/homebrew/bin/tesseract", "/usr/local/bin/tesseract"]
    for c in candidates:
        if c and Path(c).is_file():
            return c
    return None


@dataclass
class TWord:
    box: Box
    text: str
    conf: float
    key: tuple[int, int, int]   # (block, paragraph, line)
    order: int


class TesseractEngine(Engine):
    id = "tesseract"
    name = "Tesseract"

    def __init__(self) -> None:
        self._cmd = None
        self._langs: list[str] | None = None

    # ------------------------------------------------------------ setup

    def _ready(self):
        import pytesseract

        if self._cmd is None:
            self._cmd = find_tesseract() or ""
            # The app's own language folder (filled by setup) wins over the system's.
            from ..languages import folder, installed

            if installed():
                os.environ["TESSDATA_PREFIX"] = str(folder())
        if self._cmd:
            pytesseract.pytesseract.tesseract_cmd = self._cmd
        return pytesseract

    def availability(self) -> Availability:
        try:
            pt = self._ready()
            version = str(pt.get_tesseract_version())
        except Exception as exc:  # not installed, or not on PATH
            return Availability(False, "tesseractMissing", str(exc))
        return Availability(True, detail="Tesseract " + version.split()[0])

    def languages(self) -> list[str]:
        if self._langs is None:
            try:
                langs = self._ready().get_languages(config="")
            except Exception:
                langs = []
            self._langs = sorted(l for l in langs if l not in ("osd", "equ", "snum"))
        return self._langs

    def usable_languages(self, wanted: list[str]) -> list[str]:
        have = set(self.languages())
        langs = [l for l in wanted if l in have]
        if not langs:
            langs = ["eng"] if "eng" in have else self.languages()[:1]
        return langs

    # ------------------------------------------------------------ OCR

    def process(self, image: np.ndarray, index: int, dpi: float, options: Options) -> PageResult:
        langs = self.usable_languages(options.languages)
        gray = cv.denoise(cv.to_gray(image))
        h, w = gray.shape
        ink = cv.ink_mask(gray)
        rules = cv.find_rules(ink, dpi)
        grids = cv.find_tables(rules, dpi)
        clean = cv.erase_rules(gray, rules)
        words = self._ocr_words(clean, langs, dpi)
        result = PageResult(index, w, h, dpi, self.id)

        sure = [tw.box for tw in words if tw.conf >= 30]
        figures = cv.find_figures(
            ink, rules, sure, [g.box for g in grids], dpi,
            is_text=lambda box: self._looks_like_text(clean, ink, box, langs, dpi),
        )
        figures = [cv.expand_figure(f, ink, sure, dpi) for f in figures]
        # Text Tesseract's page layout skipped (it happens to headings near tables).
        words += self._recover_orphans(clean, ink, rules, words, [g.box for g in grids] + figures, langs, dpi)

        # Which words belong to a table or a figure (by their centre)?
        def inside(tw: TWord, box: Box) -> bool:
            cx, cy = (tw.box[0] + tw.box[2]) / 2, (tw.box[1] + tw.box[3]) / 2
            return box[0] <= cx <= box[2] and box[1] <= cy <= box[3]

        table_words: dict[int, list[TWord]] = {i: [] for i in range(len(grids))}
        figure_words: set[int] = set()
        free: list[TWord] = []
        for tw in words:
            for i, g in enumerate(grids):
                if inside(tw, g.box):
                    table_words[i].append(tw)
                    break
            else:
                if any(inside(tw, f) for f in figures):
                    figure_words.add(tw.order)
                else:
                    free.append(tw)

        keyed = _paragraph_blocks(free, h, ink)
        text_blocks = [b for k, b in keyed if k[0] < ORPHAN_BLOCK]
        placed: list[Block] = [b for k, b in keyed if k[0] >= ORPHAN_BLOCK]
        cell_lines: list[Line] = []
        for i, g in enumerate(grids):
            self._read_cells(clean, g, table_words[i], langs, dpi)
            html, text = _table_html(g)
            if text.strip():
                placed.append(Block(TABLE, g.box, text=text, html=html))
            for c in g.cells:
                if c.text:
                    inside = [tw.box for tw in table_words[i]
                              if c.box[0] <= (tw.box[0] + tw.box[2]) / 2 <= c.box[2]
                              and c.box[1] <= (tw.box[1] + tw.box[3]) / 2 <= c.box[3]]
                    box = union(inside) if inside else _inset(c.box, dpi * 0.03)
                    cell_lines.append(Line(box, c.text.replace("\n", " ")))
        # Text layer: the page OCR, except inside tables, where the per-cell reading is better.
        in_tables = {tw.order for ws in table_words.values() for tw in ws}
        result.lines = _lines([tw for tw in words if tw.order not in in_tables]) + cell_lines
        for f in figures:
            placed.append(Block(FIGURE, f))
        result.blocks = _reading_order(text_blocks, placed)
        _mark_captions(result.blocks, dpi)
        return result

    def _tsv(self, image: np.ndarray, lang: str, dpi: float) -> list[TWord]:
        pt = self._ready()
        data = pt.image_to_data(
            image, lang=lang, config="--psm 3 --dpi %d" % int(dpi), output_type=pt.Output.DICT
        )
        out = []
        for i, raw in enumerate(data["text"]):
            text = clean_text(raw or "")
            if not text:
                continue
            try:
                conf = float(data["conf"][i])
            except (TypeError, ValueError):
                conf = -1.0
            if conf < 0 or (conf < 60 and not any(ch.isalnum() for ch in text)):
                continue  # specks read as quotes, dots or dashes
            x, y, bw, bh = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
            key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
            out.append(TWord((float(x), float(y), float(x + bw), float(y + bh)), text, conf, key, len(out)))
        return out

    def _ocr_words(self, image: np.ndarray, langs: list[str], dpi: float) -> list[TWord]:
        base = self._tsv(image, "+".join(langs), dpi)
        if len(langs) < 2 or not base:
            return base
        line_rtl = {}
        for tw in base:
            line_rtl.setdefault(tw.key, []).append(tw.text)
        line_rtl = {k: mostly_rtl(" ".join(v)) for k, v in line_rtl.items()}

        def score(text: str, conf: float, rtl_line: bool) -> float:
            return conf + (SCRIPT_BONUS if is_rtl(text) == rtl_line else 0.0)

        # A lone, unsure Latin letter inside an Arabic line is a speck, not a word.
        base = [tw for tw in base if not (line_rtl[tw.key] and len(tw.text) == 1
                                          and tw.text.isascii() and tw.text.isalpha() and tw.conf < 75)]
        # Only words with letters are re-read: models of other scripts misread digits.
        suspicious = [tw for tw in base if any(ch.isalpha() for ch in tw.text)
                      and (tw.conf < 80 or is_rtl(tw.text) != line_rtl[tw.key])]
        if not suspicious:
            return base
        singles = [self._tsv(image, lang, dpi) for lang in langs]
        for tw in suspicious:
            rtl_line = line_rtl[tw.key]
            best = score(tw.text, tw.conf, rtl_line)
            for pass_words in singles:
                for cand in pass_words:
                    if _iou(cand.box, tw.box) < 0.5 or not any(ch.isalpha() for ch in cand.text):
                        continue
                    s = score(cand.text, cand.conf, rtl_line)
                    if s > best:
                        best, tw.text, tw.conf = s, cand.text, cand.conf
        return base

    def _recover_orphans(self, gray: np.ndarray, ink: np.ndarray, rules: cv.Rules, words: list[TWord],
                         taken: list[Box], langs: list[str], dpi: float) -> list[TWord]:
        """OCR line-shaped ink that no word, table or figure accounts for."""
        rest = cv.remove_specks(cv.bitwise_without(ink, rules.both), dpi)
        # Generous margins: dots and diacritics just outside a known word are not new text.
        for b in [tw.box for tw in words]:
            pad = int(max(dpi * 0.02, 0.35 * (b[3] - b[1])))
            rest[max(0, int(b[1]) - pad): int(b[3]) + pad, max(0, int(b[0]) - pad): int(b[2]) + pad] = 0
        pad = int(dpi * 0.03)
        for b in taken:
            rest[max(0, int(b[1]) - pad): int(b[3]) + pad, max(0, int(b[0]) - pad): int(b[2]) + pad] = 0
        joined = cv2.dilate(rest, cv2.getStructuringElement(cv2.MORPH_RECT, (max(3, int(dpi * 0.12)), max(1, int(dpi * 0.015)))))
        n, _, stats, _ = cv2.connectedComponentsWithStats(joined, connectivity=8)
        h, w = gray.shape
        out: list[TWord] = []
        next_order = max((tw.order for tw in words), default=0) + 1
        for i in range(1, n):
            x, y, bw, bh, count = stats[i]
            if not (dpi * 0.06 <= bh <= dpi * 0.6 and bw >= dpi * 0.12 and bw >= bh):
                continue
            m = int(dpi * 0.06)
            x0, y0, x1, y1 = max(0, x - m), max(0, y - m), min(w, x + bw + m), min(h, y + bh + m)
            crop = cv2.copyMakeBorder(gray[y0:y1, x0:x1], 20, 20, 20, 20, cv2.BORDER_CONSTANT, value=255)
            pt = self._ready()
            data = pt.image_to_data(crop, lang="+".join(langs), config="--psm 6 --dpi %d" % int(dpi),
                                    output_type=pt.Output.DICT)
            for j, raw in enumerate(data["text"]):
                text = clean_text(raw or "")
                try:
                    conf = float(data["conf"][j])
                except (TypeError, ValueError):
                    continue
                if not text or conf < 70 or sum(ch.isalnum() for ch in text) < 2:
                    continue
                bx = x0 - 20 + data["left"][j]
                by = y0 - 20 + data["top"][j]
                box = (float(bx), float(by), float(bx + data["width"][j]), float(by + data["height"][j]))
                key = (ORPHAN_BLOCK + i, data["par_num"][j], data["line_num"][j])
                out.append(TWord(box, text, conf, key, next_order))
                next_order += 1
        return out

    def _read_cells(self, gray: np.ndarray, grid: cv.TableGrid, words: list[TWord], langs: list[str], dpi: float) -> None:
        """OCR every cell on its own: far more reliable than page-level OCR for
        numbers in tables. Page words are the fallback for a cell that reads empty."""
        page_text = {}
        for c in grid.cells:
            inside = [tw for tw in words
                      if c.box[0] <= (tw.box[0] + tw.box[2]) / 2 <= c.box[2]
                      and c.box[1] <= (tw.box[1] + tw.box[3]) / 2 <= c.box[3]]
            page_text[id(c)] = _join_lines([" ".join(tw.text for tw in line) for line in _visual_lines(inside)])
        table_rtl = mostly_rtl(" ".join(page_text.values()))
        inset = max(2, int(dpi * 0.012))
        for c in grid.cells:
            x0, y0, x1, y1 = (int(v) for v in c.box)
            crop = gray[y0 + inset: y1 - inset, x0 + inset: x1 - inset]
            if crop.size == 0 or not (cv.ink_mask(crop) > 0).any() and not page_text[id(c)]:
                c.text = ""
                continue
            n_lines = len(cv.line_bands(crop, (0, 0, crop.shape[1], crop.shape[0]), dpi))
            psm = 7 if n_lines <= 1 else 6
            # Binarise small crops ourselves: Tesseract's own threshold on a mostly
            # blank, speckled cell misreads digits ("57.9" came out as "97-9").
            crop = 255 - cv.remove_specks(cv.remove_edge_lines(cv.ink_mask(crop), dpi), dpi)
            crop = cv2.copyMakeBorder(crop, 20, 20, 20, 20, cv2.BORDER_CONSTANT, value=255)
            text, conf = self._read_crop(crop, "+".join(langs), dpi, psm)
            has_letters = any(ch.isalpha() for ch in text)
            if len(langs) > 1 and has_letters and (conf < 70 or mostly_rtl(text) != table_rtl):
                best = conf + (SCRIPT_BONUS if mostly_rtl(text) == table_rtl else 0)
                for lang in langs:
                    t2, c2 = self._read_crop(crop, lang, dpi, psm)
                    if not any(ch.isalpha() for ch in t2):
                        continue  # numbers stay as the combined model read them
                    s2 = c2 + (SCRIPT_BONUS if mostly_rtl(t2) == table_rtl else 0)
                    if s2 > best:
                        best, text = s2, t2
            c.text = text or page_text[id(c)]

    def _read_crop(self, crop: np.ndarray, lang: str, dpi: float, psm: int = 7) -> tuple[str, float]:
        """Text and mean confidence of a small image; a block read is the fallback."""
        pt = self._ready()
        for mode in dict.fromkeys((psm, 6)):
            data = pt.image_to_data(crop, lang=lang, config="--psm %d --dpi %d" % (mode, int(dpi)),
                                    output_type=pt.Output.DICT)
            words = []
            for i, raw in enumerate(data["text"]):
                text = clean_text(raw or "")
                try:
                    conf = float(data["conf"][i])
                except (TypeError, ValueError):
                    continue
                if text and conf >= 0 and (conf >= 60 or any(ch.isalnum() for ch in text)) \
                        and not (len(text) == 1 and conf < 50):
                    words.append(TWord((data["left"][i], data["top"][i], data["left"][i] + data["width"][i],
                                        data["top"][i] + data["height"][i]), text, conf, (0, 0, 0), i))
            if words:
                text = _join_lines([" ".join(tw.text for tw in line) for line in _visual_lines(words)])
                return text, float(np.mean([tw.conf for tw in words]))
        return "", 0.0

    def _looks_like_text(self, gray: np.ndarray, ink: np.ndarray, box: Box, langs: list[str], dpi: float) -> bool:
        """OCR a figure candidate; if confident words cover most of its ink, it is text."""
        x0, y0, x1, y1 = (int(v) for v in box)
        crop = gray[y0:y1, x0:x1]
        ink_crop = ink[y0:y1, x0:x1] > 0
        total = int(ink_crop.sum())
        if crop.size == 0 or total == 0:
            return False
        pt = self._ready()
        data = pt.image_to_data(crop, lang="+".join(langs), config="--psm 6 --dpi %d" % int(dpi),
                                output_type=pt.Output.DICT)
        covered = np.zeros_like(ink_crop)
        good = 0
        for i, raw in enumerate(data["text"]):
            try:
                conf = float(data["conf"][i])
            except (TypeError, ValueError):
                continue
            if conf >= 60 and len(clean_text(raw or "")) >= 2:
                good += 1
                l, t = data["left"][i], data["top"][i]
                covered[t:t + data["height"][i], l:l + data["width"][i]] = True
        return good >= 2 and (ink_crop & covered).sum() / total >= 0.55


# ---------------------------------------------------------------- assembly


def _inset(box: Box, d: float) -> Box:
    return (box[0] + d, box[1] + d, max(box[0] + d + 1, box[2] - d), max(box[1] + d + 1, box[3] - d))


def _iou(a: Box, b: Box) -> float:
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    if inter <= 0:
        return 0.0
    return inter / ((a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter)


def _group(words: list[TWord], depth: int) -> dict[tuple, list[TWord]]:
    groups: dict[tuple, list[TWord]] = {}
    for tw in words:
        groups.setdefault(tw.key[:depth], []).append(tw)
    return groups


def _lines(words: list[TWord]) -> list[Line]:
    """Every OCR line with its words: the searchable text layer."""
    out = []
    for group in _group(words, 3).values():
        out.append(Line(
            union([tw.box for tw in group]),
            " ".join(tw.text for tw in group),
            [Word(tw.box, tw.text, tw.conf) for tw in group],
        ))
    return out


def _join_lines(lines: list[str]) -> str:
    """Join wrapped lines, mending words hyphenated across a line break."""
    text = ""
    for line in lines:
        if text.endswith("-") and line[:1].islower() and len(text) > 1 and text[-2].isalpha():
            text = text[:-1] + line
        else:
            text = (text + " " + line) if text else line
    return text


def _paragraph_blocks(words: list[TWord], page_h: int, ink: np.ndarray) -> list[tuple[tuple, Block]]:
    """Paragraphs from Tesseract's grouping, split where the line style changes
    (a bigger or bolder first line is a heading, even when Tesseract kept it
    with the paragraph below)."""
    pars: dict[tuple, list[list[TWord]]] = {}
    for key, group in _group(words, 3).items():
        pars.setdefault(key[:2], []).append(group)

    def stats(line: list[TWord]) -> tuple[float, float]:
        """Median word height, and stroke width (bold text has thicker strokes)."""
        size = float(np.median([tw.box[3] - tw.box[1] for tw in line]))
        x0, y0, x1, y1 = (int(v) for v in union([tw.box for tw in line]))
        region = (ink[y0:y1, x0:x1] > 0).astype(np.uint8)
        if not region.any():
            return size, 0.0
        dist = cv2.distanceTransform(region, cv2.DIST_L2, 3)
        return size, float(2 * np.median(dist[dist > 0]))

    all_lines = [(line, stats(line)) for group in pars.values() for line in group]
    body_lines = [st for line, st in all_lines if len(line) >= 3] or [st for _, st in all_lines]
    body_size = float(np.median([st[0] for st in body_lines])) if body_lines else 0.0
    body_stroke = float(np.median([st[1] for st in body_lines])) if body_lines else 0.0
    line_stats = {id(line): st for line, st in all_lines}

    def heading_like(line: list[TWord]) -> bool:
        size, stroke = line_stats[id(line)]
        text = " ".join(tw.text for tw in line)
        if body_size <= 0 or len(line) > 12 or text.rstrip().endswith((".", ",", ";", "،", "؛")):
            return False
        bold = body_stroke > 0 and stroke >= 1.35 * body_stroke
        return bold or size >= 1.2 * body_size or (size >= 1.1 * body_size and len(line) <= 6)

    blocks, sizes, keys = [], [], []
    for par_key, group in pars.items():
        segments: list[list[list[TWord]]] = []
        for line in group:
            if segments and heading_like(line) == heading_like(segments[-1][-1]):
                segments[-1].append(line)
            else:
                segments.append([line])
        for seg in segments:
            text = _join_lines([" ".join(tw.text for tw in line) for line in seg])
            if not text.strip():
                continue
            box = union([tw.box for line in seg for tw in line])
            size = max(line_stats[id(line)][0] for line in seg)
            kind, level = TEXT, 1
            if len(seg) <= 2 and heading_like(seg[0]):
                kind, level = HEADING, (2 if size >= 1.45 * body_size else 3)
            n_words = len(text.split())
            if box[3] < page_h * 0.055 or box[1] > page_h * 0.945:
                if re.fullmatch(r"[\W\d٠-٩ivxlcdmIVXLCDM\s]{1,12}", text) and any(ch.isdigit() for ch in text):
                    kind = PAGE_NUMBER
                elif n_words <= 12 and kind == TEXT:
                    kind = HEADER if box[3] < page_h * 0.5 else FOOTER
            blocks.append(Block(kind, box, text=text, level=level))
            sizes.append(size)
            keys.append(par_key)
    # The biggest heading among the first two blocks, in the top third, is the page title.
    lead = [(sizes[i], blocks[i]) for i in range(min(2, len(blocks)))
            if blocks[i].kind == HEADING and blocks[i].level == 2 and blocks[i].box[1] < page_h * 0.35]
    if lead:
        top = max(lead, key=lambda t: t[0])[1]
        top.kind, top.level = TITLE, 1
    return list(zip(keys, blocks, strict=True))


def _visual_lines(words: list[TWord]) -> list[list[TWord]]:
    """Group words into lines by vertical overlap, each in reading order."""
    lines: list[list[TWord]] = []
    for tw in sorted(words, key=lambda w: (w.box[1] + w.box[3]) / 2):
        cy = (tw.box[1] + tw.box[3]) / 2
        for line in lines:
            top = min(w.box[1] for w in line)
            bottom = max(w.box[3] for w in line)
            if top <= cy <= bottom:
                line.append(tw)
                break
        else:
            lines.append([tw])
    out = []
    for line in lines:
        rtl = mostly_rtl(" ".join(w.text for w in line))
        out.append(sorted(line, key=lambda w: w.box[0], reverse=rtl))
    return out


def _table_html(grid: cv.TableGrid) -> tuple[str, str]:
    """HTML for a detected table whose cells have been read."""
    import html as htmllib

    cells = grid.cells
    rtl = mostly_rtl(" ".join(c.text for c in cells))
    nr, nc = grid.shape
    rows_html, rows_text = [], []
    for r in range(nr):
        row = sorted((c for c in cells if c.row == r), key=lambda c: c.col, reverse=rtl)
        if not row:
            rows_html.append("<tr></tr>")
            continue
        tag = "th" if r == 0 and nr > 1 else "td"
        parts = []
        for c in row:
            attrs = ""
            if c.rowspan > 1:
                attrs += ' rowspan="%d"' % c.rowspan
            if c.colspan > 1:
                attrs += ' colspan="%d"' % c.colspan
            parts.append("<%s%s>%s</%s>" % (tag, attrs, htmllib.escape(c.text), tag))
        rows_html.append("<tr>" + "".join(parts) + "</tr>")
        rows_text.append(" ".join(c.text for c in row))
    table = '<table dir="rtl">' if rtl else "<table>"
    return table + "".join(rows_html) + "</table>", "\n".join(t for t in rows_text if t.strip())


def _reading_order(text_blocks: list[Block], placed: list[Block]) -> list[Block]:
    """Tesseract's order for text; each table or figure goes before the first text
    block that starts below it in the same column."""
    order = list(text_blocks)
    for item in sorted(placed, key=lambda b: (b.box[1], b.box[0])):
        at = len(order)
        for i, b in enumerate(order):
            same_column = min(b.box[2], item.box[2]) - max(b.box[0], item.box[0]) > 0
            if same_column and b.box[1] >= item.box[1] - 1:
                at = i
                break
        order.insert(at, item)
    return order


def _mark_captions(blocks: list[Block], dpi: float) -> None:
    """A short paragraph that starts like "Figure 2." next to a figure or table."""
    near = dpi * 1.2
    for i, b in enumerate(blocks):
        if b.kind not in (TEXT, HEADING) or not CAPTION_RE.match(b.text) or len(b.text.split()) > 60:
            continue
        for j in (i - 1, i + 1):
            if 0 <= j < len(blocks) and blocks[j].kind in (FIGURE, TABLE):
                o = blocks[j].box
                gap = max(b.box[1] - o[3], o[1] - b.box[3])
                if gap < near:
                    b.kind = CAPTION
                    break
