#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pydantic>=2", "pyyaml>=6"]
# ///
"""Entry point vengine. Jalankan: python <folder-skill>/scripts/vengine_cli.py <perintah> ...
Atau tanpa setup dependensi: uv run <folder-skill>/scripts/vengine_cli.py <perintah> ..."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

if sys.version_info < (3, 10):
    sys.exit("Python 3.10+ dibutuhkan.")
try:
    from vengine.cli import main
except ModuleNotFoundError as e:
    if e.name in ("pydantic", "yaml"):
        sys.exit(f"Modul '{e.name}' belum terpasang. Jalankan: pip install pydantic pyyaml  (atau pakai `uv run`)")
    raise

if __name__ == "__main__":
    sys.exit(main())
