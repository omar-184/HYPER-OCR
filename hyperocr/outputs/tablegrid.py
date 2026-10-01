"""Read an HTML <table> into a grid that knows about merged cells."""

from __future__ import annotations

import html as htmllib
from dataclasses import dataclass, field
from html.parser import HTMLParser


@dataclass
class GridCell:
    text: str
    row: int
    col: int
    rowspan: int = 1
    colspan: int = 1
    header: bool = False


@dataclass
class Grid:
    cells: list[GridCell] = field(default_factory=list)
    rows: int = 0
    cols: int = 0
    rtl: bool = False

    def at(self) -> list[list[GridCell | None]]:
        """rows x cols, each slot pointing at the cell that covers it."""
        slots: list[list[GridCell | None]] = [[None] * self.cols for _ in range(self.rows)]
        for c in self.cells:
            for r in range(c.row, min(self.rows, c.row + c.rowspan)):
                for k in range(c.col, min(self.cols, c.col + c.colspan)):
                    slots[r][k] = c
        return slots


class _TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[list[dict]] = []
        self.cell: dict | None = None
        self.rtl = False
        self.depth = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "table":
            self.depth += 1
            if self.depth == 1 and (a.get("dir") or "").lower() == "rtl":
                self.rtl = True
        elif self.depth != 1:
            return
        elif tag == "tr":
            self.rows.append([])
        elif tag in ("td", "th"):
            if not self.rows:
                self.rows.append([])
            self.cell = {"text": [], "header": tag == "th",
                         "rowspan": _int(a.get("rowspan")), "colspan": _int(a.get("colspan"))}
            self.rows[-1].append(self.cell)
        elif tag == "br" and self.cell is not None:
            self.cell["text"].append("\n")

    def handle_endtag(self, tag):
        if tag == "table":
            self.depth -= 1
        elif tag in ("td", "th") and self.depth == 1:
            self.cell = None

    def handle_data(self, data):
        if self.cell is not None:
            self.cell["text"].append(data)


def _int(v) -> int:
    try:
        return max(1, min(int(v), 1000))
    except (TypeError, ValueError):
        return 1


def parse_table(table_html: str) -> Grid:
    p = _TableParser()
    p.feed(table_html)
    p.close()
    grid = Grid(rtl=p.rtl)
    taken: set[tuple[int, int]] = set()
    for r, row in enumerate(p.rows):
        c = 0
        for cell in row:
            while (r, c) in taken:
                c += 1
            raw = "".join(cell["text"]).replace("\xa0", " ")
            text = "\n".join(" ".join(line.split()) for line in raw.split("\n")).strip()
            gc = GridCell(text, r, c, cell["rowspan"], cell["colspan"], cell["header"])
            grid.cells.append(gc)
            for rr in range(r, r + gc.rowspan):
                for cc in range(c, c + gc.colspan):
                    taken.add((rr, cc))
            c += gc.colspan
    grid.rows = max([r for r, _ in taken], default=-1) + 1
    grid.rows = max(grid.rows, len(p.rows))
    grid.cols = max([c for _, c in taken], default=-1) + 1
    return grid


def flat_html(table_html: str, pipe_token: str) -> str:
    """A span-free copy for Markdown: a merged cell's text is repeated down its
    rows (so each row stands alone) and left blank across its extra columns.
    The first row becomes the header row. `|` is swapped for `pipe_token`."""
    grid = parse_table(table_html)
    if not grid.rows or not grid.cols:
        return ""
    slots = grid.at()
    out = ['<table dir="rtl">' if grid.rtl else "<table>"]
    for r in range(grid.rows):
        tag = "th" if r == 0 else "td"
        cells = []
        for k in range(grid.cols):
            cell = slots[r][k]
            text = ""
            if cell is not None and k == cell.col:
                text = cell.text.replace("\n", " ").replace("|", pipe_token)
            cells.append("<%s>%s</%s>" % (tag, htmllib.escape(text), tag))
        out.append("<tr>" + "".join(cells) + "</tr>")
    out.append("</table>")
    return "".join(out)
