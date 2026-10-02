"""The local web API."""

import io
import time

import pytest

from conftest import FIXTURES, needs_tesseract
from hyperocr.jobs import JobManager
from hyperocr.server import create_app

HEADERS = {"X-HyperOCR": "1"}


@pytest.fixture
def client(tmp_path):
    app = create_app(JobManager(tmp_path))
    app.testing = True
    return app.test_client()


def test_index_and_security_headers(client):
    r = client.get("/")
    assert r.status_code == 200 and b"HYPER-OCR" in r.data
    assert "default-src 'none'" in r.headers["Content-Security-Policy"]
    assert "connect-src 'self'" in r.headers["Content-Security-Policy"]


def test_other_hosts_are_refused(client):
    assert client.get("/api/system", headers={"Host": "evil.example"}).status_code == 403
    assert client.get("/api/system", headers={"Host": "localhost:8765"}).status_code == 200


def test_writes_need_the_app_header(client):
    data = {"file": (open(FIXTURES / "scanned_english.pdf", "rb"), "a.pdf")}
    assert client.post("/api/jobs", data=data).status_code == 403


def test_rejects_files_that_are_neither_pdf_nor_picture(client):
    data = {"file": (io.BytesIO(b"hello"), "notes.pdf")}
    r = client.post("/api/jobs", data=data, headers=HEADERS)
    assert r.status_code == 400 and r.get_json() == {"error": "notSupported", "detail": "notes.pdf"}


def test_unknown_job_and_bad_ids(client):
    assert client.get("/api/jobs/0123456789abcdef").status_code == 404
    assert client.get("/api/jobs/../../etc").status_code == 404


@needs_tesseract
def test_full_job(client):
    with open(FIXTURES / "scanned_english.pdf", "rb") as f:
        data = {"file": (f, "My scan.pdf"), "options": '{"engine": "tesseract", "languages": ["eng"], "ui_lang": "en"}'}
        r = client.post("/api/jobs", data=data, headers=HEADERS)
    assert r.status_code == 201
    job_id = r.get_json()["id"]
    for _ in range(600):
        job = client.get("/api/jobs/" + job_id).get_json()
        if job["state"] in ("done", "failed"):
            break
        time.sleep(0.2)
    assert job["state"] == "done", job
    res = job["result"]
    doc = res["documents"][0]
    assert res["totals"]["pages"] == 2 and res["zip"] == "My scan_HYPER-OCR.zip"
    assert doc["pdf"] == "My scan/My scan_searchable.pdf" and len(doc["images"]) == 2
    z = client.get("/api/jobs/%s/download" % job_id)
    assert z.status_code == 200 and z.data[:2] == b"PK"
    img = client.get("/api/jobs/%s/files/%s" % (job_id, doc["images"][0]))
    assert img.status_code == 200 and img.data[:4] == b"\x89PNG"
    # Originals and page previews go as soon as the job ends.
    folder = client.application.extensions["hyperocr.jobs"].get(job_id).folder
    assert job["preview"] == "" and not any((folder / w).exists() for w in ("_uploads", "_inputs", "_previews"))
    assert client.get("/api/jobs/%s/files/../input.pdf" % job_id).status_code == 404
    assert client.get("/api/jobs/%s/files/_previews/001-0001.jpg" % job_id).status_code == 404
    assert client.get("/api/jobs/%s/files/%%2e%%2e/%%2e%%2e/x" % job_id).status_code == 404
    assert client.delete("/api/jobs/" + job_id, headers=HEADERS).status_code == 200
    assert client.get("/api/jobs/" + job_id).status_code == 404


@needs_tesseract
def test_several_pictures_each_on_its_own(client, tmp_path):
    from test_inputs import page_photo

    files = [(io.BytesIO(page_photo(0, "JPEG")), "IMG_1.jpg"), (io.BytesIO(page_photo(1, "PNG")), "IMG_2.png")]
    data = {"file": files, "options": '{"engine": "tesseract", "languages": ["eng"], "mode": "separate"}'}
    r = client.post("/api/jobs", data=data, headers=HEADERS)
    assert r.status_code == 201, r.get_json()
    job_id = r.get_json()["id"]
    for _ in range(600):
        job = client.get("/api/jobs/" + job_id).get_json()
        if job["state"] in ("done", "failed"):
            break
        time.sleep(0.2)
    assert job["state"] == "done", job
    assert [d["folder"] for d in job["result"]["documents"]] == ["IMG_1", "IMG_2"]
    assert job["result"]["zip"] == "HYPER-OCR_2-documents.zip"
