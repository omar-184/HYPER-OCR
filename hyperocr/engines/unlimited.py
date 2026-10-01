"""GPU engine: Baidu Unlimited-OCR (https://github.com/baidu/Unlimited-OCR).

Two ways to run the same model, both entirely on this computer:

* "unlimited": Hugging Face transformers in this process, on an NVIDIA GPU.
  The weights live in ./models/Unlimited-OCR (download once with
  `python -m hyperocr.download_model`); nothing is fetched at run time.
* "unlimited-server": a local vLLM or SGLang server started from Baidu's
  official recipe (Linux), reached at HYPEROCR_OCR_SERVER, for example
  http://127.0.0.1:10000. Only localhost addresses are accepted.

The model answers with blocks tagged by type and box (see detparse.py). It
does not report line positions, so the text layer finds each block's lines
from the page image and spreads the block's words over them.
"""

from __future__ import annotations

import base64
import contextlib
import inspect
import io
import json
import os
import tempfile
import threading
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import cv2
import numpy as np

from ..document import CAPTION, FOOTER, HEADER, HEADING, PAGE_NUMBER, TABLE, TEXT, TITLE, PageResult
from . import detparse
from . import layout_cv as cv
from .base import Availability, Engine, EngineError, Options, Progress

MODEL_ID = "baidu/Unlimited-OCR"
PROMPT = "<image>document parsing."
ROOT = Path(__file__).resolve().parents[2]
TEXT_KINDS = {TITLE, HEADING, TEXT, CAPTION, HEADER, FOOTER, PAGE_NUMBER}


def model_dir() -> Path:
    return Path(os.environ.get("HYPEROCR_MODEL_DIR", ROOT / "models" / "Unlimited-OCR"))


def model_present(path: Path | None = None) -> bool:
    path = path or model_dir()
    return (path / "config.json").is_file() and any(path.glob("*.safetensors"))


def page_lines(result: PageResult, image: np.ndarray) -> None:
    """Fill `result.lines` from the blocks: real line positions, block text."""
    gray = cv.to_gray(image)
    lines = []
    for block in result.blocks:
        if block.kind in TEXT_KINDS and block.text:
            text = block.text
        elif block.kind == TABLE and block.text:
            text = block.text.replace("\n", " ")
        else:
            continue
        bands = cv.line_bands(gray, block.box, result.dpi)
        lines.extend(cv.distribute_text(text, bands, block.box))
    result.lines = lines


class UnlimitedOCREngine(Engine):
    id = "unlimited"
    name = "Unlimited-OCR"

    def __init__(self) -> None:
        self._model = None
        self._tokenizer = None
        self._lock = threading.Lock()
        self._infer_kwargs: dict | None = None

    def availability(self) -> Availability:
        try:
            import torch  # noqa: F401
            import transformers  # noqa: F401
        except Exception as exc:
            return Availability(False, "gpuPackagesMissing", str(exc))
        import torch

        if not torch.cuda.is_available():
            return Availability(False, "noNvidiaGpu")
        gpu = torch.cuda.get_device_name(0)
        if not model_present():
            return Availability(False, "modelMissing", gpu)
        return Availability(True, detail=gpu)

    def prepare(self, progress: Progress) -> None:
        if self._model is not None:
            return
        state = self.availability()
        if not state.ok:
            raise EngineError(state.reason, state.detail)
        progress("loading-model")
        os.environ.setdefault("HF_HUB_OFFLINE", "1")          # never reach the internet
        os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
        import torch
        from transformers import AutoModel, AutoTokenizer

        path = str(model_dir())
        try:
            self._tokenizer = AutoTokenizer.from_pretrained(path, trust_remote_code=True, local_files_only=True)
            model = AutoModel.from_pretrained(
                path, trust_remote_code=True, use_safetensors=True,
                torch_dtype=torch.bfloat16, local_files_only=True,
            )
        except Exception as exc:
            raise EngineError("modelLoadFailed", str(exc)) from exc
        self._model = model.eval().cuda()

    def process(self, image: np.ndarray, index: int, dpi: float, options: Options) -> PageResult:
        h, w = image.shape[:2]
        with tempfile.TemporaryDirectory(prefix="hyperocr-page-") as tmp:
            path = os.path.join(tmp, "page.png")
            cv2.imwrite(path, cv2.cvtColor(image, cv2.COLOR_RGB2BGR))
            with self._lock:
                raw = self._infer(path, tmp)
        result = PageResult(index, w, h, dpi, self.id)
        pages = [p for p in detparse.split_pages(raw) if p.strip()]
        result.blocks = detparse.parse(pages[0] if pages else "", w, h)
        page_lines(result, image)
        if not result.blocks:
            result.warnings.append("emptyPage")
        return result

    def _infer(self, image_path: str, out_dir: str) -> str:
        """Run model.infer and recover the raw tagged text, whichever way the
        model's own code hands it back (return value, printout or saved file)."""
        model, tok = self._model, self._tokenizer
        if self._infer_kwargs is None:
            params = inspect.signature(model.infer).parameters
            kwargs = dict(
                prompt=PROMPT, image_file=image_path, output_path=out_dir,
                base_size=1024, image_size=640, crop_mode=True,           # the "gundam" single-page setting
                max_length=32768, no_repeat_ngram_size=35, ngram_window=128,
            )
            accepts_any = any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values())
            if "eval_mode" in params:
                kwargs["eval_mode"] = True       # return the text instead of streaming it
            if "save_results" in params or accepts_any:
                kwargs["save_results"] = "eval_mode" not in params
            if not accepts_any:
                kwargs = {k: v for k, v in kwargs.items() if k in params}
            self._infer_kwargs = kwargs
        kwargs = dict(self._infer_kwargs, image_file=image_path, output_path=out_dir)
        buffer = io.StringIO()
        try:
            with contextlib.redirect_stdout(buffer):
                returned = model.infer(tok, **kwargs)
        except Exception as exc:
            raise EngineError("ocrFailed", str(exc)) from exc
        if isinstance(returned, str) and returned.strip():
            return returned
        if isinstance(returned, (list, tuple)) and returned and isinstance(returned[0], str):
            return "\n".join(returned)
        printed = buffer.getvalue()
        if "<|det|>" in printed:
            return printed[printed.index("<|det|>"):]
        for name in ("result_ori.mmd", "result.mmd", "result.md"):
            f = Path(out_dir) / name
            if f.is_file():
                return f.read_text(encoding="utf-8", errors="replace")
        return printed


class UnlimitedServerEngine(Engine):
    """Unlimited-OCR behind a local OpenAI-compatible server (vLLM or SGLang)."""

    id = "unlimited-server"
    name = "Unlimited-OCR (local server)"

    def __init__(self) -> None:
        self.url = os.environ.get("HYPEROCR_OCR_SERVER", "").rstrip("/")

    def configured(self) -> bool:
        return bool(self.url)

    def _local(self) -> bool:
        host = urllib.parse.urlparse(self.url).hostname or ""
        return host in ("127.0.0.1", "localhost", "::1")

    def availability(self) -> Availability:
        if not self.url:
            return Availability(False, "serverNotConfigured")
        if not self._local():
            return Availability(False, "serverNotLocal", self.url)
        try:
            with _no_proxy().open(self.url + "/v1/models", timeout=3) as r:
                models = json.loads(r.read().decode("utf-8")).get("data", [])
        except Exception as exc:
            return Availability(False, "serverUnreachable", str(exc))
        self.model = models[0]["id"] if models else "Unlimited-OCR"
        return Availability(True, detail=self.url)

    def prepare(self, progress: Progress) -> None:
        state = self.availability()
        if not state.ok:
            raise EngineError(state.reason, state.detail)

    def process(self, image: np.ndarray, index: int, dpi: float, options: Options) -> PageResult:
        h, w = image.shape[:2]
        ok, png = cv2.imencode(".png", cv2.cvtColor(image, cv2.COLOR_RGB2BGR))
        if not ok:
            raise EngineError("ocrFailed", "could not encode the page image")
        data_uri = "data:image/png;base64," + base64.b64encode(png.tobytes()).decode("ascii")
        payload = {
            "model": getattr(self, "model", "Unlimited-OCR"),
            "messages": [{"role": "user", "content": [
                {"type": "text", "text": "document parsing."},
                {"type": "image_url", "image_url": {"url": data_uri}},
            ]}],
            "temperature": 0,
            "max_tokens": 16384,
            "skip_special_tokens": False,       # keep the <|det|> tags
            "images_config": {"image_mode": "gundam"},
        }
        req = urllib.request.Request(
            self.url + "/v1/chat/completions", data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        try:
            with _no_proxy().open(req, timeout=1200) as r:
                body = json.loads(r.read().decode("utf-8"))
            raw = body["choices"][0]["message"]["content"] or ""
        except (urllib.error.URLError, KeyError, ValueError) as exc:
            raise EngineError("ocrFailed", str(exc)) from exc
        result = PageResult(index, w, h, dpi, self.id)
        pages = [p for p in detparse.split_pages(raw) if p.strip()]
        result.blocks = detparse.parse(pages[0] if pages else "", w, h)
        page_lines(result, image)
        return result


def _no_proxy() -> urllib.request.OpenerDirector:
    """Talk to localhost directly, even when a system proxy is set."""
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))
