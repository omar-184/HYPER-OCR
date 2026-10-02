"""Tesseract is the engine; the experimental GPU engine stays out of the way unless asked for."""

import pytest

from conftest import needs_tesseract
from hyperocr import engines
from hyperocr.engines.base import Availability, EngineError, Options


class FakeReadyGpu:
    """A card that claims it can run Unlimited-OCR (like the GeForce MX130 did)."""

    id = "unlimited"
    name = "Unlimited-OCR"

    def availability(self):
        return Availability(True, detail="NVIDIA GeForce MX130")


@pytest.fixture
def claimed_gpu(monkeypatch):
    monkeypatch.delenv("HYPEROCR_GPU", raising=False)
    engines.get("tesseract")  # build the registry
    monkeypatch.setitem(engines._engines, "unlimited", FakeReadyGpu())


@needs_tesseract
def test_automatic_is_tesseract_even_when_a_gpu_claims_to_be_ready(claimed_gpu):
    engine, passed_over = engines.choose(Options(engine="auto"))
    assert engine.id == "tesseract" and passed_over is None
    assert [e["id"] for e in engines.describe()] == ["tesseract"]


def test_gpu_engines_are_refused_unless_switched_on(claimed_gpu):
    for engine_id in ("unlimited", "unlimited-server"):
        with pytest.raises(EngineError) as err:
            engines.choose(Options(engine=engine_id))
        assert err.value.key == "unknownEngine"


@needs_tesseract
def test_the_interface_offers_only_tesseract(claimed_gpu):
    from hyperocr.server import create_app

    info = create_app().test_client().get("/api/system").get_json()
    assert info["auto"] == "tesseract"
    assert [e["id"] for e in info["engines"]] == ["tesseract"]


def test_setup_never_offers_the_gpu_add_on():
    from conftest import ROOT

    for script in ("setup.sh", "setup-windows.bat"):
        text = (ROOT / script).read_text(encoding="utf-8").lower()
        assert "nvidia" not in text and "torch" not in text and "requirements-gpu" not in text, script


def test_a_rejoined_arabic_line_is_put_back_in_reading_order():
    """Tesseract 5.4.0 read the title's last word as "A" + "Sal]" and put them first, as English.
    Once rejoined, the line is ordered right to left; English runs stay left to right, and a
    number next to Arabic follows the line, as Tesseract itself orders them."""
    from hyperocr.engines.tesseract_engine import TWord, _reorder_lines

    def line(*words, key=(1, 1, 1)):
        return [TWord((x0, 0.0, x1, 10.0), text, 90.0, key, i) for i, (text, x0, x1) in enumerate(words)]

    title = line(("الطبية", 205, 359), ("تقرير", 601, 738), ("المتابعة", 390, 577))
    other = line(("Sal]", 0, 50), ("x", 60, 70), key=(1, 1, 2))
    out = _reorder_lines(title + other, {(1, 1, 1): True, (1, 1, 2): True}, {(1, 1, 1)})
    assert [w.text for w in out] == ["تقرير", "المتابعة", "الطبية", "Sal]", "x"]   # only the named line moves

    drug = line(("الدواء", 500, 560), ("mg", 420, 440), ("5", 400, 410), ("Amlodipine", 300, 390), ("يومياً", 200, 260))
    assert [w.text for w in _reorder_lines(drug, {(1, 1, 1): True}, {(1, 1, 1)})] == \
        ["الدواء", "Amlodipine", "5", "mg", "يومياً"]
    lab = line(("الكرياتينين", 400, 560), ("1.1", 340, 380), ("mg/dL", 260, 330))
    assert [w.text for w in _reorder_lines(lab, {(1, 1, 1): True}, {(1, 1, 1)})] == ["الكرياتينين", "1.1", "mg/dL"]


def test_a_decimal_point_in_a_table_cell_is_not_taken_for_a_speck():
    """At 200 dpi the point of "5.3" is a 3-pixel dot, the size of scanner dust, and was removed
    before Tesseract saw it: every such value came out as "53"."""
    import numpy as np

    from hyperocr.engines.layout_cv import remove_specks

    ink = np.zeros((40, 80), np.uint8)
    ink[10:30, 10:22] = 255          # "5"
    ink[28:30, 26:28] = 255          # "." on the baseline, between the digits
    ink[10:30, 31:43] = 255          # "3"
    ink[3:5, 60:62] = 255            # dust above the line
    ink[28:30, 70:72] = 255          # a dot after the last character: no character on its right
    kept = remove_specks(ink, 200, keep_points=True)
    assert kept[29, 27] == 255                             # the point stays
    assert kept[4, 61] == 0 and kept[29, 71] == 0          # the specks go
    assert remove_specks(ink, 200)[29, 27] == 0            # (outside cells, as before)
