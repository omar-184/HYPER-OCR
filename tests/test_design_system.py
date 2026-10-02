"""The "Apple style App" design system must match the interface it documents."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_design_system_is_in_step_with_the_interface():
    out = subprocess.run([sys.executable, str(ROOT / "design-system-apple" / "build.py"), "--check"],
                         capture_output=True, text=True, check=False)
    assert out.returncode == 0, "run python design-system-apple/build.py:\n" + out.stdout + out.stderr


def test_a_windows_checkout_with_crlf_line_endings_is_still_in_step(tmp_path):
    """Git on Windows may turn LF into CRLF; that alone must not fail the check."""
    import shutil

    for name in ("hyperocr", "design-system-apple"):
        shutil.copytree(ROOT / name, tmp_path / name, ignore=shutil.ignore_patterns("__pycache__"))
    for p in tmp_path.rglob("*"):
        if p.suffix in (".css", ".html", ".js", ".json", ".md", ".svg") and p.is_file():
            p.write_bytes(p.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
    out = subprocess.run([sys.executable, str(tmp_path / "design-system-apple" / "build.py"), "--check"],
                         capture_output=True, text=True, check=False)
    assert out.returncode == 0, out.stdout + out.stderr
