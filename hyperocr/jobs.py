"""Conversion jobs: one worker thread (the GPU model must not be shared), a queue,
progress for the interface, and clean-up of temporary files."""

from __future__ import annotations

import queue
import shutil
import tempfile
import threading
import time
import traceback
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from .engines.base import EngineError, Options
from .pipeline import Cancelled, Output, convert

KEEP_SECONDS = 6 * 3600   # finished jobs are deleted after six hours


@dataclass
class Job:
    id: str
    name: str
    folder: Path
    pdf: Path
    options: Options
    state: str = "queued"          # queued | running | done | failed | cancelled
    stage: str = "queued"
    page: int = 0
    pages: int = 0
    error: str = ""
    detail: str = ""
    output: Output | None = None
    created: float = field(default_factory=time.time)
    finished: float = 0.0
    deleted: bool = False
    cancel: threading.Event = field(default_factory=threading.Event)

    def public(self) -> dict:
        data = {
            "id": self.id, "name": self.name, "state": self.state, "stage": self.stage,
            "page": self.page, "pages": self.pages, "error": self.error, "detail": self.detail,
        }
        out = self.output
        if out is not None:
            data["result"] = {
                "title": out.title, "engine": out.engine, "pages": out.pages, "words": out.words,
                "images": out.images, "tables": out.tables, "warnings": out.warnings,
                "pdf": out.pdf_file, "markdown_file": out.md_file, "zip": out.zip_path.name,
                "markdown": out.markdown[:60000], "markdown_truncated": len(out.markdown) > 60000,
                "seconds": out.seconds,
            }
        return data


class JobManager:
    def __init__(self, root: Path | None = None) -> None:
        if root is None:
            _remove_stale_folders()
        self.root = Path(root or tempfile.mkdtemp(prefix="hyperocr-"))
        self.root.mkdir(parents=True, exist_ok=True)
        self.jobs: dict[str, Job] = {}
        self.lock = threading.Lock()
        self.queue: queue.Queue[str] = queue.Queue()
        self.worker = threading.Thread(target=self._run, name="hyperocr-worker", daemon=True)
        self.worker.start()

    def submit(self, name: str, data_path: Path, options: Options) -> Job:
        job_id = uuid.uuid4().hex[:16]
        folder = self.root / job_id
        folder.mkdir(parents=True)
        pdf = folder / "input.pdf"
        shutil.move(str(data_path), pdf)
        job = Job(job_id, name, folder, pdf, options)
        with self.lock:
            self._sweep()
            self.jobs[job_id] = job
        self.queue.put(job_id)
        return job

    def get(self, job_id: str) -> Job | None:
        with self.lock:
            return self.jobs.get(job_id)

    def cancel(self, job_id: str) -> None:
        job = self.get(job_id)
        if job:
            job.cancel.set()
            if job.state == "queued":
                job.state, job.stage = "cancelled", "cancelled"

    def delete(self, job_id: str) -> None:
        job = self.get(job_id)
        if not job:
            return
        job.cancel.set()
        job.deleted = True
        if job.state in ("queued", "running"):
            return  # the worker removes it when it stops
        with self.lock:
            self.jobs.pop(job_id, None)
        shutil.rmtree(job.folder, ignore_errors=True)

    def close(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    # ------------------------------------------------------------ worker

    def _run(self) -> None:
        while True:
            job_id = self.queue.get()
            job = self.get(job_id)
            if job is None:
                continue
            if job.cancel.is_set():
                self._discard_if_deleted(job)
                continue
            job.state = "running"
            try:
                job.output = convert(job.pdf, job.folder, job.options, lambda d, j=job: self._report(j, d),
                                     job.cancel, original_name=job.name)
                job.state, job.stage = "done", "done"
            except Cancelled:
                job.state, job.stage = "cancelled", "cancelled"
            except EngineError as exc:
                job.state, job.error, job.detail = "failed", exc.key, exc.detail
            except MemoryError:
                job.state, job.error = "failed", "outOfMemory"
            except Exception as exc:  # report, never crash the worker
                job.state, job.error = "failed", "unexpected"
                job.detail = "%s: %s" % (type(exc).__name__, exc)
                traceback.print_exc()
            finally:
                job.finished = time.time()
                try:
                    job.pdf.unlink(missing_ok=True)   # the upload is no longer needed
                except OSError:
                    pass
                self._discard_if_deleted(job)

    def _discard_if_deleted(self, job: Job) -> None:
        if job.deleted:
            with self.lock:
                self.jobs.pop(job.id, None)
            shutil.rmtree(job.folder, ignore_errors=True)

    @staticmethod
    def _report(job: Job, data: dict) -> None:
        job.stage = data.get("stage", job.stage)
        if "page" in data:
            job.page = data["page"]
        if "pages" in data:
            job.pages = data["pages"]

    def _sweep(self) -> None:
        now = time.time()
        for job_id, job in list(self.jobs.items()):
            if job.finished and now - job.finished > KEEP_SECONDS:
                self.jobs.pop(job_id, None)
                shutil.rmtree(job.folder, ignore_errors=True)


def _remove_stale_folders(max_age: float = 24 * 3600) -> None:
    """Folders left by an earlier run that was closed without stopping cleanly."""
    now = time.time()
    for folder in Path(tempfile.gettempdir()).glob("hyperocr-*"):
        try:
            if folder.is_dir() and now - folder.stat().st_mtime > max_age:
                shutil.rmtree(folder, ignore_errors=True)
        except OSError:
            pass
