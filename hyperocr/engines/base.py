"""What every OCR engine provides."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import numpy as np

from ..document import PageResult

Progress = Callable[[str], None]   # receives a short stage key, e.g. "loading-model"


@dataclass
class Options:
    engine: str = "auto"                     # auto | unlimited | unlimited-server | tesseract
    languages: list[str] = field(default_factory=lambda: ["eng", "ara"])
    dpi: int = 300
    skip_furniture: bool = True              # leave running headers, footers and page numbers out of Markdown
    ui_lang: str = "en"                      # language for labels inside the Word files


@dataclass
class Availability:
    ok: bool
    reason: str = ""          # a message key for the interface when not ok
    detail: str = ""          # e.g. the GPU name, or the technical error


class EngineError(RuntimeError):
    """A problem the person can act on; `key` names the interface message."""

    def __init__(self, key: str, detail: str = ""):
        super().__init__(detail or key)
        self.key = key
        self.detail = detail


class Engine:
    id = ""
    name = ""

    def availability(self) -> Availability:
        raise NotImplementedError

    def prepare(self, progress: Progress) -> None:
        """Load models before the first page. Called once per job."""

    def process(self, image: np.ndarray, index: int, dpi: float, options: Options) -> PageResult:
        """OCR one page image (RGB, uint8)."""
        raise NotImplementedError

    def pages_at_once(self) -> int:
        """How many pages this engine can read at the same time (each from its own thread)."""
        return 1
