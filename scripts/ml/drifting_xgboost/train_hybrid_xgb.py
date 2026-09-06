#!/usr/bin/env python3
"""
PHASE 3G — EXPERIMENT C: Hybrid Persistence + XGBoost residual correction

Persistence baseline: predicted position = current position (lat, lon).

Residual target:
  residual_lat = target_lat - current_lat   (= delta_lat)
  residual_lon = target_lon - current_lon   (= delta_lon)

Hybrid prediction:
  hybrid_lat = current_lat + predicted_residual_lat
  hybrid_lon = current_lon + predicted_residual_lon

This is mathematically equivalent to Experiment A when trajectories are
compared directly; the "hybrid" framing is offered for interpretability
(residual language) and for the optional safety-clipping analysis. For the
primary training, it uses the same env-only feature design as Experiment A.
A motion-aware hybrid variant is run as a second row for comparison when
Experiment B's subset supports it.

Trained ONLY on the drifting (non-D23) training population.

Output (data/processed/ml/models/drifting_xgboost/):
  hybrid_xgb_latitude.json, hybrid_xgb_longitude.json
  hybrid_xgb_metadata.json, hybrid_xgb_predictions.csv
  hybrid_motion_aware_xgb_metadata.json (optional, if B-subset size allows)

Output (outputs/ml/drifting_xgboost/):
  hybrid_xgb_evaluation.json

Deterministic seed: 42
Does NOT modify existing Phase 3C models or datasets.
"""
from __future__ import annotations

import itertools
import json
import logging
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import mean_absolute_error

sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parents[3]
EXP = PROJECT_ROOT / "data" / "processed" / "ml" / "expanded"
MOD_DIR = PROJECT_ROOT / "data" / "processed" / "ml" / "models" / "drifting_xgboost"
OUT_DIR = PROJECT_ROOT / "outputs" / "ml" / "drifting_xgboost"
GROUNDED_ICEBERGS = {"D23"}

# Canonical env-only hybrid (same 19 features as Experiment A)
FEATURE_COLS_HYBRID = [
    "lat", "lon",
    "iceberg_length_nm", "iceberg_width_nm",
    "sea_ice_concentration",
    "wind_u_10m", "wind_v_10m",
    "temperature_2m", "mean_sea_level_pressure",
    "total_precipitation", "bathymetry_elevation",
    "ocean_current_u", "ocean_current_v",
    "wind_speed", "wind_dir",
    "ocean_speed", "ocean_dir",
    "wind_ocean_angle", "exposed_water_fraction",
]
# Motion-augmented hybrid (for the supplementary row / clipping analysis)
FEATURE_COLS_HYBRID_MOTION = [
    "lat", "lon",
    "iceberg_length_nm", "iceberg_width_nm",
    "sea_ice_concentration",
    "wind_u_10m", "wind_v_10m",
    "temperature_2m", "mean_sea_level_pressure",
    "total_precipitation", "bathymetry_elevation",
    "ocean_current_u", "ocean_current_v",
    "wind_speed", "wind_dir",
    "ocean_speed", "ocean_dir",
    "wind_ocean_angle", "exposed_water_fraction",
    "prev_delta_lat", "prev_delta_lon",
    "prev_speed", "prev_bearing",
]
TARGET_LAT = "delta_lat"  # delta_lat == residual_lat = target_lat - lat
TARGET_LON = "delta_lon"
RANDOM_STATE = 42

PARAM_GRID = {
    "n_estimators":     [100, 200, 300],
    "max_depth":        [2, 3, 4],
    "learning_rate":    [0.05, 0.1],
    "min_child_weight": [5, 10],
    "subsample":        [0.8],
    "colsample_bytree": [0.8],
    "reg_alpha":        [0.1, 1.0],
    "reg_lambda":       [1.0, 5.0],
}

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)


def _haversine_km(lat1, lon1, lat2, lon2) -> np.ndarray:
    lat1, lon1, lat2, lon2 = map(np.asarray, [lat1, lon1, lat2, lon2])
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1; dlon = lon2 - lon1
    a = np.sin(dlat/2)**2 + np.cos(lat1)*np.cos(lat2)*np.sin(dlon/2)**2
    return 2 * 6371.0088 * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


def _build_combos():
    keys = list(PARAM_GRID.keys())
    return [dict(zip(keys, v)) for v in itertools.product(*PARAM_GRID.values())]


def _tune(X_tr, y_tr, X_val, y_val, target_name):
    combos = _build_combos()
    log.info("    [%s] Tuning %d combos ...", target_name, len(combos))
    t0 = time.perf_counter()
    best_mae = float("inf"); best_params = combos[0]
    for params in combos:
        m = xgb.XGBRegressor(**params, random_state=RANDOM_STATE, verbosity=0,
                              objective="reg:squarederror", n_jobs=-1)
        m.fit(X_tr, y_tr, eval_set=[(X_val, y_val)], verbose=False)
        ma = mean_absolute_error(y_val, m.predict(X_val))
        if ma < best_mae:
            best_mae = ma; best_params = params
    t = time.perf_counter() - t0
    log.info("    [%s] Best val_mae=%.6f params=%s (%.1fs)", target_name, best_mae, best_params, t)
    return best_params


def _evaluate(df, pred_lat, pred_lon) -> dict:
    ice = df["iceberg_id"].values
    drifting = ~np.isin(ice, list(GROUNDED_ICEBERGS))
    c39 = ice == "C39"
    pos_all = _haversine_km(df["target_lat"].values, df["target_lon"].values, pred_lat, pred_lon)
    pos_drift = _haversine_km(df["target_lat"].values[drifting], df["target_lon"].values[drifting],
                               pred_lat[drifting], pred_lon[drifting])
    pos_c39 = _haversine_km(df["target_lat"].values[c39], df["target_lon"].values[c39],
                             pred_lat[c39], pred_lon[c39])
    lat_e_all = np.abs(pred_lat - df["target_lat"].values)
    lon_e_all = np.abs(pred_lon - df["target_lon"].values)
    lat_e_d = np.abs(pred_lat[drifting] - df["target_lat"].values[drifting])
    lon_e_d = np.abs(pred_lon[drifting] - df["target_lon"].values[drifting])
    lat_e_c = np.abs(pred_lat[c39] - df["target_lat"].values[c39])
    lon_e_c = np.abs(pred_lon[c39] - df["target_lon"].values[c39])

    def _m(pos_e, lat_e, lon_e, n, _df=df, _pred_lat=pred_lat, _pred_lon=pred_lon):
        if n == 0:
            return {"n": 0, "pos_mae": None, "pos_rmse": None, "pos_median": None,
                    "pos_p90": None, "pos_max": None,
                    "lat_mae": None, "lon_mae": None, "lat_rmse": None, "lon_rmse": None,
                    "mean_disp_error": None}
        disp = _haversine_km(_df["lat"].values[:len(pos_e)], _df["lon"].values[:len(pos_e)],
                              _df["lat"].values[:len(pos_e)] + (_pred_lat[:len(pos_e)] - _df["lat"].values[:len(pos_e)]),
                              _df["lon"].values[:len(pos_e)] + (_pred_lon[:len(pos_e)] - _df["lon"].values[:len(pos_e)]))
        true_disp = _df["displacement_km"].values[:len(pos_e)]
        _ = _haversine_km(_df["lat"].values, _df["lon"].values, _pred_lat, _pred_lon)
        return {
            "n": int(n),
            "pos_mae":    float(np.mean(pos_e)),
            "pos_rmse":   float(np.sqrt(np.mean(pos_e**2))),
            "pos_median": float(np.median(pos_e)),
            "pos_p90":    float(np.quantile(pos_e, 0.90)),
            "pos_max":    float(np.max(pos_e)),
            "lat_mae":    float(np.mean(lat_e)),
            "lon_mae":    float(np.mean(lon_e)),
            "lat_rmse":   float(np.sqrt(np.mean(lat_e**2))),
            "lon_rmse":   float(np.sqrt(np.mean(lon_e**2))),
            "mean_disp_error": float(np.mean(np.abs(_ - true_disp[:len(pos_e)]))) if len(pos_e) == len(_df) else
                                       float(np.mean(np.abs(pos_e))),
        }

    drifting_n = int(drifting.sum())
    return {
        "overall":  _m(pos_all, lat_e_all, lon_e_all, len(df)),
        "drifting": _m(pos_drift, lat_e_d, lon_e_d, drifting_n),
        "grounded": {"n": int((~drifting).sum())},
        "C39":      _m(pos_c39, lat_e_c, lon_e_c, int(c39.sum())),
    }


def _run_one(tag: str, feat_cols: list[str],
             train_df, val_df, test_df,
             filter_missing: bool = False) -> dict:
    """Run one hybrid training pass and return (metrics, params, train_n, val_n, test_n)."""
    if filter_missing:
        mask_tr = train_df["prev_delta_lat"].notna()
        mask_va = val_df["prev_delta_lat"].notna()
        mask_te = test_df["prev_delta_lat"].notna()
        tr = train_df[mask_tr].reset_index(drop=True)
        va = val_df[mask_va].reset_index(drop=True)
        te = test_df[mask_te].reset_index(drop=True)
        dropped = (int((~mask_tr).sum()), int((~mask_va).sum()), int((~mask_te).sum()))
        log.info("  [%s] predecessor-filtered: train=%d/%d val=%d/%d test=%d/%d",
                 tag, len(tr), len(train_df), len(va), len(val_df), len(te), len(test_df))
    else:
        tr, va, te = train_df, val_df, test_df
        dropped = (0, 0, 0)

    n_tr, n_va, n_te = len(tr), len(va), len(te)
    X_tr = tr[feat_cols].values; y_tr_lat = tr[TARGET_LAT].values; y_tr_lon = tr[TARGET_LON].values
    X_va = va[feat_cols].values; y_va_lat = va[TARGET_LAT].values; y_va_lon = va[TARGET_LON].values
    X_te = te[feat_cols].values

    params_lat = _tune(X_tr, y_tr_lat, X_va, y_va_lat, f"{tag}:delta_lat")
    params_lon = _tune(X_tr, y_tr_lon, X_va, y_va_lon, f"{tag}:delta_lon")

    X_tv = np.vstack([X_tr, X_va])
    y_tv_lat = np.concatenate([y_tr_lat, y_va_lat])
    y_tv_lon = np.concatenate([y_tr_lon, y_va_lon])
    log.info("  [%s] Retraining on %d samples ...", tag, len(X_tv))
    t0 = time.perf_counter()
    lat_m = xgb.XGBRegressor(**params_lat, random_state=RANDOM_STATE, verbosity=0,
                               objective="reg:squarederror", n_jobs=-1)
    lon_m = xgb.XGBRegressor(**params_lon, random_state=RANDOM_STATE, verbosity=0,
                               objective="reg:squarederror", n_jobs=-1)
    lat_m.fit(X_tv, y_tv_lat, verbose=False)
    lon_m.fit(X_tv, y_tv_lon, verbose=False)
    train_s = time.perf_counter() - t0

    pred_dlat = lat_m.predict(X_te)
    pred_dlon = lon_m.predict(X_te)
    # Hybrid reconstruction = persistence + residual (= current + displacement)
    pred_lat = te["lat"].values + pred_dlat
    pred_lon = te["lon"].values + pred_dlon

    metrics = _evaluate(te, pred_lat, pred_lon)
    log.info("  TEST metrics  drift_pos_mae=%.4f  drift_pos_rmse=%.4f  drift_lat_mae=%.4f  drift_lon_mae=%.4f",
             metrics["drifting"]["pos_mae"], metrics["drifting"]["pos_rmse"],
             metrics["drifting"]["lat_mae"], metrics["drifting"]["lon_mae"])

    return {
        "lat_model": lat_m, "lon_model": lon_m,
        "pred_lat": pred_lat, "pred_lon": pred_lon,
        "te": te, "params_lat": params_lat, "params_lon": params_lon,
        "metrics": metrics, "train_s": train_s,
        "n_tr": n_tr, "n_va": n_va, "n_te": n_te, "dropped": dropped,
    }


def main() -> int:
    print("=" * 70)
    print("PHASE 3G — EXPERIMENT C: Hybrid Persistence + XGBoost residual")
    print("=" * 70)

    train_df = pd.read_parquet(EXP / "train.parquet")
    val_df   = pd.read_parquet(EXP / "val.parquet")
    test_df  = pd.read_parquet(EXP / "test.parquet")

    is_drift = lambda d: ~d["iceberg_id"].isin(list(GROUNDED_ICEBERGS))
    tr = train_df[is_drift(train_df)].reset_index(drop=True)
    va = val_df[is_drift(val_df)].reset_index(drop=True)
    te = test_df[is_drift(test_df)].reset_index(drop=True)

    print(f"  Drifting: train={len(tr)}  val={len(va)}  test={len(te)}")
    print(f"  Residual = actual_future - current (== delta_lat/lon)")
    print(f"  Hybrid  = current + predicted_residual")

    # Primary hybrid (env-only)
    print("\n  ── Primary Hybrid (env-only, no prev_*) ──")
    h = _run_one("HYBRID(env)", FEATURE_COLS_HYBRID, tr, va, te, filter_missing=False)

    MOD_DIR.mkdir(parents=True, exist_ok=True)
    h["lat_model"].save_model(MOD_DIR / "hybrid_xgb_latitude.json")
    h["lon_model"].save_model(MOD_DIR / "hybrid_xgb_longitude.json")

    meta = {
        "experiment": "C",
        "model_name": "hybrid_xgb",
        "description": "Hybrid persistence + XGBoost residual (env-only, drifting-only)",
        "feature_columns": FEATURE_COLS_HYBRID,
        "n_features": len(FEATURE_COLS_HYBRID),
        "target_columns": [TARGET_LAT, TARGET_LON],
        "drifting_train_n": h["n_tr"], "drifting_val_n": h["n_va"],
        "drifting_test_n": h["n_te"],
        "test_icebergs": sorted(h["te"]["iceberg_id"].unique().tolist()),
        "hyperparameters": {"latitude": h["params_lat"], "longitude": h["params_lon"]},
        "training_samples": h["n_tr"] + h["n_va"],
        "training_time_s": h["train_s"],
        "random_state": RANDOM_STATE,
        "metrics": h["metrics"],
        "note": "Residual = delta_lat/lon; hybrid = current + residual",
    }
    (MOD_DIR / "hybrid_xgb_metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    pred_df = h["te"][["iceberg_id", "obs_date", "target_date", "lat", "lon",
                         "target_lat", "target_lon"]].copy()
    pred_df["pred_lat"] = h["pred_lat"]; pred_df["pred_lon"] = h["pred_lon"]
    pred_df.to_csv(MOD_DIR / "hybrid_xgb_predictions.csv", index=False)
    print(f"  Saved: {MOD_DIR / 'hybrid_xgb_*'}")

    # Supplementary motion-augmented hybrid
    print("\n  ── Supplementary Hybrid (env + prev_*) ──")
    try:
        hm = _run_one("HYBRID(motion)", FEATURE_COLS_HYBRID_MOTION, tr, va, te, filter_missing=True)
        hm_meta = {
            "experiment": "C-motion",
            "model_name": "hybrid_motion_aware_xgb",
            "description": "Hybrid persistence + XGBoost residual (env + prev_*, predecessor-filtered)",
            "feature_columns": FEATURE_COLS_HYBRID_MOTION,
            "n_features": len(FEATURE_COLS_HYBRID_MOTION),
            "target_columns": [TARGET_LAT, TARGET_LON],
            "drifting_train_n_raw": len(tr), "drifting_train_n": hm["n_tr"],
            "drifting_val_n_raw": len(va), "drifting_val_n": hm["n_va"],
            "drifting_test_n_raw": len(te), "drifting_test_n": hm["n_te"],
            "excluded_no_predecessor": {"train": hm["dropped"][0], "val": hm["dropped"][1], "test": hm["dropped"][2]},
            "test_icebergs": sorted(hm["te"]["iceberg_id"].unique().tolist()),
            "hyperparameters": {"latitude": hm["params_lat"], "longitude": hm["params_lon"]},
            "training_samples": hm["n_tr"] + hm["n_va"],
            "training_time_s": hm["train_s"],
            "random_state": RANDOM_STATE,
            "metrics": hm["metrics"],
        }
        (MOD_DIR / "hybrid_motion_aware_xgb_metadata.json").write_text(
            json.dumps(hm_meta, indent=2), encoding="utf-8")
        hm["lat_model"].save_model(MOD_DIR / "hybrid_motion_aware_xgb_latitude.json")
        hm["lon_model"].save_model(MOD_DIR / "hybrid_motion_aware_xgb_longitude.json")
        pred_df2 = hm["te"][["iceberg_id", "obs_date", "target_date", "lat", "lon",
                              "target_lat", "target_lon"]].copy()
        pred_df2["pred_lat"] = hm["pred_lat"]; pred_df2["pred_lon"] = hm["pred_lon"]
        pred_df2.to_csv(MOD_DIR / "hybrid_motion_aware_xgb_predictions.csv", index=False)
        print(f"  Saved supplementary: hybrid_motion_aware_xgb_*")
    except Exception as e:
        print(f"  Supplementary hybrid skipped: {e}")

    # Optional clipping safety-check on the primary hybrid (documented heuristic)
    gt_disp = te["displacement_km"].values
    pred_disp = _haversine_km(te["lat"].values, te["lon"].values, h["pred_lat"], h["pred_lon"])
    print("\n  ── Displacement inspection (spec §16) ──")
    print(f"    Predicted disp (km): mean={np.mean(pred_disp):.3f} 95th={np.quantile(pred_disp, 0.95):.3f} max={np.max(pred_disp):.3f}")
    print(f"    Actual    disp (km): mean={np.mean(gt_disp):.3f} 95th={np.quantile(gt_disp, 0.95):.3f} max={np.max(gt_disp):.3f}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    # canonical evaluation json reflects the primary hybrid
    (OUT_DIR / "hybrid_xgb_evaluation.json").write_text(
        json.dumps(h["metrics"], indent=2), encoding="utf-8")

    print(f"\n  Outputs: {MOD_DIR}  {OUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
