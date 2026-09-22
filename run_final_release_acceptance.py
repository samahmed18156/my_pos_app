"""Run the complete BKPOS automated release acceptance suite."""
from __future__ import annotations
import subprocess
import sys

if __name__ == "__main__":
    result = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-v"],
        cwd=__file__.rsplit("\\", 1)[0] if "\\" in __file__ else ".",
    )
    raise SystemExit(result.returncode)
