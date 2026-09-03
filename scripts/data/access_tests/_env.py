"""
Shared environment-var loading helper for access tests.

Loads credentials from the process environment, optionally enriched by a
project `.env` file (using python-dotenv when installed, else a tiny
fallback parser). Never writes or exposes credentials in source code.
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_ENV_FILE = _PROJECT_ROOT / ".env"

# Real python-dotenv is preferred; fall back to a minimal parser so the
# tests work even before `pip install python-dotenv`.


def load_env_file() -> None:
    """Load KEY=VALUE pairs from the project .env file into os.environ."""
    if not _ENV_FILE.exists():
        return
    try:
        from dotenv import load_dotenv

        load_dotenv(_ENV_FILE)
        logger.debug("Loaded %s via python-dotenv", _ENV_FILE)
        return
    except ImportError:
        pass

    # Minimal fallback parser (no interpolation, no quoted-value handling).
    for line in _ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        import os

        os.environ.setdefault(key, value)
    logger.debug("Loaded %s via fallback parser", _ENV_FILE)


def get_secret(key: str) -> str:
    """Return an environment variable, or '' if unset/empty."""
    import os

    return os.environ.get(key, "").strip()
