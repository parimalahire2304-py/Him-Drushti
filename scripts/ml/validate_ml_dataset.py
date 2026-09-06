#!/usr/bin/env python3
"""
Phase 3 Step 2 — Validate the Supervised ML Dataset

Checks performed:
  1. File existence and structure
  2. Sample counts (train/val/test)
  3. Trajectory count
  4. Timestamp ordering within each trajectory
  5. 7-day target alignment (target_date = obs_date + 7 days)
  6. Feature/target separation (targets not in features)
  7. Missing values
  8. Duplicate samples
  9. Invalid coordinates (out of bbox)
 10. Feature value ranges (physical sanity)
 11. Target value ranges (physical sanity)
 12. Temporal leakage (no future info in features)
 13. Future-information leakage check
 14. Consistency between saved dataset and metadata JSON

Usage:
    python scripts/ml/validate_ml_dataset.py
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

# ── Paths ────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR   = PROJECT_ROOT / "data" / "processed" / "ml"
FULL_PATH    = OUTPUT_DIR / "full.parquet"
TRAIN_PATH   = OUTPUT_DIR / "train.parquet"
VAL_PATH     = OUTPUT_DIR / "val.parquet"
TEST_PATH    = OUTPUT_DIR / "test.parquet"
META_PATH    = OUTPUT_DIR / "ml_dataset_metadata.json"

# ── Expected values ──────────────────────────────────────────────────────
EXPECTED_DT_DAYS    = 7
EXPECTED_SPLITS     = {"train", "val", "test"}
SPLIT_VAL_START     = date(2020, 8, 15)
SPLIT_TEST_START    = date(2020, 10, 31)
BBOX                = {"lat_min": -70.0, "lat_max": -66.0,
                       "lon_min": 72.0,  "lon_max": 80.0}

# Columns that are features (input to model)
FEATURE_COLS = [
    "lat", "lon",
    "iceberg_length_nm", "iceberg_width_nm",
    "sea_ice_concentration", "wind_u_10m", "wind_v_10m",
    "temperature_2m", "mean_sea_level_pressure",
    "total_precipitation", "bathymetry_elevation",
    "ocean_current_u", "ocean_current_v",
    "wind_speed", "wind_dir", "ocean_speed", "ocean_dir",
    "wind_ocean_angle", "exposed_water_fraction",
    "prev_lat", "prev_lon", "prev_delta_lat", "prev_delta_lon",
    "prev_speed", "prev_bearing",
]

# Columns that are targets (MUST NOT appear in features)
TARGET_COLS = ["target_lat", "target_lon"]

# Derived evaluation columns (also NOT inputs)
DERIVED_COLS = ["delta_lat", "delta_lon", "displacement_km", "speed_km_day", "bearing_deg"]

# Metadata columns (not features)
META_COLS = ["iceberg_id", "obs_date", "target_date", "dt_days", "split",
             "persist_lat", "persist_lon"]

# Physical ranges for feature sanity
FEATURE_RANGES = {
    "lat":                         (-70.0, -66.0),
    "lon":                         (72.0, 80.0),
    "iceberg_length_nm":           (1.0, 50.0),
    "iceberg_width_nm":            (1.0, 30.0),
    "sea_ice_concentration":       (0.0, 1.0),
    "wind_u_10m":                  (-50.0, 50.0),
    "wind_v_10m":                  (-50.0, 50.0),
    "temperature_2m":              (200.0, 320.0),
    "mean_sea_level_pressure":     (90000.0, 105000.0),
    "total_precipitation":         (0.0, 0.1),
    "bathymetry_elevation":        (-6000.0, 1000.0),
    "ocean_current_u":             (-2.0, 2.0),
    "ocean_current_v":             (-2.0, 2.0),
    "wind_speed":                  (0.0, 60.0),
    "wind_dir":                    (0.0, 360.0),
    "ocean_speed":                 (0.0, 3.0),
    "ocean_dir":                   (0.0, 360.0),
    "wind_ocean_angle":            (0.0, 180.0),
    "exposed_water_fraction":      (0.0, 1.0),
}

# Expected number of features
EXPECTED_N_FEATURES = len(FEATURE_COLS)  # 25

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)


# ── Check runner ─────────────────────────────────────────────────────────
_check_pass_count = 0
_check_fail_count = 0


def _pass(name: str) -> None:
    global _check_pass_count
    _check_pass_count += 1
    log.info("  ✅ PASS  %s", name)


def _fail(name: str, msg: str) -> None:
    global _check_fail_count
    _check_fail_count += 1
    log.error("  ❌ FAIL  %s: %s", name, msg)


def _warn(name: str, msg: str) -> None:
    log.warning("  ⚠️  WARN  %s: %s", name, msg)


# ── 1. File existence ────────────────────────────────────────────────────
def check_files() -> pd.DataFrame | None:
    log.info("\n--- 1. File existence ---")
    for p in [FULL_PATH, TRAIN_PATH, VAL_PATH, TEST_PATH, META_PATH]:
        if not p.exists():
            _fail("file_exists", f"Missing: {p.name}")
            return None
        sz = p.stat().st_size / 1e6
        log.info("    %s: %.2f MB", p.name, sz)
    _pass("file_exists")

    df = pd.read_parquet(FULL_PATH)
    log.info("    full.parquet: %d rows × %d cols", *df.shape)
    return df


# ── 2. Sample counts ─────────────────────────────────────────────────────
def check_sample_counts(df: pd.DataFrame) -> None:
    log.info("\n--- 2. Sample counts ---")
    n = len(df)
    if n == 0:
        _fail("sample_count", "Dataset is empty")
        return

    counts = df["split"].value_counts()
    for s in EXPECTED_SPLITS:
        c = counts.get(s, 0)
        log.info("    %s: %d", s.upper(), c)
        if c == 0:
            _fail("sample_count", f"Split '{s}' has zero samples")

    total = sum(counts.get(s, 0) for s in EXPECTED_SPLITS)
    if total != n:
        _fail("sample_count",
              f"Split counts ({total}) ≠ total rows ({n}). "
              f"Extra values: {set(df['split']) - EXPECTED_SPLITS}")
    else:
        _pass("sample_count")


# ── 3. Trajectory count ──────────────────────────────────────────────────
def check_trajectories(df: pd.DataFrame) -> None:
    log.info("\n--- 3. Trajectory count ---")
    icebergs = sorted(df["iceberg_id"].unique())
    log.info("    Icebergs: %s (%d)", icebergs, len(icebergs))
    for ice in icebergs:
        n = (df["iceberg_id"] == ice).sum()
        log.info("      %s: %d pairs", ice, n)
    if len(icebergs) == 0:
        _fail("trajectory_count", "No icebergs found")
    else:
        _pass("trajectory_count")


# ── 4. Timestamp ordering ────────────────────────────────────────────────
def check_timestamp_ordering(df: pd.DataFrame) -> None:
    log.info("\n--- 4. Timestamp ordering ---")
    ok = True
    for ice in df["iceberg_id"].unique():
        sub = df[df["iceberg_id"] == ice].sort_values("obs_date")
        obs_dates = pd.to_datetime(sub["obs_date"]).values
        diffs = np.diff(obs_dates).astype("timedelta64[D]").astype(int)
        if np.any(diffs <= 0):
            _fail("timestamp_order", f"{ice}: non-increasing obs_date detected")
            ok = False
    if ok:
        _pass("timestamp_order")


# ── 5. 7-day target alignment ────────────────────────────────────────────
def check_target_alignment(df: pd.DataFrame) -> None:
    log.info("\n--- 5. 7-day target alignment ---")
    obs_dates  = pd.to_datetime(df["obs_date"]).values
    tgt_dates  = pd.to_datetime(df["target_date"]).values
    dt_days    = (tgt_dates - obs_dates).astype("timedelta64[D]").astype(int)
    bad = dt_days != EXPECTED_DT_DAYS
    n_bad = int(bad.sum())
    if n_bad > 0:
        _fail("target_alignment",
              f"{n_bad}/{len(df)} rows have target_date ≠ obs_date + {EXPECTED_DT_DAYS} days")
    else:
        _pass("target_alignment")


# ── 6. Feature/target separation ─────────────────────────────────────────
def check_feature_target_separation(df: pd.DataFrame) -> None:
    log.info("\n--- 6. Feature/target separation ---")
    cols = set(df.columns)
    leaking_targets = cols.intersection(TARGET_COLS + DERIVED_COLS)
    # target_lat, target_lon, delta_lat, delta_lon, displacement_km etc. must NOT be in FEATURE_COLS
    feature_overlap = set(FEATURE_COLS).intersection(TARGET_COLS + DERIVED_COLS)
    if feature_overlap:
        _fail("feature_target_sep",
              f"Target/derived columns found in feature list: {feature_overlap}")
    else:
        _pass("feature_target_sep")


# ── 7. Missing values ────────────────────────────────────────────────────
def check_missing_values(df: pd.DataFrame) -> None:
    log.info("\n--- 7. Missing values ---")
    missing = df.isnull().sum()
    missing = missing[missing > 0]
    if len(missing) == 0:
        _pass("missing_values")
        return

    log.warning("    Columns with NaN:")
    all_ok = True
    for col, n in missing.items():
        pct = n / len(df) * 100
        log.warning("      %s: %d (%.1f%%)", col, n, pct)
        # prev_* features are expected to be NaN for first observation in each trajectory
        if col.startswith("prev_"):
            log.info("        (expected: first observation per trajectory has no previous step)")
        else:
            all_ok = False
            _warn("missing_values", f"Unexpected NaN in '{col}'")

    if all_ok:
        _pass("missing_values")
    else:
        # prev_* NaN is expected; everything else should be 0
        non_prev = missing.drop([c for c in missing.index if c.startswith("prev_")], errors="ignore")
        if len(non_prev) == 0:
            _pass("missing_values")
        else:
            _fail("missing_values", f"Unexpected NaN columns: {list(non_prev.index)}")


# ── 8. Duplicate samples ─────────────────────────────────────────────────
def check_duplicates(df: pd.DataFrame) -> None:
    log.info("\n--- 8. Duplicate samples ---")
    dup = df.duplicated(subset=["iceberg_id", "obs_date"])
    n = int(dup.sum())
    if n > 0:
        _fail("duplicates", f"{n} duplicate (iceberg_id, obs_date) pairs")
    else:
        _pass("duplicates")


# ── 9. Invalid coordinates ───────────────────────────────────────────────
def check_coordinates(df: pd.DataFrame) -> None:
    log.info("\n--- 9. Invalid coordinates ---")
    lat_bad = ((df["lat"] < BBOX["lat_min"]) | (df["lat"] > BBOX["lat_max"]))
    lon_bad = ((df["lon"] < BBOX["lon_min"]) | (df["lon"] > BBOX["lon_max"]))
    n_lat = int(lat_bad.sum())
    n_lon = int(lon_bad.sum())
    if n_lat > 0:
        _fail("coordinates", f"{n_lat} rows have lat outside [{BBOX['lat_min']}, {BBOX['lat_max']}]")
    elif n_lon > 0:
        _fail("coordinates", f"{n_lon} rows have lon outside [{BBOX['lon_min']}, {BBOX['lon_max']}]")
    else:
        _pass("coordinates")


# ── 10. Feature ranges ───────────────────────────────────────────────────
def check_feature_ranges(df: pd.DataFrame) -> None:
    log.info("\n--- 10. Feature value ranges ---")
    ok = True
    for col, (lo, hi) in FEATURE_RANGES.items():
        if col not in df.columns:
            _fail("feature_range", f"Expected feature column '{col}' not found")
            ok = False
            continue
        vmin = df[col].min()
        vmax = df[col].max()
        in_range = (vmin >= lo - 1e-6) and (vmax <= hi + 1e-6)
        status = "✅" if in_range else "❌"
        log.info("    %s: [%.4f, %.4f] (expected [%.1f, %.1f]) %s",
                 col, vmin, vmax, lo, hi, status)
        if not in_range:
            ok = False
    if ok:
        _pass("feature_range")
    else:
        _fail("feature_range", "One or more features outside expected physical range")


# ── 11. Target ranges ────────────────────────────────────────────────────
def check_target_ranges(df: pd.DataFrame) -> None:
    log.info("\n--- 11. Target value ranges ---")
    lat_min, lat_max = df["target_lat"].min(), df["target_lat"].max()
    lon_min, lon_max = df["target_lon"].min(), df["target_lon"].max()
    log.info("    target_lat: [%.4f, %.4f]", lat_min, lat_max)
    log.info("    target_lon: [%.4f, %.4f]", lon_min, lon_max)
    in_bbox = ((lat_min >= BBOX["lat_min"] - 0.5) and (lat_max <= BBOX["lat_max"] + 0.5) and
               (lon_min >= BBOX["lon_min"] - 0.5) and (lon_max <= BBOX["lon_max"] + 0.5))
    if in_bbox:
        _pass("target_range")
    else:
        _warn("target_range",
              "Some target positions are outside the feature-stack bbox "
              "(expected: icebergs may drift slightly outside)")


# ── 12. Temporal leakage ────────────────────────────────────────────────
def check_temporal_leakage(df: pd.DataFrame) -> None:
    """Verify chronological split: max obs_date in train < min in val < min in test."""
    log.info("\n--- 12. Temporal leakage ---")
    split_dates = {}
    for s in EXPECTED_SPLITS:
        sub = df[df["split"] == s]
        if len(sub) == 0:
            split_dates[s] = (None, None)
            continue
        dates = pd.to_datetime(sub["obs_date"])
        split_dates[s] = (dates.min(), dates.max())
        log.info("    %s: %s → %s", s.upper(),
                 split_dates[s][0].date(), split_dates[s][1].date())

    train_max = split_dates["train"][1]
    val_min   = split_dates["val"][0]
    val_max   = split_dates["val"][1]
    test_min  = split_dates["test"][0]

    if train_max is not None and val_min is not None and train_max >= val_min:
        _fail("temporal_leakage",
              f"train max ({train_max.date()}) >= val min ({val_min.date()})")
    elif val_max is not None and test_min is not None and val_max >= test_min:
        _fail("temporal_leakage",
              f"val max ({val_max.date()}) >= test min ({test_min.date()})")
    else:
        _pass("temporal_leakage")


# ── 13. Future-information leakage ───────────────────────────────────────
def check_future_leakage(df: pd.DataFrame) -> None:
    """Ensure no target-derived columns are in the feature list."""
    log.info("\n--- 13. Future-information leakage ---")
    target_in_features = set(FEATURE_COLS).intersection(TARGET_COLS + DERIVED_COLS)
    persist_in_features = set(FEATURE_COLS).intersection(["persist_lat", "persist_lon"])

    # Also check: obs_date features should not be present as numeric features
    date_in_features = "obs_date" in FEATURE_COLS or "target_date" in FEATURE_COLS

    if target_in_features:
        _fail("future_leakage", f"Target columns in feature list: {target_in_features}")
    elif persist_in_features:
        _fail("future_leakage", f"Baseline columns in feature list: {persist_in_features}")
    elif date_in_features:
        _fail("future_leakage", "Date columns in feature list (would enable leakage)")
    else:
        _pass("future_leakage")


# ── 14. Consistency with metadata ────────────────────────────────────────
def check_metadata_consistency(df: pd.DataFrame) -> None:
    log.info("\n--- 14. Metadata consistency ---")
    if not META_PATH.exists():
        _fail("metadata_consistency", "Metadata JSON not found")
        return

    meta = json.loads(META_PATH.read_text())

    # Total pairs
    meta_total = meta.get("total_pairs")
    if meta_total != len(df):
        _fail("metadata_consistency",
              f"metadata total_pairs={meta_total} ≠ actual rows={len(df)}")
        return

    # Split counts
    for s in ["train", "val", "test"]:
        meta_c = meta.get("samples_per_split", {}).get(s)
        actual_c = int((df["split"] == s).sum())
        if meta_c != actual_c:
            _fail("metadata_consistency",
                  f"metadata samples_per_split[{s}]={meta_c} ≠ actual={actual_c}")
            return

    # Feature count
    meta_nf = meta.get("n_features")
    if meta_nf is not None and meta_nf != len(FEATURE_COLS):
        _warn("metadata_consistency",
              f"metadata n_features={meta_nf} vs expected={len(FEATURE_COLS)}")

    _pass("metadata_consistency")


# ──────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────
def main() -> int:
    global _check_pass_count, _check_fail_count
    _check_pass_count = 0
    _check_fail_count = 0

    log.info("=" * 60)
    log.info("PHASE 3 STEP 2 — ML DATASET VALIDATION")
    log.info("=" * 60)

    df = check_files()
    if df is None:
        log.error("Cannot continue without the dataset file.")
        return 1

    check_sample_counts(df)
    check_trajectories(df)
    check_timestamp_ordering(df)
    check_target_alignment(df)
    check_feature_target_separation(df)
    check_missing_values(df)
    check_duplicates(df)
    check_coordinates(df)
    check_feature_ranges(df)
    check_target_ranges(df)
    check_temporal_leakage(df)
    check_future_leakage(df)
    check_metadata_consistency(df)

    log.info("")
    log.info("=" * 60)
    log.info("VALIDATION RESULT:  %d passed,  %d failed", _check_pass_count, _check_fail_count)
    log.info("=" * 60)

    if _check_fail_count > 0:
        log.error("❌  DATASET VALIDATION FAILED — do not proceed to training.")
        return 1
    else:
        log.info("✅  DATASET VALIDATION PASSED — ready for model training.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
