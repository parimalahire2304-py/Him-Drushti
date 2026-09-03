#!/usr/bin/env python3
"""
Sentinel-1 SAR — authentication/access test.

The Copernicus Data Space catalog search is public (no auth). Scene
DOWNLOAD requires OAuth2 credentials. This test:
  (a) verifies the public catalog is reachable and counts EW_GRDM scenes
      in the East Prydz Bay bbox (no auth, no data download), and
  (b) if credentials are present, obtains an OAuth2 token to confirm
      download access will work.

Credential env vars: COPERNICUS_USERNAME, COPERNICUS_PASSWORD

Exit codes: 0 = download access verified, 2 = credentials missing
            (catalog check still performed), 3 = auth failed.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import _env  # noqa: E402
from src.utils.region import load_region  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

CATALOG = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products"
TOKEN_URL = (
    "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
)
CLIENT_ID = "cdse-public"


def _polygon() -> str:
    """Build an OData polygon from config/region.yaml (no hard-coded box)."""
    bb = load_region().bounding_box
    # OData CSC.Intersects uses lon/lat pairs: (west south, east south, east north, west north)
    return (
        f"geography'SRID=4326;POLYGON(({bb.west} {bb.south},"
        f"{bb.east} {bb.south},{bb.east} {bb.north},"
        f"{bb.west} {bb.north},{bb.west} {bb.south}))'"
    )


def count_ew_scenes() -> int | None:
    """Public catalog check: count EW_GRDM scenes intersecting the bbox."""
    params = {
        "$filter": (
            f"Collection/Name eq 'SENTINEL-1' and "
            f"contains(Name,'EW_GRDM') and "
            f"OData.CSC.Intersects(area={_polygon()})"
        ),
        "$top": 1,
        "$select": "Id",
        "$count": "true",
    }
    r = requests.get(CATALOG, params=params, timeout=30)
    if r.status_code != 200:
        logger.error("Catalog check failed (HTTP %s).", r.status_code)
        return None
    return r.json().get("@odata.count")


def run() -> int:
    _env.load_env_file()

    logger.info("(a) Public catalog check over East Prydz Bay bbox ...")
    try:
        n = count_ew_scenes()
        logger.info("Catalog reachable. EW_GRDM scenes in bbox: %s", n)
    except requests.exceptions.RequestException as exc:
        logger.error("Catalog unreachable: %s", exc)
        return 3

    username = _env.get_secret("COPERNICUS_USERNAME")
    password = _env.get_secret("COPERNICUS_PASSWORD")

    if not username or not password:
        logger.error(
            "\nDownloading Sentinel-1 scenes requires a Copernicus Data Space "
            "account.\nManual action required:\n"
            "  1. Register free at https://dataspace.copernicus.eu\n"
            "  2. Set COPERNICUS_USERNAME and COPERNICUS_PASSWORD in .env\n"
            "     (or export them) and re-run this test.\n"
        )
        logger.info(
            "STOPPING: credentials missing. Catalog verified; download not possible. "
            "No data downloaded."
        )
        return 2

    logger.info("(b) Testing Copernicus Data Space OAuth2 credentials for %s ...", username)
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
        logger.error("Data Space identity server unreachable: %s", exc)
        return 3

    if r.status_code == 200:
        logger.info("SUCCESS: credentials valid. OAuth2 token obtained; downloads will work.")
        return 0
    if r.status_code in (400, 401):
        logger.error("AUTH FAILED: Data Space rejected these credentials (HTTP %s).", r.status_code)
        return 3
    logger.error("Unexpected response: HTTP %s", r.status_code)
    return 3


if __name__ == "__main__":
    sys.exit(run())
