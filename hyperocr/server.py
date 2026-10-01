"""The local web app: serves the interface and a small JSON API on 127.0.0.1."""

from __future__ import annotations

import json
import re
import tempfile
import threading
from pathlib import Path

from flask import Flask, abort, jsonify, request, send_file, send_from_directory

from . import __version__, engines
from .engines.base import Options
from .jobs import JobManager

STATIC = Path(__file__).with_name("static")
LOCAL_HOSTS = {"127.0.0.1", "localhost", "[::1]", "::1"}
CSP = ("default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' blob: data:; "
       "connect-src 'self'; font-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'")


def create_app(jobs: JobManager | None = None) -> Flask:
    app = Flask(__name__, static_folder=None)
    app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 ** 3
    manager = jobs or JobManager()
    app.extensions["hyperocr.jobs"] = manager
    system_cache: dict = {}
    cache_lock = threading.Lock()

    def system_info(refresh: bool = False) -> dict:
        with cache_lock:
            if refresh or not system_cache:
                described = engines.describe()
                tesseract = engines.get("tesseract")
                langs = tesseract.languages() if tesseract.availability().ok else []
                gpu = next((e for e in described if e["id"] == "unlimited"), None)
                auto = "unlimited" if gpu and gpu["ok"] else next(
                    (e["id"] for e in described if e["id"] == "unlimited-server" and e["ok"]), "tesseract")
                system_cache.clear()
                system_cache.update({
                    "version": __version__,
                    "engines": described,
                    "auto": auto,
                    "languages": langs,
                    "defaults": {"languages": [l for l in ("eng", "ara") if l in langs] or langs[:1], "dpi": 300},
                })
            return dict(system_cache)

    # Warm the engine check in the background: importing torch can take seconds.
    threading.Thread(target=system_info, daemon=True).start()

    @app.before_request
    def guard():
        if _hostname(request.host or "") not in LOCAL_HOSTS:
            abort(403)  # only this computer, also against DNS-rebinding pages
        if request.method in ("POST", "PUT", "DELETE") and request.headers.get("X-HyperOCR") != "1":
            abort(403)  # a custom header other websites cannot send without permission

    @app.after_request
    def headers(resp):
        resp.headers["Content-Security-Policy"] = CSP
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["Referrer-Policy"] = "no-referrer"
        resp.headers["Cache-Control"] = "no-store"
        return resp

    @app.get("/")
    def index():
        return send_from_directory(STATIC, "index.html")

    @app.get("/static/<path:name>")
    def static_file(name: str):
        return send_from_directory(STATIC, name)

    @app.get("/api/system")
    def api_system():
        return jsonify(system_info(refresh=request.args.get("refresh") == "1"))

    @app.post("/api/jobs")
    def api_create():
        upload = request.files.get("file")
        if upload is None or not upload.filename:
            return jsonify(error="noFile"), 400
        try:
            raw = json.loads(request.form.get("options") or "{}")
        except ValueError:
            raw = {}
        info = system_info()
        options = _options(raw, info)
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf", dir=manager.root)
        with tmp:
            upload.save(tmp)
        path = Path(tmp.name)
        with path.open("rb") as f:
            head = f.read(1024)
        if b"%PDF-" not in head:
            path.unlink(missing_ok=True)
            return jsonify(error="notPdf"), 400
        name = Path(upload.filename.replace("\\", "/")).name or "document.pdf"
        job = manager.submit(name, path, options)
        return jsonify(job.public()), 201

    @app.get("/api/jobs/<job_id>")
    def api_job(job_id: str):
        return jsonify(_job(manager, job_id).public())

    @app.post("/api/jobs/<job_id>/cancel")
    def api_cancel(job_id: str):
        manager.cancel(_job(manager, job_id).id)
        return jsonify(ok=True)

    @app.delete("/api/jobs/<job_id>")
    def api_delete(job_id: str):
        manager.delete(_job(manager, job_id).id)
        return jsonify(ok=True)

    @app.get("/api/jobs/<job_id>/download")
    def api_zip(job_id: str):
        job = _job(manager, job_id)
        if job.output is None or not job.output.zip_path.is_file():
            abort(404)
        return send_file(job.output.zip_path, as_attachment=True, download_name=job.output.zip_path.name)

    @app.get("/api/jobs/<job_id>/files/<path:rel>")
    def api_file(job_id: str, rel: str):
        job = _job(manager, job_id)
        if job.output is None:
            abort(404)
        base = job.output.folder.resolve()
        target = (base / rel).resolve()
        if base not in target.parents or not target.is_file():
            abort(404)
        return send_file(target, as_attachment=request.args.get("download") == "1", download_name=target.name)

    @app.errorhandler(413)
    def too_big(_):
        return jsonify(error="tooBig"), 413

    return app


def _hostname(host: str) -> str:
    """'127.0.0.1:8765' -> '127.0.0.1'; '[::1]:8765' -> '[::1]'."""
    if host.startswith("["):
        return host.split("]")[0] + "]"
    return host.rsplit(":", 1)[0] if ":" in host else host


def _job(manager: JobManager, job_id: str):
    if not re.fullmatch(r"[0-9a-f]{16}", job_id or ""):
        abort(404)
    job = manager.get(job_id)
    if job is None:
        abort(404)
    return job


def _options(raw: dict, info: dict) -> Options:
    engine = raw.get("engine") if raw.get("engine") in ("auto", "unlimited", "unlimited-server", "tesseract") else "auto"
    langs = [l for l in raw.get("languages") or [] if isinstance(l, str) and l in info["languages"]]
    try:
        dpi = int(raw.get("dpi", 300))
    except (TypeError, ValueError):
        dpi = 300
    return Options(
        engine=engine,
        languages=langs or info["defaults"]["languages"] or ["eng"],
        dpi=dpi if dpi in (200, 300, 400) else 300,
        table_snapshot=bool(raw.get("table_snapshot", True)),
        skip_furniture=bool(raw.get("skip_furniture", True)),
        ui_lang="ar" if raw.get("ui_lang") == "ar" else "en",
    )
