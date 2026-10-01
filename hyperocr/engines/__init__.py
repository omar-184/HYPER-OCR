"""OCR engines and the automatic choice between them."""

from __future__ import annotations

import threading

from .base import Availability, Engine, EngineError, Options
from .tesseract_engine import TesseractEngine
from .unlimited import UnlimitedOCREngine, UnlimitedServerEngine

_lock = threading.Lock()
_engines: dict[str, Engine] = {}


def get(engine_id: str) -> Engine:
    with _lock:
        if not _engines:
            for cls in (UnlimitedOCREngine, UnlimitedServerEngine, TesseractEngine):
                _engines[cls.id] = cls()
        if engine_id not in _engines:
            raise EngineError("unknownEngine", engine_id)
        return _engines[engine_id]


def describe() -> list[dict]:
    """Every engine with whether it can run here, for the interface."""
    out = []
    for engine_id in ("unlimited", "unlimited-server", "tesseract"):
        engine = get(engine_id)
        if engine_id == "unlimited-server" and not engine.configured():
            continue  # only shown to people who set up the local server
        state = engine.availability()
        out.append({"id": engine_id, "name": engine.name, "ok": state.ok, "reason": state.reason, "detail": state.detail})
    return out


def choose(options: Options) -> tuple[Engine, Availability | None]:
    """The engine to use, and why the GPU engine was passed over (auto only)."""
    if options.engine != "auto":
        engine = get(options.engine)
        state = engine.availability()
        if not state.ok:
            raise EngineError(state.reason, state.detail)
        return engine, None
    gpu = get("unlimited")
    gpu_state = gpu.availability()
    if gpu_state.ok:
        return gpu, None
    server = get("unlimited-server")
    if server.configured() and server.availability().ok:
        return server, None
    cpu = get("tesseract")
    cpu_state = cpu.availability()
    if not cpu_state.ok:
        raise EngineError(cpu_state.reason, cpu_state.detail)
    return cpu, gpu_state


__all__ = ["Engine", "EngineError", "Options", "choose", "describe", "get"]
