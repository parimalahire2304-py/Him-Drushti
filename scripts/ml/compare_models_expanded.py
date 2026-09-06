#!/usr/bin/env python3
"""
PHASE 3C — Model comparison across persistence / RF / XGBoost / LSTM
on the expanded 54-sample test set.

Loads the saved metadata + predictions from each model and assembles:
  - comparison tables per subgroup (overall, drifting, grounded, C39)
  - best-overall / best-drifting determination
  - the required verdicts (does ML beat persistence? does XGB beat RF?
    does LSTM beat XGB? does any model improve drifting? is C39 useful?)

Writes data/processed/ml/expanded/models/comparison_summary.json for the
report generator.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
EXP = PROJECT_ROOT / "data" / "processed" / "ml" / "expanded"
OUT_DIR = EXP / "models"


def load_group(m):
    """Normalise a model's metrics dict to {group: {pos_mae, ...}}."""
    return {g: v for g, v in m["metrics"].items()}


def _groups(m, g):
    mm = m.get("metrics", {}).get(g, {})
    if not mm and "test_metrics" in m:
        mm = m["test_metrics"].get(g, {})
    return mm


def main() -> int:
    print("=" * 70)
    print("PHASE 3C — MODEL COMPARISON")
    print("=" * 70)

    pers = json.loads((OUT_DIR / "persistence_metrics.json").read_text())
    pers = pers["metrics"] if "metrics" in pers else pers["test_metrics"]
    rf = json.loads((OUT_DIR / "rf_expanded_metadata.json").read_text())
    xgb = json.loads((OUT_DIR / "xgb_expanded_metadata.json").read_text())
    lstm = json.loads((OUT_DIR / "lstm_expanded_metadata.json").read_text())
    # normalise keys
    rf = {"metrics": rf["test_metrics"], **{k: v for k, v in rf.items() if k != "test_metrics"}}
    xgb = {"metrics": xgb["test_metrics"], **{k: v for k, v in xgb.items() if k != "test_metrics"}}
    lstm = {"metrics": lstm["test_metrics"], **{k: v for k, v in lstm.items() if k != "test_metrics"}}
    pers = {"metrics": pers, **{k: v for k, v in pers.items()}}

    models = {
        "Persistence": pers,
        "RandomForest": rf,
        "XGBoost": xgb,
        "LSTM": lstm,
    }

    groups = ["overall", "drifting", "grounded", "C39"]

    # ── Build per-group tables of key metrics ──
    tables = {}
    for g in groups:
        rows = {}
        for name, m in models.items():
            mm = m["metrics"].get(g, {})
            if mm.get("n", 0) == 0:
                rows[name] = None
                continue
            rows[name] = {
                "n": mm["n"],
                "pos_mae": mm["pos_mae"],
                "pos_rmse": mm["pos_rmse"],
                "pos_median": mm["pos_median"],
                "pos_max": mm["pos_max"],
                "final_position_error": mm["final_position_error"],
                "trajectory_error": mm["trajectory_error"],
                "mean_displacement_error": mm["mean_displacement_error"],
                "lat_mae": mm["lat_mae"],
                "lon_mae": mm["lon_mae"],
                "lat_rmse": mm["lat_rmse"],
                "lon_rmse": mm["lon_rmse"],
            }
        tables[g] = rows

    for g in groups:
        print(f"\n  [{g.upper()}]  Position MAE (km) by model:")
        for name, r in tables[g].items():
            if r:
                print(f"    {name:13s} n={r['n']:3d}  pos_mae={r['pos_mae']:.4f}  "
                      f"pos_rmse={r['pos_rmse']:.4f}  med={r['pos_median']:.4f}  "
                      f"max={r['pos_max']:.4f}  final={r['final_position_error']:.4f}  "
                      f"traj={r['trajectory_error']:.4f}  disp={r['mean_displacement_error']:.4f}")
            else:
                print(f"    {name:13s}  (no samples)")

    # ── Verdicts ──
    def pos_mae(name, g="overall"):
        r = tables[g][name]
        return r["pos_mae"] if r else float("inf")

    overall = {n: pos_mae(n, "overall") for n in models}
    best_overall = min(overall, key=overall.get)
    drifting = {n: pos_mae(n, "drifting") for n in models}
    best_drifting = min(drifting, key=drifting.get)

    def impr(base, new):
        if base == float("inf"):
            return None
        return (base - new) / base * 100

    verdicts = {
        "best_overall_model": best_overall,
        "best_drifting_model": best_drifting,
        "does_RF_beat_persistence": pos_mae("RandomForest") < pos_mae("Persistence"),
        "does_XGB_beat_RF": pos_mae("XGBoost") < pos_mae("RandomForest"),
        "does_LSTM_beat_XGB": pos_mae("LSTM") < pos_mae("XGBoost"),
        "does_any_improve_drifting": any(drifting[n] < drifting["Persistence"] for n in models
                                         if n != "Persistence"),
        "drifting_pos_mae": drifting,
        "overall_pos_mae": overall,
        "improvement_over_persistence_pct": {
            n: impr(overall["Persistence"], v) for n, v in overall.items() if n != "Persistence"
        },
    }

    # ── Computational cost ──
    cost = {}
    for name, m in models.items():
        timing = m.get("timing", {})
        if name == "Persistence":
            cost[name] = {"train_s": 0.0, "infer_s": timing.get("inference_time_s", 0.0)}
        elif name == "LSTM":
            cost[name] = {"train_s": (timing.get("train_lat_s", 0) + timing.get("train_lon_s", 0)
                                      + timing.get("final_lat_s", 0) + timing.get("final_lon_s", 0)),
                          "infer_s": timing.get("infer_s", 0.0)}
        else:  # RF / XGB
            cost[name] = {"train_s": timing.get("train_s", 0.0),
                          "infer_s": (timing.get("infer_lat_s", 0) + timing.get("infer_lon_s", 0))}
    verdicts["computational_cost"] = cost

    # ── Feature importance comparison (RF vs XGB) ──
    rf_imp = rf.get("feature_importance_avg", {})
    xgb_imp = xgb.get("feature_importance_avg", {})
    imp_df = pd.DataFrame({"feature": list(rf_imp.keys()),
                           "rf_importance": [rf_imp.get(k, 0) for k in rf_imp],
                           "xgb_importance": [xgb_imp.get(k, 0) for k in rf_imp]})
    imp_df["rf_rank"] = imp_df["rf_importance"].rank(ascending=False)
    imp_df["xgb_rank"] = imp_df["xgb_importance"].rank(ascending=False)
    imp_df = imp_df.sort_values("rf_importance", ascending=False).reset_index(drop=True)
    verdicts["feature_importance"] = imp_df.to_dict(orient="records")
    verdicts["rf_ocean_importance_share"] = rf.get("ocean_importance_share")
    verdicts["xgb_ocean_importance_share"] = xgb.get("ocean_importance_share")
    verdicts["rf_env_importance_share"] = rf.get("env_importance_share")
    verdicts["xgb_env_importance_share"] = xgb.get("env_importance_share")

    verdicts["tables"] = tables
    (OUT_DIR / "comparison_summary.json").write_text(json.dumps(verdicts, indent=2), encoding="utf-8")

    print("\n" + "=" * 70)
    print("VERDICTS")
    print("=" * 70)
    print(f"  Best overall model:   {best_overall}")
    print(f"  Best drifting model:  {best_drifting}")
    print(f"  Does RF beat persistence?  {'YES' if verdicts['does_RF_beat_persistence'] else 'NO'}")
    print(f"  Does XGB beat RF?          {'YES' if verdicts['does_XGB_beat_RF'] else 'NO'}")
    print(f"  Does LSTM beat XGB?        {'YES' if verdicts['does_LSTM_beat_XGB'] else 'NO'}")
    print(f"  Does any model improve drifting over persistence?  "
          f"{'YES' if verdicts['does_any_improve_drifting'] else 'NO'}")
    print("\n  Overall pos_mae:", {k: round(v, 3) for k, v in overall.items()})
    print("  Drifting pos_mae:", {k: round(v, 3) for k, v in drifting.items()})
    print("\n  Saved → comparison_summary.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
