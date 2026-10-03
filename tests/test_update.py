"""The in-app updater, against a local stand-in for GitHub's API."""

import hashlib
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


def _newer_zip(app, version="9.9.0", requirements_extra=""):
    """A release zip as tools/make_release.py builds it: everything inside HYPER-OCR-<version>/."""
    buf = io.BytesIO()
    top = "HYPER-OCR-%s/" % version
    with zipfile.ZipFile(buf, "w") as z:
        for path in sorted(app.rglob("*")):
            rel = path.relative_to(app).as_posix()
            if path.is_dir() or "__pycache__" in rel or rel == "hyperocr/static/icon.svg" \
                    or rel.split("/")[0] in ("models", ".venv", "My scans", ".backup"):
                continue                                    # icon.svg: a file the new version dropped
            data = path.read_bytes()
            if rel == "hyperocr/__init__.py":
                data = data.replace(__version__.encode(), version.encode())
            if rel == "README.md":
                data += b"\nNew in 9.9.0.\n"
            if rel == "requirements.txt":
                data += requirements_extra.encode()
            z.writestr(top + rel, data)
        z.writestr(top + "hyperocr/brand_new.py", "X = 1\n")
        z.writestr(top + "models/should-not-arrive.txt", "no")
    return buf.getvalue()


class FakeGitHub:
    """GitHub's releases API and download server, on this computer."""

    def __init__(self, app):
        self.app = app
        self.release = None          # None: nothing published yet
        self.files = {}
        self.rate_limited = False    # True: answer as GitHub does past 60 calls an hour
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if fake.rate_limited:
                    body = b'{"message": "API rate limit exceeded"}'
                    self.send_response(403)
                    self.send_header("X-RateLimit-Remaining", "0")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return
                if self.path == "/repos/omar-184/HYPER-OCR/releases/latest" and fake.release:
                    body, kind = json.dumps(fake.release).encode(), "application/json"
                else:
                    body, kind = fake.files.get(self.path, (b"", "text/plain"))
                self.send_response(200 if body else 404)
                self.send_header("Content-Type", kind)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.base = "http://127.0.0.1:%d" % self.server.server_port
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def publish(self, version="9.9.0", data=None, checksum=None, **zip_args):
        data = data if data is not None else _newer_zip(self.app, version, **zip_args)
        name = "HYPER-OCR-%s.zip" % version
        checksum = checksum or hashlib.sha256(data).hexdigest()
        self.files = {"/dl/" + name: (data, "application/zip"),
                      "/dl/" + name + ".sha256": (("%s  %s\n" % (checksum, name)).encode(), "text/plain")}
        self.release = {"tag_name": "v" + version, "assets": [
            {"name": name, "browser_download_url": self.base + "/dl/" + name},
            {"name": name + ".sha256", "browser_download_url": self.base + "/dl/" + name + ".sha256"}]}

    def publish_installer(self, version="9.9.0", data=b"MZ stand-in installer", checksum=None):
        """What the release workflow attaches for the desktop app, beside the zip."""
        name = "HYPER-OCR-Setup-%s.exe" % version
        checksum = checksum or hashlib.sha256(data).hexdigest()
        self.files["/dl/" + name] = (data, "application/octet-stream")
        self.files["/dl/" + name + ".sha256"] = (("%s  %s\n" % (checksum, name)).encode(), "text/plain")
        self.release["assets"] += [
            {"name": name, "browser_download_url": self.base + "/dl/" + name},
            {"name": name + ".sha256", "browser_download_url": self.base + "/dl/" + name + ".sha256"}]


@pytest.fixture
def fake_github(tmp_path):
    app = _copy_app(tmp_path / "app")
    (app / "models").mkdir()
    (app / "models" / "weights.bin").write_bytes(b"keep me")
    (app / ".venv").mkdir()
    (app / ".venv" / "marker").write_text("keep me")
    (app / "My scans").mkdir()                                  # a folder of the user's own
    (app / "My scans" / "lab.pdf").write_bytes(b"%PDF mine")
    (app / ".backup" / "0.9.0").mkdir(parents=True)             # an older update's backup
    github = FakeGitHub(app)
    github.publish()
    env = dict(os.environ, HYPEROCR_UPDATE_API=github.base, HYPEROCR_APP_ROOT=str(app),
               NO_PROXY="127.0.0.1,localhost", no_proxy="127.0.0.1,localhost")
    yield app, env, github
    github.server.shutdown()


def _run(app, env, *args):
    out = subprocess.run([sys.executable, "-m", "hyperocr.update", "--json", *args], cwd=app, env=env,
                         capture_output=True, text=True, timeout=120)
    return out, [json.loads(l) for l in out.stdout.splitlines() if l.startswith("{")]


def test_check_reports_the_newer_release(fake_github):
    app, env, github = fake_github
    out, events = _run(app, env, "--check")
    assert out.returncode == 0, out.stderr
    state = events[-1]
    assert (state["current"], state["latest"], state["available"], state["release"]) == (__version__, "9.9.0", True, "v9.9.0")


def test_update_replaces_app_files_and_keeps_everything_else(fake_github):
    app, env, github = fake_github
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
    assert (app / "My scans" / "lab.pdf").read_bytes() == b"%PDF mine"        # the user's folder too
    backup = app / ".backup" / __version__
    assert [p.name for p in (app / ".backup").iterdir()] == [__version__]     # only the last backup is kept
    assert __version__ in (backup / "hyperocr" / "__init__.py").read_text()
    assert (backup / "hyperocr" / "static" / "icon.svg").is_file()
    assert not (backup / "My scans").exists() and not (backup / "models").exists()   # app files only


def test_up_to_date_does_nothing(fake_github):
    app, env, github = fake_github
    _run(app, env, "--yes")
    out, events = _run(app, env, "--yes")                 # now running 9.9.0 itself
    assert events[-1]["step"] == "upToDate"


def test_nothing_is_installed_without_a_published_release(fake_github):
    """A push to a branch, however new, never reaches people: only a release does."""
    app, env, github = fake_github
    github.release = None
    out, events = _run(app, env, "--yes")
    assert out.returncode == 0 and events[-1]["step"] == "upToDate" and events[-1]["available"] is False
    assert __version__ in (app / "hyperocr" / "__init__.py").read_text()


def test_a_download_that_does_not_match_its_checksum_is_refused(fake_github):
    app, env, github = fake_github
    github.publish(checksum="0" * 64)
    out, events = _run(app, env, "--yes")
    assert out.returncode == 1 and events[-1]["step"] == "failed" and "SHA-256" in events[-1]["error"]
    assert __version__ in (app / "hyperocr" / "__init__.py").read_text()
    assert not (app / "hyperocr" / "brand_new.py").exists()


def test_a_failed_package_install_leaves_the_old_version_running(fake_github):
    app, env, github = fake_github
    github.publish(requirements_extra="\nhyperocr-package-that-does-not-exist==0.0.1\n")
    env = dict(env, PIP_NO_INDEX="1")                     # fail fast, offline
    out, events = _run(app, env, "--yes")
    assert out.returncode == 1 and events[-1]["step"] == "failed", events
    assert [e["step"] for e in events] == ["downloading", "unpacking", "packages", "failed"]
    assert __version__ in (app / "hyperocr" / "__init__.py").read_text()     # no file was replaced
    assert not (app / "hyperocr" / "brand_new.py").exists()
    assert "does-not-exist" not in (app / "requirements.txt").read_text()


def test_server_check_endpoint(fake_github, monkeypatch, tmp_path):
    app, env, github = fake_github
    for key in ("HYPEROCR_UPDATE_API", "HYPEROCR_APP_ROOT", "NO_PROXY", "no_proxy"):
        monkeypatch.setenv(key, env[key])
    from hyperocr.jobs import JobManager
    from hyperocr.server import create_app

    client = create_app(JobManager(tmp_path / "jobs")).test_client()
    r = client.post("/api/update/check", headers={"X-HyperOCR": "1"})
    assert r.status_code == 200 and r.get_json()["latest"] == "9.9.0"
    assert client.get("/api/update/status").get_json()["state"] == "idle"


def test_the_desktop_app_updates_through_its_checked_installer(fake_github, tmp_path):
    """HYPER-OCR.exe downloads the release's installer, checks it and starts it (here: everything
    but starting it); its own files are left to the installer."""
    app, env, github = fake_github
    github.publish_installer()
    temp = tmp_path / "temp"
    temp.mkdir()
    env = dict(env, HYPEROCR_UPDATE_KIND="installer", HYPEROCR_UPDATE_DRY_RUN="1", TMPDIR=str(temp), TEMP=str(temp),
               TMP=str(temp))
    out, events = _run(app, env, "--yes")
    assert out.returncode == 0, out.stderr
    assert [e["step"] for e in events] == ["downloading", "installing", "done"]
    setup = events[-1]["installer"]
    assert setup.endswith("HYPER-OCR-Setup-9.9.0.exe") and open(setup, "rb").read() == b"MZ stand-in installer"
    assert __version__ in (app / "hyperocr" / "__init__.py").read_text()      # the installer replaces the app
    _run(app, env, "--yes")
    assert len(list(temp.glob("hyperocr-setup-*"))) == 1                       # only the latest installer is kept

    github.publish(); github.publish_installer(checksum="0" * 64)
    out, events = _run(app, env, "--yes")
    assert out.returncode == 1 and events[-1]["step"] == "failed" and "SHA-256" in events[-1]["error"]


def test_a_release_without_the_installer_is_not_offered_to_the_desktop_app(fake_github):
    app, env, github = fake_github                         # the zip only
    out, events = _run(app, dict(env, HYPEROCR_UPDATE_KIND="installer"), "--check")
    assert out.returncode == 1 and "HYPER-OCR-Setup-9.9.0.exe" in events[-1]["error"]


def test_githubs_rate_limit_gets_its_own_message(fake_github, monkeypatch, tmp_path):
    """Computers behind one hospital connection share GitHub's 60 checks an hour: the app says
    so, instead of blaming the internet connection."""
    app, env, github = fake_github
    github.rate_limited = True
    out, events = _run(app, env, "--check")
    assert out.returncode == 1 and events[-1]["kind"] == "rateLimited" and "rate limit" in events[-1]["error"]
    for key in ("HYPEROCR_UPDATE_API", "HYPEROCR_APP_ROOT", "NO_PROXY", "no_proxy"):
        monkeypatch.setenv(key, env[key])
    from hyperocr.jobs import JobManager
    from hyperocr.server import create_app

    r = create_app(JobManager(tmp_path / "jobs")).test_client().post("/api/update/check", headers={"X-HyperOCR": "1"})
    assert r.status_code == 429 and r.get_json()["error"] == "updateRateLimited"
