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
from .pipeline import Cancelled, JobOutput, convert_job

KEEP_SECONDS = 6 * 3600   # finished jobs are deleted after six hours


@dataclass
class Job:
    id: str
    folder: Path
    options: Options
    mode: str = "combine"          # combine | separate (several files only)
    uploads: list = field(default_factory=list)
    state: str = "queued"          # queued | running | done | failed | cancelled
    stage: str = "queued"
    page: int = 0
    pages: int = 0
    doc: int = 0
    docs: int = 0
    doc_name: str = ""
    doc_page: int = 0
    doc_pages: int = 0
    preview: str = ""
    error: str = ""
    detail: str = ""
    output: JobOutput | None = None
    created: float = field(default_factory=time.time)
    finished: float = 0.0
    deleted: bool = False
    cancel: threading.Event = field(default_factory=threading.Event)

    @property
    def name(self) -> str:
        return self.uploads[0].name if len(self.uploads) == 1 else "%d files" % len(self.uploads)

    def public(self) -> dict:
        data = {
            "id": self.id, "name": self.name, "files": len(self.uploads), "mode": self.mode,
            "state": self.state, "stage": self.stage, "page": self.page, "pages": self.pages,
            "doc": self.doc, "docs": self.docs, "doc_name": self.doc_name,
            "doc_page": self.doc_page, "doc_pages": self.doc_pages,
            "preview": ("/api/jobs/%s/preview/%s" % (self.id, self.preview)) if self.preview else "",
            "error": self.error, "detail": self.detail,
        }
        out = self.output
        if out is not None:
            docs = []
            for o in out.documents:
                prefix = o.folder.name + "/"
                docs.append({
                    "name": o.name, "title": o.title, "folder": o.folder.name, "pages": o.pages, "words": o.words,
                    "images": [prefix + p for p in o.images],
                    "tables": [dict(t, file=prefix + t["file"]) for t in o.tables],
                    "warnings": o.warnings, "pdf": prefix + o.pdf_file, "markdown_file": prefix + o.md_file,
                    "markdown": o.markdown[:60000], "markdown_truncated": len(o.markdown) > 60000,
                })
            data["result"] = {
                "engine": out.engine, "seconds": out.seconds, "zip": out.zip_path.name, "warnings": out.warnings,
                "documents": docs,
                "totals": {k: sum(len(d[k]) if isinstance(d[k], list) else d[k] for d in docs)
                           for k in ("pages", "words", "images", "tables")},
            }
        return data

    def output_folders(self) -> set[str]:
        return {o.folder.name for o in self.output.documents} if self.output else set()


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

    def create(self, options: Options, mode: str = "combine") -> Job:
        """A new job with its own folder; add uploads to it, then `start` it."""
        job_id = uuid.uuid4().hex[:16]
        folder = self.root / job_id
        (folder / "_uploads").mkdir(parents=True)
        return Job(job_id, folder, options, mode if mode in ("combine", "separate") else "combine")

    def start(self, job: Job) -> Job:
        with self.lock:
            self._sweep()
            self.jobs[job.id] = job
        self.queue.put(job.id)
        return job

    def discard(self, job: Job) -> None:
        shutil.rmtree(job.folder, ignore_errors=True)

    def submit(self, name: str, data_path: Path, options: Options) -> Job:
        """One PDF already saved on disk (kept for scripts and tests)."""
        from .inputs import Upload

        job = self.create(options)
        target = job.folder / "_uploads" / "001.pdf"
        shutil.move(str(data_path), target)
        job.uploads.append(Upload(name, target, "pdf"))
        return self.start(job)

    def busy(self) -> bool:
        with self.lock:
            return any(j.state in ("queued", "running") for j in self.jobs.values())

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
                job.output = convert_job(job.uploads, job.mode, job.folder, job.options,
                                         lambda d, j=job: self._report(j, d), job.cancel)
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
                for temp in ("_uploads", "_inputs"):   # the originals are no longer needed
                    shutil.rmtree(job.folder / temp, ignore_errors=True)
                self._discard_if_deleted(job)

    def _discard_if_deleted(self, job: Job) -> None:
        if job.deleted:
            with self.lock:
                self.jobs.pop(job.id, None)
            shutil.rmtree(job.folder, ignore_errors=True)

    @staticmethod
    def _report(job: Job, data: dict) -> None:
        job.stage = data.get("stage", job.stage)
        for key in ("page", "pages", "doc", "docs", "doc_page", "doc_pages", "preview"):
            if key in data:
                setattr(job, key, data[key])
        if "name" in data:
            job.doc_name = data["name"]

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
