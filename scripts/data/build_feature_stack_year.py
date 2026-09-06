#!/usr/bin/env python3
"""
Build a per-year harmonised forcing/feature stack for East Prydz Bay.

Merges (mirroring the Phase 2 Step 3 2020 stack, but parameterised by year):
  1. NSIDC-0051 sea-ice concentration (daily → hourly, reprojected)
  2. ERA5 atmospheric forcing (hourly, standardised)
  3. GEBCO bathymetry (static, coarsened to 0.25°, broadcast hourly)
  4. GLORYS12V1 ocean currents (daily → hourly, resampled to 0.25°)

The 2020 baseline stack is READ-ONLY and never overwritten. This script
writes year-suffixed outputs, e.g. east_prydz_bay_2019_feature_stack.nc.

Usage:
    python scripts/data/build_feature_stack_year.py --year 2019
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import xarray as xr

# Ensure project root is on the path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.preprocessing.gridding import (
    coarsen_bathymetry,
    get_common_grid,
    reproject_sea_ice,
    resample_glorys,
    standardise_era5,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW = PROJECT_ROOT / "data" / "raw"
PROCESSED = PROJECT_ROOT / "data" / "processed"

# Static bathymetry (reused across all years; never re-downloaded)
BATHY_PATH = PROCESSED / "bathymetry" / "east_prydz_bay_bathymetry_15arcsec.nc"
ICEBERG_PATH = PROCESSED / "icebergs" / "east_prydz_bay_icebergs.csv"

INTEGRATION_DIR = PROCESSED / "integration"


def _find_era5(year: int) -> Path:
    """Locate the processed ERA5 combined file for a year."""
    candidates = [
        PROCESSED / "weather" / f"east_prydz_bay_era5_{year}-01-01_{year}-12-31.nc",
        PROCESSED / "weather" / f"east_prydz_bay_era5_{year}-01-01_{year}-12-31.nc",
    ]
    for c in candidates:
        if c.exists():
            return c
    raise FileNotFoundError(
        f"ERA5 processed file for {year} not found. Run download_weather.py "
        f"--start {year}-01-01 --end {year}-12-31 first."
    )


def _find_sea_ice(year: int) -> Path:
    """Locate the processed NSIDC combined file for a year."""
    for pat in [f"east_prydz_bay_sea_ice_concentration_{year}-01-01_{year}-12-31.nc"]:
        hits = list(PROCESSED.glob(f"sea_ice/{pat}"))
        if hits:
            return hits[0]
    raise FileNotFoundError(
        f"NSIDC sea-ice processed file for {year} not found. Run "
        f"download_sea_ice.py --start {year}-01-01 --end {year}-12-31 first."
    )


def _find_glorys(year: int) -> Path:
    """Locate the raw GLORYS file for a year (prefer year-suffixed download)."""
    # Prefer the year-suffixed download produced by download_glorys.py
    yr_file = RAW / "ocean" / "glorys" / f"glorys12v1_east_prydz_bay_{year}.nc"
    if yr_file.exists():
        return yr_file
    # Fall back to the 2020 file if no year-specific one exists
    fallback = list((RAW / "ocean" / "glorys").glob("cmems_mod_glo_phy_my_0.083deg_P1D-m_*.nc"))
    if fallback:
        logger.warning(
            "No year-specific GLORYS file for %s; falling back to %s. "
            "Ensure it covers %s.",
            year, fallback[0].name, year,
        )
        return fallback[0]
    raise FileNotFoundError(
        f"GLORYS ocean file for {year} not found. Run download_glorys.py "
        f"--start {year}-01-01 --end {year}-12-31 first."
    )


def check_inputs(year: int) -> dict[str, Path]:
    """Verify all source files exist before starting processing."""
    paths = {
        "era5": _find_era5(year),
        "sea_ice": _find_sea_ice(year),
        "glorys": _find_glorys(year),
        "bathymetry": BATHY_PATH,
        "icebergs": ICEBERG_PATH,
    }
    missing = [name for name, path in paths.items() if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Missing required input files: {missing}")
    logger.info("All input files verified present for %s:", year)
    for name, path in paths.items():
        logger.info("  %-10s %s", name, path.name)
    return paths


def build_feature_stack(year: int, paths: dict[str, Path]) -> xr.Dataset:
    """Main assembly pipeline for a single year."""
    logger.info("=" * 60)
    logger.info("STEP 1: Define common grid from ERA5 (%s)", year)
    logger.info("=" * 60)
    grid = get_common_grid(paths["era5"])
    target_lat = grid["lat"].values
    target_lon = grid["lon"].values

    logger.info("=" * 60)
    logger.info("STEP 2: Standardise ERA5 (rename dims/vars)")
    logger.info("=" * 60)
    era5 = standardise_era5(paths["era5"])
    logger.info("ERA5 time range: %s → %s (%d steps)",
                era5.time.values[0], era5.time.values[-1], len(era5.time))

    logger.info("=" * 60)
    logger.info("STEP 3: Reproject sea ice (polar-stereo → 0.25° lat/lon)")
    logger.info("=" * 60)
    siconc_hourly = reproject_sea_ice(paths["sea_ice"], target_lat, target_lon)
    logger.info("Sea ice after reproject+ffill: %s", dict(siconc_hourly.sizes))

    logger.info("=" * 60)
    logger.info("STEP 4: Coarsen bathymetry (15 arc-sec → 0.25°)")
    logger.info("=" * 60)
    bathy = coarsen_bathymetry(paths["bathymetry"], target_lat, target_lon)
    logger.info("Bathymetry coarsened: %s", dict(bathy.sizes))

    # Broadcast bathymetry across time to match ERA5's time axis
    logger.info("Broadcasting bathymetry across %d time steps...", len(era5.time))
    bathy_time = bathy.expand_dims(time=era5.time)

    logger.info("=" * 60)
    logger.info("STEP 5: Resample GLORYS ocean currents (1/12° daily → 0.25° hourly)")
    logger.info("=" * 60)
    glorys = resample_glorys(paths["glorys"], target_lat, target_lon, variables=["uo", "vo"])
    logger.info("GLORYS ocean currents resampled: %s", dict(glorys.sizes))

    logger.info("=" * 60)
    logger.info("STEP 6: Merge all features into single Dataset")
    logger.info("=" * 60)
    merged = xr.Dataset(
        {
            "sea_ice_concentration": siconc_hourly,
            "wind_u_10m": era5["wind_u_10m"],
            "wind_v_10m": era5["wind_v_10m"],
            "temperature_2m": era5["temperature_2m"],
            "mean_sea_level_pressure": era5["mean_sea_level_pressure"],
            "total_precipitation": era5["total_precipitation"],
            "bathymetry_elevation": bathy_time,
            "ocean_current_u": glorys["ocean_current_u"],
            "ocean_current_v": glorys["ocean_current_v"],
        },
        coords={
            "time": era5.time,
            "lat": era5.lat,
            "lon": era5.lon,
        },
    )

    is_leap = (year % 4 == 0) and (year % 100 != 0 or year % 400 == 0)
    merged.attrs.update({
        "title": f"East Prydz Bay {year} Harmonised Feature Stack",
        "institution": "Prototype-1 SIH Antarctic Navigation DSS",
        "source": "NSIDC-0051 v2.0, ERA5 reanalysis, GEBCO_2024, GLORYS12V1",
        "processing_date": datetime.now(timezone.utc).isoformat(),
        "region": "East Prydz Bay (S -70.0, N -66.0, W 72.0, E 80.0)",
        "crs": "EPSG:4326 (WGS 84)",
        "spatial_resolution": "0.25 degrees (~31 km)",
        "temporal_resolution": "hourly",
        "temporal_range": f"{year}-01-01T00:00 to {year}-12-31T23:00 UTC",
        "leap_year": f"{year} {'is' if is_leap else 'is NOT'} a leap year ({366 if is_leap else 365} days, {8784 if is_leap else 8760} hours)",
        "conventions": "CF-1.8",
        "feature_count": "9 gridded variables (7 atmospheric/ice + 2 ocean currents)",
        "glorys_status": "INCLUDED — GLORYS12V1 ocean currents (uo, vo)",
        "missing_data": "sea_ice_concentration and ocean_current_u/v have NaN over land/coast/pole-hole mask; atmospheric variables 0% missing.",
        "baseline": "Mirrors east_prydz_bay_2020_feature_stack.nc (Phase 2 Step 3). 2020 baseline NOT modified.",
    })
    logger.info("Merged dataset: %s", dict(merged.sizes))
    logger.info("Variables: %s", list(merged.data_vars))
    return merged


def save_outputs(ds: xr.Dataset, year: int, paths: dict[str, Path]) -> None:
    """Write the year feature stack to NetCDF and companion metadata JSON."""
    INTEGRATION_DIR.mkdir(parents=True, exist_ok=True)
    out_nc = INTEGRATION_DIR / f"east_prydz_bay_{year}_feature_stack.nc"
    out_json = INTEGRATION_DIR / f"east_prydz_bay_{year}_feature_stack_metadata.json"

    logger.info("Writing NetCDF: %s ...", out_nc)
    ds.to_netcdf(out_nc)
    size_mb = out_nc.stat().st_size / 1e6
    logger.info("  Saved (%.2f MB)", size_mb)

    is_leap = (year % 4 == 0) and (year % 100 != 0 or year % 400 == 0)
    meta = {
        "provider": "Multi-source (NSIDC + ECMWF + GEBCO + CMEMS)",
        "product": f"East Prydz Bay {year} Harmonised Feature Stack",
        "version": "1.0",
        "processing_date": datetime.now(timezone.utc).isoformat(),
        "baseline_note": "2020 baseline stack east_prydz_bay_2020_feature_stack.nc is read-only and unchanged.",
        "spatial_grid": {
            "crs": "EPSG:4326",
            "resolution_deg": 0.25,
            "lat_range": [float(ds.lat.min()), float(ds.lat.max())],
            "lon_range": [float(ds.lon.min()), float(ds.lon.max())],
            "n_lat": int(ds.sizes["lat"]),
            "n_lon": int(ds.sizes["lon"]),
            "grid_cells": int(ds.sizes["lat"] * ds.sizes["lon"]),
        },
        "temporal_grid": {
            "frequency": "hourly",
            "start": str(ds.time.values[0]),
            "end": str(ds.time.values[-1]),
            "n_steps": int(ds.sizes["time"]),
            "timezone": "UTC",
            "leap_year": is_leap,
        },
        "variables": {},
        "source_files": {
            "sea_ice": str(paths["sea_ice"]),
            "era5": str(paths["era5"]),
            "bathymetry": str(paths["bathymetry"]),
            "icebergs": str(paths["icebergs"]),
            "glorys": str(paths["glorys"]),
        },
        "variable_mapping": {
            "sea_ice_concentration": {"source": "NSIDC-0051", "original": "sea_ice_concentration", "unit": "fraction (0-1)", "processing": "nearest-neighbor reproject + ffill daily→hourly"},
            "wind_u_10m": {"source": "ERA5", "original": "u10", "unit": "m s-1", "processing": "rename only"},
            "wind_v_10m": {"source": "ERA5", "original": "v10", "unit": "m s-1", "processing": "rename only"},
            "temperature_2m": {"source": "ERA5", "original": "t2m", "unit": "K", "processing": "rename only"},
            "mean_sea_level_pressure": {"source": "ERA5", "original": "msl", "unit": "Pa", "processing": "rename only"},
            "total_precipitation": {"source": "ERA5", "original": "tp", "unit": "m", "processing": "rename only"},
            "bathymetry_elevation": {"source": "GEBCO_2024", "original": "elevation", "unit": "m", "processing": "coarsen 15 arc-sec→0.25° + broadcast across time"},
            "ocean_current_u": {"source": "GLORYS12V1", "original": "uo", "unit": "m s-1", "processing": "nearest-neighbor resample 1/12°→0.25° + ffill daily→hourly"},
            "ocean_current_v": {"source": "GLORYS12V1", "original": "vo", "unit": "m s-1", "processing": "nearest-neighbor resample 1/12°→0.25° + ffill daily→hourly"},
        },
        "missing_value_handling": {
            "sea_ice_concentration": "NaN preserved over land/coast/pole-hole mask. Not interpolated.",
            "ocean_current_u": "NaN preserved over land mask. Not interpolated.",
            "ocean_current_v": "NaN preserved over land mask. Not interpolated.",
            "atmospheric_variables": "0% missing values in source",
            "bathymetry": "0% missing values; land points have positive elevation",
        },
    }

    for var in ds.data_vars:
        data = ds[var]
        total = data.size
        nan_count = int(np.isnan(data).values.sum())
        nan_pct = nan_count / total * 100
        meta["variables"][var] = {
            "dims": list(data.dims),
            "shape": list(data.shape),
            "dtype": str(data.dtype),
            "units": data.attrs.get("units", "?"),
            "nan_count": nan_count,
            "nan_pct": round(nan_pct, 2),
            "min": float(np.nanmin(data.values)),
            "max": float(np.nanmax(data.values)),
            "mean": float(np.nanmean(data.values)),
        }

    out_json.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    logger.info("Metadata saved: %s", out_json)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, required=True, help="Calendar year, e.g. 2019")
    args = parser.parse_args()
    year = args.year

    logger.info("Phase 3A: Feature Stack Assembly for %s", year)
    logger.info("Region: East Prydz Bay | Window: %s-01-01 → %s-12-31", year, year)

    paths = check_inputs(year)

    out_nc = INTEGRATION_DIR / f"east_prydz_bay_{year}_feature_stack.nc"
    if out_nc.exists() and out_nc.stat().st_size > 1e6:
        logger.info("Feature stack already exists: %s (%.2f MB)",
                     out_nc.name, out_nc.stat().st_size / 1e6)
        logger.info("Delete it to force rebuild. Exiting.")
        return

    ds = build_feature_stack(year, paths)
    save_outputs(ds, year, paths)

    logger.info("")
    logger.info("=" * 60)
    logger.info("FEATURE STACK ASSEMBLY COMPLETE (%s)", year)
    logger.info("=" * 60)
    logger.info("Output: %s", out_nc)
    logger.info("Size: %.2f MB", out_nc.stat().st_size / 1e6)
    logger.info("Dims: %s", dict(ds.sizes))
    logger.info("Variables: %s", list(ds.data_vars))
    logger.info("GLORYS: INCLUDED (ocean_current_u, ocean_current_v)")


if __name__ == "__main__":
    main()
