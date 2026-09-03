#!/usr/bin/env python3
"""
Download the US National Ice Center (NIC) Antarctic iceberg position
archive as weekly CSV snapshots.

This is the authoritative source of Antarctic iceberg observations
(the same NIC data underlying the BYU/NIC tracking database). Files are
downloaded to data/raw/icebergs/ and are never modified.

Usage:
    python scripts/data/download_icebergs.py [--start MM/DD/YYYY] [--end MM/DD/YYYY]

Requires no authentication (publicly available).
"""

from __future__ import annotations

import argparse
import logging
import re
from pathlib import Path

import requests

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

ARCHIVE_URL = "https://usicecenter.gov/Products/DisplaySearchResults"
BASE_URL = "https://usicecenter.gov"
RAW_DIR = Path(__file__).resolve().parents[2] / "data" / "raw" / "icebergs"


def get_archive_file_list(start: str, end: str) -> list[str]:
    """Return the list of archive download paths for the date range."""
    payload = {
        "searchText": "IcebergProducts",
        "searchProduct": "Antarctic Icebergs CSV",
        "startDate": start,
        "endDate": end,
    }
    resp = requests.post(ARCHIVE_URL, data=payload, timeout=120)
    resp.raise_for_status()
    return re.findall(r"/File/DownloadArchive\?prd=\d+", resp.text)


def download_all(files: list[str], dest_dir: Path) -> int:
    """Download all archive files, skipping those already present.

    Archive listings occasionally include dates for which the file does
    not exist (server returns 404). Such entries are logged and skipped
    rather than aborting the whole download.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    downloaded = 0
    skipped = 0
    not_found = 0
    for i, rel in enumerate(files, start=1):
        url = BASE_URL + rel
        try:
            with requests.get(url, stream=True, timeout=120) as r:
                r.raise_for_status()
                fname = r.headers.get(
                    "Content-Disposition", ""
                ).split("filename=")[-1].strip('"').split(";")[0]
                dest = dest_dir / fname
                if dest.exists() and dest.stat().st_size > 0:
                    skipped += 1
                    continue
                with open(dest, "wb") as fh:
                    for chunk in r.iter_content(chunk_size=8192):
                        fh.write(chunk)
                downloaded += 1
                logger.info("Downloaded %s (%d/%d)", fname, downloaded, len(files))
        except requests.exceptions.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 404:
                not_found += 1
                logger.warning(
                    "Skipping missing archive entry %d/%d: %s", i, len(files), rel
                )
            else:
                raise exc
    total_expected = len(files) - not_found
    logger.info(
        "Done: %d downloaded, %d already present, %d missing on server "
        "(of %d expected)",
        downloaded,
        skipped,
        not_found,
        total_expected,
    )
    return downloaded


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", default="01/01/2014", help="Start date MM/DD/YYYY")
    parser.add_argument("--end", default="12/31/2026", help="End date MM/DD/YYYY")
    args = parser.parse_args()

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    files = get_archive_file_list(args.start, args.end)
    logger.info("Found %d archive files in range", len(files))
    download_all(files, RAW_DIR)


if __name__ == "__main__":
    main()
