"""Keep HYPER-OCR off the network while it runs.

* Libraries that can phone home are told not to (Hugging Face).
* ONNX Runtime is never loaded: merely importing it makes Microsoft telemetry
  connections (seen with onnxruntime 1.30 on Linux). MarkItDown imports it only
  for its file-type guesser ("magika"), which HYPER-OCR does not need: it hands
  MarkItDown HTML and says so. A stand-in for magika keeps it out.
* `lock_down()` makes every outgoing connection from this process fail unless it
  goes to this computer itself. The setup helpers (model and language
  downloads) run as separate commands and are not affected.
"""

from __future__ import annotations

import importlib.abc
import ipaddress
import os
import socket
import sys
import types

BLOCKED_MODULES = {"onnxruntime"}
_installed = False


class _Blocker(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path=None, target=None):
        if name.split(".")[0] in BLOCKED_MODULES:
            raise ImportError("%s is disabled in HYPER-OCR (it sends telemetry)" % name)
        return None


def quiet_libraries() -> None:
    for key in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "HF_HUB_DISABLE_TELEMETRY", "HF_DATASETS_OFFLINE", "DO_NOT_TRACK"):
        os.environ.setdefault(key, "1")
    if not any(isinstance(f, _Blocker) for f in sys.meta_path):
        sys.meta_path.insert(0, _Blocker())
    if "magika" not in sys.modules:
        stub = types.ModuleType("magika")
        stub.__doc__ = "Stand-in: HYPER-OCR never asks MarkItDown to guess file types."

        class Magika:
            def __init__(self, *args, **kwargs):
                raise RuntimeError("file-type guessing is disabled in HYPER-OCR")

        stub.Magika = Magika
        sys.modules["magika"] = stub


def _allowed(family: int, address) -> bool:
    if family not in (socket.AF_INET, socket.AF_INET6):
        return True  # local sockets (AF_UNIX) only reach this computer
    host = address[0] if isinstance(address, tuple) else address
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(str(host).split("%")[0]).is_loopback
    except ValueError:
        return False


def lock_down() -> None:
    """Refuse outgoing network connections from this process, except to localhost."""
    global _installed
    quiet_libraries()
    if _installed:
        return
    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex

    def connect(self, address):
        if not _allowed(self.family, address):
            raise ConnectionRefusedError("HYPER-OCR works offline: blocked a connection to %r" % (address,))
        return real_connect(self, address)

    def connect_ex(self, address):
        if not _allowed(self.family, address):
            return 111  # ECONNREFUSED
        return real_connect_ex(self, address)

    socket.socket.connect = connect
    socket.socket.connect_ex = connect_ex
    _installed = True
