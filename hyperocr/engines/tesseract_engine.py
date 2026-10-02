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
import subprocess
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
from ..paths import APP_ROOT, FROZEN, no_window
from . import layout_cv as cv
from .base import Availability, Engine, Options

CAPTION_RE = re.compile(
    r"^\s*(fig(ure)?|table|tab|chart|graph|plate|exhibit|scheme|"
    r"شكل|الشكل|جدول|الجدول|صورة|الصورة|رسم|مخطط)\s*\.?\s*[\dIVX٠-٩]+",
    re.I,
)
SCRIPT_BONUS = 8.0
ORPHAN_BLOCK = 100000   # block numbers for text recovered outside Tesseract's own layout
# Line heights (px) at which Tesseract reads a lone line or word reliably; used to
# re-read unsure words and recovered lines (see _reread_word, _read_orphan).
LINE_HEIGHTS = (36, 48)
REREAD_LIMIT = 60          # unsure words re-read per page, least confident first
SURE = 90.0                # a reading this confident is not re-read at another size
# Straighten only from this tilt on. Measured on both fixtures at 12 tilts (204 checks of table
# cells, headings and key words): no straightening 133, from 0.3 degrees 194-196, from 0.8 degrees
# 199. Below 0.8 Tesseract copes, and resampling the page costs more than it gains.
DESKEW_FROM = 0.8
OSD_DPI = 150              # page orientation is read at this resolution: at 100 dpi it guessed wrong
OSD_MIN_CONF = 3.0         # turned pages measured 6.2-13.8; wrong guesses at 100 dpi were below 0.2


# The Tesseract release the tests pass on; Windows setup installs exactly this build.
TESTED_VERSION = "5.4.0"
WINGET_VERSION = "5.4.0.20240606"


def tesseract_version(path: str | None = None) -> str:
    """The version of the Tesseract that HYPER-OCR will use, e.g. "5.4.0" ("" if none)."""
    path = path or find_tesseract()
    if not path:
        return ""
    try:
        out = subprocess.run([path, "--version"], capture_output=True, text=True, timeout=30, **no_window()).stdout
    except (OSError, subprocess.SubprocessError):
        return ""
    m = re.search(r"tesseract v?(\d+\.\d+\.\d+)", out)
    return m.group(1) if m else ""


def version_note() -> str:
    """For setup: a sentence when the installed Tesseract isn't the tested one, else ''."""
    found = tesseract_version()
    if found and found != TESTED_VERSION:
        return ("Tesseract %s found. HYPER-OCR is tested with Tesseract %s: other versions read some words and "
                "numbers differently." % (found, TESTED_VERSION))
    return ""


def find_tesseract() -> str | None:
    """The tesseract executable: setting, PATH, then the usual install folders."""
    candidates = [os.environ.get("HYPEROCR_TESSERACT", "")]
    if FROZEN:      # the desktop app always uses the Tesseract it was built and tested with
        candidates.append(str(APP_ROOT / "tesseract" / ("tesseract.exe" if sys.platform == "win32" else "tesseract")))
    candidates.append(shutil.which("tesseract") or "")
    here = APP_ROOT
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

    def page_turn(self, image: np.ndarray, dpi: float) -> int:
        """Degrees (90, 180 or 270) the page must be turned clockwise to stand upright: 0 when it
        already does, or when Tesseract isn't sure (little text, no `osd` language data)."""
        pt = self._ready()
        gray = cv.to_gray(image)
        scale = min(1.0, OSD_DPI / dpi)
        if scale < 1.0:
            gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        try:
            osd = pt.image_to_osd(gray, config="--psm 0 --dpi %d" % int(dpi * scale), output_type=pt.Output.DICT)
        except Exception:   # too few characters, no osd data, or a Linux build of 5.4 that stops on a
            return 0        # floating-point check here (Windows builds don't): leave the page as it is
        turn = int(osd.get("rotate", 0)) % 360
        if turn not in (90, 180, 270) or float(osd.get("orientation_conf", 0)) < OSD_MIN_CONF:
            return 0
        return turn

    def usable_languages(self, wanted: list[str]) -> list[str]:
        have = set(self.languages())
        langs = [l for l in wanted if l in have]
        if not langs:
            langs = ["eng"] if "eng" in have else self.languages()[:1]
        return langs

    # ------------------------------------------------------------ OCR

    def process(self, image: np.ndarray, index: int, dpi: float, options: Options) -> PageResult:
        """Read one page. A slightly tilted scan (up to 5 degrees) is straightened first: at 1 degree
        a table's columns ran together, at 2 degrees the table was lost. The boxes are then moved
        back onto the page as scanned, which is what the searchable PDF and the crops use."""
        angle = cv.skew_angle(cv.to_gray(image), dpi)
        if abs(angle) < DESKEW_FROM:
            return self._read(image, index, dpi, options)
        straight, m = cv.rotate_bound(image, angle)
        result = self._read(straight, index, dpi, options)
        h, w = image.shape[:2]
        back = cv2.invertAffineTransform(m)
        for line in result.lines:
            line.box = cv.map_box(line.box, back, w, h)
            for word in line.words:
                word.box = cv.map_box(word.box, back, w, h)
        for block in result.blocks:
            block.box = cv.map_box(block.box, back, w, h)
        result.width, result.height = w, h
        result.skew = angle
        return result

    def _read(self, image: np.ndarray, index: int, dpi: float, options: Options) -> PageResult:
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
        placed: list[Block] = [b for k, b in keyed if k[0] >= ORPHAN_BLOCK and not _continues(b, text_blocks)]
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
        if not base:
            return base
        line_rtl = {}
        for tw in base:
            line_rtl.setdefault(tw.key, []).append(tw.text)
        line_rtl = {k: mostly_rtl(" ".join(v)) for k, v in line_rtl.items()}
        was_rtl = {id(tw): is_rtl(tw.text) for tw in base}

        def score(text: str, conf: float, rtl_line: bool) -> float:
            return conf + (SCRIPT_BONUS if is_rtl(text) == rtl_line else 0.0)

        def vote(tw: TWord, candidates) -> None:
            rtl_line = line_rtl[tw.key]
            best = score(tw.text, tw.conf, rtl_line)
            for text, conf in candidates:
                s = score(text, conf, rtl_line)
                if s > best:
                    best, tw.text, tw.conf = s, text, conf

        def speck(tw: TWord) -> bool:
            """A lone, unsure Latin letter inside an Arabic line: a dot or a fragment, not a word."""
            return (len(langs) > 1 and line_rtl[tw.key] and len(tw.text) == 1
                    and tw.text.isascii() and tw.text.isalpha() and tw.conf < 75)

        if len(langs) > 1:
            # Only words with letters are re-read: models of other scripts misread digits.
            suspicious = [tw for tw in base if any(ch.isalpha() for ch in tw.text) and not speck(tw)
                          and (tw.conf < 80 or is_rtl(tw.text) != line_rtl[tw.key])]
            singles = [self._tsv(image, lang, dpi) for lang in langs] if suspicious else []
            for tw in suspicious:
                vote(tw, [(c.text, c.conf) for words in singles for c in words
                          if _iou(c.box, tw.box) >= 0.5 and any(ch.isalpha() for ch in c.text)])

        # Words still unsure are read once more on their own, scaled to line heights
        # Tesseract reads well. At 400 dpi the page reading was confidently wrong on
        # Arabic ("ااطبية", "سنئوات"); read alone, the same words come out right.
        bands: dict[tuple, tuple[float, float]] = {}
        for tw in base:
            top, bottom = bands.get(tw.key, (tw.box[1], tw.box[3]))
            bands[tw.key] = (min(top, tw.box[1]), max(bottom, tw.box[3]))
        def unsure(tw: TWord) -> bool:
            return tw.conf < 80 and any(ch.isalpha() for ch in tw.text)

        # A word Tesseract cut in two ("الطبية" read as "A" + "Sal]" by 5.4.0) can't be recovered
        # piece by piece: neighbouring unsure pieces of an Arabic line (specks included, as they may
        # be a piece) are read again as one span, and replaced by that reading when it is a single,
        # better word. Specks left over afterwards are dropped.
        dropped: set[int] = set()
        joined: set[tuple] = set()
        for run in _unsure_runs(base, lambda tw: unsure(tw) and line_rtl[tw.key]):
            box = union([tw.box for tw in run])
            rtl_line = line_rtl[run[0].key]
            worst = max(score(tw.text, tw.conf, rtl_line) for tw in run)
            best = max(self._reread_word(image, box, bands[run[0].key], langs, dpi),
                       key=lambda c: score(c[0], c[1], rtl_line), default=None)
            if best and score(best[0], best[1], rtl_line) > worst and best[1] >= 50:
                keep = run[0]
                keep.box, keep.text, keep.conf = box, best[0], best[1]
                dropped.update(id(tw) for tw in run[1:])
                joined.add(keep.key)
        base = [tw for tw in base if id(tw) not in dropped and not speck(tw)]
        for tw in sorted((tw for tw in base if unsure(tw)), key=lambda tw: tw.conf)[:REREAD_LIMIT]:
            vote(tw, self._reread_word(image, tw.box, bands[tw.key], langs, dpi))
        # Tesseract orders a line by the scripts it read. Where pieces were joined or a word changed
        # script, its order no longer holds ("Sal] تقرير المتابعة" put the title's last word first).
        redo = joined | {tw.key for tw in base if is_rtl(tw.text) != was_rtl.get(id(tw), is_rtl(tw.text))}
        return _reorder_lines(base, line_rtl, redo)

    def _reread_word(self, image: np.ndarray, box: Box, band: tuple[float, float], langs: list[str],
                     dpi: float) -> list[tuple[str, float]]:
        """Readings of one word cut out with its line's full height (so dots and
        descenders are kept), at each of LINE_HEIGHTS, as a line and as a single word
        (Tesseract 5.4.0 sometimes reads nothing in line mode). Only single-word readings count."""
        y0, y1 = int(min(box[1], band[0])), int(max(box[3], band[1]))
        if y1 <= y0:
            return []
        m = int(dpi * 0.02)
        crop = image[max(0, y0 - m): y1 + m, max(0, int(box[0]) - m): int(box[2]) + m]
        if crop.size == 0:
            return []
        pt = self._ready()
        out = []
        for target in LINE_HEIGHTS:
            s = target / (y1 - y0)
            for psm in (7, 8):
                data = pt.image_to_data(_scaled(crop, s), lang="+".join(langs),
                                        config="--psm %d --dpi %d" % (psm, max(70, int(dpi * s))),
                                        output_type=pt.Output.DICT)
                tokens = []
                for raw, conf in zip(data["text"], data["conf"], strict=False):
                    text = clean_text(raw or "")
                    try:
                        conf = float(conf)
                    except (TypeError, ValueError):
                        continue
                    if text and conf >= 0:
                        tokens.append((text, conf))
                if len(tokens) == 1 and any(ch.isalpha() for ch in tokens[0][0]):
                    out.append(tokens[0])
                    if tokens[0][1] >= SURE:
                        return out
        return out

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
            box = (max(0, x - m), max(0, y - m), min(w, x + bw + m), min(h, y + bh + m))
            for wbox, text, conf, par, line in self._read_orphan(gray, rest, box, langs, dpi):
                out.append(TWord(wbox, text, conf, (ORPHAN_BLOCK + i, par, line), next_order))
                next_order += 1
        return out

    def _read_orphan(self, gray: np.ndarray, rest: np.ndarray, box: tuple[int, int, int, int],
                     langs: list[str], dpi: float) -> list[tuple[Box, str, float, int, int]]:
        """Read one patch of leftover ink.

        Tesseract's reading of a lone line depends on its size: the heading
        "نتائج التحاليل" came out as "ئج التحاليل" at 300 dpi, with high
        confidence, and read perfectly when scaled to a smaller line height.
        So a single line is also read as a line at two normalised heights, and
        the reading whose words account for most of the leftover ink wins."""
        x0, y0, x1, y1 = box
        crop = gray[y0:y1, x0:x1]
        left = rest[y0:y1, x0:x1] > 0
        ink_cols = left.any(axis=0)
        total = int(ink_cols.sum())
        variants = [(1.0, 6)]
        rows = np.flatnonzero(left.any(axis=1))
        # Lines are counted in the leftover ink only: a descender of the line above, inside the
        # margin, made "الخارجية." look like two lines and lose its single-line readings.
        alone = np.where(left, crop, 255).astype(crop.dtype)
        if total and len(rows) and len(cv.line_bands(alone, (0, 0, x1 - x0, y1 - y0), dpi)) <= 1:
            height = rows[-1] - rows[0] + 1
            # As a line (psm 7), a raw line (13) and a single word (8): Tesseract 5.4.0 often returns
            # nothing for a lone Arabic line in modes 6 and 7, and reads it right in one of the others.
            variants += [(1.0, 13)] + [(target / height, psm) for target in LINE_HEIGHTS for psm in (7, 8, 13)]
        pt = self._ready()
        best: list[tuple[Box, str, float, int, int]] = []
        best_score = (-1.0, -1.0)
        for scale, psm in variants:
            data = pt.image_to_data(_scaled(crop, scale), lang="+".join(langs),
                                    config="--psm %d --dpi %d" % (psm, max(70, int(dpi * scale))),
                                    output_type=pt.Output.DICT)
            found = []
            covered = np.zeros_like(ink_cols)
            for j, raw in enumerate(data["text"]):
                text = clean_text(raw or "")
                try:
                    conf = float(data["conf"][j])
                except (TypeError, ValueError):
                    continue
                if not text or conf < 70 or sum(ch.isalnum() for ch in text) < 2:
                    continue
                bx0 = x0 + (data["left"][j] - 20) / scale
                by0 = y0 + (data["top"][j] - 20) / scale
                wbox = (bx0, by0, bx0 + data["width"][j] / scale, by0 + data["height"][j] / scale)
                found.append((wbox, text, conf, data["par_num"][j], data["line_num"][j]))
                covered[max(0, int(wbox[0]) - x0): max(0, int(wbox[2]) - x0 + 1)] = True
            if not found:
                continue
            # Most leftover ink explained first; confidence breaks ties.
            score = (round(float((covered & ink_cols).sum()) / max(1, total), 2),
                     float(np.mean([f[2] for f in found])))
            if score > best_score:
                best, best_score = found, score
        return best

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
            ink_only = 255 - cv.remove_specks(cv.remove_edge_lines(cv.ink_mask(crop), dpi), dpi)
            crop = _scaled(ink_only, 1.0)
            text, conf = self._read_crop(crop, "+".join(langs), dpi, psm)

            def score(t: str, cf: float) -> float:
                return cf + (SCRIPT_BONUS if any(ch.isalpha() for ch in t) and mostly_rtl(t) == table_rtl else 0)

            def off_script(t: str) -> int:
                return sum(1 for w in t.split() if any(ch.isalpha() for ch in w) and is_rtl(w) != table_rtl)

            best = score(text, conf)
            rows = np.flatnonzero((ink_only < 128).any(axis=1))
            if psm == 7 and len(rows) and conf < SURE:
                # A one-line cell is also read scaled to line heights Tesseract reads
                # well ("Jasall" -> "المعدل" at 400 dpi, "$7.9" -> "57.9" at 200 dpi).
                # A reading that brings in words of the other script is not taken
                # ("sang)! جلوبين" for "الهيموجلوبين").
                for target in LINE_HEIGHTS:
                    s = target / (rows[-1] - rows[0] + 1)
                    t2, c2 = self._read_crop(_scaled(ink_only, s), "+".join(langs), max(70.0, dpi * s), 7)
                    if t2 and score(t2, c2) > best and off_script(t2) <= off_script(text):
                        best, text, conf = score(t2, c2), t2, c2
                    if conf >= SURE:
                        break
            has_letters = any(ch.isalpha() for ch in text)
            if len(langs) > 1 and has_letters and (conf < 70 or mostly_rtl(text) != table_rtl):
                for lang in langs:
                    t2, c2 = self._read_crop(crop, lang, dpi, psm)
                    if not any(ch.isalpha() for ch in t2):
                        continue  # numbers stay as the combined model read them
                    if score(t2, c2) > best:
                        best, text = score(t2, c2), t2
            c.text = text or page_text[id(c)]

    def _read_crop(self, crop: np.ndarray, lang: str, dpi: float, psm: int = 7) -> tuple[str, float]:
        """Text and mean confidence of a small image. A one-line reading that comes back empty is
        tried as a single word (Tesseract 5.4.0 returns nothing for some one-word Arabic cells, such
        as "التحليل", read as a line), then as a block."""
        pt = self._ready()
        for mode in dict.fromkeys((psm, 8, 6) if psm == 7 else (psm, 6)):
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


def _reorder_lines(words: list[TWord], line_rtl: dict, keys: set) -> list[TWord]:
    """The Arabic lines among `keys` with their words in reading order; other lines as they are.

    Words are put right to left by position, with runs of English words kept left to right
    inside ("Amlodipine 5 mg"), by the rule Tesseract itself orders a line with."""
    order: dict[tuple, list[TWord]] = {}
    for tw in words:
        order.setdefault(tw.key, []).append(tw)
    for key, line in order.items():
        if key in keys and line_rtl.get(key):
            line[:] = _bidi_order(sorted(line, key=lambda tw: -tw.box[2]))
    out, seen = [], set()
    for tw in words:
        if tw.key not in seen:
            seen.add(tw.key)
            out.extend(order[tw.key])
    return out


def _bidi_order(right_to_left: list[TWord]) -> list[TWord]:
    """Words of a right-to-left line, given right to left by position, in reading order.
    English words are left to right; numbers and punctuation have no direction of their own."""
    def kind(tw: TWord) -> str:
        if is_rtl(tw.text):
            return "R"
        return "L" if any(ch.isalpha() for ch in tw.text) else "N"

    kinds = [kind(tw) for tw in right_to_left]
    # A number or sign between two English words belongs to their run ("Amlodipine 5 mg"); anywhere
    # else it follows the line ("الكرياتينين 1.1 mg/dL").
    for i, k in enumerate(kinds):
        if k == "N":
            before = next((kinds[j] for j in range(i - 1, -1, -1) if kinds[j] != "N"), "R")
            after = next((kinds[j] for j in range(i + 1, len(kinds)) if kinds[j] != "N"), "R")
            kinds[i] = "L" if before == after == "L" else "R"
    out, run = [], []
    for tw, k in zip(right_to_left, kinds, strict=True):
        if k == "L":
            run.append(tw)
            continue
        out.extend(reversed(run))
        run = []
        out.append(tw)
    out.extend(reversed(run))
    return out


def _unsure_runs(words: list[TWord], unsure) -> list[list[TWord]]:
    """Runs of two or more neighbouring unsure words on one line (closer than a line height)."""
    runs = []
    for line in _group(words, 3).values():
        line = sorted(line, key=lambda tw: tw.box[0])
        run: list[TWord] = []
        for tw in line:
            height = max(1.0, tw.box[3] - tw.box[1])
            if unsure(tw) and run and tw.box[0] - run[-1].box[2] <= height:
                run.append(tw)
            else:
                if len(run) >= 2:
                    runs.append(run)
                run = [tw] if unsure(tw) else []
        if len(run) >= 2:
            runs.append(run)
    return runs


def _scaled(img: np.ndarray, scale: float) -> np.ndarray:
    """`img` resized by `scale`, with the white margin Tesseract needs around text."""
    if scale != 1.0:
        img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC)
    return cv2.copyMakeBorder(img, 20, 20, 20, 20, cv2.BORDER_CONSTANT, value=255)


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
        stroke = 2.0 * float(np.median(dist[dist > 0]))
        # A box with no background pixel (solid ink) has no measurable stroke, not an infinite one.
        return size, stroke if stroke < max(region.shape) else 0.0

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


def _continues(block: Block, paragraphs: list[Block]) -> bool:
    """A recovered line of text right under a paragraph, within its width, is that paragraph's
    last line (Tesseract 5.4.0 skipped "الخارجية." at the end of one): it is joined to it."""
    if block.kind != TEXT:
        return False
    line_h = block.box[3] - block.box[1]
    for p in paragraphs:
        if (p.kind == TEXT and abs(block.box[1] - p.box[3]) <= 0.5 * line_h
                and p.box[0] - line_h <= block.box[0] and block.box[2] <= p.box[2] + line_h):
            p.text = _join_lines([p.text, block.text])
            p.box = union([p.box, block.box])
            return True
    return False


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
