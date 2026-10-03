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
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))     # the window's settings: Linux,
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "data"))      # Windows
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
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "data"))
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


def test_opening_it_again_brings_the_open_window_forward(monkeypatch, tmp_path):
    """One copy runs: a second start asks the open one to show its window, and ends."""
    import threading

    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "data"))
    monkeypatch.setattr("hyperocr.offline.lock_down", lambda: None)
    monkeypatch.setattr(desktop, "edge_available", lambda: True)
    started, release, windows = threading.Event(), threading.Event(), []

    class Window(FakeWindow):
        def __init__(self, *args, **options):
            super().__init__(*args, **options)
            self.calls = []

        def restore(self):
            self.calls.append("restore")

        def show(self):
            self.calls.append("show")

    module = types.ModuleType("webview")
    module.settings = {}
    module.create_window = lambda title, url, **options: windows.append(Window(title, url, **options)) or windows[-1]

    def start(**options):
        started.set()
        release.wait(30)

    module.start = start
    monkeypatch.setitem(sys.modules, "webview", module)
    # Something else holds the usual address, so the open copy runs on another: the second start
    # must find it there all the same (on GitHub's Linux runner it once had to).
    import socket

    taken = socket.socket()
    if sys.platform != "win32":
        taken.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)   # even if an earlier test just closed it
    try:
        taken.bind(("127.0.0.1", desktop.PORT))
        taken.listen(1)
        holding = True
    except OSError:
        holding = False                                 # something else holds it: the same situation
    first = threading.Thread(target=desktop.main, args=([],), daemon=True)
    first.start()
    assert started.wait(30)
    try:
        assert desktop.main([]) == 0                    # the second start ends at once...
        assert len(windows) == 1                        # ...without a window of its own
        assert windows[0].calls == ["restore", "show"]  # and the first one came forward
        if holding:
            assert "127.0.0.1:%d/" % desktop.PORT not in windows[0].url
    finally:
        release.set()
        first.join(30)
        taken.close()


def test_the_windowed_app_keeps_a_log_across_starts(monkeypatch, tmp_path):
    """A window app has no console: its output goes to a log, which a later start adds to rather
    than replaces (a second start used to wipe the open copy's log)."""
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "data"))
    for run in ("first", "second"):
        monkeypatch.setattr(sys, "stdout", None)
        monkeypatch.setattr(sys, "stderr", None)
        desktop._keep_a_log()
        print("this is the %s start" % run)
        sys.stdout.close()
    log = next((tmp_path / "data").rglob("hyperocr.log")).read_text(encoding="utf-8")
    assert "this is the first start" in log and "this is the second start" in log
    assert log.count("--- ") == 2


def test_the_log_says_when_the_window_shows_the_interface(tmp_path, capsys):
    """Once, when the page's script calls home from the Edge engine; not for other callers."""
    from hyperocr.jobs import JobManager
    from hyperocr.server import create_app

    app = create_app(JobManager(tmp_path / "jobs"))
    desktop.note_when_the_interface_runs(app)
    client = app.test_client()
    client.get("/api/system", headers={"User-Agent": "Mozilla/5.0 WindowsPowerShell/5.1"})
    assert "shows the interface" not in capsys.readouterr().out
    edge = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0) AppleWebKit/537.36 Chrome/140.0 Safari/537.36 Edg/140.0"}
    client.get("/api/system", headers=edge)
    client.get("/api/system", headers=edge)
    assert capsys.readouterr().out.count("The window shows the interface.") == 1


def test_the_window_fits_a_small_screen():
    """On a 1366 x 768 laptop (728 above the taskbar) the window must not be taller than the screen."""
    def screens(width, height, free_height):
        return types.SimpleNamespace(screens=[types.SimpleNamespace(
            width=width, height=height, frame=types.SimpleNamespace(Width=width, Height=free_height))])

    assert desktop.window_size(screens(1920, 1080, 1040)) == desktop.SIZE
    assert desktop.window_size(screens(1366, 768, 728)) == (1120, 688)
    assert desktop.window_size(screens(1024, 768, 728)) == (984, 688)
    assert desktop.window_size(types.SimpleNamespace()) == desktop.SIZE         # no screen information
