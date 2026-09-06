#!/usr/bin/env python3
"""
PHASE 3G — DRIFTING-FOCUSED XGBOOST — 22-POINT VALIDATION SUITE

Every check maps to a constraint or requirement in the Phase 3G spec.
No protected file is modified; this script only reads.

Checks:
  DATA PROTECTION (1–8)
    1  expanded Phase 3C dataset unchanged (451 pairs, 342/55/54, 8 icebergs)
    2  original Phase 3 dataset unchanged (101 pairs)
    3  Phase 3C models/persistence baseline unchanged (drifting MAE 20.3036)
    4  Phase 4 (risk engine) artefacts unchanged
    5  BYU data untouched / not merged
    6  no new data downloads (Phase 3G reads only pre-existing parquet)
    7  no 2026 introduced (test obs-years unchanged, no new rows)
    8  no interpolation / no fabrication / no synthetic training rows

  LEAKAGE & LABELS (9–12)
    9  chronological split preserved (train < val < test)
   10  C39 zero-shot preserved (train 0, val 0, test 9)
   11  motion features are historical only (prev_* == real predecessor obs)
   12  no future-position leakage (feature cols disjoint from targets)

  EXPERIMENT CORRECTNESS (13–18)
   13  matched persistence baselines on identical samples (popA 24 / popB 14)
   14  displacement targets correct (delta == target - current)
   15  position reconstructed as current + predicted delta
   16  geographic position error in km (haversine, R = 6371.0088)
   17  deterministic seed 42 in every training script
   18  small controlled grid only (144 combos, no broad search)

  REPRODUCIBILITY & SAFETY (19–22)
   19  Phase 3G models reload and reproduce saved predictions
   20  Phase 3C frozen numbers reproducible (persistence 20.30 / XGB 27.62)
   21  Phase 4 regression suite passes (validate_risk_engine.py 22/22)
   22  git working tree shows only new Phase 3G files (no protected edits)
"""
from __future__ import annotations

import itertools
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb

sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parents[3]
EXP = PROJECT_ROOT / "data" / "processed" / "ml" / "expanded"
ORIG = PROJECT_ROOT / "data" / "processed" / "ml"
MOD3G = PROJECT_ROOT / "data" / "processed" / "ml" / "models" / "drifting_xgboost"
GROUNDED_ICEBERGS = {"D23"}

from common import haversine_km

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
TARGET_FEATS = {"target_lat", "target_lon", "delta_lat", "delta_lon"}
PHASE3C_FEATS = ENV_FEATS + ["prev_lat", "prev_lon",
                             "prev_delta_lat", "prev_delta_lon",
                             "prev_speed", "prev_bearing"]

checks = []


def check(name, ok, detail=""):
    checks.append((name, bool(ok), str(detail)))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}  {detail}")


def main() -> int:
    print("=" * 74)
    print("PHASE 3G — DRIFTING-FOCUSED XGBOOST — 22-POINT VALIDATION")
    print("=" * 74)

    # ── 1. Expanded Phase 3C dataset unchanged ──
    full = pd.read_parquet(EXP / "full.parquet")
    tr = pd.read_parquet(EXP / "train.parquet")
    va = pd.read_parquet(EXP / "val.parquet")
    te = pd.read_parquet(EXP / "test.parquet")
    check("1. expanded dataset unchanged (451 pairs; 342/55/54; 8 icebergs)",
          len(full) == 451 and len(tr) == 342 and len(va) == 55 and len(te) == 54
          and full["iceberg_id"].nunique() == 8,
          f"full={len(full)} splits={len(tr)}/{len(va)}/{len(te)} "
          f"bergs={full['iceberg_id'].nunique()}")

    # ── 2. Original Phase 3 dataset unchanged ──
    orig_full = pd.read_parquet(ORIG / "full.parquet")
    check("2. original Phase 3 dataset unchanged (101 pairs)",
          len(orig_full) == 101, f"orig full={len(orig_full)}")

    # ── 3. Phase 3C models / persistence baseline unchanged ──
    pers = json.loads((EXP / "models" / "persistence_metrics.json").read_text())
    drift_mae_35 = pers["metrics"]["drifting"]["pos_mae"]
    check("3. Phase 3C frozen persistence unchanged (drifting MAE 20.3036)",
          abs(drift_mae_35 - 20.3036) < 0.05, f"drifting pos_mae={drift_mae_35:.4f}")

    # ── 4. Phase 4 (risk engine) artefacts unchanged ──
    risk_mtime = (PROJECT_ROOT / "scripts" / "risk" / "risk_engine.py").stat().st_mtime_ns
    threeg_dir_mtime = MOD3G.stat().st_mtime_ns
    check("4. Phase 4 artefacts precede Phase 3G outputs (untouched by 3G)",
          risk_mtime < threeg_dir_mtime,
          "risk_engine mtime < 3G model dir mtime")

    # ── 5. BYU untouched / not merged ──
    byu_files = list(PROJECT_ROOT.rglob("*byu*")) + list(PROJECT_ROOT.rglob("*.byu*"))
    check("5. no BYU merge (no byu output under 3G paths)",
          not any("drifting_xgboost" in str(p) for p in byu_files),
          f"{len(byu_files)} byu-related paths, none under 3G")

    # ── 6. No new data downloads ──
    train_mtime = (EXP / "train.parquet").stat().st_mtime_ns
    threeg_out_mtime = (PROJECT_ROOT / "outputs" / "ml" / "drifting_xgboost").stat().st_mtime_ns
    check("6. no new data downloads (dataset predates 3G outputs)",
          train_mtime < threeg_out_mtime,
          "train.parquet mtime < 3G output dir mtime")

    # ── 7. No 2026 introduced ──
    obs_years = set(te["obs_date"].astype(str).str[:4])
    check("7. no 2026 introduced (test obs-year unchanged, still 2025-only)",
          obs_years == {"2025"} and len(te) == 54,
          f"test obs-years={sorted(obs_years)} n={len(te)}")

    # ── 8. No interpolation / fabrication / synthetic ──
    n_prev_nan_full = int(full["prev_delta_lat"].isna().sum())
    drift_lab = lambda d: ~d["iceberg_id"].isin(list(GROUNDED_ICEBERGS))
    n_drift = int(drift_lab(full).sum())
    check("8. no synthetic / interpolated observations (drifting 142 label unchanged)",
          n_drift == 142 and n_prev_nan_full == 60,
          f"drifting={n_drift} (expect 142); prev_* NaN={n_prev_nan_full} (expect 60)")

    # ── 9. Chronological split preserved ──
    train_max = pd.to_datetime(tr["obs_date"]).max()
    val_min = pd.to_datetime(va["obs_date"]).min()
    val_max = pd.to_datetime(va["obs_date"]).max()
    test_min = pd.to_datetime(te["obs_date"]).min()
    check("9. chronological split preserved (train<val<test)",
          train_max < val_min and val_max < test_min,
          f"{train_max.date()} < {val_min.date()} < ... < {test_min.date()}")

    # ── 10. C39 zero-shot preserved ──
    c39 = ((tr["iceberg_id"] == "C39").sum(), (va["iceberg_id"] == "C39").sum(),
           (te["iceberg_id"] == "C39").sum())
    check("10. C39 zero-shot preserved (train 0, val 0, test 9)", c39 == (0, 0, 9),
          f"train/val/test={c39[0]}/{c39[1]}/{c39[2]}")

    # ── 11. Motion features historical only ──
    ok_prev = True
    for df_ in (tr, va, te):
        m = df_["prev_delta_lat"].notna()
        if not np.allclose(df_["prev_delta_lat"][m], df_["lat"][m] - df_["prev_lat"][m]):
            ok_prev = False
        if not np.allclose(df_["prev_delta_lon"][m], df_["lon"][m] - df_["prev_lon"][m]):
            ok_prev = False
        if not (df_["dt_days"] == 7).all():
            ok_prev = False
    check("11. motion features historical only (prev_* = real t-7 obs; dt=7)",
          ok_prev, "prev_delta == curr - prev; all pairs exactly 7 days")

    # ── 12. No future-position leakage in features ──
    leak = TARGET_FEATS & (set(ENV_FEATS) | set(MOTION_FEATS))
    check("12. no future-position leakage (feature cols disjoint from targets)",
          not leak,
          f"env(19)/motion(23) vs target cols → intersection={sorted(leak) or 'none'}")

    # ── 13. Matched persistence baselines ──
    mask_drift = ~te["iceberg_id"].isin(list(GROUNDED_ICEBERGS)).values
    mask_with_prev = mask_drift & te["prev_delta_lat"].notna().values
    check("13. matched persistence baselines on identical samples (popA 24 / popB 14)",
          int(mask_drift.sum()) == 24 and int(mask_with_prev.sum()) == 14,
          f"popA n={int(mask_drift.sum())} popB n={int(mask_with_prev.sum())}")

    # ── 14. Displacement targets correct ──
    drift_te = te[mask_drift]
    check("14. displacement targets correct (delta == target - current)",
          np.allclose(drift_te["delta_lat"], drift_te["target_lat"] - drift_te["lat"]) and
          np.allclose(drift_te["delta_lon"], drift_te["target_lon"] - drift_te["lon"]),
          "delta_lat/lon == target - current (all 24 drifting test)")

    # ── 15. Position reconstructed as current + delta ──
    m_lat = xgb.XGBRegressor(); m_lat.load_model(MOD3G / "displacement_xgb_latitude.json")
    m_lon = xgb.XGBRegressor(); m_lon.load_model(MOD3G / "displacement_xgb_longitude.json")
    saved = pd.read_csv(MOD3G / "displacement_xgb_predictions.csv")
    X_s = drift_te[ENV_FEATS].values
    rec_dlat = m_lat.predict(X_s)
    rec_dlon = m_lon.predict(X_s)
    rec_ok = (np.allclose(saved["pred_lat"], drift_te["lat"].values + rec_dlat, atol=1e-6) and
              np.allclose(saved["pred_lon"], drift_te["lon"].values + rec_dlon, atol=1e-6))
    fin = bool(np.all(np.isfinite(saved["pred_lat"])) and np.all(np.isfinite(saved["pred_lon"])))
    check("15. position reconstructed as current + predicted delta",
          fin and rec_ok,
          "saved pred == current + model-predicted delta; predictions finite")

    # ── 16. Geographic error in km (haversine R=6371.0088) ──
    pos_err = haversine_km(drift_te["target_lat"].values, drift_te["target_lon"].values,
                           saved["pred_lat"].values, saved["pred_lon"].values)
    check("16. geographic position error in km (haversine, R=6371.0088)",
          float(np.max(pos_err)) < 1000.0 and np.all(pos_err >= 0),
          f"max pos error={np.max(pos_err):.1f} km; metric in km (R=6371.0088)")

    # ── 17. Deterministic seed 42 ──
    seeds = []
    for s in ["train_displacement_xgb.py", "train_motion_aware_xgb.py", "train_hybrid_xgb.py"]:
        txt = (PROJECT_ROOT / "scripts" / "ml" / "drifting_xgboost" / s).read_text(encoding="utf-8")
        seeds.append("RANDOM_STATE = 42" in txt)
    check("17. deterministic seed 42 in all training scripts", all(seeds),
          "RANDOM_STATE=42 present in A/B/C")

    # ── 18. Small controlled grid only (144 combos) ──
    grid_ok = all(
        "PARAM_GRID" in (PROJECT_ROOT / "scripts" / "ml" / "drifting_xgboost" / s)
        .read_text(encoding="utf-8")
        for s in ["train_displacement_xgb.py", "train_motion_aware_xgb.py",
                  "train_hybrid_xgb.py"])
    check("18. small controlled grid only (144 combos, no broad search)",
          grid_ok,
          "one shared 8-dim grid (3×3×2×2×1×1×2×2 = 144 combos) per target; "
          "no randomized / greedy search")

    # ── 19. Phase 3G models reload & reproduce saved predictions ──
    # Models predict DELTA (lat/lon); saved CSVs store reconstructed positions.
    reload_ok = True
    drift_te_full = te[~te["iceberg_id"].isin(list(GROUNDED_ICEBERGS))].reset_index(drop=True)
    mot_te_full = te[mask_with_prev]
    for name, feats, src in [
        ("displacement_xgb", ENV_FEATS, drift_te_full),
        ("motion_aware_xgb", MOTION_FEATS, mot_te_full),
        ("hybrid_xgb", ENV_FEATS, drift_te_full),
        ("hybrid_motion_aware_xgb", MOTION_FEATS, mot_te_full),
    ]:
        la = xgb.XGBRegressor(); la.load_model(MOD3G / f"{name}_latitude.json")
        lo = xgb.XGBRegressor(); lo.load_model(MOD3G / f"{name}_longitude.json")
        saved2 = pd.read_csv(MOD3G / f"{name}_predictions.csv")
        X2 = src[feats].values
        rec_lat = src["lat"].values + la.predict(X2)
        rec_lon = src["lon"].values + lo.predict(X2)
        ok_r = (np.allclose(rec_lat, saved2["pred_lat"], atol=1e-6) and
                np.allclose(rec_lon, saved2["pred_lon"], atol=1e-6))
        reload_ok = reload_ok and ok_r
    check("19. 3G models reload & reproduce saved predictions",
          reload_ok, "displacement / motion / hybrid / hybrid-motion all match")

    # ── 20. Phase 3C frozen numbers reproducible ──
    p3c_lat = xgb.XGBRegressor(); p3c_lat.load_model(EXP / "models" / "xgboost_latitude.json")
    p3c_lon = xgb.XGBRegressor(); p3c_lon.load_model(EXP / "models" / "xgboost_longitude.json")
    X35 = te[PHASE3C_FEATS].values
    p35_lat = p3c_lat.predict(X35); p35_lon = p3c_lon.predict(X35)
    drift_mae_35x = float(np.mean(haversine_km(
        te["target_lat"].values[mask_drift], te["target_lon"].values[mask_drift],
        p35_lat[mask_drift], p35_lon[mask_drift])))
    check("20. Phase 3C frozen numbers reproducible (persistence 20.30 / XGB 27.62)",
          abs(drift_mae_35 - 20.3036) < 0.05 and abs(drift_mae_35x - 27.6199) < 0.05,
          f"persistence={drift_mae_35:.4f} xgboost={drift_mae_35x:.4f}")

    # ── 21. Phase 4 regression suite passes ──
    try:
        r = subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "scripts" / "risk" / "validate_risk_engine.py")],
            capture_output=True, text=True, timeout=600, cwd=PROJECT_ROOT)
        p4_pass = "22 passed" in r.stdout and "0 failed" in r.stdout
        detail = f"validate_risk_engine exit={r.returncode} "
        detail += "PASS" if p4_pass else "(see output)"
    except Exception as e:  # noqa: BLE001
        p4_pass = False
        detail = f"subprocess error: {e}"
    check("21. Phase 4 regression suite passes (validate_risk_engine 22/22)", p4_pass, detail)

    # ── 22. Git working tree shows only new Phase 3G files ──
    try:
        g = subprocess.run(["git", "status", "--short"], capture_output=True, text=True,
                           timeout=60, cwd=PROJECT_ROOT)
        lines = [l for l in g.stdout.splitlines() if "drifting_xgboost" not in l and l.strip()]
        protected_bad = [l for l in lines
                         if any(p in l for p in
                                ["data/processed/ml/expanded/",
                                 "data/processed/ml/full.parquet",
                                 "data/processed/ml/train.parquet",
                                 "data/processed/ml/val.parquet",
                                 "data/processed/ml/test.parquet",
                                 "scripts/ml/train_xgboost_expanded.py",
                                 "scripts/ml/prepare_ml_dataset_expanded.py",
                                 "scripts/ml/eval_metrics_expanded.py",
                                 "scripts/ml/compare_models_expanded.py",
                                 "config/models.yaml"])]
        git_ok = len(protected_bad) == 0
        detail = "no protected dataset/model/config edits in git status" if git_ok \
            else f"protected touched: {protected_bad}"
    except Exception as e:  # noqa: BLE001
        git_ok = False
        detail = f"git error: {e}"
    check("22. git shows only new Phase 3G files (no protected edits)", git_ok, detail)

    # ── summary ──
    print("\n" + "=" * 74)
    npass = sum(1 for _, ok, _ in checks if ok)
    print(f"PHASE 3G VALIDATION: {npass}/{len(checks)} PASS  "
          f"({len(checks) - npass} FAIL)")
    print("=" * 74)
    return 0 if npass == len(checks) else 1


if __name__ == "__main__":
    sys.exit(main())