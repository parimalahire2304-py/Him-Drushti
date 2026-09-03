#!/usr/bin/env python3
"""
GLORYS ocean — authentication/access test.

Validates Copernicus Marine (CMEMS) credentials WITHOUT downloading
data. If credentials are absent, prints the exact manual steps and
exits cleanly (does NOT bypass authentication).

Credential env vars: CMEMS_USERNAME, CMEMS_PASSWORD

Note: the CMEMS identity server is DNS-unreachable from some networks
(including this build environment). If unreachable, this test reports
that clearly and does not attempt to work around it.

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

# CMEMS Marine Data Store OAuth2 token endpoint (public, documented).
TOKEN_URL = (
    "https://identity.marine.copernicus.eu/auth/realms/cmems/protocol/openid-connect/token"
)
# Public OAuth client used by the Marine Data Store.
CLIENT_ID = "cds-marine-ondemand"


def run() -> int:
    _env.load_env_file()
    username = _env.get_secret("CMEMS_USERNAME")
    password = _env.get_secret("CMEMS_PASSWORD")

    if not username or not password:
        logger.error(
            "\nGLORYS requires a Copernicus Marine (CMEMS) account.\n"
            "Manual action required:\n"
            "  1. Register free at https://data.marine.copernicus.eu/register\n"
            "  2. Log in and subscribe to the GLORYS12V1 product.\n"
            "  3. Set CMEMS_USERNAME and CMEMS_PASSWORD in .env (or export\n"
            "     them) and re-run this test.\n"
        )
        logger.info("STOPPING: credentials missing. No data downloaded.")
        return 2

    logger.info("Testing CMEMS credentials for %s ...", username)
    try:
        r = requests.post(
            TOKEN_URL,
            data={
                "grant_type": "password",
                "username": username,
                "password": password,
                "client_id": CLIENT_ID,
            },
            timeout=30,
        )
    except requests.exceptions.RequestException as exc:
        logger.error(
            "CMEMS identity server unreachable from this network (%s).\n"
            "This is an environment/DNS limitation, not a credential problem. "
            "Re-run the test from a network that can resolve "
            "identity.marine.copernicus.eu.", exc
        )
        return 3

    if r.status_code == 200:
        data = r.json()
        logger.info("SUCCESS: credentials valid. Obtained OAuth2 access token.")
        logger.info(
            "A full downloader will use this token to request GLORYS12V1 daily "
            "surface uo/vo/thetao over the East Prydz Bay bbox via the Marine "
            "Data Store, and write NetCDF to data/processed/ocean/."
        )
        return 0
    if r.status_code in (400, 401):
        logger.error("AUTH FAILED: CMEMS rejected these credentials (HTTP %s).", r.status_code)
        logger.error("Confirm your username/password and GLORYS12V1 subscription.")
        return 3
    logger.error("Unexpected response: HTTP %s", r.status_code)
    return 3


if __name__ == "__main__":
    sys.exit(run())
