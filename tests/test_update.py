"""The in-app updater, against a local stand-in for GitHub's API."""

import io
import json
import os
import shutil
import subprocess
import sys
import threading
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from conftest import ROOT
from hyperocr import __version__

APP_FILES = ["hyperocr", "requirements.txt", "requirements-gpu.txt", "README.md", "start.sh"]


def _copy_app(dest):
    dest.mkdir()
    for name in APP_FILES:
        src = ROOT / name
        if src.is_dir():
            shutil.copytree(src, dest / name, ignore=shutil.ignore_patterns("__pycache__"))
        else:
            shutil.copy2(src, dest / name)
    return dest


def _newer_zip(app, version="9.9.0"):
    """GitHub's zipball layout: everything inside owner-repo-sha/."""
    buf = io.BytesIO()
    top = "omar-184-HYPER-OCR-abc1234/"
    with zipfile.ZipFile(buf, "w") as z:
        for path in sorted(app.rglob("*")):
            rel = path.relative_to(app).as_posix()
            if path.is_dir() or "__pycache__" in rel or rel == "hyperocr/static/icon.svg":
                continue                                    # icon.svg: a file the new version dropped
            data = path.read_bytes()
            if rel == "hyperocr/__init__.py":
                data = data.replace(__version__.encode(), version.encode())
            if rel == "README.md":
                data += b"\nNew in 9.9.0.\n"
            z.writestr(top + rel, data)
        z.writestr(top + "hyperocr/brand_new.py", "X = 1\n")
        z.writestr(top + "models/should-not-arrive.txt", "no")
    return buf.getvalue()


@pytest.fixture
def fake_github(tmp_path):
    app = _copy_app(tmp_path / "app")
    (app / "models").mkdir()
    (app / "models" / "weights.bin").write_bytes(b"keep me")
    (app / ".venv").mkdir()
    (app / ".venv" / "marker").write_text("keep me")
    newer = _newer_zip(app)
    init = (app / "hyperocr" / "__init__.py").read_text().replace(__version__, "9.9.0")

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            routes = {
                "/repos/omar-184/HYPER-OCR": (json.dumps({"default_branch": "main"}).encode(), "application/json"),
                "/repos/omar-184/HYPER-OCR/contents/hyperocr/__init__.py?ref=main": (init.encode(), "text/plain"),
                "/repos/omar-184/HYPER-OCR/zipball/main": (newer, "application/zip"),
            }
            body, kind = routes.get(self.path, (b"", ""))
            self.send_response(200 if body else 404)
            self.send_header("Content-Type", kind or "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    env = dict(os.environ, HYPEROCR_UPDATE_API="http://127.0.0.1:%d" % server.server_port,
               HYPEROCR_APP_ROOT=str(app), NO_PROXY="127.0.0.1,localhost", no_proxy="127.0.0.1,localhost")
    yield app, env
    server.shutdown()


def _run(app, env, *args):
    out = subprocess.run([sys.executable, "-m", "hyperocr.update", "--json", *args], cwd=app, env=env,
                         capture_output=True, text=True, timeout=120)
    return out, [json.loads(l) for l in out.stdout.splitlines() if l.startswith("{")]


def test_check_reports_the_newer_version(fake_github):
    app, env = fake_github
    out, events = _run(app, env, "--check")
    assert out.returncode == 0, out.stderr
    assert events[-1] == {"current": __version__, "latest": "9.9.0", "available": True, "branch": "main"}


def test_update_replaces_app_files_and_keeps_everything_else(fake_github):
    app, env = fake_github
    out, events = _run(app, env, "--yes")
    assert out.returncode == 0, out.stderr
    assert [e["step"] for e in events] == ["downloading", "unpacking", "installing", "done"]
    assert events[-1]["updated"] is True and events[-1]["packages"] is False   # same requirements: no reinstall
    assert '"9.9.0"' in (app / "hyperocr" / "__init__.py").read_text()
    assert (app / "hyperocr" / "brand_new.py").is_file()
    assert not (app / "hyperocr" / "static" / "icon.svg").exists()           # removed in the new version
    assert "New in 9.9.0." in (app / "README.md").read_text()
    assert (app / "models" / "weights.bin").read_bytes() == b"keep me"        # the model is untouched
    assert not (app / "models" / "should-not-arrive.txt").exists()
    assert (app / ".venv" / "marker").read_text() == "keep me"
    backup = app / ".backup" / __version__
    assert __version__ in (backup / "hyperocr" / "__init__.py").read_text()
    assert (backup / "hyperocr" / "static" / "icon.svg").is_file()


def test_up_to_date_does_nothing(fake_github):
    app, env = fake_github
    _run(app, env, "--yes")
    out, events = _run(app, env, "--yes")                 # now running 9.9.0 itself
    assert events[-1]["step"] == "upToDate"


def test_server_check_endpoint(fake_github, monkeypatch, tmp_path):
    app, env = fake_github
    for key in ("HYPEROCR_UPDATE_API", "HYPEROCR_APP_ROOT", "NO_PROXY", "no_proxy"):
        monkeypatch.setenv(key, env[key])
    from hyperocr.jobs import JobManager
    from hyperocr.server import create_app

    client = create_app(JobManager(tmp_path / "jobs")).test_client()
    r = client.post("/api/update/check", headers={"X-HyperOCR": "1"})
    assert r.status_code == 200 and r.get_json()["latest"] == "9.9.0"
    assert client.get("/api/update/status").get_json()["state"] == "idle"
