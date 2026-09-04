#!/usr/bin/env python3
"""
Download and process NSIDC-0051 sea-ice concentration for the East Prydz Bay region.

Product: NSIDC-0051 v2.0 "Sea Ice Concentrations from Nimbus-7 SMMR and DMSP
SSM/I-SSMIS Passive Microwave Data" (NASA Team algorithm). Daily, ~25 km,
polar stereographic south (EPSG:3412).

Access:
  - Requires a free NASA Earthdata Login (NSIDC_USERNAME / NSIDC_PASSWORD).
  - Uses an Earthdata bearer token for authorized download.
  - Discovers daily granule URLs via NASA CMR, downloads from Earthdata Cloud.

Processing (to data/processed/sea_ice/):
  - Unpack F17_ICECON (packed 0-250 -> fraction 0.0-1.0; flags 251-254).
  - Attach geolocation (lat/lon) from the CRS.
  - Subset to the East Prydz Bay bbox from config/region.yaml.
  - Save a per-period combined NetCDF + metadata JSON.

Usage:
    python scripts/data/download_sea_ice.py [--start YYYY-MM-DD] [--end YYYY-MM-DD]
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import requests
import xarray as xr

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.utils.region import load_region

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

EARTHDATA_TOKEN_URL = "https://urs.earthdata.nasa.gov/api/users/token"
CMR_URL = "https://cmr.earthdata.nasa.gov/search/granules.json"
PRODUCT = "NSIDC-0051"

RAW_DIR = Path(__file__).resolve().parents[2] / "data" / "raw" / "sea_ice"
PROCESSED_DIR = Path(__file__).resolve().parents[2] / "data" / "processed" / "sea_ice"

# Packed data: valid range 0-250 maps to 0.0-1.0 fraction; 251-254 are flags.
_VALID_MAX = 250
_FLAG_VALUES = {251: "pole_hole", 252: "unused", 253: "coast", 254: "land"}


def load_env() -> tuple[str, str]:
    """Load NSIDC credentials from environment (optionally via .env)."""
    try:
        from dotenv import load_dotenv

        load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    except ImportError:
        pass
    username = os.getenv("NSIDC_USERNAME", "")
    password = os.getenv("NSIDC_PASSWORD", "")
    if not username or not password:
        raise RuntimeError(
            "NSIDC_USERNAME / NSIDC_PASSWORD not set. "
            "Register at https://urs.earthdata.nasa.gov and set them in .env."
        )
    return username, password


def get_earthdata_token(username: str, password: str) -> str:
    """Obtain (or reuse) an Earthdata bearer token."""
    # Reuse an existing token if present.
    existing = requests.get(
        "https://urs.earthdata.nasa.gov/api/users/tokens",
        auth=(username, password),
        timeout=30,
        headers={"Accept": "application/json"},
    )
    if existing.status_code == 200:
        try:
            lst = existing.json()
            if isinstance(lst, list) and lst:
                tok = lst[0].get("access_token") or lst[0].get("token")
                if tok:
                    return tok
        except Exception:
            pass
    # Otherwise create a new token.
    r = requests.post(
        EARTHDATA_TOKEN_URL,
        auth=(username, password),
        timeout=30,
        headers={"Accept": "application/json"},
    )
    r.raise_for_status()
    return r.json()["access_token"]


def cmr_daily_urls(token: str, start: str, end: str) -> list[tuple[str, str]]:
    """Return [(date_str, https_url)] of daily NSIDC-0051 granules in range."""
    headers = {"Authorization": f"Bearer {token}"}
    # CMR searches by day; page through the whole range.
    start_dt = datetime.strptime(start, "%Y-%m-%d")
    end_dt = datetime.strptime(end, "%Y-%m-%d")
    found: dict[str, str] = {}
    page = 1
    while True:
        params = {
            "short_name": PRODUCT,
            "temporal": f"{start_dt.isoformat()}Z,{end_dt.isoformat()}Z",
            "page_size": 200,
            "page_num": page,
            "bounding_box": "-180,-90,180,-65",
        }
        r = requests.get(CMR_URL, params=params, headers=headers, timeout=60)
        r.raise_for_status()
        entries = r.json().get("feed", {}).get("entry", [])
        if not entries:
            break
        for e in entries:
            title = e.get("title", "")
            # Keep only daily granules (date appears in the name; monthly has YYYYMM only).
            # Daily name form: NSIDC0051_SEAICE_PS_S25km_YYYYMMDD_v2.0.nc
            for link in e.get("links", []):
                href = link.get("href", "")
                if href.endswith(".nc") and "earthdatacloud" in href and "_v2.0.nc" in href:
                    # Determine the date from the title.
                    date_part = _extract_date(title)
                    if date_part:
                        found[date_part] = href
        if len(entries) < 200:
            break
        page += 1
    result = sorted(found.items())
    logger.info("CMR found %d daily granules in range", len(result))
    return result


def _extract_date(title: str) -> str | None:
    """Extract a YYYYMMDD date from an NSIDC-0051 granule title."""
    # Title like NSIDC0051_SEAICE_PS_S25km_20200115_v2.0.nc
    import re

    m = re.search(r"_(\d{8})_v2\.0", title)
    if m:
        return m.group(1)
    return None


def download_daily(url: str, token: str, dest: Path) -> Path:
    """Download one daily granule, skipping if already present."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    r = requests.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=120)
    r.raise_for_status()
    dest.write_bytes(r.content)
    return dest


def process_one(file: Path) -> xr.Dataset:
    """
    Geolocate and clip one daily file to the bbox.

    NOTE: The NSIDC-0051 v2.0 NetCDF already ships UNPACKED — F17_ICECON is
    float64 in fraction units (0.0-1.0), with scale_factor already applied.
    Values above 1.0 (1.004..1.016) correspond to the packed flags 251-254
    (pole_hole / unused / coast / land) and must be masked to NaN.
    """
    ds = xr.open_dataset(file)
    packed = ds["F17_ICECON"]

    # Flag values (> 1.0 in unpacked units) become NaN with attributes.
    frac = packed.where(packed <= 1.0)
    frac.attrs["units"] = "fraction (0.0-1.0)"
    frac.attrs["long_name"] = "Sea Ice Concentration (NASA Team)"
    frac.attrs["standard_name"] = "sea_ice_area_fraction"
    frac.attrs["flag_values"] = "251=pole_hole 252=unused 253=coast 254=land"

    ds_out = xr.Dataset({"sea_ice_concentration": frac}, attrs=ds.attrs)
    # Attach x/y (native) and compute geolocation.
    ds_out = ds_out.assign_coords(x=ds["x"], y=ds["y"])
    return ds_out


def add_latlon(ds: xr.Dataset) -> xr.Dataset:
    """Add lat/lon coordinates by transforming the polar-stereographic grid."""
    from pyproj import Transformer

    src_crs = "EPSG:3412"
    transformer = Transformer.from_crs(src_crs, "EPSG:4326", always_xy=True)
    xv, yv = np.meshgrid(ds["x"].values, ds["y"].values)
    lon, lat = transformer.transform(xv, yv)
    ds = ds.assign_coords(
        lon=(("y", "x"), lon),
        lat=(("y", "x"), lat),
    )
    return ds


def clip_to_bbox(ds: xr.Dataset, bbox) -> xr.Dataset:
    """Select grid cells whose centroid falls inside the bbox."""
    mask = (
        (ds["lat"] >= bbox.south)
        & (ds["lat"] <= bbox.north)
        & (ds["lon"] >= bbox.west)
        & (ds["lon"] <= bbox.east)
    )
    # Find bounding indices in x/y.
    ys, xs = np.where(mask)
    if len(ys) == 0:
        return ds.isel(y=slice(0, 0), x=slice(0, 0))
    y0, y1 = int(ys.min()), int(ys.max())
    x0, x1 = int(xs.min()), int(xs.max())
    return ds.isel(y=slice(y0, y1 + 1), x=slice(x0, x1 + 1))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", default="2020-01-01")
    parser.add_argument("--end", default="2020-12-31")
    parser.add_argument("--limit", type=int, default=None,
                        help="Limit number of days (for smoke tests)")
    args = parser.parse_args()

    region = load_region()
    bb = region.bounding_box
    logger.info("Region %s | bbox S=%.1f N=%.1f W=%.1f E=%.1f",
                region.region_name, bb.south, bb.north, bb.west, bb.east)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    username, password = load_env()
    token = get_earthdata_token(username, password)
    logger.info("Earthdata token acquired")

    granule_dates = cmr_daily_urls(token, args.start, args.end)
    if args.limit:
        granule_dates = granule_dates[: args.limit]
    logger.info("Downloading %d daily files", len(granule_dates))

    raw_files = []
    for date_str, url in granule_dates:
        dest = RAW_DIR / f"NSIDC0051_{date_str}_v2.0.nc"
        download_daily(url, token, dest)
        raw_files.append(dest)

    # Process each raw file and concatenate over time.
    processed = []
    for f in raw_files:
        ds = process_one(f)
        ds = add_latlon(ds)
        ds = clip_to_bbox(ds, bb)
        # Set a time coordinate from filename date (keep original time, concat will use it).
        pass
        processed.append(ds)

    if not processed:
        logger.warning("No daily granules processed.")
        return

    combined = xr.concat(processed, dim="time")
    out_file = PROCESSED_DIR / f"east_prydz_bay_sea_ice_concentration_{args.start}_{args.end}.nc"
    combined.to_netcdf(out_file)
    logger.info("Saved processed -> %s", out_file)
    logger.info("Shape: %s", dict(combined.sizes))

    # Metadata JSON
    meta = {
        "provider": "NASA NSIDC DAAC (Earthdata Cloud)",
        "product": "NSIDC-0051 v2.0",
        "variables": ["sea_ice_concentration"],
        "units": "fraction (0.0-1.0), flags 251-254",
        "crs": "EPSG:3412 (polar stereographic south, 25 km)",
        "spatial_bounds": {"south": bb.south, "north": bb.north, "west": bb.west, "east": bb.east},
        "temporal_range": {"start": args.start, "end": args.end},
        "acquisition_date": datetime.utcnow().isoformat(),
        "n_raw_files": len(raw_files),
        "n_processed_files": 1,
        "raw_dir": str(RAW_DIR),
        "processed_file": str(out_file),
    }
    meta_file = PROCESSED_DIR / f"east_prydz_bay_sea_ice_metadata.json"
    meta_file.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    logger.info("Saved metadata -> %s", meta_file)

    # Validation summary
    siconc = combined["sea_ice_concentration"]
    logger.info("=== VALIDATION ===")
    logger.info("Time steps: %d", combined.sizes["time"])
    logger.info("Valid concentration cells: %d", int(np.isfinite(siconc).sum()))
    logger.info("Concentration range in box: %.3f .. %.3f",
                float(siconc.min()), float(siconc.max()))
    logger.info("Flagged (coast/land/pole) cells: %d",
                int(np.isnan(combined["sea_ice_concentration"]).sum()))


if __name__ == "__main__":
    main()
