#!/usr/bin/env python3
"""
ERA5 meteorology — authentication/access test.

Validates ECMWF Climate Data Store (CDS) API credentials WITHOUT
downloading data. If credentials are absent, prints the exact manual
steps and exits cleanly (does NOT bypass authentication).

Credential env vars: CDS_API_URL, CDS_API_KEY
  (key format <uid>:<token>; URL defaults to the public CDS API.)

Exit codes: 0 = access verified, 2 = credentials missing, 3 = auth failed.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import _env  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_CDS_URL = "https://cds.climate.copernicus.eu/api"


def run() -> int:
    _env.load_env_file()
    url = _env.get_secret("CDS_API_URL") or DEFAULT_CDS_URL
    key = _env.get_secret("CDS_API_KEY")

    if not key:
        logger.error(
            "\nERA5 requires an ECMWF Climate Data Store (CDS) API key.\n"
            "Manual action required:\n"
            "  1. Register free at https://cds.climate.copernicus.eu\n"
            "  2. Generate your personal API key in your CDS profile.\n"
            "  3. Set CDS_API_URL and CDS_API_KEY in .env (or export them),\n"
            "     key format is <uid>:<token>, and re-run this test.\n"
        )
        logger.info("STOPPING: credentials missing. No data downloaded.")
        return 2

    # Reachability (public, no credentials) first.
    try:
        r0 = requests.get(url, timeout=30)
        logger.info("CDS API endpoint reachable (HTTP %s).", r0.status_code)
    except requests.exceptions.RequestException as exc:
        logger.error("CDS API endpoint unreachable: %s", exc)
        return 3

    # Validate the key via basic auth on the API base URL.
    uid, _, token = key.partition(":")
    logger.info("Testing CDS API key (uid=%s) ...", uid or "(empty uid)")
    try:
        r = requests.get(
            url,
            auth=(uid, token),
            timeout=30,
        )
    except requests.exceptions.RequestException as exc:
        logger.error("Network error validating CDS key: %s", exc)
        return 3

    # CDS accepts the request structure (202 = accepted) once authenticated;
    # 401/403 indicate a bad or unauthorized key.
    if r.status_code in (200, 202):
        logger.info("SUCCESS: CDS API accepted the request with this key (HTTP %s).", r.status_code)
        logger.info(
            "A full downloader will request the 'reanalysis-era5-single-levels' "
            "dataset for u10/v10/2t/msl/tp over the East Prydz Bay bbox, hourly."
        )
        return 0
    if r.status_code in (401, 403):
        logger.error("AUTH FAILED: CDS rejected this key (HTTP %s).", r.status_code)
        logger.error("Confirm the key is <uid>:<token> and your account is active.")
        return 3
    logger.info("CDS responded HTTP %s (key present; result inconclusive).", r.status_code)
    return 3


if __name__ == "__main__":
    sys.exit(run())
