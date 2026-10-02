"""Start HYPER-OCR:  python -m hyperocr  [--port 8765] [--no-browser]"""

from __future__ import annotations

import argparse
import os
import socket
import sys
import threading
import time
import webbrowser

from . import __version__

RESTART = 3   # exit code that tells the start script to start the app again (after an update)


def free_port(preferred: int) -> int:
    for port in [preferred] + list(range(preferred + 1, preferred + 50)):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main(argv: list[str] | None = None) -> int:
    """Run the app, starting it again whenever it exits to finish an update."""
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--serve" in argv:
        serve_app([a for a in argv if a != "--serve"])
        return 0
    import subprocess

    env = dict(os.environ)
    while True:
        try:
            code = subprocess.call([sys.executable, "-m", "hyperocr", "--serve", *argv], env=env)
        except KeyboardInterrupt:
            return 0
        if code != RESTART:
            return code
        print("Restarting HYPER-OCR to finish the update ...")
        env["HYPEROCR_NO_BROWSER"] = "1"   # the open page reloads by itself


def serve_app(argv: list[str]) -> None:
    parser = argparse.ArgumentParser(prog="hyperocr", description="Offline scanned-PDF converter.")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true", help="do not open the browser")
    args = parser.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass

    from .offline import lock_down

    lock_down()  # from here on, this process can only talk to this computer
    from waitress import serve

    from .jobs import JobManager
    from .server import create_app

    port = free_port(args.port)
    url = "http://127.0.0.1:%d/" % port
    jobs = JobManager()
    app = create_app(jobs)

    def restart() -> None:
        def stop() -> None:
            time.sleep(1.5)               # let the page receive "restarting"
            jobs.close()
            os._exit(RESTART)
        threading.Thread(target=stop, daemon=True).start()

    app.extensions["hyperocr.restart"] = restart
    print("HYPER-OCR %s is running at %s" % (__version__, url))
    print("Everything stays on this computer. Close this window to stop it.")
    if not args.no_browser and not os.environ.get("HYPEROCR_NO_BROWSER"):
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        serve(app, host="127.0.0.1", port=port, threads=8, channel_timeout=600, max_request_body_size=2 * 1024 ** 3,
              _quiet=True)
    finally:
        jobs.close()


if __name__ == "__main__":
    sys.exit(main())
