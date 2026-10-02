"""The "Apple style App" design system must match the interface it documents."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_design_system_is_in_step_with_the_interface():
    out = subprocess.run([sys.executable, str(ROOT / "design-system-apple" / "build.py"), "--check"],
                         capture_output=True, text=True, check=False)
    assert out.returncode == 0, "run python design-system-apple/build.py:\n" + out.stdout + out.stderr
