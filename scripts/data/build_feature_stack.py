#!/usr/bin/env python3
"""
Build the harmonised 2020 forcing/feature stack for East Prydz Bay.

Merges:
  1. NSIDC-0051 sea-ice concentration (daily → hourly, reprojected)
  2. ERA5 atmospheric forcing (hourly, standardised)
  3. GEBCO bathymetry (static, coarsened to 0.25°, broadcast hourly)
  4. GLORYS12V1 ocean currents (daily → hourly, resampled to 0.25°)

Output:
  data/processed/integration/east_prydz_bay_2020_feature_stack.nc
  data/processed/integration/east_prydz_bay_2020_feature_stack_metadata.json

Usage:
    python scripts/data/build_feature_stack.py
"""

from __future__ import annotations

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
    ERA5_RENAME,
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

# Source processed files (verified in Phase 2 Step 2 audit)
SEA_ICE_PATH = PROCESSED / "sea_ice" / "east_prydz_bay_sea_ice_concentration_2020-01-01_2020-12-31.nc"
ERA5_PATH = PROCESSED / "weather" / "east_prydz_bay_era5_2020-01-01_2020-12-31.nc"
BATHY_PATH = PROCESSED / "bathymetry" / "east_prydz_bay_bathymetry_15arcsec.nc"
ICEBERG_PATH = PROCESSED / "icebergs" / "east_prydz_bay_icebergs.csv"
GLORYS_PATH = RAW / "ocean" / "glorys" / "cmems_mod_glo_phy_my_0.083deg_P1D-m_1788490478516.nc"

INTEGRATION_DIR = PROCESSED / "integration"
OUT_NC = INTEGRATION_DIR / "east_prydz_bay_2020_feature_stack.nc"
OUT_JSON = INTEGRATION_DIR / "east_prydz_bay_2020_feature_stack_metadata.json"


def check_inputs() -> None:
    """Verify all source files exist before starting processing."""
    required = {
        "Sea ice": SEA_ICE_PATH,
        "ERA5": ERA5_PATH,
        "Bathymetry": BATHY_PATH,
        "Iceberg tracks": ICEBERG_PATH,
        "GLORYS ocean": GLORYS_PATH,
    }
    missing = [name for name, path in required.items() if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Missing required input files: {missing}")
    logger.info("All input files verified present.")


def check_disk_space() -> None:
    """Log available disk space before expensive operations."""
    import shutil
    usage = shutil.disk_usage(str(PROJECT_ROOT))
    free_gb = usage.free / (1024**3)
    logger.info("Disk free: %.1f GB", free_gb)
    if free_gb < 2.0:
        logger.warning("Less than 2 GB free — feature stack is ~40 MB, should be fine.")


def build_feature_stack() -> xr.Dataset:
    """
    Main assembly pipeline.

    Returns the merged xarray Dataset with all gridded features on the
    common 0.25° hourly grid.
    """
    logger.info("=" * 60)
    logger.info("STEP 1: Define common grid from ERA5")
    logger.info("=" * 60)
    grid = get_common_grid(ERA5_PATH)
    target_lat = grid["lat"].values
    target_lon = grid["lon"].values

    logger.info("=" * 60)
    logger.info("STEP 2: Standardise ERA5 (rename dims/vars)")
    logger.info("=" * 60)
    era5 = standardise_era5(ERA5_PATH)
    logger.info("ERA5 time range: %s → %s (%d steps)",
                era5.time.values[0], era5.time.values[-1], len(era5.time))

    logger.info("=" * 60)
    logger.info("STEP 3: Reproject sea ice (polar-stereo → 0.25° lat/lon)")
    logger.info("=" * 60)
    siconc_hourly = reproject_sea_ice(SEA_ICE_PATH, target_lat, target_lon)
    logger.info("Sea ice after reproject+ffill: %s", dict(siconc_hourly.sizes))

    logger.info("=" * 60)
    logger.info("STEP 4: Coarsen bathymetry (15 arc-sec → 0.25°)")
    logger.info("=" * 60)
    bathy = coarsen_bathymetry(BATHY_PATH, target_lat, target_lon)
    logger.info("Bathymetry coarsened: %s", dict(bathy.sizes))

    # Broadcast bathymetry across time to match ERA5's time axis
    logger.info("Broadcasting bathymetry across %d time steps...", len(era5.time))
    bathy_time = bathy.expand_dims(time=era5.time)

    logger.info("=" * 60)
    logger.info("STEP 5: Resample GLORYS ocean currents (1/12° daily → 0.25° hourly)")
    logger.info("=" * 60)
    glorys = resample_glorys(GLORYS_PATH, target_lat, target_lon, variables=["uo", "vo"])
    logger.info("GLORYS ocean currents resampled: %s", dict(glorys.sizes))

    logger.info("=" * 60)
    logger.info("STEP 6: Merge all features into single Dataset")
    logger.info("=" * 60)
    # Ensure all datasets share the same lat/lon/time coords
    # ERA5 defines the canonical coordinates
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

    # Add CF-compliant attributes
    merged.attrs.update({
        "title": "East Prydz Bay 2020 Harmonised Feature Stack",
        "institution": "Prototype-1 SIH Antarctic Navigation DSS",
        "source": "NSIDC-0051 v2.0, ERA5 reanalysis, GEBCO_2024, GLORYS12V1",
        "processing_date": datetime.now(timezone.utc).isoformat(),
        "region": "East Prydz Bay (S -70.0, N -66.0, W 72.0, E 80.0)",
        "crs": "EPSG:4326 (WGS 84)",
        "spatial_resolution": "0.25 degrees (~31 km)",
        "temporal_resolution": "hourly",
        "temporal_range": "2020-01-01T00:00 to 2020-12-31T23:00 UTC",
        "leap_year": "2020 is a leap year (366 days, 8784 hours)",
        "conventions": "CF-1.8",
        "feature_count": "9 gridded variables (7 atmospheric/ice + 2 ocean currents)",
        "glorys_status": "INCLUDED — GLORYS12V1 ocean currents (uo, vo) acquired via manual CMEMS download and integrated (1/12° daily → 0.25° hourly, nearest-neighbor). ocean_current_u, ocean_current_v present in stack.",
        "missing_data": "sea_ice_concentration and ocean_current_u/v have NaN over land/coast/pole-hole mask (~35% of grid cells for sea ice; ~23.8% for ocean). All atmospheric variables have 0% missing values.",
        "processing_notes": [
            "Sea ice: nearest-neighbor reprojection from EPSG:3412, forward-fill daily→hourly",
            "ERA5: dimension/variable rename only (no interpolation)",
            "Bathymetry: spatial mean coarsen 15 arc-sec→0.25° + linear interp",
            "GLORYS: nearest-neighbor resample 1/12°→0.25°, squeeze depth, forward-fill daily→hourly",
            "All raw and previously-processed files preserved unchanged",
        ],
    })

    logger.info("Merged dataset: %s", dict(merged.sizes))
    logger.info("Variables: %s", list(merged.data_vars))
    return merged


def save_outputs(ds: xr.Dataset) -> None:
    """Write the feature stack to NetCDF and companion metadata JSON."""
    INTEGRATION_DIR.mkdir(parents=True, exist_ok=True)

    # Write NetCDF
    logger.info("Writing NetCDF: %s ...", OUT_NC)
    ds.to_netcdf(OUT_NC)
    size_mb = OUT_NC.stat().st_size / 1e6
    logger.info("  Saved (%.2f MB)", size_mb)

    # Write metadata JSON
    meta = {
        "provider": "Multi-source (NSIDC + ECMWF + GEBCO)",
        "product": "East Prydz Bay 2020 Harmonised Feature Stack",
        "version": "1.0",
        "processing_date": datetime.now(timezone.utc).isoformat(),
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
            "leap_year_2020": True,
        },
        "variables": {},
        "source_files": {
            "sea_ice": str(SEA_ICE_PATH),
            "era5": str(ERA5_PATH),
            "bathymetry": str(BATHY_PATH),
            "icebergs": str(ICEBERG_PATH),
            "glorys": str(GLORYS_PATH),
        },
        "variable_mapping": {
            "sea_ice_concentration": {"source": "NSIDC-0051", "original": "sea_ice_concentration", "unit": "fraction (0-1)", "processing": "nearest-neighbor reproject + ffill daily→hourly"},
            "wind_u_10m": {"source": "ERA5", "original": "u10", "unit": "m s-1", "processing": "rename only"},
            "wind_v_10m": {"source": "ERA5", "original": "v10", "unit": "m s-1", "processing": "rename only"},
            "temperature_2m": {"source": "ERA5", "original": "t2m", "unit": "K", "processing": "rename only"},
            "mean_sea_level_pressure": {"source": "ERA5", "original": "msl", "unit": "Pa", "processing": "rename only"},
            "total_precipitation": {"source": "ERA5", "original": "tp", "unit": "m", "processing": "rename only"},
            "bathymetry_elevation": {"source": "GEBCO_2024", "original": "elevation", "unit": "m", "processing": "coarsen 15 arc-sec→0.25° + linear interp + broadcast across time"},
            "ocean_current_u": {"source": "GLORYS12V1", "original": "uo", "unit": "m s-1", "processing": "nearest-neighbor resample 1/12°→0.25° + squeeze depth + ffill daily→hourly"},
            "ocean_current_v": {"source": "GLORYS12V1", "original": "vo", "unit": "m s-1", "processing": "nearest-neighbor resample 1/12°→0.25° + squeeze depth + ffill daily→hourly"},
        },
        "glorys": {
            "status": "INCLUDED",
            "source": "CMEMS GLORYS12V1 (manual download via Marine Data Store, 2026-09-04)",
            "file": str(GLORYS_PATH),
            "original_variables": ["uo", "vo"],
            "feature_names": ["ocean_current_u", "ocean_current_v"],
            "resolution": "1/12 deg daily → 0.25 deg hourly",
            "resampling": "nearest-neighbor spatial + forward-fill temporal",
            "note": "Manually downloaded through Copernicus Marine website (not via project download_ocean.py, which remains blocked by CMEMS DNS). uo/vo integrated; thetao/so/other GLORYS vars available in raw file but not merged.",
        },
        "iceberg_tracks": {
            "status": "AVAILABLE (not merged into gridded stack)",
            "file": str(ICEBERG_PATH),
            "note": "Point observations kept as separate tabular dataset; used as target/labels for trajectory models",
        },
        "missing_value_handling": {
            "sea_ice_concentration": "NaN preserved over land/coast/pole-hole mask (~35% of cells). Not interpolated.",
            "ocean_current_u": "NaN preserved over land mask (~23.8% of cells, from GLORYS source). Not interpolated.",
            "ocean_current_v": "NaN preserved over land mask (~23.8% of cells, from GLORYS source). Not interpolated.",
            "atmospheric_variables": "0% missing values in source",
            "bathymetry": "0% missing values; land points have positive elevation",
        },
    }

    # Per-variable stats
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

    OUT_JSON.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    logger.info("Metadata saved: %s", OUT_JSON)


def main() -> None:
    logger.info("Phase 2 Step 3: Feature Stack Assembly")
    logger.info("Region: East Prydz Bay | Window: 2020-01-01 → 2020-12-31")
    logger.info("")

    check_inputs()
    check_disk_space()

    # Idempotent: skip if output already exists and is valid
    if OUT_NC.exists() and OUT_NC.stat().st_size > 1e6:
        logger.info("Feature stack already exists: %s (%.2f MB)",
                     OUT_NC.name, OUT_NC.stat().st_size / 1e6)
        logger.info("Delete it to force rebuild. Exiting.")
        return

    ds = build_feature_stack()
    save_outputs(ds)

    logger.info("")
    logger.info("=" * 60)
    logger.info("FEATURE STACK ASSEMBLY COMPLETE")
    logger.info("=" * 60)
    logger.info("Output: %s", OUT_NC)
    logger.info("Size: %.2f MB", OUT_NC.stat().st_size / 1e6)
    logger.info("Dims: %s", dict(ds.sizes))
    logger.info("Variables: %s", list(ds.data_vars))
    logger.info("GLORYS: INCLUDED (ocean_current_u, ocean_current_v)")


if __name__ == "__main__":
    main()
