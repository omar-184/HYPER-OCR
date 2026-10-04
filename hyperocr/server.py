"""The local web app: serves the interface and a small JSON API on 127.0.0.1."""

from __future__ import annotations

import json
import re
import subprocess
import sys
import threading
from pathlib import Path

from flask import Flask, abort, jsonify, request, send_file, send_from_directory

from . import __version__, engines, inputs
from .engines.base import OUTPUTS, Options
from .jobs import JobManager
from .paths import APP_ROOT, FROZEN, no_window

STATIC = Path(__file__).with_name("static")
MAX_FILES = 500
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
                # Without HYPEROCR_GPU=1 only Tesseract is described, so Automatic is Tesseract.
                system_cache.clear()
                system_cache.update({
                    "version": __version__,
                    "desktop": FROZEN,          # the installed app: updates come as an installer
                    "engines": described,
                    "auto": auto,
                    "languages": langs,
                    # The languages ticked until someone chooses: the interface language's own.
                    "defaults": {"languages": default_languages(langs, "en"), "dpi": 300,
                                 "languagesByUi": {ui: default_languages(langs, ui) for ui in ("en", "ar")}},
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
        uploads = [f for f in request.files.getlist("file") if f and f.filename]
        if not uploads:
            return jsonify(error="noFile"), 400
        if len(uploads) > MAX_FILES:
            return jsonify(error="tooManyFiles", detail=str(MAX_FILES)), 400
        try:
            raw = json.loads(request.form.get("options") or "{}")
        except ValueError:
            raw = {}
        info = system_info()
        job = manager.create(_options(raw, info), raw.get("mode", "combine"))
        for i, upload in enumerate(uploads):
            name = Path(upload.filename.replace("\\", "/")).name or "file-%d" % (i + 1)
            target = job.folder / "_uploads" / ("%03d%s" % (i + 1, Path(name).suffix.lower()[:8]))
            upload.save(target)
            kind = inputs.detect(target)
            if kind is None:
                manager.discard(job)
                return jsonify(error="notSupported", detail=name), 400
            job.uploads.append(inputs.Upload(name, target, kind))
        manager.start(job)
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
        if job.output is None or rel.split("/", 1)[0] not in job.output_folders():
            abort(404)
        base = job.folder.resolve()
        target = (base / rel).resolve()
        if base not in target.parents or not target.is_file():
            abort(404)
        return send_file(target, as_attachment=request.args.get("download") == "1", download_name=target.name)

    @app.get("/api/jobs/<job_id>/preview/<name>")
    def api_preview(job_id: str, name: str):
        job = _job(manager, job_id)
        if not re.fullmatch(r"\d{3}-\d{4}\.jpg", name):
            abort(404)
        path = job.folder / "_previews" / name
        if not path.is_file():
            abort(404)
        return send_file(path, mimetype="image/jpeg")

    # ------------------------------------------------------------ updates
    # The update runs as its own process (python -m hyperocr.update, or HYPER-OCR.exe
    # --update in the desktop app): this server stays offline. Nothing is checked unless
    # the person asks.
    update_state: dict = {"state": "idle", "events": []}
    update_lock = threading.Lock()

    def updater(*args: str) -> list[str]:
        if FROZEN:
            return [sys.executable, "--update", "--json", *args]
        return [sys.executable, "-m", "hyperocr.update", "--json", *args]

    @app.post("/api/update/check")
    def api_update_check():
        try:
            done = subprocess.run(updater("--check"), cwd=str(APP_ROOT), capture_output=True, text=True, timeout=60,
                                  **no_window())
            lines = [l for l in done.stdout.splitlines() if l.strip().startswith("{")]
            data = json.loads(lines[-1]) if lines else {}
        except (subprocess.TimeoutExpired, ValueError, OSError) as exc:
            return jsonify(error="updateNetwork", detail=str(exc)), 502
        if data.get("kind") == "rateLimited":
            return jsonify(error="updateRateLimited", detail=data.get("error", "")), 429
        if done.returncode != 0 or "available" not in data:
            return jsonify(error="updateNetwork", detail=data.get("error", done.stderr[-300:])), 502
        return jsonify(data)

    @app.post("/api/update/apply")
    def api_update_apply():
        with update_lock:
            if update_state["state"] == "running":
                return jsonify(update_state)
            if manager.busy():
                return jsonify(error="updateBusy"), 409
            update_state.update(state="running", events=[])
        threading.Thread(target=run_update, daemon=True).start()
        return jsonify(update_state)

    def run_update() -> None:
        try:
            proc = subprocess.Popen(updater("--yes"), cwd=str(APP_ROOT), stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, text=True, **no_window())
            for line in proc.stdout:
                try:
                    update_state["events"].append(json.loads(line))
                except ValueError:
                    continue
            proc.wait()
        except OSError as exc:
            update_state["events"].append({"step": "failed", "error": str(exc)})
        last = update_state["events"][-1] if update_state["events"] else {"step": "failed", "error": "no output"}
        if last.get("step") == "done" and last.get("updated"):
            restart = app.extensions.get("hyperocr.restart")
            update_state["state"] = "restarting" if restart else "done"
            if restart:
                restart()
        elif last.get("step") == "upToDate":
            update_state["state"] = "done"
        else:
            update_state["state"] = "failed"

    @app.post("/api/desktop/show")
    def api_desktop_show():
        """The desktop app, opened a second time, asks the open copy to bring its window forward."""
        show = app.extensions.get("hyperocr.show")
        if show is None:
            abort(404)
        show()
        return jsonify(ok=True)

    @app.get("/api/update/status")
    def api_update_status():
        return jsonify(update_state)

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


def default_languages(installed: list[str], ui_lang) -> list[str]:
    """English documents read as English only (Arabic slows them and adds misreads);
    with the Arabic interface, Arabic plus English for the drug names and units."""
    wanted = ("eng", "ara") if ui_lang == "ar" else ("eng",)
    return [l for l in wanted if l in installed] or installed[:1]


def _options(raw: dict, info: dict) -> Options:
    engine = raw.get("engine") if raw.get("engine") in ("auto", "unlimited", "unlimited-server", "tesseract") else "auto"
    langs = [l for l in raw.get("languages") or [] if isinstance(l, str) and l in info["languages"]]
    try:
        dpi = int(raw.get("dpi", 300))
    except (TypeError, ValueError):
        dpi = 300
    return Options(
        engine=engine,
        languages=langs or default_languages(info["languages"], raw.get("ui_lang")) or ["eng"],
        dpi=dpi if dpi in (200, 300, 400) else 300,
        skip_furniture=bool(raw.get("skip_furniture", True)),
        ui_lang="ar" if raw.get("ui_lang") == "ar" else "en",
        own_text=raw.get("own_text", True) is not False,
        outputs=_outputs(raw.get("outputs")),
    )


def _outputs(raw) -> tuple[str, ...]:
    """The files asked for, in the usual order; all of them when none (or nothing valid) is."""
    asked = {o for o in raw if isinstance(o, str)} if isinstance(raw, list) else set()
    return tuple(o for o in OUTPUTS if o in asked) or OUTPUTS
