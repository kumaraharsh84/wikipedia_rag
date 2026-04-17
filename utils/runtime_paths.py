"""
Helpers for choosing writable runtime directories across local, Docker, and Vercel.
"""

from __future__ import annotations

import os
from pathlib import Path


def _is_vercel() -> bool:
    return os.getenv("VERCEL") == "1"


def get_data_dir() -> Path:
    """
    Return a writable directory for caches, logs, and local SQLite files.

    On Vercel, the deployment bundle is read-only, so we use /tmp.
    Elsewhere, keep the existing repo-local data directory behavior.
    """
    if _is_vercel():
        base = Path(os.getenv("VERCEL_TMP_DIR", "/tmp")) / "wikiqa-data"
    else:
        base = Path(__file__).resolve().parent.parent / "data"

    base.mkdir(parents=True, exist_ok=True)
    return base
