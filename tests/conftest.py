import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
FIXTURES = ROOT / "tests" / "fixtures"


def tesseract_ready() -> bool:
    from hyperocr.engines.tesseract_engine import find_tesseract

    return bool(find_tesseract() or shutil.which("tesseract"))


needs_tesseract = pytest.mark.skipif(not tesseract_ready(), reason="Tesseract is not installed")
