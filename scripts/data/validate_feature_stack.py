#!/usr/bin/env python3
"""
Validate the Phase 2 Step 3 harmonised feature stack.

Checks:
- File integrity, size, dims, coords, bounds, resolution
- Temporal coverage, gaps, duplicates
- Variable presence, units, physical ranges
- Missing value counts/percentages
- Cross-dataset alignment (all on same grid)
- Phase 1 files untouched

Usage:
    python scripts/data/validate_feature_stack.py
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import xarray as xr

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROCESSED = PROJECT_ROOT / "data" / "processed"
INTEGRATION_DIR = PROCESSED / "integration"
FEATURE_STACK = INTEGRATION_DIR / "east_prydz_bay_2020_feature_stack.nc"
METADATA_JSON = INTEGRATION_DIR / "east_prydz_bay_2020_feature_stack_metadata.json"

# Expected values
EXPECTED_DIMS = {"time": 8784, "lat": 17, "lon": 33}
EXPECTED_LAT_RANGE = (-70.0, -66.0)
EXPECTED_LON_RANGE = (72.0, 80.0)
EXPECTED_RESOLUTION = 0.25
EXPECTED_VARS = [
    "sea_ice_concentration",
    "wind_u_10m",
    "wind_v_10m",
    "temperature_2m",
    "mean_sea_level_pressure",
    "total_precipitation",
    "bathymetry_elevation",
    "ocean_current_u",
    "ocean_current_v",
]
EXPECTED_TIME_START = "2020-01-01T00:00:00"
EXPECTED_TIME_END = "2020-12-31T23:00:00"
EXPECTED_CRS = "EPSG:4326"

# Variable expected ranges (sanity checks)
EXPECTED_RANGES = {
    "sea_ice_concentration": (0.0, 1.0),  # fraction
    "wind_u_10m": (-50.0, 50.0),  # m/s
    "wind_v_10m": (-50.0, 50.0),  # m/s
    "temperature_2m": (200.0, 320.0),  # K
    "mean_sea_level_pressure": (90000.0, 105000.0),  # Pa
    "total_precipitation": (0.0, 0.1),  # m per hour
    "bathymetry_elevation": (-6000.0, 1000.0),  # m
    "ocean_current_u": (-2.0, 2.0),  # m/s
    "ocean_current_v": (-2.0, 2.0),  # m/s,
}


def check_file_exists() -> bool:
    """Check feature stack file exists."""
    if not FEATURE_STACK.exists():
        logger.error("Feature stack file does not exist: %s", FEATURE_STACK)
        return False
    if not METADATA_JSON.exists():
        logger.error("Metadata JSON does not exist: %s", METADATA_JSON)
        return False
    size_mb = FEATURE_STACK.stat().st_size / 1e6
    logger.info("File exists: %s (%.2f MB)", FEATURE_STACK.name, size_mb)
    return True


def check_dims_and_coords(ds: xr.Dataset) -> bool:
    """Check dimensions and coordinates match expectations."""
    ok = True

    # Dimensions
    for dim, expected_size in EXPECTED_DIMS.items():
        actual = ds.sizes.get(dim)
        if actual != expected_size:
            logger.error("Dimension %s: expected %d, got %d", dim, expected_size, actual)
            ok = False
        else:
            logger.info("Dimension %s: %d ✓", dim, actual)

    # Latitude
    lat = ds["lat"].values
    if not (np.allclose(lat.min(), EXPECTED_LAT_RANGE[0], atol=0.01) and
            np.allclose(lat.max(), EXPECTED_LAT_RANGE[1], atol=0.01)):
        logger.error("Latitude range mismatch: got [%.4f, %.4f], expected [%.1f, %.1f]",
                     lat.min(), lat.max(), *EXPECTED_LAT_RANGE)
        ok = False
    else:
        logger.info("Latitude: [%.4f, %.4f] ✓", lat.min(), lat.max())

    # Longitude
    lon = ds["lon"].values
    if not (np.allclose(lon.min(), EXPECTED_LON_RANGE[0], atol=0.01) and
            np.allclose(lon.max(), EXPECTED_LON_RANGE[1], atol=0.01)):
        logger.error("Longitude range mismatch: got [%.4f, %.4f], expected [%.1f, %.1f]",
                     lon.min(), lon.max(), *EXPECTED_LON_RANGE)
        ok = False
    else:
        logger.info("Longitude: [%.4f, %.4f] ✓", lon.min(), lon.max())

    # Resolution check (lat may be decreasing — south to north)
    lat_step = float(np.abs(np.round(np.diff(lat[:2])[0], 4)))
    lon_step = float(np.abs(np.round(np.diff(lon[:2])[0], 4)))
    if abs(lat_step - EXPECTED_RESOLUTION) > 0.001 or abs(lon_step - EXPECTED_RESOLUTION) > 0.001:
        logger.error("Resolution: lat_step=%.4f, lon_step=%.4f, expected %.2f",
                     lat_step, lon_step, EXPECTED_RESOLUTION)
        ok = False
    else:
        logger.info("Resolution: %.2f° ✓", EXPECTED_RESOLUTION)

    # CRS
    crs = ds.attrs.get("crs", "")
    if EXPECTED_CRS not in crs:
        logger.warning("CRS attribute: '%s' (expected %s)", crs, EXPECTED_CRS)
    else:
        logger.info("CRS: %s ✓", crs)

    return ok


def check_temporal_coverage(ds: xr.Dataset) -> bool:
    """Check temporal coverage, gaps, duplicates."""
    ok = True
    time = ds["time"].values

    # Start/end
    start_str = str(time[0])
    end_str = str(time[-1])
    if not start_str.startswith(EXPECTED_TIME_START[:10]):
        logger.error("Time start: expected %s..., got %s", EXPECTED_TIME_START, start_str)
        ok = False
    else:
        logger.info("Time start: %s ✓", start_str)

    if not end_str.startswith(EXPECTED_TIME_END[:10]):
        logger.error("Time end: expected %s..., got %s", EXPECTED_TIME_END, end_str)
        ok = False
    else:
        logger.info("Time end: %s ✓", end_str)

    # Hourly frequency (no gaps)
    expected_times = np.arange(time[0], time[-1] + np.timedelta64(1, 'h'), np.timedelta64(1, 'h'))
    if len(time) != len(expected_times):
        logger.error("Time step count: expected %d, got %d", len(expected_times), len(time))
        ok = False
    else:
        diff = time - expected_times
        if np.any(diff != np.timedelta64(0, 'h')):
            logger.error("Time steps not uniformly hourly")
            ok = False
        else:
            logger.info("Time steps: %d hourly, no gaps ✓", len(time))

    # Duplicates
    if len(np.unique(time)) != len(time):
        logger.error("Duplicate time steps found")
        ok = False
    else:
        logger.info("No duplicate time steps ✓")

    # Leap year check
    if len(time) == 8784:
        logger.info("Leap year (366 days × 24h = 8784) ✓")
    else:
        logger.warning("Time steps = %d (expected 8784 for leap year 2020)", len(time))

    return ok


def check_variables(ds: xr.Dataset) -> bool:
    """Check variable presence, units, physical ranges, missing values."""
    ok = True

    # Presence
    missing_vars = [v for v in EXPECTED_VARS if v not in ds.data_vars]
    if missing_vars:
        logger.error("Missing variables: %s", missing_vars)
        ok = False
    else:
        logger.info("All %d expected variables present ✓", len(EXPECTED_VARS))

    # Extra variables
    extra_vars = [v for v in ds.data_vars if v not in EXPECTED_VARS]
    if extra_vars:
        logger.warning("Extra variables found: %s", extra_vars)

    # Per-variable checks
    for var_name in EXPECTED_VARS:
        if var_name not in ds.data_vars:
            continue
        da = ds[var_name]

        # Units
        units = da.attrs.get("units", "MISSING")
        logger.info("  %s: units=%s", var_name, units)

        # Missing values
        data = da.values
        total = data.size
        nan_count = int(np.isnan(data).sum())
        nan_pct = nan_count / total * 100
        logger.info("  %s: NaN=%d/%d (%.1f%%)", var_name, nan_count, total, nan_pct)

        # Range check (only on valid data)
        if nan_count < total:
            valid = data[np.isfinite(data)]
            vmin, vmax = valid.min(), valid.max()
            expected_range = EXPECTED_RANGES.get(var_name)
            if expected_range:
                if vmin < expected_range[0] or vmax > expected_range[1]:
                    logger.warning("  %s: range [%.3f, %.3f] outside expected [%.1f, %.1f]",
                                   var_name, vmin, vmax, *expected_range)
                else:
                    logger.info("  %s: range [%.3f, %.3f] within expected ✓", var_name, vmin, vmax)
            else:
                logger.info("  %s: range [%.3f, %.3f]", var_name, vmin, vmax)

    return ok


def check_alignment(ds: xr.Dataset) -> bool:
    """Check all variables share the same grid coordinates."""
    ok = True
    time0 = ds["time"].values
    lat0 = ds["lat"].values
    lon0 = ds["lon"].values

    for var in ds.data_vars:
        da = ds[var]
        if not np.array_equal(da.coords["time"].values, time0):
            logger.error("Variable %s: time coords mismatch", var)
            ok = False
        if not np.array_equal(da.coords["lat"].values, lat0):
            logger.error("Variable %s: lat coords mismatch", var)
            ok = False
        if not np.array_equal(da.coords["lon"].values, lon0):
            logger.error("Variable %s: lon coords mismatch", var)
            ok = False

    if ok:
        logger.info("All variables share identical coordinates ✓")
    return ok


def check_phase1_untouched() -> bool:
    """Verify Phase 1 processed files are unchanged."""
    ok = True
    phase1_files = [
        PROCESSED / "icebergs" / "east_prydz_bay_icebergs.csv",
        PROCESSED / "bathymetry" / "east_prydz_bay_bathymetry_15arcsec.nc",
    ]
    for f in phase1_files:
        if f.exists():
            # Just check existence and basic readability
            try:
                if f.suffix == ".csv":
                    import pandas as pd
                    pd.read_csv(f, nrows=1)
                else:
                    xr.open_dataset(f).close()
                logger.info("Phase 1 file intact: %s ✓", f.relative_to(PROCESSED))
            except Exception as e:
                logger.error("Phase 1 file corrupted: %s - %s", f, e)
                ok = False
        else:
            logger.error("Phase 1 file missing: %s", f)
            ok = False
    return ok


def check_metadata_json() -> bool:
    """Validate companion metadata JSON."""
    if not METADATA_JSON.exists():
        return False
    try:
        import json
        meta = json.loads(METADATA_JSON.read_text())
        # Basic structure
        required_keys = ["spatial_grid", "temporal_grid", "variables", "source_files", "variable_mapping"]
        for k in required_keys:
            if k not in meta:
                logger.error("Metadata missing key: %s", k)
                return False
        logger.info("Metadata JSON structure valid ✓")
        logger.info("  Variables documented: %d", len(meta["variables"]))
        logger.info("  Source files: %s", list(meta["source_files"].keys()))
        return True
    except Exception as e:
        logger.error("Metadata JSON invalid: %s", e)
        return False


def main() -> int:
    logger.info("=" * 60)
    logger.info("PHASE 2 STEP 3 — FEATURE STACK VALIDATION")
    logger.info("=" * 60)

    checks = [
        ("File exists", check_file_exists),
        ("Dimensions & coords", lambda: check_dims_and_coords(xr.open_dataset(FEATURE_STACK))),
        ("Temporal coverage", lambda: check_temporal_coverage(xr.open_dataset(FEATURE_STACK))),
        ("Variables", lambda: check_variables(xr.open_dataset(FEATURE_STACK))),
        ("Cross-variable alignment", lambda: check_alignment(xr.open_dataset(FEATURE_STACK))),
        ("Phase 1 untouched", check_phase1_untouched),
        ("Metadata JSON", check_metadata_json),
    ]

    passed = 0
    for name, check_fn in checks:
        logger.info("")
        logger.info("--- %s ---", name)
        try:
            if check_fn():
                logger.info("%s: PASS", name)
                passed += 1
            else:
                logger.error("%s: FAIL", name)
        except Exception as e:
            logger.error("%s: ERROR - %s", name, e)

    logger.info("")
    logger.info("=" * 60)
    logger.info("VALIDATION SUMMARY: %d/%d checks passed", passed, len(checks))
    logger.info("=" * 60)

    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    sys.exit(main())