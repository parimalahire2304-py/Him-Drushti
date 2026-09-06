#!/usr/bin/env python3
"""
Download GLORYS12V1 ocean reanalysis for the East Prydz Bay region.

Uses the copernicusmarine Python library to programmatically download
surface ocean currents (uo, vo) from the CMEMS GLORYS12V1 product.

Output: data/raw/ocean/glorys/cmems_mod_glo_phy_my_0.083deg_P1D-m_{year}.nc

Usage:
    python scripts/data/download_glorys.py --start 2019-01-01 --end 2019-12-31
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.utils.region import load_region

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

RAW_DIR = Path(__file__).resolve().parents[2] / "data" / "raw" / "ocean" / "glorys"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", default="2019-01-01")
    parser.add_argument("--end", default="2019-12-31")
    args = parser.parse_args()

    region = load_region()
    bb = region.bounding_box
    logger.info("Region %s | bbox S=%.1f N=%.1f W=%.1f E=%.1f",
                region.region_name, bb.south, bb.north, bb.west, bb.east)

    RAW_DIR.mkdir(parents=True, exist_ok=True)

    try:
        from dotenv import load_dotenv
        load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    except ImportError:
        pass

    import os
    username = os.getenv("CMEMS_USERNAME", "")
    password = os.getenv("CMEMS_PASSWORD", "")
    if not username or not password:
        logger.error("CMEMS_USERNAME / CMEMS_PASSWORD not set in .env")
        sys.exit(2)

    try:
        import copernicusmarine
    except ImportError:
        logger.error("copernicusmarine not installed. Run: pip install copernicusmarine")
        sys.exit(2)

    # Build output filename
    year = args.start[:4]
    out_file = RAW_DIR / f"glorys12v1_east_prydz_bay_{year}.nc"
    if out_file.exists() and out_file.stat().st_size > 1e6:
        logger.info("GLORYS file already exists: %s (%.2f MB)",
                     out_file.name, out_file.stat().st_size / 1e6)
        logger.info("Delete it to force re-download. Exiting.")
        return

    logger.info("Downloading GLORYS12V1 for %s to %s ...", args.start, args.end)
    logger.info("Variables: uo (eastward current), vo (northward current)")
    logger.info("Resolution: 1/12 degree daily (P1D-m)")

    import time
    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            ds = copernicusmarine.open_dataset(
                dataset_id="cmems_mod_glo_phy_my_0.083deg_P1D-m",
                variables=["uo", "vo"],
                minimum_longitude=bb.west,
                maximum_longitude=bb.east,
                minimum_latitude=bb.south,
                maximum_latitude=bb.north,
                start_datetime=f"{args.start}T00:00:00",
                end_datetime=f"{args.end}T23:59:59",
                username=username,
                password=password,
            )
            break
        except Exception as e:
            logger.warning("Attempt %d/%d failed: %s: %s", attempt, max_retries, type(e).__name__, e)
            if attempt < max_retries:
                wait = 30 * attempt
                logger.info("Retrying in %ds...", wait)
                time.sleep(wait)
            else:
                logger.error("GLORYS download failed after %d attempts: %s", max_retries, e)
                sys.exit(1)

    logger.info("Downloaded: %s", dict(ds.dims))
    logger.info("Variables: %s", list(ds.data_vars))

    # Select only the surface depth level (closest to 0.494m)
    if "depth" in ds.dims:
        # Select the shallowest depth level
        ds = ds.isel(depth=0)
        logger.info("Selected surface depth level: %.3f m", float(ds.depth))
        if "depth" in ds.dims:
            ds = ds.squeeze("depth", drop=True)
        else:
            logger.info("Depth dimension already dropped by isel")

    # Save
    ds.to_netcdf(out_file)
    size_mb = out_file.stat().st_size / 1e6
    logger.info("Saved: %s (%.2f MB)", out_file.name, size_mb)

    # Log stats
    for var in ["uo", "vo"]:
        if var in ds:
            data = ds[var]
            nan_pct = float(data.isnull().sum()) / data.size * 100
            logger.info("  %s: range=%.4f..%.4f m/s, NaN=%.1f%%",
                        var, float(data.min()), float(data.max()), nan_pct)


if __name__ == "__main__":
    main()
