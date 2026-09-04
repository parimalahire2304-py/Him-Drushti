#!/usr/bin/env python3
"""
Download and process ERA5 weather reanalysis for the East Prydz Bay region.

Dataset: ERA5 atmospheric reanalysis (single levels), ~0.25 degrees.
Access: ECMWF Climate Data Store (CDS) via the cdsapi Python package.
Credentials are provided via CDS_API_URL and CDS_API_KEY in .env.

Variables (focused set for iceberg-drift forcing):
  - 10m U/V wind components (10m_u_component_of_wind, 10m_v_component_of_wind)
  - 2m temperature (2m_temperature)
  - Mean sea level pressure (mean_sea_level_pressure)
  - Total precipitation (total_precipitation)

The request is subset to the East Prydz Bay bounding box read from
config/region.yaml (CDS area = [north, west, south, east]).

Temporal strategy: for the 2020 prototype window, request monthly in a
loop (one NetCDF per month) to keep the CDS reply size manageable.

Usage:
    python scripts/data/download_weather.py [--start YYYY-MM-DD] [--end YYYY-MM-DD]

Reads region bbox from config/region.yaml (do-not-hardcode).
"""

from __future__ import annotations

import argparse
import json
import logging
import os
from datetime import datetime
from pathlib import Path

import xarray as xr

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.utils.region import load_region

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

RAW_DIR = Path(__file__).resolve().parents[2] / "data" / "raw" / "weather"
PROCESSED_DIR = Path(__file__).resolve().parents[2] / "data" / "processed" / "weather"

SHORT_NAMES = [
    "10m_u_component_of_wind",
    "10m_v_component_of_wind",
    "2m_temperature",
    "mean_sea_level_pressure",
    "total_precipitation",
]

# CDS returns these as the variable short names in the delivered NetCDFs
# (instant step-type -> u10/v10/t2m/msl; accumulated step-type -> tp).
OUTPUT_VARS = ["u10", "v10", "t2m", "msl", "tp"]


def check_creds() -> None:
    """Fail fast if the CDS credentials are absent (never print them)."""
    if not os.getenv("CDS_API_KEY"):
        raise RuntimeError(
            "CDS_API_KEY not set. Register at https://cds.climate.copernicus.eu "
            "and set CDS_API_URL / CDS_API_KEY in .env."
        )


def cds_client():
    """Create a cdsapi.Client (load .env via python-dotenv if present)."""
    try:
        from dotenv import load_dotenv

        load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    except ImportError:
        pass
    check_creds()
    import cdsapi

    # cdsapi reads ~/.cdsapirc if set; otherwise use the URL/KEY env fallback.
    # Explicitly point it at the right URL if one is configured.
    import os as _os

    c = cdsapi.Client(url=_os.getenv("CDS_API_URL") or "https://cds.climate.copernicus.eu/api",
                      key=_os.getenv("CDS_API_KEY"))
    return c


def request_month(  # type: ignore[no-untyped-def]
    c,  # cdsapi.Client
    year: int,
    month: int,
    bbox,
    raw_dest: Path,
) -> Path:
    """
    Retrieve one month of ERA5 hourly data for the bbox to raw_dest.

    Per ECMWF/ERA5 guidance, hourly retrieval converges more reliably as
    single-month slices than a 12-month bulk request.
    """
    if raw_dest.exists() and raw_dest.stat().st_size > 0:
        logger.info("Skipping (already present): %s", raw_dest.name)
        return raw_dest
    area = [bbox.north, bbox.west, bbox.south, bbox.east]  # CDS order: N, W, S, E
    logger.info("Requesting %04d-%02d (area %s) ...", year, month, area)
    c.retrieve(
        "reanalysis-era5-single-levels",
        {
            "product_type": "reanalysis",
            "variable": SHORT_NAMES,
            "year": f"{year}",
            "month": f"{month:02d}",
            "day": [f"{d:02d}" for d in range(1, 32)],
            "time": [f"{h:02d}:00" for h in range(24)],
            "area": area,
            "format": "netcdf",
        },
        str(raw_dest),
    )
    logger.info("Saved %s (%.2f MB)", raw_dest.name, raw_dest.stat().st_size / 1e6)
    return raw_dest


def _read_month(raw_path: Path) -> xr.Dataset:
    """
    Open one monthly raw ERA5 file into a single Dataset.

    When a CDS request mixes instantaneous and accumulated step-types, CDS
    returns a ZIP archive containing one NetCDF per step-type (instant ->
    u10/v10/t2m/msl; accum -> tp), saved to disk with a '.nc' extension.
    Detect the ZIP magic bytes, extract the inner NetCDFs to a temp dir, and
    merge them on the shared valid_time/latitude/longitude grid. Plain single
    NetCDF responses are opened directly.
    """
    import io
    import tempfile
    import zipfile

    data = raw_path.read_bytes()
    if data[:2] != b"PK":  # not a ZIP -> single NetCDF
        return xr.open_dataset(raw_path)

    with tempfile.TemporaryDirectory() as td:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            for name in z.namelist():
                if name.endswith(".nc"):
                    z.extract(name, td)
        inner = sorted(Path(td).rglob("*.nc"))
        if not inner:
            raise ValueError(f"No NetCDF inside ZIP archive: {raw_path.name}")
        dsets = []
        for p in inner:
            ds = xr.open_dataset(p)
            ds.load()  # materialise arrays so the file can be closed on Windows
            ds.close()
            dsets.append(ds)
    return xr.merge(dsets, compat="override")


def process_months_to_combined(
    raw_files: list[Path],
    start: str,
    end: str,
    bbox,
) -> Path:
    """Concatenate raw monthly NetCDFs over time and save the 2020 combined product."""
    dsets = []
    for p in sorted(raw_files):
        if not p.exists() or p.stat().st_size == 0:
            logger.warning("Missing/empty %s — skipping", p.name)
            continue
        ds = _read_month(p)
        dsets.append(ds)
    if not dsets:
        raise ValueError("No monthly ERA5 files found.")
    combined = xr.concat(dsets, dim="valid_time" if "valid_time" in dsets[0] else "time")

    out = PROCESSED_DIR / f"east_prydz_bay_era5_{start}_{end}.nc"
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    combined.to_netcdf(out)
    logger.info("Saved processed -> %s (%.2f MB)", out, out.stat().st_size / 1e6)
    logger.info("Dims: %s", dict(combined.sizes))
    for name in OUTPUT_VARS:
        if name in combined:
            data = combined[name]
            logger.info("  %s units=%s shape=%s range %.3g .. %.3g",
                        name, data.attrs.get("units", "?"), tuple(data.dims),
                        float(data.min()), float(data.max()))
    return out


def write_metadata(
    start: str, end: str, bbox, raw_files: list[Path], processed_file: Path
) -> Path:
    meta = {
        "provider": "ECMWF / Climate Data Store (CDS)",
        "product": "reanalysis-era5-single-levels (reanalysis)",
        "variables": OUTPUT_VARS,
        "units": "m/s (u10,v10), K (t2m), Pa (msl), m (tp)",
        "crs": "EPSG:4326 (regular lat/lon, 0.25 deg)",
        "spatial_bounds": {"south": bbox.south, "north": bbox.north, "west": bbox.west, "east": bbox.east},
        "temporal_range": {"start": start, "end": end},
        "acquisition_date": datetime.utcnow().isoformat(),
        "n_raw_files": len(raw_files),
        "raw_dir": str(RAW_DIR),
        "processed_file": str(processed_file),
    }
    dest = PROCESSED_DIR / f"east_prydz_bay_era5_metadata.json"
    dest.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    logger.info("Saved metadata -> %s", dest)
    return dest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", default="2020-01-01")
    parser.add_argument("--end", default="2020-12-31")
    parser.add_argument("--smoke", action="store_true",
                        help="Download only January 2020 (small smoke test)")
    args = parser.parse_args()

    region = load_region()
    bb = region.bounding_box
    logger.info("Region %s | bbox S=%.1f N=%.1f W=%.1f E=%.1f",
                region.region_name, bb.south, bb.north, bb.west, bb.east)

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    sy, sm, _ = map(int, args.start.split("-"))
    ey, em, _ = map(int, args.end.split("-"))

    if args.smoke:
        ey, em = sy, sm  # single month

    months = []
    y, m = sy, sm
    while (y, m) <= (ey, em):
        months.append((y, m))
        m += 1
        if m > 12:
            m = 1
            y += 1

    c = cds_client()

    raw_files: list[Path] = []
    for (y, m) in months:
        raw_dest = RAW_DIR / f"ERA5_{y:04d}-{m:02d}_east_prydz_bay.nc"
        try:
            request_month(c, y, m, bb, raw_dest)
        except Exception as exc:
            logger.error("Failed %04d-%02d: %s", y, m, exc)
            raise
        raw_files.append(raw_dest)

    combined_path = process_months_to_combined(raw_files, args.start, args.end, bb)
    write_metadata(args.start, args.end, bb, raw_files, combined_path)


if __name__ == "__main__":
    main()
