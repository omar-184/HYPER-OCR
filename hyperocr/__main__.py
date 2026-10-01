"""Start HYPER-OCR:  python -m hyperocr  [--port 8765] [--no-browser]"""

from __future__ import annotations

import argparse
import socket
import sys
import threading
import webbrowser

from . import __version__


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


def main(argv: list[str] | None = None) -> None:
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
    print("HYPER-OCR %s is running at %s" % (__version__, url))
    print("Everything stays on this computer. Close this window to stop it.")
    if not args.no_browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        serve(app, host="127.0.0.1", port=port, threads=8, channel_timeout=600, max_request_body_size=2 * 1024 ** 3,
              _quiet=True)
    finally:
        jobs.close()


if __name__ == "__main__":
    main()
