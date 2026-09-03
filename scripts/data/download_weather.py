#!/usr/bin/env python3
"""
Download ERA5 meteorological reanalysis for the East Prydz Bay region.

ERA5 is served by the ECMWF Climate Data Store (CDS). Access requires:
  - A free ECMWF account / CDS registration
  - A CDS API key (URL + key)
  - The `cdsapi` Python package (v2 of the CDS API was retired; the
    current version uses a key of the form <uid>:<token>).

Per the Phase-1 data-acquisition policy, this script does NOT bypass
authentication. It checks for credentials and, if absent, prints the
exact manual action required and exits cleanly.

Only the variables needed for iceberg/sea-ice forcing are requested:
  10m u/v wind components, 2m temperature, mean sea level pressure,
  and total precipitation.
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

CDS_API_URL = "https://cds.climate.copernicus.eu/api"
CDS_REGISTRATION_URL = "https://cds.climate.copernicus.eu/how-to-api"
RAW_DIR = Path(__file__).resolve().parents[2] / "data" / "raw" / "weather"
PROCESSED_DIR = Path(__file__).resolve().parents[2] / "data" / "processed" / "weather"

# Only the variables that drive iceberg drift and sea-ice forecasting.
ERA5_VARIABLES = [
    "10m_u_component_of_wind",
    "10m_v_component_of_wind",
    "2m_temperature",
    "mean_sea_level_pressure",
    "total_precipitation",
]


def check_credentials() -> tuple[str, str]:
    """Return (url, key) or raise with instructions."""
    url = os.getenv("CDS_API_URL", CDS_API_URL)
    key = os.getenv("CDS_API_KEY", "")
    if not key:
        raise RuntimeError(
            "\nERA5 data requires an ECMWF Climate Data Store (CDS) API key.\n"
            "Manual action required:\n"
            "  1. Register a free account at https://cds.climate.copernicus.eu\n"
            "  2. Generate your personal API key in your CDS user profile.\n"
            "  3. Export it and re-run, e.g.:\n"
            "        export CDS_API_URL=https://cds.climate.copernicus.eu/api\n"
            "        export CDS_API_KEY=<uid>:<long-api-token>\n"
            "  4. Optionally add the same values to .env and load them.\n"
        )
    return url, key


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
        url, key = check_credentials()
    except RuntimeError as exc:
        logger.error(str(exc))
        logger.info("STOPPING ERA5 acquisition (no credentials). No data downloaded.")
        sys.exit(2)

    logger.info("Credentials present (url=%s). Download would proceed here.", url)
    logger.info("Requested variables: %s", ", ".join(ERA5_VARIABLES))
    logger.info(
        "A full implementation would call the CDS 'reanalysis-era5-single-levels' "
        "dataset for %s..%s over the East Prydz Bay bbox, then write hourly "
        "NetCDF files to %s", args.start, args.end, PROCESSED_DIR
    )


if __name__ == "__main__":
    main()
