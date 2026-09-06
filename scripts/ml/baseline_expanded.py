#!/usr/bin/env python3
"""
PHASE 3C — Persistence baseline on the EXPANDED 54-sample test set.

Deterministic, no training. Predict next position = current position.
Evaluated with the shared metrics module (eval_metrics_expanded) so the
numbers are identical in structure to every ML model's.

Outputs:
  data/processed/ml/expanded/models/persistence_metrics.json
  data/processed/ml/expanded/models/persistence_predictions.csv
"""
from __future__ import annotations

import json
import sys
import time
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from eval_metrics_expanded import evaluate_groups

sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
EXP = PROJECT_ROOT / "data" / "processed" / "ml" / "expanded"
TEST_PATH = EXP / "test.parquet"
OUT_DIR = EXP / "models"


def main() -> int:
    print("=" * 70)
    print("PHASE 3C — PERSISTENCE BASELINE (expanded 54-sample test set)")
    print("=" * 70)

    te = pd.read_parquet(TEST_PATH)
    assert len(te) == 54, f"Expected 54 test samples, got {len(te)}"

    # Persistence: predict next position = current position
    t0 = time.perf_counter()
    pred_lat = te["persist_lat"].values.copy()
    pred_lon = te["persist_lon"].values.copy()
    infer_s = time.perf_counter() - t0

    assert np.all(np.isfinite(pred_lat)) and np.all(np.isfinite(pred_lon))
    results = evaluate_groups(te, pred_lat, pred_lon)

    print("\nPERSISTENCE BASELINE METRICS")
    for group, m in results.items():
        print(f"  {group:10s} n={m['n']:3d}  pos_mae={m['pos_mae']:.4f}  "
              f"pos_rmse={m['pos_rmse']:.4f}  med={m['pos_median']:.4f}  "
              f"max={m['pos_max']:.4f}  final={m['final_position_error']:.4f}  "
              f"traj={m['trajectory_error']:.4f}  disp={m['mean_displacement_error']:.4f}")

    # Save
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "model": "persistence",
        "dataset": "expanded",
        "test_samples": int(len(te)),
        "date": date.today().isoformat(),
        "inference_time_s": infer_s,
        "metrics": results,
    }
    (OUT_DIR / "persistence_metrics.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

    pred_df = te[["iceberg_id", "obs_date", "target_date", "lat", "lon",
                  "target_lat", "target_lon", "persist_lat", "persist_lon"]].copy()
    pred_df["pred_lat"] = pred_lat
    pred_df["pred_lon"] = pred_lon
    pred_df.to_csv(OUT_DIR / "persistence_predictions.csv", index=False)
    print(f"\nSaved → {OUT_DIR / 'persistence_metrics.json'}")
    print(f"Saved → {OUT_DIR / 'persistence_predictions.csv'}")

    print("\nRESULT: persistence baseline complete. Overall Position MAE = %.3f km" %
          results["overall"]["pos_mae"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
