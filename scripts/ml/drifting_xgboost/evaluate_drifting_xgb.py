#!/usr/bin/env python3
"""
PHASE 3G — DRIFTING-FOCUSED XGBOOST — FULL EVALUATION & COMPARISON

Loads the saved Phase 3G models AND the FROZEN Phase 3C XGBoost + persistence,
then computes MATCHED baselines on the exact same eligible test samples each
experiment used, plus the per-iceberg and C39 analyses.

Never retrains: every model is reloaded from disk and only predicts.

Populations:
  popA      : 24 drifting test samples (no predecessor filter)
                -> Displacement XGB (env), Hybrid-env
  popB      : 14 drifting test samples WITH predecessor
                -> Motion-aware XGB, Hybrid-motion
  (existing XGBoost + persistence are computed on BOTH populations)

Outputs:
  outputs/ml/drifting_xgboost/comparison_summary.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb

sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parents[3]
EXP = PROJECT_ROOT / "data" / "processed" / "ml" / "expanded"
MOD35 = EXP / "models"
MOD3G = PROJECT_ROOT / "data" / "processed" / "ml" / "models" / "drifting_xgboost"
OUT = PROJECT_ROOT / "outputs" / "ml" / "drifting_xgboost"
GROUNDED_ICEBERGS = {"D23"}

from common import haversine_km, compute_group_metrics, EARTH_RADIUS_KM

# Feature columns (must match training scripts exactly)
ENV_FEATS = [
    "lat", "lon", "iceberg_length_nm", "iceberg_width_nm",
    "sea_ice_concentration", "wind_u_10m", "wind_v_10m",
    "temperature_2m", "mean_sea_level_pressure", "total_precipitation",
    "bathymetry_elevation", "ocean_current_u", "ocean_current_v",
    "wind_speed", "wind_dir", "ocean_speed", "ocean_dir",
    "wind_ocean_angle", "exposed_water_fraction",
]
MOTION_FEATS = ENV_FEATS + [
    "prev_delta_lat", "prev_delta_lon", "prev_speed", "prev_bearing",
]
PHASE3C_FEATS = [
    "lat", "lon", "iceberg_length_nm", "iceberg_width_nm",
    "sea_ice_concentration", "wind_u_10m", "wind_v_10m",
    "temperature_2m", "mean_sea_level_pressure", "total_precipitation",
    "bathymetry_elevation", "ocean_current_u", "ocean_current_v",
    "wind_speed", "wind_dir", "ocean_speed", "ocean_dir",
    "wind_ocean_angle", "exposed_water_fraction",
    "prev_lat", "prev_lon", "prev_delta_lat", "prev_delta_lon",
    "prev_speed", "prev_bearing",
]


def _errs(df, pred_lat, pred_lon, mask):
    m = compute_group_metrics(df, pred_lat, pred_lon, mask)
    return {k: m[k] for k in
            ["n", "pos_mae", "pos_rmse", "pos_median", "pos_p90", "pos_max",
             "lat_mae", "lon_mae", "lat_rmse", "lon_rmse", "mean_displacement_error"]}


def _load_pair(name_lat, name_lon, mod_dir):
    m_lat = xgb.XGBRegressor(); m_lat.load_model(mod_dir / name_lat)
    m_lon = xgb.XGBRegressor(); m_lon.load_model(mod_dir / name_lon)
    return m_lat, m_lon


def main() -> int:
    print("=" * 70)
    print("PHASE 3G — FULL EVALUATION & MATCHED BASELINES")
    print("=" * 70)
    test = pd.read_parquet(EXP / "test.parquet")
    assert len(test) == 54

    ice = test["iceberg_id"].values
    mask_drift = ~np.isin(ice, list(GROUNDED_ICEBERGS))
    mask_with_prev = mask_drift & test["prev_delta_lat"].notna().values
    print(f"  popA (all drifting test)      : {int(mask_drift.sum())}")
    print(f"  popB (drifting + predecessor) : {int(mask_with_prev.sum())}")

    # Persistence = current position
    pers_pred_lat = test["persist_lat"].values
    pers_pred_lon = test["persist_lon"].values

    def _fill(mask, vals, n=54):
        out = np.zeros(n)
        out[mask] = vals
        return out

    # Frozen Phase 3C XGBoost
    p3c_lat, p3c_lon = _load_pair("xgboost_latitude.json", "xgboost_longitude.json", MOD35)

    def _frozen_35(mask):
        X = test.loc[mask, PHASE3C_FEATS].values
        return p3c_lat.predict(X), p3c_lon.predict(X)

    # Phase 3G models
    dis_lat, dis_lon = _load_pair("displacement_xgb_latitude.json",
                                  "displacement_xgb_longitude.json", MOD3G)
    mot_lat, mot_lon = _load_pair("motion_aware_xgb_latitude.json",
                                  "motion_aware_xgb_longitude.json", MOD3G)
    hyb_lat, hyb_lon = _load_pair("hybrid_xgb_latitude.json",
                                  "hybrid_xgb_longitude.json", MOD3G)
    if (MOD3G / "hybrid_motion_aware_xgb_latitude.json").exists():
        hym_lat, hym_lon = _load_pair("hybrid_motion_aware_xgb_latitude.json",
                                      "hybrid_motion_aware_xgb_longitude.json", MOD3G)
    else:
        # fall back to motion model if supplementary hybrid unavailable
        hym_lat, hym_lon = mot_lat, mot_lon

    # ── Build full-length (54) prediction arrays per model/population ──
    def _pred(mask, model_lat, model_lon, feats):
        sel = test.loc[mask]
        X = sel[feats].values
        pl = model_lat.predict(X); po = model_lon.predict(X)
        full_lat = _fill(mask, sel["lat"].values + pl)
        full_lon = _fill(mask, sel["lon"].values + po)
        return full_lat, full_lon

    # popA (24): displacement + hybrid-env; existing XGB + persistence
    pl35, po35 = _frozen_35(mask_drift)
    ex35A = (_fill(mask_drift, pl35), _fill(mask_drift, po35))
    disA = _pred(mask_drift, dis_lat, dis_lon, ENV_FEATS)
    hybA = _pred(mask_drift, hyb_lat, hyb_lon, ENV_FEATS)

    # popB (14): motion + hybrid-motion; existing XGB + persistence
    pl35b, po35b = _frozen_35(mask_with_prev)
    ex35B = (_fill(mask_with_prev, pl35b), _fill(mask_with_prev, po35b))
    motB = _pred(mask_with_prev, mot_lat, mot_lon, MOTION_FEATS)
    hymB = _pred(mask_with_prev, hym_lat, hym_lon, MOTION_FEATS)

    resA = {
        "persistence":         _errs(test, pers_pred_lat, pers_pred_lon, mask_drift),
        "existing_xgboost":    _errs(test, ex35A[0], ex35A[1], mask_drift),
        "displacement_xgboost":_errs(test, disA[0], disA[1], mask_drift),
        "hybrid":              _errs(test, hybA[0], hybA[1], mask_drift),
    }
    resB = {
        "persistence":         _errs(test, pers_pred_lat, pers_pred_lon, mask_with_prev),
        "existing_xgboost":    _errs(test, ex35B[0], ex35B[1], mask_with_prev),
        "motion_aware_xgboost":_errs(test, motB[0], motB[1], mask_with_prev),
        "hybrid_motion":       _errs(test, hymB[0], hymB[1], mask_with_prev),
    }

    print("\n  ── popA (24 drifting, all-eligible) ──")
    for k, v in resA.items():
        print(f"    {k:22s} n={v['n']:3d}  pos_mae={v['pos_mae']:.4f}  "
              f"pos_rmse={v['pos_rmse']:.4f}  med={v['pos_median']:.4f}  "
              f"p90={v['pos_p90']:.4f}  max={v['pos_max']:.4f}")

    print("\n  ── popB (14 drifting, predecessor-eligible) ──")
    for k, v in resB.items():
        print(f"    {k:22s} n={v['n']:3d}  pos_mae={v['pos_mae']:.4f}  "
              f"pos_rmse={v['pos_rmse']:.4f}  med={v['pos_median']:.4f}  "
              f"p90={v['pos_p90']:.4f}  max={v['pos_max']:.4f}")

    # ── Breakdown: year / magnitude / direction ──
    def _breakdown(mask, preds: dict) -> dict:
        """preds: {name: (pred_lat_full, pred_lon_full)} all full-length 54 arrays."""
        sub = test.loc[mask]
        full_year = sub["obs_date"].astype(str).str[:4].values
        mag = sub["displacement_km"].values
        dirn = sub["bearing_deg"].values

        def _err_over(sel_idx, names):
            out = {}
            for nm, (pl, po) in preds.items():
                m = np.zeros(len(test), dtype=bool); m[mask] = sel_idx
                out[nm] = _errs(test, pl, po, m)["pos_mae"]
            return out

        year_out = {}
        for yr in sorted(set(full_year)):
            sel = full_year == yr
            year_out[yr] = {"n": int(sel.sum()),
                            **{k: v for k, v in _err_over(sel, preds).items()}}
        mag_out = {}
        for lo, hi in [(0, 5), (5, 20), (20, 50), (50, float("inf"))]:
            lbl = f"disp_{lo}_{hi}" if hi != float("inf") else f"disp_{lo}_inf"
            sel = (mag >= lo) & (mag < hi)
            mag_out[lbl] = {"n": int(sel.sum()),
                            **{k: v for k, v in _err_over(sel, preds).items()}}
        dir_out = {}
        for name, cond in [("N", dirn < 90), ("E", (dirn >= 90) & (dirn < 180)),
                           ("S", (dirn >= 180) & (dirn < 270)), ("W", dirn >= 270)]:
            sel = cond
            dir_out[name] = {"n": int(sel.sum()),
                             **{k: v for k, v in _err_over(sel, preds).items()}}
        return {"by_year": year_out, "by_magnitude_km": mag_out, "by_direction": dir_out}

    predsA = {
        "persistence": (pers_pred_lat, pers_pred_lon),
        "existing_xgboost": ex35A,
        "displacement_xgboost": disA,
        "hybrid": hybA,
    }
    predsB = {
        "persistence": (pers_pred_lat, pers_pred_lon),
        "existing_xgboost": ex35B,
        "motion_aware_xgboost": motB,
        "hybrid_motion": hymB,
    }
    breakdownA = _breakdown(mask_drift, predsA)
    breakdownB = _breakdown(mask_with_prev, predsB)
    print("\n  ── popA breakdown (24 drifting) ──")
    for grp, d in breakdownA.items():
        print(f"  [{grp}] " + ", ".join(f"{k}:n={v['n']},mae={v['displacement_xgboost']:.0f}" for k, v in d.items())[:160])

    # ── Improvement vs matched persistence ──
    def _improvement(baseline_mae, model_mae):
        return {"abs_km": round(baseline_mae - model_mae, 4),
                "pct": round(100 * (baseline_mae - model_mae) / baseline_mae, 4)}

    result = {
        "popA": resA,
        "popB": resB,
        "breakdown_popA": breakdownA,
        "breakdown_popB": breakdownB,
        "matched_improvement_A_vs_persist": {
            k: _improvement(resA["persistence"]["pos_mae"], v["pos_mae"])
            for k, v in resA.items() if k != "persistence"
        },
        "matched_improvement_B_vs_persist": {
            k: _improvement(resB["persistence"]["pos_mae"], v["pos_mae"])
            for k, v in resB.items() if k != "persistence"
        },
    }

    # ── Per-iceberg analysis ──
    def _per_iceberg(mask, pred_lat_full, pred_lon_full):
        out = {}
        sub = test.loc[mask]
        for berg in sorted(sub["iceberg_id"].unique()):
            m = (ice == berg) & mask
            out[berg] = {
                "n": int(m.sum()),
                "persistence_mae": compute_group_metrics(
                    test, pers_pred_lat, pers_pred_lon, m)["pos_mae"],
                "model_mae": _errs(test, pred_lat_full, pred_lon_full, m)["pos_mae"],
            }
        return out

    # popA per-iceberg uses the displacement/hybrid env predictions (== hybrid)
    resA["per_iceberg"] = _per_iceberg(mask_drift, disA[0], disA[1])
    # popB per-iceberg uses the motion-aware predictions
    resB["per_iceberg"] = _per_iceberg(mask_with_prev, motB[0], motB[1])

    # ── C39 zero-shot ──
    c39 = ice == "C39"
    c39_with_prev = c39 & test["prev_delta_lat"].notna().values
    p35_c39 = _frozen_35(c39)
    p35_c39w = _frozen_35(c39_with_prev)
    resC39 = {
        "all_C39": {
            "persistence": _errs(test, pers_pred_lat, pers_pred_lon, c39),
            "existing_xgboost": _errs(
                test, _fill(c39, p35_c39[0]), _fill(c39, p35_c39[1]), c39),
            "displacement_xgboost": _errs(test, disA[0], disA[1], c39),
            "hybrid": _errs(test, disA[0], disA[1], c39),  # hybrid==displacement for env-only
        },
        "C39_with_prev": {
            "persistence": _errs(test, pers_pred_lat, pers_pred_lon, c39_with_prev),
            "existing_xgboost": _errs(
                test, _fill(c39_with_prev, p35_c39w[0]),
                _fill(c39_with_prev, p35_c39w[1]), c39_with_prev),
            "motion_aware_xgboost": _errs(test, motB[0], motB[1], c39_with_prev),
            "hybrid_motion": _errs(test, hymB[0], hymB[1], c39_with_prev),
        },
    }
    result["C39"] = resC39

    print("\n  ── C39 zero-shot ──")
    for grp, d in resC39.items():
        print(f"  [{grp}]")
        for k, v in d.items():
            print(f"    {k:22s} n={v['n']:3d}  pos_mae={v['pos_mae']:.4f}")

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "comparison_summary.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"\n  Saved → {OUT / 'comparison_summary.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())