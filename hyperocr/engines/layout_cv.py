"""Classical computer-vision layout helpers (OpenCV, no learned models).

* ruling lines and bordered tables, with merged cells
* figure regions (pictures, charts) once the text is known
* text-line bands inside a block, to place the searchable text layer when an
  engine only reports whole-block boxes
* the skew of a slightly tilted scan, to straighten it before reading
"""

from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np

from ..document import Box, Line, area, intersection, overlap_ratio


SKEW_LIMIT = 5.0      # degrees either way; more than that is not a slightly tilted scan
SKEW_DPI = 100        # the angle is measured on a copy at this resolution
SKEW_MIN_GAIN = 1.02  # the straight reading must be this much sharper than the page as it is


def skew_angle(gray: np.ndarray, dpi: float) -> float:
    """The angle (degrees, counter-clockwise positive, as cv2.getRotationMatrix2D) that makes
    the page's lines of text and table rules horizontal; 0.0 when the page is straight or has
    too little ink to tell.

    Rows of a straight page alternate between dense ink and blank gaps; rotate the ink until
    the row profile is sharpest (largest sum of squared differences between neighbouring rows).
    """
    scale = min(1.0, SKEW_DPI / max(dpi, 1.0))
    ink = ink_mask(gray)
    small = cv2.resize(ink, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA) if scale < 1.0 else ink
    small = (small > 64).astype(np.float32)
    if small.sum() < 200:
        return 0.0
    h, w = small.shape
    center = (w / 2.0, h / 2.0)

    def sharpness(angle: float) -> float:
        m = cv2.getRotationMatrix2D(center, angle, 1.0)
        rotated = cv2.warpAffine(small, m, (w, h), flags=cv2.INTER_NEAREST, borderValue=0)
        rows = rotated.sum(axis=1)
        return float(np.sum(np.diff(rows) ** 2))

    best = max(np.arange(-SKEW_LIMIT, SKEW_LIMIT + 0.01, 0.5), key=sharpness)
    for step in (0.1, 0.02):
        best = max(np.arange(best - 5 * step, best + 5 * step + step / 2, step), key=sharpness)
    best = float(np.clip(best, -SKEW_LIMIT, SKEW_LIMIT))
    if abs(best) < 0.05 or sharpness(best) < SKEW_MIN_GAIN * sharpness(0.0):
        return 0.0
    return round(best, 2)


def rotate_bound(image: np.ndarray, angle: float) -> tuple[np.ndarray, np.ndarray]:
    """`image` rotated by `angle` on a canvas large enough to keep every corner (white
    around it), and the 2x3 matrix that maps original points onto the new canvas."""
    h, w = image.shape[:2]
    m = cv2.getRotationMatrix2D((w / 2.0, h / 2.0), angle, 1.0)
    cos, sin = abs(m[0, 0]), abs(m[0, 1])
    nw, nh = int(round(h * sin + w * cos)), int(round(h * cos + w * sin))
    m[0, 2] += nw / 2.0 - w / 2.0
    m[1, 2] += nh / 2.0 - h / 2.0
    white = (255,) * image.shape[2] if image.ndim == 3 else 255
    return cv2.warpAffine(image, m, (nw, nh), flags=cv2.INTER_CUBIC, borderValue=white), m


def map_box(box: Box, m: np.ndarray, width: int, height: int) -> Box:
    """The axis-aligned box, inside a `width` x `height` image, around `box` moved by matrix `m`."""
    x0, y0, x1, y1 = box
    pts = np.array([[x0, y0], [x1, y0], [x0, y1], [x1, y1]], dtype=np.float64)
    moved = pts @ m[:, :2].T + m[:, 2]
    return (float(max(0.0, moved[:, 0].min())), float(max(0.0, moved[:, 1].min())),
            float(min(width, moved[:, 0].max())), float(min(height, moved[:, 1].max())))


def to_gray(image: np.ndarray) -> np.ndarray:
    if image.ndim == 3:
        return cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    return image


def denoise(gray: np.ndarray) -> np.ndarray:
    """A 3x3 median removes scanner specks that Tesseract mistakes for diacritics."""
    return cv2.medianBlur(gray, 3)


def ink_mask(gray: np.ndarray) -> np.ndarray:
    """255 where there is ink. Otsu, falling back to a fixed level on blank pages."""
    level, mask = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    if level > 235 or level < 40:
        _, mask = cv2.threshold(gray, 160, 255, cv2.THRESH_BINARY_INV)
    return mask


def remove_specks(ink: np.ndarray, dpi: float, keep_points: bool = False) -> np.ndarray:
    """Drop isolated dots far smaller than any letter or diacritic.

    With `keep_points` (inside a table cell), a dot on the baseline of the characters either
    side of it is kept: it is a decimal point or a comma. At 200 dpi the point of "5.3" is a
    3-pixel dot, which this used to remove, and every such value came out without it ("53")."""
    limit = max(4, int((dpi * 0.012) ** 2))
    n, labels, stats, _ = cv2.connectedComponentsWithStats(ink, connectivity=8)
    small = np.where(stats[:, cv2.CC_STAT_AREA] <= limit)[0]
    small = small[small != 0]
    if keep_points and small.size:
        small = np.array([i for i in small if not _on_baseline(i, stats, limit)], dtype=int)
    out = ink.copy()
    if small.size:
        out[np.isin(labels, small)] = 0
    return out


def _on_baseline(i: int, stats: np.ndarray, limit: int) -> bool:
    """Is small component `i` a point between two characters: with a character on each side
    (closer than a character's height) whose bottom is level with its own?"""
    x, y, w, h = stats[i, :4]
    bottom, centre = y + h, x + w / 2
    left = right = False
    for j in range(1, len(stats)):
        bx, by, bw, bh, area = stats[j]
        if j == i or area <= limit or bh < 3 * h:
            continue
        if abs(by + bh - bottom) > 0.2 * bh:
            continue
        if 0 <= centre - (bx + bw) <= bh:
            left = True
        elif 0 <= bx - centre <= bh:
            right = True
    return left and right


def remove_edge_lines(ink: np.ndarray, dpi: float) -> np.ndarray:
    """Inside a table cell: drop thin strokes touching the cell's edge. They are
    pieces of the border left over when a slightly tilted scan's rules drift."""
    thin = max(3, int(dpi * 0.02))
    h, w = ink.shape
    n, labels, stats, _ = cv2.connectedComponentsWithStats(ink, connectivity=8)
    out = ink.copy()
    for i in range(1, n):
        x, y, bw, bh, _ = stats[i]
        touches = x <= 1 or y <= 1 or x + bw >= w - 1 or y + bh >= h - 1
        if touches and (bh <= thin or bw <= thin):
            out[labels == i] = 0
    return out


@dataclass
class Rules:
    horizontal: np.ndarray
    vertical: np.ndarray

    @property
    def both(self) -> np.ndarray:
        return cv2.bitwise_or(self.horizontal, self.vertical)


def find_rules(ink: np.ndarray, dpi: float) -> Rules:
    """Long straight horizontal and vertical strokes (table borders, separators)."""
    h_len = max(25, int(dpi * 0.35))
    v_len = max(20, int(dpi * 0.17))
    horizontal = cv2.morphologyEx(ink, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (h_len, 1)))
    vertical = cv2.morphologyEx(ink, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (1, v_len)))
    # A rule is thin. Filled shapes (chart bars, photos) pass the opening too: drop them.
    max_thick = max(3, int(dpi * 0.025))
    horizontal = _thin_only(horizontal, max_thick, axis=0)
    vertical = _thin_only(vertical, max_thick, axis=1)
    # Bridge one-pixel breaks from scanning so a border reads as one stroke.
    horizontal = cv2.dilate(horizontal, cv2.getStructuringElement(cv2.MORPH_RECT, (5, 3)))
    vertical = cv2.dilate(vertical, cv2.getStructuringElement(cv2.MORPH_RECT, (3, 5)))
    return Rules(horizontal, vertical)


def _thin_only(mask: np.ndarray, max_thick: int, axis: int) -> np.ndarray:
    """Keep the parts of `mask` thinner than `max_thick` across the stroke direction."""
    if axis == 0:   # horizontal strokes: measure thickness down each column
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max_thick + 1))
    else:
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max_thick + 1, 1))
    thick = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)       # what survives is too thick
    thick = cv2.dilate(thick, cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)))
    return cv2.bitwise_and(mask, cv2.bitwise_not(thick))


def bitwise_without(mask: np.ndarray, remove: np.ndarray) -> np.ndarray:
    return cv2.bitwise_and(mask, cv2.bitwise_not(remove))


def erase_rules(gray: np.ndarray, rules: Rules) -> np.ndarray:
    """The page without ruling lines, which helps OCR inside table cells."""
    out = gray.copy()
    out[rules.both > 0] = 255
    return out


# ---------------------------------------------------------------- tables


@dataclass
class Cell:
    row: int
    col: int
    rowspan: int
    colspan: int
    box: Box
    text: str = ""
    header: bool = False


@dataclass
class TableGrid:
    box: Box
    rows: list[float]               # y of each horizontal separator, top to bottom
    cols: list[float]               # x of each vertical separator, left to right
    cells: list[Cell] = field(default_factory=list)

    @property
    def shape(self) -> tuple[int, int]:
        return len(self.rows) - 1, len(self.cols) - 1


def find_tables(rules: Rules, dpi: float) -> list[TableGrid]:
    """Bordered tables: grids of crossing horizontal and vertical rules."""
    grid = rules.both
    n, labels, stats, _ = cv2.connectedComponentsWithStats(grid, connectivity=8)
    tables = []
    min_side = dpi * 0.4
    for i in range(1, n):
        x, y, w, h, _ = stats[i]
        if w < min_side or h < dpi * 0.25:
            continue
        sub_h = rules.horizontal[y:y + h, x:x + w]
        sub_v = rules.vertical[y:y + h, x:x + w]
        rows = _separators(sub_h, axis=0, min_cover=0.25, gap=max(4, int(dpi * 0.04)))
        cols = _separators(sub_v, axis=1, min_cover=0.25, gap=max(4, int(dpi * 0.04)))
        if len(rows) < 3 or len(cols) < 2 or (len(rows) - 1) * (len(cols) - 1) < 2:
            continue  # a box or an underline, not a table
        rows = [r + y for r in rows]
        cols = [c + x for c in cols]
        table = TableGrid((cols[0], rows[0], cols[-1], rows[-1]), rows, cols)
        table.cells = _cells(table, rules)
        tables.append(table)
    tables.sort(key=lambda t: (t.box[1], t.box[0]))
    return tables


def _separators(mask: np.ndarray, axis: int, min_cover: float, gap: int) -> list[float]:
    """Positions of rules that span at least `min_cover` of the table."""
    if axis == 0:   # horizontal rules -> y positions
        profile = (mask > 0).sum(axis=1) / max(1, mask.shape[1])
    else:           # vertical rules -> x positions
        profile = (mask > 0).sum(axis=0) / max(1, mask.shape[0])
    idx = np.where(profile >= min_cover)[0]
    if idx.size == 0:
        return []
    groups, start, prev = [], idx[0], idx[0]
    for v in idx[1:]:
        if v - prev > gap:
            groups.append((start + prev) / 2.0)
            start = v
        prev = v
    groups.append((start + prev) / 2.0)
    return groups


def _cells(table: TableGrid, rules: Rules) -> list[Cell]:
    """Grid cells, merging neighbours that have no rule between them."""
    nr, nc = table.shape
    parent = list(range(nr * nc))

    def find(a: int) -> int:
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def join(a: int, b: int) -> None:
        parent[find(a)] = find(b)

    rows, cols = table.rows, table.cols
    for r in range(nr):
        for c in range(nc):
            if c + 1 < nc and not _has_rule(rules.vertical, cols[c + 1], rows[r], rows[r + 1], vertical=True):
                join(r * nc + c, r * nc + c + 1)
            if r + 1 < nr and not _has_rule(rules.horizontal, rows[r + 1], cols[c], cols[c + 1], vertical=False):
                join(r * nc + c, (r + 1) * nc + c)
    groups: dict[int, list[tuple[int, int]]] = {}
    for r in range(nr):
        for c in range(nc):
            groups.setdefault(find(r * nc + c), []).append((r, c))
    cells = []
    for members in groups.values():
        r0 = min(m[0] for m in members)
        r1 = max(m[0] for m in members)
        c0 = min(m[1] for m in members)
        c1 = max(m[1] for m in members)
        if len(members) != (r1 - r0 + 1) * (c1 - c0 + 1):
            # Not a rectangle (a broken rule): fall back to separate cells.
            for r, c in members:
                cells.append(Cell(r, c, 1, 1, (cols[c], rows[r], cols[c + 1], rows[r + 1])))
            continue
        cells.append(Cell(r0, c0, r1 - r0 + 1, c1 - c0 + 1, (cols[c0], rows[r0], cols[c1 + 1], rows[r1 + 1])))
    cells.sort(key=lambda k: (k.row, k.col))
    return cells


def _has_rule(mask: np.ndarray, at: float, start: float, end: float, vertical: bool) -> bool:
    """Is there a rule at `at` covering most of the span start..end?"""
    pad = 4
    a, b = int(start) + pad, int(end) - pad
    if b <= a:
        return True
    p = int(round(at))
    if vertical:
        strip = mask[a:b, max(0, p - 3): p + 4]
        covered = (strip > 0).any(axis=1).mean() if strip.size else 0
    else:
        strip = mask[max(0, p - 3): p + 4, a:b]
        covered = (strip > 0).any(axis=0).mean() if strip.size else 0
    return covered >= 0.6


# ---------------------------------------------------------------- figures


def find_figures(ink: np.ndarray, rules: Rules, text_boxes: list[Box], tables: list[Box], dpi: float,
                 is_text=None) -> list[Box]:
    """Regions of non-text ink big enough to be a picture, chart or photo.

    `is_text(box) -> bool`, when given, gets the last word on each candidate
    (an OCR check that catches headings the first OCR pass was unsure of).
    """
    h, w = ink.shape
    rest = ink.copy()   # chart axes are rules too, and they hold a chart together
    pad = int(dpi * 0.02)
    for x0, y0, x1, y1 in text_boxes:
        rest[max(0, int(y0) - pad): int(y1) + pad, max(0, int(x0) - pad): int(x1) + pad] = 0
    edge = int(dpi * 0.03)  # the outer half of a table's border lies outside its box
    for x0, y0, x1, y1 in tables:
        rest[max(0, int(y0) - edge): int(y1) + edge + 1, max(0, int(x0) - edge): int(x1) + edge + 1] = 0
    # Speckle never forms a figure; join the strokes of one drawing together.
    rest = cv2.morphologyEx(rest, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    no_rules = cv2.bitwise_and(rest, cv2.bitwise_not(rules.both))
    k = max(9, int(dpi * 0.12))
    joined = cv2.dilate(rest, cv2.getStructuringElement(cv2.MORPH_RECT, (k, k)))
    n, _, stats, _ = cv2.connectedComponentsWithStats(joined, connectivity=8)
    min_side = dpi * 0.45
    boxes = []
    for i in range(1, n):
        x, y, bw, bh, _ = stats[i]
        if bw < min_side or bh < min_side:
            continue
        if bw * bh > 0.92 * w * h:
            continue  # the page itself (a dark border from the scanner)
        if (rest[y:y + bh, x:x + bw] > 0).mean() < 0.015:
            continue  # a few stray marks spread over a large area
        if (no_rules[y:y + bh, x:x + bw] > 0).mean() < 0.004:
            continue  # only lines: a frame around text, or a separator
        box = (float(x + k // 2), float(y + k // 2), float(x + bw - k // 2), float(y + bh - k // 2))
        if is_text is not None and is_text(box):
            continue
        boxes.append(box)
    return merge_boxes(boxes, gap=dpi * 0.1)


def merge_boxes(boxes: list[Box], gap: float = 0.0) -> list[Box]:
    boxes = list(boxes)
    changed = True
    while changed:
        changed = False
        out: list[Box] = []
        for b in boxes:
            for i, o in enumerate(out):
                grown = (o[0] - gap, o[1] - gap, o[2] + gap, o[3] + gap)
                if intersection(b, grown) > 0:
                    out[i] = (min(o[0], b[0]), min(o[1], b[1]), max(o[2], b[2]), max(o[3], b[3]))
                    changed = True
                    break
            else:
                out.append(b)
        boxes = out
    return sorted(boxes, key=lambda b: (b[1], b[0]))


def expand_figure(box: Box, ink: np.ndarray, text_boxes: list[Box], dpi: float) -> Box:
    """Grow a figure box to the ink it belongs to (labels drawn inside a chart)."""
    x0, y0, x1, y1 = box
    inside = [t for t in text_boxes if overlap_ratio(t, box) > 0.5]
    for t in inside:
        x0, y0, x1, y1 = min(x0, t[0]), min(y0, t[1]), max(x1, t[2]), max(y1, t[3])
    pad = dpi * 0.03
    h, w = ink.shape
    return (max(0.0, x0 - pad), max(0.0, y0 - pad), min(float(w), x1 + pad), min(float(h), y1 + pad))


# ---------------------------------------------------------------- text lines


def line_bands(gray: np.ndarray, box: Box, dpi: float) -> list[Box]:
    """Visual text lines inside `box`, found from the ink profile.

    Ruling lines are removed first; dots and diacritics that form their own thin
    band are merged into the nearest line.
    """
    x0, y0, x1, y1 = (int(round(v)) for v in box)
    crop = gray[max(0, y0): y1, max(0, x0): x1]
    if crop.size == 0:
        return []
    ink = ink_mask(crop)
    rules = find_rules(ink, dpi)
    ink[rules.both > 0] = 0
    ink = cv2.morphologyEx(ink, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    rows = (ink > 0).sum(axis=1)
    on = rows >= max(2, int(0.004 * crop.shape[1]))
    bands = []
    start = None
    for i, v in enumerate(on):
        if v and start is None:
            start = i
        elif not v and start is not None:
            bands.append([start, i])
            start = None
    if start is not None:
        bands.append([start, len(on)])
    if not bands:
        return []
    heights = sorted(b[1] - b[0] for b in bands)
    typical = heights[len(heights) // 2]
    # Merge slivers (dots, diacritics, underline remains) into their neighbour.
    merged: list[list[int]] = []
    for b in bands:
        if merged and ((b[1] - b[0]) < 0.45 * typical or (merged[-1][1] - merged[-1][0]) < 0.45 * typical) \
                and b[0] - merged[-1][1] < 0.6 * typical:
            merged[-1][1] = b[1]
        else:
            merged.append(b)
    out = []
    for a, b in merged:
        if b - a < max(4, int(dpi * 0.03)):
            continue
        cols = np.where((ink[a:b] > 0).any(axis=0))[0]
        if cols.size == 0:
            continue
        out.append((float(x0 + cols[0]), float(y0 + a), float(x0 + cols[-1] + 1), float(y0 + b)))
    return out


def distribute_text(text: str, bands: list[Box], box: Box) -> list[Line]:
    """Spread a block's words over its visual lines, in proportion to their widths."""
    words = text.split()
    if not words:
        return []
    if not bands:
        return [Line(box, " ".join(words))]
    if len(bands) == 1:
        return [Line(bands[0], " ".join(words))]
    widths = [b[2] - b[0] for b in bands]
    total_w = sum(widths)
    total_c = sum(len(w) + 1 for w in words)
    lines, i = [], 0
    for n, (band, width) in enumerate(zip(bands, widths, strict=True)):
        remaining_bands = len(bands) - n
        if n == len(bands) - 1:
            chunk = words[i:]
        else:
            budget = total_c * width / total_w
            chunk, used = [], 0
            while i < len(words) and (not chunk or used + (len(words[i]) + 1) / 2 <= budget):
                if len(words) - i <= remaining_bands - 1 and chunk:
                    break  # leave at least one word for each later line
                chunk.append(words[i])
                used += len(words[i]) + 1
                i += 1
        if chunk:
            lines.append(Line(band, " ".join(chunk)))
    return lines


def box_area_share(boxes: list[Box], page: Box) -> float:
    return sum(area(b) for b in boxes) / max(1.0, area(page))
