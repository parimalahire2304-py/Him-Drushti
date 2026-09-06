#!/usr/bin/env python3
"""
Phase 3 Step 2 — Build the Supervised ML Dataset

Constructs supervised learning pairs from iceberg trajectory observations
joined with the Phase 2 environmental feature stack, for the approved
7-day single-step iceberg trajectory prediction problem.

Output:
  data/processed/ml/
    train.parquet, val.parquet, test.parquet   — split datasets
    full.parquet                                 — all samples combined
    ml_dataset_metadata.json                     — provenance & statistics

No Phase 1 or Phase 2 files are modified. The feature stack is READ-ONLY.

Usage:
    python scripts/ml/prepare_ml_dataset.py
"""

from __future__ import annotations

import json
import logging
import math
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

# ── Paths ────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parents[2]
ICEBERG_CSV = PROJECT_ROOT / "data" / "processed" / "icebergs" / "east_prydz_bay_icebergs.csv"
FEATURE_STACK_NC = PROJECT_ROOT / "data" / "processed" / "integration" / "east_prydz_bay_2020_feature_stack.nc"
OUTPUT_DIR = PROJECT_ROOT / "data" / "processed" / "ml"
METADATA_JSON = OUTPUT_DIR / "ml_dataset_metadata.json"

# ── Constants ────────────────────────────────────────────────────────────
TARGET_DT_DAYS = 7

# Gridded feature variable names (must match feature stack NC)
GRID_VARS = [
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

# How each variable is temporally aggregated over 24 hours on the obs date
# "mean" for rate/intensity fields, "sum" for accumulated fields
VAR_AGG = {
    "sea_ice_concentration": "mean",
    "wind_u_10m": "mean",
    "wind_v_10m": "mean",
    "temperature_2m": "mean",
    "mean_sea_level_pressure": "mean",
    "total_precipitation": "sum",
    "bathymetry_elevation": "mean",
    "ocean_current_u": "mean",
    "ocean_current_v": "mean",
}

# Sea ice and bathymetry use nearest-neighbour (sharp ice-edge / coastline boundaries)
NN_VARS = {"sea_ice_concentration", "bathymetry_elevation"}

# Chronological split boundaries (inclusive start, exclusive end for val/test)
#   Train:  obs_date <  2020-08-15
#   Val:    2020-08-15 <= obs_date < 2020-10-31
#   Test:   obs_date >= 2020-10-31
SPLIT_VAL_START = date(2020, 8, 15)
SPLIT_TEST_START = date(2020, 10, 31)

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────
# Geodesic helpers
# ──────────────────────────────────────────────────────────────────────────
_EARTH_RADIUS_KM = 6371.0088


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two points (degrees) in km."""
    rlat1, rlon1, rlat2, rlon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = rlat2 - rlat1
    dlon = rlon2 - rlon1
    a = math.sin(dlat / 2) ** 2 + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlon / 2) ** 2
    return 2 * _EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def _bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Initial bearing (0=N, 90=E, clockwise) from point 1 to point 2."""
    rlat1, rlon1, rlat2, rlon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlon = rlon2 - rlon1
    x = math.sin(dlon) * math.cos(rlat2)
    y = math.cos(rlat1) * math.sin(rlat2) - math.sin(rlat1) * math.cos(rlat2) * math.cos(dlon)
    brng = math.degrees(math.atan2(x, y))
    return (brng + 360) % 360


# ──────────────────────────────────────────────────────────────────────────
# Interpolation at an arbitrary (lat, lon) from the 0.25° grid
# ──────────────────────────────────────────────────────────────────────────
def _interp_bilinear(arr_2d: np.ndarray, lat_vals: np.ndarray, lon_vals: np.ndarray,
                     lat_obs: float, lon_obs: float) -> float:
    """Bilinear interpolation from a regular lat/lon 2-D array.  NaN-safe."""
    # lat_vals is decreasing (south→north in the NC, e.g. -70..-66 stored as -70 first)
    # Find bounding indices in lat (may be decreasing)
    if lat_vals[0] < lat_vals[-1]:          # increasing
        idx_lat = np.searchsorted(lat_vals, lat_obs) - 1
    else:                                    # decreasing
        flipped = lat_vals[::-1]
        idx_from_south = np.searchsorted(flipped, lat_obs) - 1
        idx_lat = len(lat_vals) - 1 - idx_from_south

    idx_lon = np.searchsorted(lon_vals, lon_obs) - 1

    # Clamp to valid range
    idx_lat = max(0, min(idx_lat, len(lat_vals) - 2))
    idx_lon = max(0, min(idx_lon, len(lon_vals) - 2))

    # Fractional distances
    if lat_vals[0] < lat_vals[-1]:          # increasing
        t_lat = (lat_obs - lat_vals[idx_lat]) / (lat_vals[idx_lat + 1] - lat_vals[idx_lat])
    else:                                    # decreasing
        t_lat = (lat_obs - lat_vals[idx_lat]) / (lat_vals[idx_lat + 1] - lat_vals[idx_lat])

    t_lon = (lon_obs - lon_vals[idx_lon]) / (lon_vals[idx_lon + 1] - lon_vals[idx_lon])

    t_lat = float(np.clip(t_lat, 0.0, 1.0))
    t_lon = float(np.clip(t_lon, 0.0, 1.0))

    v00 = arr_2d[idx_lat,     idx_lon]
    v10 = arr_2d[idx_lat + 1, idx_lon]
    v01 = arr_2d[idx_lat,     idx_lon + 1]
    v11 = arr_2d[idx_lat + 1, idx_lon + 1]

    vals = [v00, v10, v01, v11]
    if any(math.isnan(v) for v in vals):
        # Fall back to nearest
        dists = [
            abs(lat_obs - lat_vals[idx_lat])     + abs(lon_obs - lon_vals[idx_lon]),
            abs(lat_obs - lat_vals[idx_lat + 1]) + abs(lon_obs - lon_vals[idx_lon]),
            abs(lat_obs - lat_vals[idx_lat])     + abs(lon_obs - lon_vals[idx_lon + 1]),
            abs(lat_obs - lat_vals[idx_lat + 1]) + abs(lon_obs - lon_vals[idx_lon + 1]),
        ]
        return vals[int(np.argmin(dists))]

    return (1 - t_lat) * (1 - t_lon) * v00 + t_lat * (1 - t_lon) * v10 + \
           (1 - t_lat) * t_lon * v01       + t_lat * t_lon * v11


def _interp_nearest_with_fallback(arr_2d: np.ndarray, lat_vals: np.ndarray, lon_vals: np.ndarray,
                                 lat_obs: float, lon_obs: float, max_radius: int = 5) -> float:
    """Nearest-neighbour with expanding-radius fallback for NaN coastal cells."""
    if lat_vals[0] < lat_vals[-1]:
        idx_lat = int(np.argmin(np.abs(lat_vals - lat_obs)))
    else:
        idx_lat = int(np.argmin(np.abs(lat_vals - lat_obs)))
    idx_lon = int(np.argmin(np.abs(lon_vals - lon_obs)))

    val = arr_2d[idx_lat, idx_lon]
    if not math.isnan(val):
        return float(val)

    # Expanding search: ring by ring around (idx_lat, idx_lon)
    n_lat, n_lon = arr_2d.shape
    for r in range(1, max_radius + 1):
        best_val, best_dist = np.nan, float("inf")
        for di in range(-r, r + 1):
            for dj in range(-r, r + 1):
                if abs(di) != r and abs(dj) != r:
                    continue  # only ring boundary
                li, lj = idx_lat + di, idx_lon + dj
                if 0 <= li < n_lat and 0 <= lj < n_lon:
                    v = arr_2d[li, lj]
                    if not math.isnan(v):
                        d = di * di + dj * dj
                        if d < best_dist:
                            best_val, best_dist = v, d
        if not math.isnan(best_val):
            return float(best_val)

    return float(arr_2d[idx_lat, idx_lon])  # last resort (may be NaN)


# ──────────────────────────────────────────────────────────────────────────
# Load phase
# ──────────────────────────────────────────────────────────────────────────
def load_icebergs_2020() -> pd.DataFrame:
    """Load and filter iceberg observations to the 2020 analysis window."""
    df = pd.read_csv(ICEBERG_CSV)
    df["obs_date"] = pd.to_datetime(df["observation_date"].astype(str), format="%Y%m%d").dt.date
    df = df[(df["obs_date"] >= date(2020, 1, 1)) & (df["obs_date"] <= date(2020, 12, 31))]
    df = df.sort_values(["Iceberg", "obs_date"]).reset_index(drop=True)
    log.info("Loaded %d iceberg observations in 2020 for %d icebergs",
             len(df), df["Iceberg"].nunique())
    return df


def load_feature_stack() -> tuple[xr.Dataset, np.ndarray, np.ndarray, np.ndarray]:
    """Load the feature stack.  Returns (dataset, lat_vals, lon_vals, time_dates)."""
    ds = xr.open_dataset(FEATURE_STACK_NC)
    lat_vals = ds["lat"].values          # decreasing: -70 .. -66
    lon_vals = ds["lon"].values          # increasing: 72 .. 80
    time_vals = ds["time"].values        # datetime64[ns]
    time_dates = pd.to_datetime(time_vals).date   # array of date objects
    log.info("Feature stack: %d time steps, lat %d points, lon %d points",
             len(time_vals), len(lat_vals), len(lon_vals))
    return ds, lat_vals, lon_vals, time_dates


# ──────────────────────────────────────────────────────────────────────────
# Feature extraction at a single (lat, lon, date)
# ──────────────────────────────────────────────────────────────────────────
def extract_features_at_point(
    ds: xr.Dataset,
    lat_vals: np.ndarray,
    lon_vals: np.ndarray,
    time_dates: np.ndarray,
    obs_lat: float,
    obs_lon: float,
    obs_date: date,
) -> dict[str, float]:
    """
    Extract 9 gridded variables at (obs_lat, obs_lon) on obs_date.
    Uses daily mean (or sum for precipitation) of the 24 hourly values.
    sea_ice_concentration uses nearest-neighbour; others bilinear.
    """
    # Boolean mask for the 24 hourly timestamps on obs_date
    mask = np.array([d == obs_date for d in time_dates])
    if mask.sum() == 0:
        raise ValueError(f"No feature-stack timestamps found for {obs_date}")

    features: dict[str, float] = {}
    for var in GRID_VARS:
        daily_slice = ds[var].values[mask, :, :]   # (n_hours, n_lat, n_lon)
        agg_method = VAR_AGG[var]

        if agg_method == "sum":
            agg_2d = np.nansum(daily_slice, axis=0)
        else:  # mean
            agg_2d = np.nanmean(daily_slice, axis=0)

        if var in NN_VARS:
            features[var] = _interp_nearest_with_fallback(agg_2d, lat_vals, lon_vals, obs_lat, obs_lon)
        else:
            features[var] = _interp_bilinear(agg_2d, lat_vals, lon_vals, obs_lat, obs_lon)

    return features


# ──────────────────────────────────────────────────────────────────────────
# Pair construction (no leakage: only data available at time t used)
# ──────────────────────────────────────────────────────────────────────────
def _deg_to_km(lat: float, dlat: float, dlon: float) -> tuple[float, float]:
    """Convert small degree offsets to km at a given latitude."""
    km_per_deg_lat = 111.32
    km_per_deg_lon = 111.32 * math.cos(math.radians(lat))
    return dlat * km_per_deg_lat, dlon * km_per_deg_lon


def build_pairs(
    df2020: pd.DataFrame,
    ds: xr.Dataset,
    lat_vals: np.ndarray,
    lon_vals: np.ndarray,
    time_dates: np.ndarray,
) -> pd.DataFrame:
    """
    Build supervised pairs.  For each consecutive observation of the same
    iceberg that is exactly 7 days apart, row at time t is the input and
    row at time t+7 is the target.

    Returns a DataFrame with one row per pair.
    """
    rows: list[dict] = []

    # Cache extracted features per (iceberg, obs_date) to avoid re-computation
    feature_cache: dict[tuple[str, date], dict[str, float]] = {}

    for iceberg_id in sorted(df2020["Iceberg"].unique()):
        traj = df2020[df2020["Iceberg"] == iceberg_id].sort_values("obs_date").reset_index(drop=True)
        static_len = float(traj["Length (NM)"].iloc[0])
        static_wid = float(traj["Width (NM)"].iloc[0])

        for i in range(len(traj) - 1):
            row_t  = traj.iloc[i]
            row_t1 = traj.iloc[i + 1]

            dt_days = (row_t1["obs_date"] - row_t["obs_date"]).days
            if dt_days != TARGET_DT_DAYS:
                continue   # only 7-day pairs

            date_t  = row_t["obs_date"]
            date_t1 = row_t1["obs_date"]

            # --- Extract features at time t (the input time) ---
            cache_key = (iceberg_id, date_t)
            if cache_key not in feature_cache:
                feature_cache[cache_key] = extract_features_at_point(
                    ds, lat_vals, lon_vals, time_dates,
                    float(row_t["Latitude"]), float(row_t["Longitude"]), date_t,
                )
            feats_t = feature_cache[cache_key]

            # --- Targets: next position (available at t+7, NOT used as input) ---
            target_lat = float(row_t1["Latitude"])
            target_lon = float(row_t1["Longitude"])

            # --- Input: current position (available at t) ---
            curr_lat = float(row_t["Latitude"])
            curr_lon = float(row_t["Longitude"])

            # --- Engineered: instantaneous vectors from features at t ---
            wind_u = feats_t["wind_u_10m"]
            wind_v = feats_t["wind_v_10m"]
            oc_u   = feats_t["ocean_current_u"]
            oc_v   = feats_t["ocean_current_v"]
            sic    = feats_t["sea_ice_concentration"]

            wind_speed    = math.sqrt(wind_u**2 + wind_v**2)
            wind_dir      = (math.degrees(math.atan2(wind_u, wind_v)) + 360) % 360
            ocean_speed   = math.sqrt(oc_u**2 + oc_v**2)
            ocean_dir     = (math.degrees(math.atan2(oc_u, oc_v)) + 360) % 360
            wind_ocean_ang = (wind_dir - ocean_dir + 360) % 360
            if wind_ocean_ang > 180:
                wind_ocean_ang = 360 - wind_ocean_ang
            exposed_water = 1.0 - sic

            # --- Previous-step features (look-back from time t) ---
            # Only available when there is a valid observation at t-7 days
            prev_lat  = np.nan
            prev_lon  = np.nan
            prev_dlat = np.nan
            prev_dlon = np.nan
            prev_speed = np.nan
            prev_bearing = np.nan
            if i > 0:
                row_tm1 = traj.iloc[i - 1]
                dt_back = (row_t["obs_date"] - row_tm1["obs_date"]).days
                if dt_back == TARGET_DT_DAYS:
                    prev_lat  = float(row_tm1["Latitude"])
                    prev_lon  = float(row_tm1["Longitude"])
                    prev_dlat = curr_lat - prev_lat
                    prev_dlon = curr_lon - prev_lon
                    prev_speed = _haversine_km(prev_lat, prev_lon, curr_lat, curr_lon) / dt_back
                    prev_bearing = _bearing_deg(prev_lat, prev_lon, curr_lat, curr_lon)

            # --- Derived targets (for evaluation, NOT used as model input) ---
            displacement_km = _haversine_km(curr_lat, curr_lon, target_lat, target_lon)
            speed_km_day    = displacement_km / TARGET_DT_DAYS
            bearing_deg     = _bearing_deg(curr_lat, curr_lon, target_lat, target_lon)
            delta_lat       = target_lat - curr_lat
            delta_lon       = target_lon - curr_lon

            row = {
                # Metadata (not features)
                "iceberg_id":    iceberg_id,
                "obs_date":      str(date_t),
                "target_date":   str(date_t1),
                "dt_days":       dt_days,
                # Static features
                "iceberg_length_nm": static_len,
                "iceberg_width_nm":  static_wid,
                # Current position (input feature)
                "lat":           curr_lat,
                "lon":           curr_lon,
                # Gridded features at (curr_lat, curr_lon, date_t)
                **feats_t,
                # Engineered features
                "wind_speed":         wind_speed,
                "wind_dir":           wind_dir,
                "ocean_speed":        ocean_speed,
                "ocean_dir":          ocean_dir,
                "wind_ocean_angle":   wind_ocean_ang,
                "exposed_water_fraction": exposed_water,
                # Previous-step features (NaN if unavailable)
                "prev_lat":       prev_lat,
                "prev_lon":       prev_lon,
                "prev_delta_lat": prev_dlat,
                "prev_delta_lon": prev_dlon,
                "prev_speed":     prev_speed,
                "prev_bearing":   prev_bearing,
                # Targets (for model training & evaluation)
                "target_lat":     target_lat,
                "target_lon":     target_lon,
                "delta_lat":      delta_lat,
                "delta_lon":      delta_lon,
                "displacement_km": displacement_km,
                "speed_km_day":   speed_km_day,
                "bearing_deg":    bearing_deg,
            }
            rows.append(row)

    df = pd.DataFrame(rows)
    log.info("Built %d supervised pairs from 4 icebergs", len(df))
    return df


# ──────────────────────────────────────────────────────────────────────────
# Chronological split
# ──────────────────────────────────────────────────────────────────────────
def assign_split(df: pd.DataFrame) -> pd.DataFrame:
    """Add a 'split' column based on chronological obs_date boundaries."""
    obs_dates = pd.to_datetime(df["obs_date"]).dt.date
    splits = []
    for d in obs_dates:
        if d < SPLIT_VAL_START:
            splits.append("train")
        elif d < SPLIT_TEST_START:
            splits.append("val")
        else:
            splits.append("test")
    df = df.copy()
    df["split"] = splits

    for s in ["train", "val", "test"]:
        sub = df[df["split"] == s]
        log.info("  %s: %d pairs  (%s to %s)",
                 s.upper(), len(sub),
                 sub["obs_date"].min() if len(sub) > 0 else "—",
                 sub["obs_date"].max() if len(sub) > 0 else "—")
    return df


# ──────────────────────────────────────────────────────────────────────────
# Persistence baseline
# ──────────────────────────────────────────────────────────────────────────
def add_persistence_baseline(df: pd.DataFrame) -> pd.DataFrame:
    """Add persistence predictions (current position = predicted next position)
    so evaluation can compare model vs. baseline."""
    df = df.copy()
    df["persist_lat"] = df["lat"]
    df["persist_lon"] = df["lon"]
    return df


# ──────────────────────────────────────────────────────────────────────────
# Metadata / provenance
# ──────────────────────────────────────────────────────────────────────────
def write_metadata(df: pd.DataFrame) -> None:
    """Write JSON metadata describing the dataset."""
    meta = {
        "description": "Supervised ML dataset for 7-day iceberg trajectory prediction",
        "created": datetime.utcnow().isoformat() + "Z",
        "problem_definition": "reports/PHASE3_STEP1_PROBLEM_DEFINITION.md",
        "feature_stack": str(FEATURE_STACK_NC.relative_to(PROJECT_ROOT)),
        "iceberg_source": str(ICEBERG_CSV.relative_to(PROJECT_ROOT)),
        "temporal_resolution": "weekly (7-day intervals)",
        "prediction_horizon_days": TARGET_DT_DAYS,
        "grid_resolution_deg": 0.25,
        "interpolation_method": {
            "default": "bilinear (4 surrounding grid cells)",
            "sea_ice_concentration": "nearest-neighbour (sharp ice-edge boundary)",
        },
        "temporal_aggregation": VAR_AGG,
        "split_boundaries": {
            "train": f"< {SPLIT_VAL_START.isoformat()}",
            "val":   f"{SPLIT_VAL_START.isoformat()} to {SPLIT_TEST_START.isoformat()}",
            "test":  f">= {SPLIT_TEST_START.isoformat()}",
        },
        "total_pairs": int(len(df)),
        "icebergs": sorted(df["iceberg_id"].unique().tolist()),
        "feature_columns": [c for c in df.columns if c not in (
            "iceberg_id", "obs_date", "target_date", "dt_days", "split",
            "target_lat", "target_lon", "delta_lat", "delta_lon",
            "displacement_km", "speed_km_day", "bearing_deg", "persist_lat", "persist_lon",
        )],
        "target_columns": ["target_lat", "target_lon"],
        "derived_evaluation_columns": ["delta_lat", "delta_lon", "displacement_km",
                                       "speed_km_day", "bearing_deg"],
        "n_features": int(len([c for c in df.columns if c not in (
            "iceberg_id", "obs_date", "target_date", "dt_days", "split",
            "target_lat", "target_lon", "delta_lat", "delta_lon",
            "displacement_km", "speed_km_day", "bearing_deg", "persist_lat", "persist_lon",
        )])),
        "leakage_prevention": [
            "Chronological split: train < val < test in time, no overlap",
            "Features extracted ONLY at observation time t; never from t+7",
            "Targets (target_lat, target_lon) are positions at t+7; excluded from input features",
            "Previous-step features use only observations before t; NaN if unavailable",
            "No future environmental conditions used as input",
            "No random splitting of sequential trajectory observations",
        ],
        "samples_per_iceberg": {k: int(v) for k, v in df["iceberg_id"].value_counts().items()},
        "samples_per_split": {s: int((df["split"] == s).sum()) for s in ["train", "val", "test"]},
        "missing_values_per_feature": {
            col: int(df[col].isna().sum())
            for col in df.columns if col in df.columns
        },
    }
    METADATA_JSON.parent.mkdir(parents=True, exist_ok=True)
    METADATA_JSON.write_text(json.dumps(meta, indent=2, default=str))
    log.info("Wrote metadata → %s", METADATA_JSON)


# ──────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────
def main() -> None:
    log.info("=" * 60)
    log.info("PHASE 3 STEP 2 — BUILD SUPERVISED ML DATASET")
    log.info("=" * 60)

    # 1. Load data
    df2020 = load_icebergs_2020()
    ds, lat_vals, lon_vals, time_dates = load_feature_stack()

    # 2. Build supervised pairs
    df = build_pairs(df2020, ds, lat_vals, lon_vals, time_dates)

    if len(df) == 0:
        log.error("No valid 7-day pairs found — aborting")
        sys.exit(1)

    # 3. Chronological split
    df = assign_split(df)

    # 4. Persistence baseline
    df = add_persistence_baseline(df)

    # 5. Save per-split parquet files
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for split_name in ["train", "val", "test"]:
        sub = df[df["split"] == split_name].reset_index(drop=True)
        out_path = OUTPUT_DIR / f"{split_name}.parquet"
        sub.to_parquet(out_path, index=False)
        log.info("Saved %s → %s (%d rows)", split_name.upper(), out_path.relative_to(PROJECT_ROOT), len(sub))

    full_path = OUTPUT_DIR / "full.parquet"
    df.to_parquet(full_path, index=False)
    log.info("Saved FULL → %s (%d rows)", full_path.relative_to(PROJECT_ROOT), len(df))

    # 6. Metadata
    write_metadata(df)

    # 7. Summary
    log.info("")
    log.info("=" * 60)
    log.info("DATASET SUMMARY")
    log.info("=" * 60)
    log.info("Total pairs:  %d", len(df))
    log.info("  Train:      %d", (df["split"] == "train").sum())
    log.info("  Val:        %d", (df["split"] == "val").sum())
    log.info("  Test:       %d", (df["split"] == "test").sum())
    log.info("Icebergs:     %s", sorted(df["iceberg_id"].unique().tolist()))
    log.info("Date range:   %s → %s", df["obs_date"].min(), df["obs_date"].max())
    log.info("Features:     %d columns", len([c for c in df.columns if c not in (
        "iceberg_id", "obs_date", "target_date", "dt_days", "split",
        "target_lat", "target_lon", "delta_lat", "delta_lon",
        "displacement_km", "speed_km_day", "bearing_deg", "persist_lat", "persist_lon",
    )]))
    log.info("=" * 60)


if __name__ == "__main__":
    main()
