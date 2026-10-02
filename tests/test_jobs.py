"""Temporary files go when the README says they do."""

import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

from conftest import ROOT
from hyperocr import jobs
from hyperocr.engines.base import Options


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _start_app(tmp: Path) -> tuple[subprocess.Popen, Path]:
    """A real copy of the app, with its temporary folder under `tmp`."""
    env = dict(os.environ, TMPDIR=str(tmp), TEMP=str(tmp), TMP=str(tmp), HYPEROCR_NO_BROWSER="1")
    before = set(tmp.glob("hyperocr-*"))
    proc = subprocess.Popen([sys.executable, "-m", "hyperocr", "--serve", "--port", str(_free_port())],
                            cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(200):
        new = [p for p in set(tmp.glob("hyperocr-*")) - before if (p / jobs.OWNER_FILE).is_file()]
        if new:
            return proc, new[0]
        time.sleep(0.05)
    proc.kill()
    raise AssertionError("the app did not create its temporary folder")


def test_a_killed_run_leaves_nothing_behind_and_a_running_copy_is_untouched(tmp_path, monkeypatch):
    running, kept = _start_app(tmp_path)
    killed, left = _start_app(tmp_path)
    try:
        killed.kill()                       # like closing the window or a crash: no clean-up runs
        killed.wait(10)
        (left / "job" / "result.pdf").parent.mkdir()
        (left / "job" / "result.pdf").write_bytes(b"%PDF")
        monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
        removed = jobs.remove_stale_folders()     # what the next start does
        assert left in removed and not left.exists()
        assert kept.exists() and kept not in removed
    finally:
        running.kill()
        running.wait(10)


def test_folders_from_older_versions_are_removed_after_an_hour(tmp_path, monkeypatch):
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    old, recent = tmp_path / "hyperocr-old", tmp_path / "hyperocr-recent"
    old.mkdir()
    recent.mkdir()
    an_hour_ago = time.time() - jobs.LEGACY_MAX_AGE - 60
    os.utime(old, (an_hour_ago, an_hour_ago))
    jobs.remove_stale_folders()
    assert not old.exists() and recent.exists()


def test_results_nobody_came_back_for_are_deleted_after_an_hour(tmp_path):
    manager = jobs.JobManager(root=tmp_path / "root")
    try:
        job = manager.create(Options())
        job.state, job.finished = "done", time.time() - jobs.KEEP_SECONDS - 1
        fresh = manager.create(Options())
        fresh.state, fresh.finished = "done", time.time()
        manager.jobs.update({job.id: job, fresh.id: fresh})
        manager._sweep()
        assert not job.folder.exists() and manager.get(job.id) is None
        assert fresh.folder.exists() and manager.get(fresh.id) is fresh
    finally:
        manager.close()


@pytest.mark.parametrize("name", ["_previews.pdf", "_uploads.pdf", "_inputs.pdf"])
def test_a_file_named_like_a_working_folder_keeps_its_results(name):
    from hyperocr.pipeline import safe_stem

    assert not safe_stem(name).startswith("_") and safe_stem(name) not in jobs.WORK_FOLDERS
