#!/usr/bin/env python3
"""
NSIDC sea-ice concentration — authentication/access test.

Validates NASA Earthdata Login credentials WITHOUT downloading data.
If credentials are absent, prints the exact manual steps and exits
cleanly (does NOT bypass authentication).

Credential env vars: NSIDC_USERNAME, NSIDC_PASSWORD
  (NASA Earthdata Login username/email and password.)

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

# Earthdata Login token endpoint — returns a JSON list of active tokens
# for the authenticated user. Minimal, non-data-downloading validation.
URS_TOKEN_URL = "https://urs.earthdata.nasa.gov/api/users/tokens"


def run() -> int:
    _env.load_env_file()
    username = _env.get_secret("NSIDC_USERNAME")
    password = _env.get_secret("NSIDC_PASSWORD")

    if not username or not password:
        logger.error(
            "\nNSIDC sea-ice requires a NASA Earthdata Login account.\n"
            "Manual action required:\n"
            "  1. Register free at https://urs.earthdata.nasa.gov\n"
            "  2. Approve the 'NSIDC DAAC' application (Earthdata profile ->\n"
            "     Applications -> Authorized Apps).\n"
            "  3. Set NSIDC_USERNAME and NSIDC_PASSWORD in .env (or export\n"
            "     them in your shell) and re-run this test.\n"
        )
        logger.info("STOPPING: credentials missing. No data downloaded.")
        return 2

    logger.info("Testing Earthdata Login credentials for %s ...", username)
    try:
        r = requests.get(
            URS_TOKEN_URL,
            auth=(username, password),
            timeout=30,
        )
    except requests.exceptions.RequestException as exc:
        logger.error("Network error reaching Earthdata Login: %s", exc)
        return 3

    if r.status_code == 200:
        tokens = r.json() if r.headers.get("content-type", "").startswith("application/json") else []
        logger.info(
            "SUCCESS: credentials valid. %d active token(s) on account.",
            len(tokens) if isinstance(tokens, list) else "?",
        )
        logger.info(
            "A full downloader will use an Earthdata bearer token (or .netrc) "
            "to fetch NSIDC-0051/0079 daily grids, subset to the East Prydz "
            "Bay bbox, and reproject to EPSG:4326."
        )
        return 0
    if r.status_code == 401:
        logger.error("AUTH FAILED: Earthdata rejected these credentials (HTTP 401).")
        logger.error("Double-check your Earthdata email/password and NSIDC DAAC approval.")
        return 3
    logger.error("Unexpected response: HTTP %s", r.status_code)
    return 3


if __name__ == "__main__":
    sys.exit(run())
