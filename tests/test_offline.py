"""HYPER-OCR stays off the network."""

import subprocess
import sys
import textwrap

from conftest import ROOT


def _run(code: str) -> str:
    out = subprocess.run([sys.executable, "-c", textwrap.dedent(code)], cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr
    return out.stdout


def test_lock_down_blocks_outside_connections_but_not_localhost():
    out = _run("""
        import socket
        from hyperocr.offline import lock_down
        server = socket.socket(); server.bind(("127.0.0.1", 0)); server.listen(1)
        lock_down()
        socket.create_connection(server.getsockname(), timeout=2).close()      # this computer: allowed
        try:
            socket.create_connection(("93.184.216.34", 80), timeout=2)        # anywhere else: refused
        except ConnectionRefusedError as exc:
            print("blocked:", "offline" in str(exc))
        print("connect_ex:", socket.socket().connect_ex(("8.8.8.8", 53)))
    """)
    assert "blocked: True" in out and "connect_ex: 111" in out


def test_markdown_never_loads_onnxruntime():
    # Importing onnxruntime alone makes telemetry connections, so it must never load.
    out = _run("""
        import sys
        from hyperocr.document import TEXT, Block, PageResult
        from hyperocr.outputs.markdown import to_markdown
        md = to_markdown([PageResult(0, 1, 1, 300, "t", blocks=[Block(TEXT, (0, 0, 1, 1), text="hello")])], "T")
        print("md:", md.strip())
        print("onnxruntime loaded:", "onnxruntime" in sys.modules)
        try:
            import onnxruntime
            print("import allowed")
        except ImportError:
            print("import blocked")
    """)
    assert "md: hello" in out and "onnxruntime loaded: False" in out and "import blocked" in out
