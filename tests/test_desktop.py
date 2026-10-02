"""The desktop app: its window, its closing, its build check. The window library is replaced
by a stand-in that records what the app asks of it, so these run without a screen."""

import json
import sys
import types
import urllib.request

import pytest

from conftest import FIXTURES, needs_tesseract
from hyperocr import desktop


class FakeWindow:
    def __init__(self, title, url, **options):
        self.title, self.url, self.options = title, url, options
        self.events = types.SimpleNamespace(closing=FakeEvent())
        self.asked = []
        self.answer = True
        self.destroyed = False

    def create_confirmation_dialog(self, title, message):
        self.asked.append((title, message))
        return self.answer

    def destroy(self):
        self.destroyed = True


class FakeEvent:
    def __init__(self):
        self.handlers = []

    def __iadd__(self, handler):
        self.handlers.append(handler)
        return self

    def set(self):
        """As pywebview: the window stays open when a handler returns False."""
        return all(h() is not False for h in self.handlers)


@pytest.fixture
def fake_webview(monkeypatch, tmp_path):
    seen = {}
    module = types.ModuleType("webview")
    module.settings = {}

    def create_window(title, url, **options):
        seen["window"] = FakeWindow(title, url, **options)
        return seen["window"]

    def start(**options):
        seen["start"] = options
        with urllib.request.urlopen(seen["window"].url + "api/system", timeout=10) as r:   # the server is up
            seen["system"] = json.loads(r.read())
        seen["closed"] = seen["window"].events.closing.set()

    module.create_window, module.start = create_window, start
    monkeypatch.setitem(sys.modules, "webview", module)
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setattr("hyperocr.offline.lock_down", lambda: None)   # keep the test process online
    # On Windows the app first checks for the Edge engine through pywebview's own module, which the
    # stand-in doesn't have; without this it would open the browser and wait for a click.
    monkeypatch.setattr(desktop, "edge_available", lambda: True)
    return seen


def test_the_app_opens_in_its_own_window_and_stops_with_it(fake_webview, tmp_path):
    assert desktop.main([]) == 0
    window, start = fake_webview["window"], fake_webview["start"]
    assert window.title == "HYPER-OCR" and window.url.startswith("http://127.0.0.1:")
    assert window.options["text_select"] and window.options["zoomable"]
    assert start["private_mode"] is False                       # the interface's choices are kept
    assert start["storage_path"].startswith(str(tmp_path / "data"))
    assert fake_webview["system"]["version"] and fake_webview["closed"]
    with pytest.raises(OSError):                                  # the server stopped with the window
        urllib.request.urlopen(window.url + "api/system", timeout=3)


def test_closing_during_a_conversion_asks_first_in_its_language():
    class Jobs:
        def __init__(self, busy):
            import threading

            self.lock = threading.Lock()
            job = types.SimpleNamespace(state="running" if busy else "done", options=types.SimpleNamespace(ui_lang="ar"))
            self.jobs = {"a": job}

        def busy(self):
            return self.jobs["a"].state == "running"

    window = FakeWindow("HYPER-OCR", "http://127.0.0.1:1/")
    assert desktop.may_close(window, Jobs(busy=False)) and window.asked == []
    window.answer = False
    assert desktop.may_close(window, Jobs(busy=True)) is False          # Cancel keeps it open
    assert window.asked == [desktop.CLOSE_WHILE_BUSY["ar"]]


def test_without_a_window_the_app_opens_in_the_browser(monkeypatch, tmp_path):
    monkeypatch.setattr("hyperocr.offline.lock_down", lambda: None)
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setattr(desktop, "open_window", lambda url, jobs, shown: False)
    opened = []
    monkeypatch.setattr(desktop, "open_in_browser", opened.append)
    assert desktop.main([]) == 0
    assert opened and opened[0].startswith("http://127.0.0.1:")


def test_the_update_helper_runs_through_the_app(monkeypatch, capsys):
    """HYPER-OCR.exe --update is the Update button's helper in the desktop app."""
    calls = []
    monkeypatch.setattr("hyperocr.update.main", lambda argv: calls.append(argv) or 0)
    assert desktop.main(["--update", "--check", "--json"]) == 0
    assert calls == [["--check", "--json"]]


@needs_tesseract
def test_self_test_converts_a_file_and_reports_it(tmp_path):
    assert desktop.main(["--self-test", str(FIXTURES / "scanned_english.pdf"), str(tmp_path), "--lang", "eng"]) == 0
    report = json.loads((tmp_path / "self-test.json").read_text(encoding="utf-8"))
    assert report["available"] and report["pages"] == 2
    assert report["markdown"].startswith("# Effect of Early Mobilisation After Surgery")
