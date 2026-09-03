"""
Base ingestion utilities shared across all dataset downloaders.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

_RAW_ROOT = Path(__file__).resolve().parents[2] / "data" / "raw"


def get_raw_dir(dataset_name: str) -> Path:
    """Return the raw data directory for a dataset, creating it if needed."""
    d = _RAW_ROOT / dataset_name
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_processed_dir(dataset_name: str) -> Path:
    """Return the processed data directory for a dataset."""
    d = Path(__file__).resolve().parents[2] / "data" / "processed" / dataset_name
    d.mkdir(parents=True, exist_ok=True)
    return d


def download_file(
    url: str,
    dest: Path,
    chunk_size: int = 8192,
    timeout: int = 120,
) -> Path:
    """
    Download a file from a URL to a local path.

    Skips download if the file already exists and is non-empty.
    Logs the file size and MD5 hash after download.
    """
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)

    if dest.exists() and dest.stat().st_size > 0:
        logger.info("File already exists, skipping download: %s", dest)
        return dest

    logger.info("Downloading %s -> %s", url, dest)
    resp = requests.get(url, stream=True, timeout=timeout)
    resp.raise_for_status()

    total = 0
    with open(dest, "wb") as fh:
        for chunk in resp.iter_content(chunk_size=chunk_size):
            fh.write(chunk)
            total += len(chunk)

    logger.info("Downloaded %.2f MB -> %s", total / 1e6, dest)

    # Compute MD5 for reproducibility tracking
    md5 = hashlib.md5(dest.read_bytes()).hexdigest()
    logger.info("MD5: %s", md5)

    return dest
