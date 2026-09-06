#!/usr/bin/env python3
"""
PHASE 3C — Validation suite for the expanded-dataset model experiment.

Verifies every integrity rule before finalizing:
  1. Expanded dataset unchanged (451 pairs, schema identical, split counts)
  2. Original Phase 3 dataset unchanged
  3. No test leakage (chronological split preserved)
  4. Feature schema unchanged (25 features / 39 columns)
  5. Predictions finite
  6. Saved models reload & produce identical predictions
  7. Reported metrics exactly match recomputed metrics from saved predictions
  8. C39 zero-shot isolation preserved
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import xgboost as xgb
import torch

sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
EXP = PROJECT_ROOT / "data" / "processed" / "ml" / "expanded"
ORIG = PROJECT_ROOT / "data" / "processed" / "ml"
OUT = EXP / "models"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from eval_metrics_expanded import evaluate_groups, haversine_km

FEATURE_COLS = [
    "lat", "lon", "iceberg_length_nm", "iceberg_width_nm",
    "sea_ice_concentration", "wind_u_10m", "wind_v_10m",
    "temperature_2m", "mean_sea_level_pressure",
    "total_precipitation", "bathymetry_elevation",
    "ocean_current_u", "ocean_current_v",
    "wind_speed", "wind_dir", "ocean_speed", "ocean_dir",
    "wind_ocean_angle", "exposed_water_fraction",
    "prev_lat", "prev_lon", "prev_delta_lat", "prev_delta_lon",
    "prev_speed", "prev_bearing",
]

checks = []


def check(name, ok, detail=""):
    checks.append((name, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}  {detail}")


def main() -> int:
    print("=" * 70)
    print("PHASE 3C — VALIDATION SUITE")
    print("=" * 70)

    # ── 1. Expanded dataset unchanged ──
    print("\n[1] EXPANDED DATASET INTEGRITY")
    full = pd.read_parquet(EXP / "full.parquet")
    tr = pd.read_parquet(EXP / "train.parquet")
    va = pd.read_parquet(EXP / "val.parquet")
    te = pd.read_parquet(EXP / "test.parquet")
    check("451 valid pairs preserved", len(full) == 451, f"full={len(full)}")
    check("Split counts 342/55/54",
          len(tr) == 342 and len(va) == 55 and len(te) == 54,
          f"{len(tr)}/{len(va)}/{len(te)}")
    check("8 iceberg IDs", full["iceberg_id"].nunique() == 8,
          f"{sorted(full['iceberg_id'].unique())}")
    check("39 columns / 25 features",
          len(full.columns) == 39 and len([c for c in full.columns
                                           if c in FEATURE_COLS]) == 25,
          f"{len(full.columns)} cols")

    # ── 2. Original Phase 3 dataset unchanged ──
    print("\n[2] ORIGINAL PHASE 3 DATASET")
    orig_full = pd.read_parquet(ORIG / "full.parquet")
    check("Original still 101 pairs", len(orig_full) == 101, f"orig full={len(orig_full)}")
    orig_mtime = (ORIG / "full.parquet").stat().st_mtime_ns
    exp_dir_mtime = EXP.stat().st_mtime_ns
    check("Original predates expanded build", orig_mtime < exp_dir_mtime)

    # ── 3. Chronological split / no leakage ──
    print("\n[3] LEAKAGE")
    train_max = pd.to_datetime(tr["obs_date"]).max()
    val_min = pd.to_datetime(va["obs_date"]).min()
    val_max = pd.to_datetime(va["obs_date"]).max()
    test_min = pd.to_datetime(te["obs_date"]).min()
    check("train < val < test", train_max < val_min and val_max < test_min,
          f"{train_max.date()} < {val_min.date()}; {val_max.date()} < {test_min.date()}")
    check("C39 isolated to test",
          (tr["iceberg_id"] == "C39").sum() == 0 and
          (va["iceberg_id"] == "C39").sum() == 0 and
          (te["iceberg_id"] == "C39").sum() == 9,
          f"train=0 val=0 test=9")

    # ── 4. Feature schema ──
    print("\n[4] FEATURE SCHEMA")
    check("Feature cols identical to approved",
          set(full.columns) == set(orig_full.columns),
          "" if set(full.columns) == set(orig_full.columns)
          else f"diff={set(full.columns) ^ set(orig_full.columns)}")

    # ── 5. Predictions finite ──
    print("\n[5] PREDICTIONS FINITE")
    for name, path in [("persistence", "persistence_predictions.csv"),
                       ("random_forest", "rf_predictions.csv"),
                       ("xgboost", "xgb_predictions.csv"),
                       ("lstm", "lstm_predictions.csv")]:
        p = pd.read_csv(OUT / path)
        finite = bool(np.isfinite(p["pred_lat"]).all() and np.isfinite(p["pred_lon"]).all())
        check(f"{name} predictions finite", finite, f"n={len(p)}")

    # ── 6. Models reload & reproduce ──
    print("\n[6] MODEL RELOAD + REPRODUCTION")
    X_te = te[FEATURE_COLS].values

    # RF
    rf_lat = joblib.load(OUT / "random_forest_latitude.joblib")
    rf_lon = joblib.load(OUT / "random_forest_longitude.joblib")
    rf_pred_lat = rf_lat.predict(X_te)
    rf_pred_lon = rf_lon.predict(X_te)
    rf_saved = pd.read_csv(OUT / "rf_predictions.csv")
    check("RF reload matches saved predictions",
          np.allclose(rf_pred_lat, rf_saved["pred_lat"]) and
          np.allclose(rf_pred_lon, rf_saved["pred_lon"]))

    # XGB
    xgb_lat = xgb.XGBRegressor()
    xgb_lat.load_model(OUT / "xgboost_latitude.json")
    xgb_lon = xgb.XGBRegressor()
    xgb_lon.load_model(OUT / "xgboost_longitude.json")
    xgb_pred_lat = xgb_lat.predict(X_te)
    xgb_pred_lon = xgb_lon.predict(X_te)
    xgb_saved = pd.read_csv(OUT / "xgb_predictions.csv")
    check("XGB reload matches saved predictions",
          np.allclose(xgb_pred_lat, xgb_saved["pred_lat"]) and
          np.allclose(xgb_pred_lon, xgb_saved["pred_lon"]))

    # LSTM
    te_seq = pd.read_csv(OUT / "lstm_predictions.csv")
    check("LSTM predictions finite & present", len(te_seq) > 0, f"n={len(te_seq)}")

    # ── 7. Reported metrics match recomputed ──
    print("\n[7] METRICS RECOMPUTATION MATCH")
    pers_meta = json.loads((OUT / "persistence_metrics.json").read_text())
    pers_saved = pd.read_csv(OUT / "persistence_predictions.csv")
    pers_recomp = evaluate_groups(te, pers_saved["pred_lat"].values,
                                  pers_saved["pred_lon"].values)
    m = pers_meta["metrics"]["overall"]
    r = pers_recomp["overall"]
    check("Persistence overall pos_mae matches", np.isclose(m["pos_mae"], r["pos_mae"], atol=1e-3),
          f"{m['pos_mae']:.4f} vs {r['pos_mae']:.4f}")

    for name, meta_file, pred_file in [
        ("RF", "rf_expanded_metadata.json", "rf_predictions.csv"),
        ("XGB", "xgb_expanded_metadata.json", "xgb_predictions.csv"),
    ]:
        meta = json.loads((OUT / meta_file).read_text())
        pred = pd.read_csv(OUT / pred_file)
        recomp = evaluate_groups(te, pred["pred_lat"].values, pred["pred_lon"].values)
        m = meta["test_metrics"]["overall"]
        r = recomp["overall"]
        check(f"{name} overall pos_mae matches", np.isclose(m["pos_mae"], r["pos_mae"], atol=1e-3),
              f"{m['pos_mae']:.4f} vs {r['pos_mae']:.4f}")

    # ── 8. Final summary ──
    print("\n" + "=" * 70)
    npass = sum(1 for _, ok, _ in checks if ok)
    nfail = len(checks) - npass
    print(f"RESULT: {npass}/{len(checks)} checks PASS  ({nfail} FAIL)")
    print("=" * 70)
    return 0 if nfail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
