"""HYPER-OCR as a desktop app: the same interface, in its own window.

    HYPER-OCR.exe                        open the app
    HYPER-OCR.exe --update [--check]     the Update button's helper (see update.py)
    HYPER-OCR.exe --self-test FILE OUT   convert FILE into OUT without a window: the build's check

The local server runs inside the app, on 127.0.0.1 only, as in the browser version,
and stops when the window closes; this run's temporary files go with it. The window
is Microsoft Edge WebView2, which Windows 10 and 11 include. Where it is missing, the
app opens in the default browser instead, and a small message keeps it running.
Opening HYPER-OCR while it is already open brings its window forward: one copy runs.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import threading
import time
import urllib.request
from pathlib import Path

from . import __version__
from .paths import user_data

# A fixed address, so the window's remembered choices (kept per address) survive a restart.
# The browser version uses 8765; both can run at once.
PORT = 8766

CLOSE_WHILE_BUSY = {
    "en": ("HYPER-OCR", "A conversion is still running. Close HYPER-OCR and stop it?"),
    "ar": ("HYPER-OCR", "ما زال التحويل جارياً. هل تريد إغلاق HYPER-OCR وإيقافه؟"),
}
NO_WINDOW = (
    "HYPER-OCR is open in your web browser: this computer can't show its own window "
    "(the Microsoft Edge WebView2 Runtime is missing).\n\n"
    "Keep this message open while you use HYPER-OCR. Click OK to close it.\n\n"
    "فُتح HYPER-OCR في متصفح الويب لأن هذا الجهاز لا يستطيع عرض نافذته الخاصة "
    "(Microsoft Edge WebView2 Runtime غير مثبت).\n\n"
    "اترك هذه الرسالة مفتوحة أثناء استخدام HYPER-OCR، واضغط موافق لإغلاقه."
)

log = logging.getLogger("hyperocr.desktop")


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv and bring_forward_running_copy():
        return 0                       # already open: nothing to log, and the open copy's log stays
    _keep_a_log()
    if argv[:1] == ["--update"]:
        from .update import main as update_main

        return update_main(argv[1:])
    if argv[:1] == ["--self-test"]:
        return self_test(argv[1:])
    return run()


LOG_LIMIT = 1_000_000      # bytes: the log starts over once it is this long


def _keep_a_log() -> None:
    """A windowed app has no console: what would be printed goes to a log beside its settings,
    one line per start and its errors, never the text of documents. It starts over at 1 MB."""
    if sys.stdout is not None and sys.stderr is not None:
        return
    try:
        folder = user_data()
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / "hyperocr.log"
        mode = "w" if path.is_file() and path.stat().st_size > LOG_LIMIT else "a"
        stream = open(path, mode, encoding="utf-8", buffering=1)  # noqa: SIM115
        stream.write("--- %s %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), " ".join(sys.argv[1:]) or "start"))
    except OSError:
        stream = open(os.devnull, "w", encoding="utf-8")  # noqa: SIM115
    sys.stdout = sys.stdout or stream
    sys.stderr = sys.stderr or stream
    logging.basicConfig(stream=stream, level=logging.WARNING, format="%(asctime)s %(name)s: %(message)s")


def bring_forward_running_copy(port: int = PORT) -> bool:
    """Is HYPER-OCR already open? Then ask it to bring its window forward; this second start
    ends there. False when nothing answers at its address, or something else does (such as
    the browser version, which has no window to show): then this one starts on another."""
    if sys.platform == "win32":
        import ctypes

        ctypes.windll.user32.AllowSetForegroundWindow(-1)   # an open copy may come to the front
    request = urllib.request.Request("http://127.0.0.1:%d/api/desktop/show" % port, method="POST",
                                     headers={"X-HyperOCR": "1"})
    try:
        with urllib.request.urlopen(request, timeout=5) as r:
            if not json.loads(r.read()).get("ok"):
                return False
    except Exception:  # noqa: BLE001  (nothing there, or not HYPER-OCR's window)
        return False
    print("HYPER-OCR is already open: brought its window forward.", flush=True)
    return True


def run() -> int:
    from .offline import lock_down

    lock_down()  # from here on, this process can only talk to this computer
    from waitress.server import create_server

    from .__main__ import free_port
    from .jobs import JobManager
    from .server import create_app

    jobs = JobManager()
    app = create_app(jobs)
    port = free_port(PORT)
    server = create_server(app, host="127.0.0.1", port=port, threads=8, channel_timeout=600,
                           max_request_body_size=2 * 1024 ** 3)
    threading.Thread(target=server.run, name="hyperocr-server", daemon=True).start()
    url = "http://127.0.0.1:%d/" % port
    print("HYPER-OCR %s (desktop) at %s" % (__version__, url), flush=True)

    shown: dict = {}

    def close_for_update() -> None:
        """The installer has started: close the window so it can replace the app."""
        def close() -> None:
            time.sleep(1.5)                       # let the page show "Restarting HYPER-OCR"
            window = shown.get("window")
            if window is not None:
                window.destroy()
            else:
                jobs.close()
                os._exit(0)
        threading.Thread(target=close, daemon=True).start()

    def show() -> None:
        """Another start of HYPER-OCR asked for this window: un-minimise it and bring it forward."""
        window = shown.get("window")
        if window is None:
            return
        try:
            window.restore()
            window.show()
            window.on_top = True       # raise it above other windows, then let it behave normally
            window.on_top = False
        except Exception:  # noqa: BLE001
            log.exception("could not bring the window forward")

    app.extensions["hyperocr.restart"] = close_for_update
    app.extensions["hyperocr.show"] = show
    note_when_the_interface_runs(app)
    try:
        if not open_window(url, jobs, shown):
            print("No window (WebView2 is missing): opened in the browser instead.", flush=True)
            open_in_browser(url)
    finally:
        server.close()
        jobs.close()
    return 0


def note_when_the_interface_runs(app) -> None:
    """Log once that the interface runs in the window: its script has asked for /api/system
    from the Edge engine (whose requests say "Edg/"). A window that stays blank logs nothing."""
    from flask import request

    seen = threading.Event()

    @app.before_request
    def note():
        if not seen.is_set() and request.path == "/api/system" and "Edg/" in (request.user_agent.string or ""):
            seen.set()
            print("The window shows the interface.", flush=True)


def edge_available() -> bool:
    """Windows: is the Edge WebView2 engine there? (Without it pywebview would fall back to
    Internet Explorer's engine, which can't run this interface.)"""
    if sys.platform != "win32":
        return True
    try:
        from webview.platforms import winforms

        return winforms.renderer == "edgechromium"
    except Exception:  # noqa: BLE001  (no .NET, no pythonnet: no window)
        log.exception("no WebView2 window")
        return False


def open_window(url: str, jobs, shown: dict) -> bool:
    """Show the app in its own window until it is closed. False when no window can be shown."""
    try:
        import webview
    except Exception:  # noqa: BLE001
        log.exception("pywebview is not available")
        return False
    if not edge_available():
        return False
    print("Window: Microsoft Edge WebView2.", flush=True)
    webview.settings["ALLOW_DOWNLOADS"] = True                 # Download buttons ask where to save
    webview.settings["OPEN_EXTERNAL_LINKS_IN_BROWSER"] = True  # GitHub and licence links
    window = webview.create_window(
        "HYPER-OCR", url, width=1120, height=860, min_size=(420, 560),
        background_color="#F2F2F7", text_select=True, zoomable=True,
    )
    shown["window"] = window
    window.events.closing += lambda: may_close(window, jobs)
    storage = user_data() / "window"
    storage.mkdir(parents=True, exist_ok=True)
    try:
        # Not private: the window keeps the interface's choices (language, appearance, engine...).
        webview.start(private_mode=False, storage_path=str(storage))
    except Exception:  # noqa: BLE001
        log.exception("the window could not be shown")
        return False
    return True


def may_close(window, jobs) -> bool:
    """Closing during a conversion asks first, in the language the conversion was started in."""
    if not jobs.busy():
        return True
    title, message = CLOSE_WHILE_BUSY.get(running_language(jobs), CLOSE_WHILE_BUSY["en"])
    return bool(window.create_confirmation_dialog(title, message))


def running_language(jobs) -> str:
    with jobs.lock:
        for job in jobs.jobs.values():
            if job.state in ("queued", "running"):
                return job.options.ui_lang
    return "en"


def open_in_browser(url: str) -> None:
    import webbrowser

    webbrowser.open(url)
    if sys.platform == "win32":
        import ctypes

        ctypes.windll.user32.MessageBoxW(None, NO_WINDOW, "HYPER-OCR", 0x40)   # waits for OK
        return
    print("HYPER-OCR is open in your browser at %s. Press Ctrl+C to stop it." % url, flush=True)
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        pass


def self_test(args: list[str]) -> int:
    """Convert one file with the app's own Tesseract and languages, and write what came out
    to OUT/self-test.json: how the Windows build is checked before it is published."""
    if len(args) < 2:
        print("usage: HYPER-OCR --self-test FILE OUT [--lang eng+ara]", file=sys.stderr)
        return 2
    src, out = Path(args[0]), Path(args[1])
    langs = args[args.index("--lang") + 1].split("+") if "--lang" in args else ["eng"]
    out.mkdir(parents=True, exist_ok=True)
    from .offline import lock_down

    lock_down()
    from . import engines, languages
    from .engines.base import Options
    from .engines.tesseract_engine import find_tesseract, tesseract_version
    from .paths import APP_ROOT, FROZEN
    from .pipeline import convert

    report: dict = {"version": __version__, "frozen": FROZEN, "app_root": str(APP_ROOT),
                    "tesseract": find_tesseract(), "tesseract_version": tesseract_version(),
                    "tessdata": str(languages.folder()), "installed_languages": languages.installed()}
    engine = engines.get("tesseract")
    report["available"] = engine.availability().ok
    code = 1
    try:
        result = convert(src, out, Options(engine="tesseract", languages=langs), lambda _: None)
        report.update(pages=result.pages, zip=str(result.zip_path), markdown=result.markdown,
                      warnings=result.warnings)
        code = 0
    except Exception as exc:  # noqa: BLE001
        report["error"] = "%s: %s" % (type(exc).__name__, exc)
    (out / "self-test.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "markdown"}, ensure_ascii=False), flush=True)
    return code


if __name__ == "__main__":
    sys.exit(main())
