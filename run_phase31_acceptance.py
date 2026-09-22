"""Run BKPOS Phase 31 release-candidate acceptance checks."""
from __future__ import annotations
import subprocess, sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

if __name__ == '__main__':
    result = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-v'], cwd=BASE_DIR)
    raise SystemExit(result.returncode)
