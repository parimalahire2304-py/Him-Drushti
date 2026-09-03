#!/usr/bin/env python3
"""
Download GLORYS ocean reanalysis (currents, temperature) for the East Prydz Bay region.

GLORYS is distributed by the Copernicus Marine Environment Monitoring
Service (CMEMS, now part of the Copernicus Marine Service). Access
requires a free CMEMS account and a personal username/password (OAuth
client id/secret for the Motu / Marine Data Store API).

Per the Phase-1 data-acquisition policy, this script does NOT bypass
authentication. It checks for credentials and, if absent, prints the
exact manual action required and exits cleanly.

Preferred product: GLORYS12V1 (1/12 degree daily) — surface ocean
currents (uo/vos) are the primary iceberg-drift forcing; sea surface
temperature (thetao) is included for completeness.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

# Ensure project root is on the Python path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.utils.region import load_region

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

CMEMS_REGISTRATION_URL = "https://data.marine.copernicus.eu/register"
RAW_DIR = Path(__file__).resolve().parents[2] / "data" / "raw" / "ocean"
PROCESSED_DIR = Path(__file__).resolve().parents[2] / "data" / "processed" / "ocean"


def check_credentials() -> tuple[str, str]:
    """Return (username, password) or raise with instructions."""
    username = os.getenv("CMEMS_USERNAME", "")
    password = os.getenv("CMEMS_PASSWORD", "")
    if not username or not password:
        raise RuntimeError(
            "\nGLORYS ocean reanalysis requires a Copernicus Marine (CMEMS) account.\n"
            "Manual action required:\n"
            "  1. Register a free account at https://data.marine.copernicus.eu/register\n"
            "  2. Log in and subscribe to the GLORYS12V1 product.\n"
            "  3. Obtain your personal credentials (username + password, or\n"
            "     OAuth client id/secret for the Marine Data Store API).\n"
            "  4. Export them and re-run, e.g.:\n"
            "        export CMEMS_USERNAME=<your-username>\n"
            "        export CMEMS_PASSWORD=<your-password>\n"
            "  5. Optionally add the same values to .env and load them.\n"
        )
    return username, password


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="Only check credentials, do not submit request")
    parser.add_argument("--start", default="2024-01-01", help="Start date YYYY-MM-DD")
    parser.add_argument("--end", default="2024-12-31", help="End date YYYY-MM-DD")
    args = parser.parse_args()

    region = load_region()
    bb = region.bounding_box
    logger.info("Region: %s | bbox S=%.1f N=%.1f W=%.1f E=%.1f",
                region.region_name, bb.south, bb.north, bb.west, bb.east)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    try:
        username, _ = check_credentials()
    except RuntimeError as exc:
        logger.error(str(exc))
        logger.info("STOPPING GLORYS acquisition (no credentials). No data downloaded.")
        sys.exit(2)

    logger.info("Credentials present for %s. Download would proceed here.", username)
    logger.info(
        "A full implementation would request GLORYS12V1 daily surface uo/vos/thetao "
        "over the East Prydz Bay bbox for %s..%s, then write NetCDF files to %s",
        args.start, args.end, PROCESSED_DIR
    )


if __name__ == "__main__":
    main()
