"""Conversion jobs: one worker thread (the GPU model must not be shared), a queue,
progress for the interface, and clean-up of temporary files."""

from __future__ import annotations

import os
import queue
import shutil
import sys
import tempfile
import threading
import time
import traceback
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from .engines.base import EngineError, Options
from .pipeline import Cancelled, JobOutput, convert_job

KEEP_SECONDS = 3600       # finished jobs are deleted an hour after they end
SWEEP_EVERY = 300         # seconds between checks for expired jobs
OWNER_FILE = "owner.pid"  # which running copy of the app a temporary folder belongs to
LEGACY_MAX_AGE = 3600     # folders from versions without an owner file: removed when this old
WORK_FOLDERS = ("_uploads", "_inputs", "_previews")   # deleted as soon as a job ends


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
            remove_stale_folders()
        self.root = Path(root or tempfile.mkdtemp(prefix="hyperocr-"))
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / OWNER_FILE).write_text(str(os.getpid()), encoding="ascii")
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
            try:
                job_id = self.queue.get(timeout=SWEEP_EVERY)
            except queue.Empty:
                with self.lock:
                    self._sweep()   # results nobody came back for go after KEEP_SECONDS
                continue
            job = self.get(job_id)
            if job is None:
                continue
            if job.cancel.is_set():
                self._discard_if_deleted(job)
                continue
            job.state = "running"
            stay_awake(True)
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
                stay_awake(False)
                job.finished = time.time()
                for temp in WORK_FOLDERS:   # originals and page previews are no longer needed
                    shutil.rmtree(job.folder / temp, ignore_errors=True)
                job.preview = ""
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


def stay_awake(on: bool) -> bool:
    """While a conversion runs, Windows must not put the computer to sleep for being left alone:
    a book left converting overnight would stop until someone woke the computer. The screen may
    still turn off, and closing a laptop's lid still puts it to sleep. Applies to the calling
    thread (the worker) until called again with False. True when Windows took the request."""
    if sys.platform != "win32":
        return False
    import ctypes

    es_continuous, es_system_required = 0x80000000, 0x00000001
    call = ctypes.windll.kernel32.SetThreadExecutionState
    call.argtypes, call.restype = [ctypes.c_uint32], ctypes.c_uint32
    return bool(call(es_continuous | (es_system_required if on else 0)))


def remove_stale_folders() -> list[Path]:
    """Folders left by an earlier run that was killed instead of stopped (a closed window,
    a crash). Each run writes its process id into its folder; a folder whose process has
    gone is removed, while a second copy of the app that is still running keeps its own."""
    removed = []
    now = time.time()
    for folder in Path(tempfile.gettempdir()).glob("hyperocr-*"):
        try:
            if not folder.is_dir():
                continue
            owner = folder / OWNER_FILE
            if owner.is_file():
                try:
                    stale = not _alive(int(owner.read_text(encoding="ascii").strip()))
                except ValueError:
                    stale = True
            else:   # made by a version before 1.2, which wrote no owner file
                stale = now - folder.stat().st_mtime > LEGACY_MAX_AGE
            if stale:
                shutil.rmtree(folder, ignore_errors=True)
                removed.append(folder)
        except OSError:
            pass
    return removed


def _alive(pid: int) -> bool:
    """Whether a process with this id is running (when unsure: yes, so nothing is wiped)."""
    if pid <= 0:
        return False
    if pid == os.getpid():
        return True
    if sys.platform == "win32":
        import ctypes

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(0x1000, False, pid)   # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return ctypes.GetLastError() == 5               # access denied: it exists
        try:
            code = ctypes.c_ulong()
            kernel32.GetExitCodeProcess(handle, ctypes.byref(code))
            return code.value == 259                         # STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)          # signal 0 only checks; never used on Windows, where 0 is Ctrl+C
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return True
    return True
