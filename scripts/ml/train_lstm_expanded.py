#!/usr/bin/env python3
"""
PHASE 3C — LSTM on the EXPANDED dataset.

Faithful adaptation of the approved Phase 3 Step 6 LSTM methodology
(sequence-based, SEQ_LENGTH=2 = 14-day context) to the expanded
342-train / 55-val / 54-test dataset.

Integrity rules preserved:
  - scaler (StandardScaler) fit on TRAINING sequences only
  - sequence length retained from prior validated methodology (train/val)
  - validation set used for early stopping only (no test leakage)
  - final model retrained on TRAIN+VAL sequences
  - evaluated once on the TEST sequences
  - C39 zero-shot isolation preserved

Note: LSTM uses sequences of 2 consecutive 7-day observations built from
each split's own data. Test obs are not all 7-day-consecutive within the
test split, so N_test_seq may be < 54; the number is reported transparently.

Outputs (data/processed/ml/expanded/models/):
  lstm_latitude.pt / lstm_longitude.pt
  lstm_scaler_lat.joblib / lstm_scaler_lon.joblib
  lstm_expanded_metadata.json
  lstm_training_history.json
  lstm_predictions.csv
"""
from __future__ import annotations

import json
import sys
import time
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from sklearn.preprocessing import StandardScaler

from eval_metrics_expanded import evaluate_groups

sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
EXP = PROJECT_ROOT / "data" / "processed" / "ml" / "expanded"
OUT_DIR = EXP / "models"
TRAIN_PATH = EXP / "train.parquet"
VAL_PATH = EXP / "val.parquet"
TEST_PATH = EXP / "test.parquet"

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
TARGET_COLS = ["target_lat", "target_lon"]
RANDOM_STATE = 42
np.random.seed(RANDOM_STATE)
torch.manual_seed(RANDOM_STATE)

SEQ_LENGTH = 2  # validated sequence length (14-day context) from Phase 3 Step 6
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

CONFIG = {
    "random_state": RANDOM_STATE,
    "feature_cols": FEATURE_COLS,
    "target_cols": TARGET_COLS,
    "n_features": len(FEATURE_COLS),
    "seq_length": SEQ_LENGTH,
    "hidden_size": 32,
    "num_layers": 1,
    "dropout": 0.2,
    "epochs": 200,
    "lr": 0.001,
    "patience": 10,
    "batch_size": 16,
}


def build_lstm_sequences(df, seq_length, split_name):
    """Build sequences of consecutive 7-day observations per iceberg."""
    sequences = []
    all_obs = set(zip(df["iceberg_id"], df["obs_date"]))
    df["obs_dt"] = pd.to_datetime(df["obs_date"])

    for iceberg_id in df["iceberg_id"].unique():
        ib = df[df["iceberg_id"] == iceberg_id].sort_values("obs_date")
        obs_dates = pd.to_datetime(ib["obs_date"]).values
        runs = []
        current = [obs_dates[0]]
        for i in range(1, len(obs_dates)):
            gap = int((obs_dates[i] - current[-1]).astype("timedelta64[D]").astype(int))
            if gap == 7:
                current.append(obs_dates[i])
            else:
                if len(current) >= 2:
                    runs.append(current)
                current = [obs_dates[i]]
        if len(current) >= 2:
            runs.append(current)

        for run in runs:
            for start_idx in range(len(run) - seq_length):
                seq_dates = run[start_idx:start_idx + seq_length]
                target_date = seq_dates[-1] + np.timedelta64(7, "D")
                tgt_key = (iceberg_id, str(target_date)[:10])
                if tgt_key not in all_obs:
                    continue
                seq_features = []
                ok = True
                for d in seq_dates:
                    d_str = str(d)[:10]
                    row = df[(df["iceberg_id"] == iceberg_id) & (df["obs_date"] == d_str)]
                    if len(row) == 0:
                        ok = False
                        break
                    seq_features.append(row[FEATURE_COLS].values[0])
                if not ok or len(seq_features) < seq_length:
                    continue
                tgt_row = df[(df["iceberg_id"] == iceberg_id) &
                             (df["obs_date"] == str(target_date)[:10])]
                if len(tgt_row) == 0:
                    continue
                target = tgt_row[TARGET_COLS].values[0]
                obs_split = ib[ib["obs_date"] == str(seq_dates[-1])[:10]]["split"].values[0]
                sequences.append({
                    "sequence": np.array(seq_features),
                    "target": target,
                    "obs_date": str(seq_dates[-1])[:10],
                    "target_date": str(target_date)[:10],
                    "iceberg_id": iceberg_id,
                    "split": obs_split,
                })
    return sequences


class IcebergDataset(Dataset):
    def __init__(self, X, y):
        self.X = torch.FloatTensor(X)
        self.y = torch.FloatTensor(y)

    def __len__(self):
        return len(self.X)

    def __getitem__(self, idx):
        return self.X[idx], self.y[idx]


class IcebergLSTM(nn.Module):
    def __init__(self, input_size, hidden_size=32, num_layers=1, dropout=0.2):
        super().__init__()
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.lstm = nn.LSTM(input_size=input_size, hidden_size=hidden_size,
                            num_layers=num_layers, batch_first=True,
                            dropout=dropout if num_layers > 1 else 0.0)
        self.fc = nn.Sequential(nn.Linear(hidden_size, 16), nn.ReLU(), nn.Linear(16, 1))

    def forward(self, x):
        lstm_out, _ = self.lstm(x)
        return self.fc(lstm_out[:, -1, :]).squeeze(-1)


def train_lstm_model(model, train_loader, val_loader, epochs, lr, patience, model_name):
    criterion = nn.MSELoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=1e-5)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode="min",
                                                           factor=0.5, patience=10)
    best_val = float("inf")
    best_state = None
    no_improve = 0
    train_losses, val_losses = [], []
    t0 = time.perf_counter()

    for epoch in range(epochs):
        model.train()
        el = 0.0
        for Xb, yb in train_loader:
            Xb, yb = Xb.to(DEVICE), yb.to(DEVICE)
            optimizer.zero_grad()
            pred = model(Xb)
            loss = criterion(pred, yb)
            if torch.isnan(loss):
                continue
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            el += loss.item() * len(Xb)
        train_losses.append(el / len(train_loader.dataset))

        model.eval()
        vl = 0.0
        with torch.no_grad():
            for Xb, yb in val_loader:
                Xb, yb = Xb.to(DEVICE), yb.to(DEVICE)
                vl += criterion(model(Xb), yb).item() * len(Xb)
        vl /= len(val_loader.dataset)
        val_losses.append(vl)
        scheduler.step(vl)

        if vl < best_val and not np.isnan(vl):
            best_val = vl
            best_state = {k: v.clone() for k, v in model.state_dict().items()}
            no_improve = 0
        else:
            no_improve += 1
            if no_improve >= patience:
                print(f"  [{model_name}] Early stopping at epoch {epoch+1}")
                break

    if best_state is not None:
        model.load_state_dict(best_state)
    train_s = time.perf_counter() - t0
    print(f"  [{model_name}] Best val loss: {best_val:.6f}  train time {train_s:.1f}s")
    return model, train_losses, val_losses, train_s


def main() -> int:
    print("=" * 70)
    print("PHASE 3C — LSTM (expanded dataset)")
    print(f"  Device: {DEVICE}  Seq length: {SEQ_LENGTH}")
    print("=" * 70)

    train_df = pd.read_parquet(TRAIN_PATH)
    val_df = pd.read_parquet(VAL_PATH)
    test_df = pd.read_parquet(TEST_PATH)
    assert len(train_df) == 342 and len(val_df) == 55 and len(test_df) == 54
    print(f"  Rows — Train {len(train_df)} | Val {len(val_df)} | Test {len(test_df)}")

    for col in FEATURE_COLS + TARGET_COLS:
        assert col in train_df.columns

    # ── Build sequences per split (validated methodology) ──
    tr_seq = build_lstm_sequences(train_df, SEQ_LENGTH, "train")
    va_seq = build_lstm_sequences(val_df, SEQ_LENGTH, "val")
    te_seq = build_lstm_sequences(test_df, SEQ_LENGTH, "test")
    print(f"  Sequences — Train {len(tr_seq)} | Val {len(va_seq)} | Test {len(te_seq)}")

    # C39 isolation in sequences
    tr_c39 = sum(1 for s in tr_seq if s["iceberg_id"] == "C39")
    va_c39 = sum(1 for s in va_seq if s["iceberg_id"] == "C39")
    te_c39 = sum(1 for s in te_seq if s["iceberg_id"] == "C39")
    print(f"  C39 sequences — Train {tr_c39} | Val {va_c39} | Test {te_c39}")
    assert tr_c39 == 0 and va_c39 == 0 and te_c39 > 0

    # ── Scale: fit on TRAIN only ──
    X_tr = np.stack([s["sequence"] for s in tr_seq])   # (N, L, F)
    X_va = np.stack([s["sequence"] for s in va_seq])
    X_te = np.stack([s["sequence"] for s in te_seq])
    y_tr = np.stack([s["target"] for s in tr_seq])
    y_va = np.stack([s["target"] for s in va_seq])
    y_te = np.stack([s["target"] for s in te_seq])

    # Scale features across (N*L, F); scale targets per-target
    scaler_lat = StandardScaler()
    scaler_lon = StandardScaler()
    flat_tr = X_tr.reshape(-1, X_tr.shape[-1])

    # Impute NaN in features with training mean (prev_* first-obs NaN)
    feat_mean = np.nanmean(flat_tr, axis=0)
    def impute(X):
        X = X.copy()
        mask = np.isnan(X)
        X[mask] = np.take(feat_mean, np.where(mask)[1])
        return X

    flat_tr_imp = impute(flat_tr)

    scaler_lat.fit(y_tr[:, 0].reshape(-1, 1))
    scaler_lon.fit(y_tr[:, 1].reshape(-1, 1))

    # Feature scaling: standardize using train-only fit (after imputation)
    feat_scaler = StandardScaler()
    feat_scaler.fit(flat_tr_imp)
    X_tr_s = feat_scaler.transform(impute(X_tr.reshape(-1, X_tr.shape[-1]))).reshape(X_tr.shape)
    X_va_s = feat_scaler.transform(impute(X_va.reshape(-1, X_va.shape[-1]))).reshape(X_va.shape)
    X_te_s = feat_scaler.transform(impute(X_te.reshape(-1, X_te.shape[-1]))).reshape(X_te.shape)
    y_tr_lat_s = scaler_lat.transform(y_tr[:, 0].reshape(-1, 1)).flatten()
    y_tr_lon_s = scaler_lon.transform(y_tr[:, 1].reshape(-1, 1)).flatten()
    y_va_lat_s = scaler_lat.transform(y_va[:, 0].reshape(-1, 1)).flatten()
    y_va_lon_s = scaler_lon.transform(y_va[:, 1].reshape(-1, 1)).flatten()
    y_te_lat_s = scaler_lat.transform(y_te[:, 0].reshape(-1, 1)).flatten()
    y_te_lon_s = scaler_lon.transform(y_te[:, 1].reshape(-1, 1)).flatten()

    print("  Feature scaler fit on TRAIN sequences only (NaN imputed with train mean)")
    print(f"  Scaled test feature shape: {X_te_s.shape}")

    # ── Train lat / lon with val early stopping ──
    def build_loaders(X, y):
        ds = IcebergDataset(X, y)
        return DataLoader(ds, batch_size=CONFIG["batch_size"], shuffle=False)

    model_lat = IcebergLSTM(CONFIG["n_features"], CONFIG["hidden_size"],
                            CONFIG["num_layers"], CONFIG["dropout"])
    model_lon = IcebergLSTM(CONFIG["n_features"], CONFIG["hidden_size"],
                            CONFIG["num_layers"], CONFIG["dropout"])
    n_params = sum(p.numel() for p in model_lat.parameters())
    print(f"  LSTM params per model: {n_params}")

    print("\n--- Training latitude LSTM (val early stopping) ---")
    model_lat, hist_lat_tr, hist_lat_va, t_lat = train_lstm_model(
        model_lat, build_loaders(X_tr_s, y_tr_lat_s), build_loaders(X_va_s, y_va_lat_s),
        CONFIG["epochs"], CONFIG["lr"], CONFIG["patience"], "lat")
    print("\n--- Training longitude LSTM (val early stopping) ---")
    model_lon, hist_lon_tr, hist_lon_va, t_lon = train_lstm_model(
        model_lon, build_loaders(X_tr_s, y_tr_lon_s), build_loaders(X_va_s, y_va_lon_s),
        CONFIG["epochs"], CONFIG["lr"], CONFIG["patience"], "lon")

    # ── Retrain final on TRAIN+VAL sequences ──
    # Scaling/statistics remain fit on TRAIN ONLY (imputation mean + scaler),
    # applied to the combined train+val and test sets.
    print("\n--- Retraining final on TRAIN+VAL sequences (scaler still train-only) ---")
    X_tv = np.concatenate([X_tr, X_va], axis=0)
    y_tv = np.concatenate([y_tr, y_va], axis=0)
    X_tv_s = feat_scaler.transform(impute(X_tv.reshape(-1, X_tv.shape[-1]))).reshape(X_tv.shape)
    X_va_s = feat_scaler.transform(impute(X_va.reshape(-1, X_va.shape[-1]))).reshape(X_va.shape)
    X_te_s = feat_scaler.transform(impute(X_te.reshape(-1, X_te.shape[-1]))).reshape(X_te.shape)
    y_tv_lat_s = scaler_lat.transform(y_tv[:, 0].reshape(-1, 1)).flatten()
    y_tv_lon_s = scaler_lon.transform(y_tv[:, 1].reshape(-1, 1)).flatten()

    final_lat = IcebergLSTM(CONFIG["n_features"], CONFIG["hidden_size"],
                            CONFIG["num_layers"], CONFIG["dropout"])
    final_lon = IcebergLSTM(CONFIG["n_features"], CONFIG["hidden_size"],
                            CONFIG["num_layers"], CONFIG["dropout"])
    final_lat, _, _, t_final_lat = train_lstm_model(
        final_lat, build_loaders(X_tv_s, y_tv_lat_s), build_loaders(X_va_s, y_va_lat_s),
        CONFIG["epochs"], CONFIG["lr"], CONFIG["patience"], "final_lat")
    final_lon, _, _, t_final_lon = train_lstm_model(
        final_lon, build_loaders(X_tv_s, y_tv_lon_s), build_loaders(X_va_s, y_va_lon_s),
        CONFIG["epochs"], CONFIG["lr"], CONFIG["patience"], "final_lon")

    # ── Evaluate once on test sequences ──
    print("\n--- Evaluating on TEST sequences ---")
    final_lat.eval()
    final_lon.eval()
    t0 = time.perf_counter()
    with torch.no_grad():
        pred_lat_s = final_lat(torch.FloatTensor(X_te_s).to(DEVICE)).cpu().numpy()
        pred_lon_s = final_lon(torch.FloatTensor(X_te_s).to(DEVICE)).cpu().numpy()
    infer_s = time.perf_counter() - t0
    pred_lat = scaler_lat.inverse_transform(pred_lat_s.reshape(-1, 1)).flatten()
    pred_lon = scaler_lon.inverse_transform(pred_lon_s.reshape(-1, 1)).flatten()
    assert np.all(np.isfinite(pred_lat)) and np.all(np.isfinite(pred_lon))

    # Build a test DataFrame aligned to the evaluated sequences for subgroup metrics
    seq_test_df = pd.DataFrame([{
        "iceberg_id": s["iceberg_id"], "obs_date": s["obs_date"],
        "target_date": s["target_date"], "target_lat": s["target"][0],
        "target_lon": s["target"][1], "lat": s["sequence"][-1, 0],
        "lon": s["sequence"][-1, 1], "displacement_km": float(np.nan),
    } for s in te_seq])
    # fill displacement_km from original test set for these samples
    key = test_df.set_index(["iceberg_id", "obs_date"])["displacement_km"]
    seq_test_df["displacement_km"] = seq_test_df.apply(
        lambda r: key.get((r["iceberg_id"], str(r["obs_date"])), np.nan), axis=1)
    seq_test_df["obs_date"] = seq_test_df["obs_date"].astype(str)

    results = evaluate_groups(seq_test_df, pred_lat, pred_lon)
    print(f"  LSTM evaluated on {len(seq_test_df)} test sequences")
    for group, m in results.items():
        print(f"    {group:10s} n={m['n']:3d}  pos_mae={m['pos_mae']:.4f}  "
              f"pos_rmse={m['pos_rmse']:.4f}  med={m['pos_median']:.4f}  max={m['pos_max']:.4f}  "
              f"final={m['final_position_error']:.4f}  traj={m['trajectory_error']:.4f}  "
              f"disp={m['mean_displacement_error']:.4f}")

    # ── Save ──
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    torch.save(final_lat.state_dict(), OUT_DIR / "lstm_latitude.pt")
    torch.save(final_lon.state_dict(), OUT_DIR / "lstm_longitude.pt")
    import joblib
    joblib.dump(feat_scaler, OUT_DIR / "lstm_feature_scaler.joblib")
    joblib.dump(scaler_lat, OUT_DIR / "lstm_scaler_lat.joblib")
    joblib.dump(scaler_lon, OUT_DIR / "lstm_scaler_lon.joblib")

    meta = {
        "model_type": "IcebergLSTM",
        "dataset": "expanded",
        "targets": TARGET_COLS,
        "n_features": CONFIG["n_features"],
        "feature_columns": FEATURE_COLS,
        "architecture": {"input_size": CONFIG["n_features"], "hidden_size": CONFIG["hidden_size"],
                          "num_layers": CONFIG["num_layers"], "dropout": CONFIG["dropout"],
                          "fc": "32->16->1"},
        "seq_length": SEQ_LENGTH,
        "n_params": int(n_params),
        "n_sequences": {"train": len(tr_seq), "val": len(va_seq),
                         "test": len(te_seq), "trainval": len(X_tv)},
        "split_counts": {"train": 342, "val": 55, "test": 54},
        "training_date": date.today().isoformat(),
        "random_state": RANDOM_STATE,
        "scaling": "StandardScaler fit on TRAIN sequences only",
        "timing": {"train_lat_s": t_lat, "train_lon_s": t_lon,
                    "final_lat_s": t_final_lat, "final_lon_s": t_final_lon,
                    "infer_s": infer_s},
        "test_metrics": results,
        "note": "LSTM evaluates on test SEQUENCES (2 consecutive 7-day obs within test split); "
                "N_test_seq may be < 54. Reported n per group is the true count.",
    }
    (OUT_DIR / "lstm_expanded_metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    history = {
        "lat": {"train_loss": hist_lat_tr, "val_loss": hist_lat_va,
                 "best_val_loss": float(min(hist_lat_va))},
        "lon": {"train_loss": hist_lon_tr, "val_loss": hist_lon_va,
                 "best_val_loss": float(min(hist_lon_va))},
    }
    (OUT_DIR / "lstm_training_history.json").write_text(json.dumps(history, indent=2), encoding="utf-8")

    pred_df = seq_test_df[["iceberg_id", "obs_date", "target_date", "lat", "lon",
                           "target_lat", "target_lon"]].copy()
    pred_df["pred_lat"] = pred_lat
    pred_df["pred_lon"] = pred_lon
    pred_df.to_csv(OUT_DIR / "lstm_predictions.csv", index=False)

    print(f"\n  Saved LSTM models + scalers + metadata → {OUT_DIR}")

    pers = evaluate_groups(test_df, test_df["persist_lat"].values, test_df["persist_lon"].values)
    print(f"\n  NOTE: LSTM evaluated on {len(seq_test_df)} test sequences vs 54 flat-test rows.")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
