# PHASE 7E — FINAL REPORT
## Replace Synthetic DEMO-A with Real Historical D22 (Controlled Demonstration Input Change)

**Date:** 2026-09-07
**Scope:** Replace the synthetic DEMO-A demonstration *input* with the real historical
D22 observation (2019-11-01) already present in the existing local dataset. **Historical
replay — not live detection.** This is an INPUT-only change; no core engine, dataset,
model, schema, or dashboard logic was modified.

---

## 1. Exact File Modified

`scripts/communication/run_offshore_publish.py` (the Phase 6 publisher entry point).

This is the only file changed by Phase 7E. `git status` shows no Phase 3G / Phase 4 /
Phase 5 / Phase 6 core file, no dataset, and no model file modified.

---

## 2. Exact DEMO-A Code/Input Replaced

The previous `_synthetic_observation()` builder (which constructed a fabricated
`DEMO-A` observation at `-68.5, 76.0`, size 12×8 NM, with invented env values such as
`sea_ice 0.3`, `wind_u 2.0`, `wind_v -1.0`, `temp 265`, `mslp 101300`, `bathy -500`,
`ocean_u 0.05`, `ocean_v -0.02`) was **removed**. The synthetic `IcebergState(…,
synthetic=True, source_note="synthetic two-laptop demo")` was replaced with
`synthetic=False, source_note="historical replay: US NIC D22 2019-11-01 (real observation)"`.

**No DEMO-A remains** in the operational path (grep-confirmed: no `DEMO-A`,
no `synthetic two-laptop demo`). The demo vessel `RV-DEMO` remains `synthetic=True`
(unchanged per spec — the ship is a demo vessel; the note it triggers in the frozen
Phase 4 engine reflects that synthetic vessel, not the iceberg).

---

## 3. Exact Source of D22 Data

Read directly from the **existing local ML dataset**:
`data/processed/ml/expanded/train.parquet` — the D22 `2019-11-01` row containing the
full 23-feature vector (19 env + 4 motion) assembled by the existing Phase 3C pipeline
from the 2019 feature stack and the real 2019-10-25 predecessor.

New functions in the publisher:
- `_load_real_d22_row()` — duckdb `read_parquet` query
  (`iceberg_id='D22' AND obs_date='2019-11-01'`) with pandas fallback; **raises** if the
  row is missing or if verified values drift (no silent fallback).
- `_real_d22_observation(row, ts)` — builds the MQTT observation via the existing
  `schemas.build_observation`, passing every real env/motion value through `**extra_env`
  (which filters `None`), so **no value is invented** and missing-data schema behavior
  is preserved.

The CSV `data/processed/icebergs/east_prydz_bay_icebergs.csv` is used for cross-checking
only and is **byte-for-byte unchanged** (see §12).

---

## 4. Verification of D22 Stored Values

| Field | Stored value (verified) |
|---|---|
| iceberg_id | `D22` |
| observation_date | `2019-11-01` |
| latitude | `-66.77` |
| longitude | `75.42` |
| size | `11.0 × 2.0` NM |
| data_source | `US NIC` |

The loader hard-guards these (id, date, lat/lon) with `ValueError` if they drift from
the dataset, so the publisher cannot silently publish wrong/corrupted data.

---

## 5. Predecessor Verification

Real predecessor **2019-10-25 at `-66.52, 76.52`** (exactly 7 days earlier) recognized
by the **existing forecast eligibility logic**:
- `prev_lat=-66.52, prev_lon=76.52`, `prev_delta_lat=-0.25, prev_delta_lon=-1.10`,
  `prev_speed=7.984, prev_bearing=239.67`.
- `_has_valid_predecessor` (4 prev_* finite) → **predecessor_available = True**,
  produced by the pipeline, **not** manually set.

---

## 6. Forecast Method (produced by existing pipeline)

**`MOTION_AWARE_XGBOOST`** — `model=motion_aware_xgb`, `predecessor=True`,
`fallback=None`. Produced by the existing Phase 3G `ForecastEngine` from the real 23-feature
row (no model modification, no manual forecast, no bypassed eligibility).

---

## 7. Forecast Output

- forecast_latitude = `-66.91608088135719`
- forecast_longitude = `74.53473017930985`

Both produced by the existing pipeline from the real D22 inputs.

---

## 8. Risk Output (Phase 4 Risk Engine)

- risk_class = **LOW**
- risk_score = `2.978`
- separation = `135.74` km, envelope = `82.27` km, corridor = `87.27` km

Computed by the unmodified Phase 4 `RiskEngine`. Note: the frozen engine appends
"SYNTHETIC DEMO DATA — NOT a real observation." because the **demo vessel** RV-DEMO is
synthetic (per spec the ship is unchanged); the iceberg itself is now `synthetic=False`
(real data).

---

## 9. Route Output (Phase 5 Route Optimizer)

- status = **SAFE** (label `ROUTE`), 52 waypoints
- route_distance = `164.31` km vs direct `141.58` km (16.05% overhead)
- high/moderate risk cells encountered = `0`, max risk score on route = `0.0`

This is the existing optimizer's **genuine** result for these real inputs — no threshold
lowering, no iceberg movement, no ship repositioning, no forced route.

---

## 10. MQTT Publication Result

Connected to the LAN broker `10.20.231.143:1883` (Mosquitto) and published all **5**
normal message types. A live broker subscription captured the actual wire payloads:

| Topic | Message type | Key content |
|---|---|---|
| `himdrushti/observation` | observation | iceberg=D22, obs_time=2019-11-01, lat=-66.77, lon=75.42, source=US NIC, historical_replay=True |
| `himdrushti/forecast` | forecast | method=MOTION_AWARE_XGBOOST, model=motion_aware_xgb, predecessor=True, lat=-66.916, lon=74.535 |
| `himdrushti/risk` | risk | LOW |
| `himdrushti/route` | route | SAFE |
| `himdrushti/status` | status | FRESH |

All published with the existing `OffshorePublisher` over the existing `PahoTransport` —
no new transport, no parallel pipeline.

---

## 11. DEMO-A Removal

**Confirmed removed.** The synthetic DEMO-A observation builder and its use in `main()`
are gone; grep finds no `DEMO-A` string anywhere in the operational path. The demo now
publishes only the real D22 record.

---

## 12. Dataset Integrity

- `data/processed/icebergs/east_prydz_bay_icebergs.csv` — **byte-for-byte unchanged**
  (SHA-256 `903ae4c553adf81a1a5d25790c67a6e64d1a782a27bad075b669e46c5918e88b`; not in
  `git status`; only read for cross-check).
- `data/processed/ml/expanded/train.parquet`, `2019_feature_stack.nc` — unchanged
  (mtimes 09-05/09-04, before this session; only read via duckdb).
- Feature stacks, raw weekly files — unmodified.

---

## 13. Model Integrity

- `data/processed/ml/models/drifting_xgboost/motion_aware_xgb_{latitude,longitude}.json`
  — unchanged (loaded read-only; "Loaded Motion-aware XGBoost (n_features=23, n_train=99)").
- No retraining performed.

---

## 14. Phase 3G / 4 / 5 / 6 Regression Results

| Suite | Result |
|---|---|
| Phase 3G (`validate_phase3g.py`) | **22/22 PASS** (incl. no protected edits, no 2026, C39 preserved, models reload & reproduce) |
| Phase 4 risk (`validate_risk_engine.py`) | **22/22 PASS** |
| Phase 5 routing (`validate_routing.py`) | **19/19 PASS** |
| Phase 6 communication (`validate_communication.py`) | **15/15 PASS** |
| Integration (`validate_integration.py`) | **18/18 PASS** |

No retraining, no downloads.

---

## 15. Limitations

1. **Not live detection** — this is a **historical replay** of the 2019-11-01 US NIC
   weekly archive record for D22. The publisher banner and observation
   `historical_replay=True` / `historical_label` identify it as such. It must not be
   presented as live satellite or ship detection.
2. The frozen Phase 4 engine labels the assessment "SYNTHETIC DEMO DATA" because the
   **demo vessel RV-DEMO is synthetic** (unchanged per spec). The D22 iceberg itself is
   marked `synthetic=False` (real). The label reflects the scenario's demo ship, not the
   iceberg.
3. Data/model files are gitignored, so integrity is established via mtimes + hash + the
   fact that only read operations were performed (no write path was ever executed).
4. Observation epoch is 2019; the risk-assessment `observed_at` is the existing demo
   framing (`now − 24h`) used by the unmodified communication-state age logic, consistent
   with the unchanged Phase 4/6 pipeline.

---

**Historical replay — not live detection.**

D22 HISTORICAL DEMO INPUT VALIDATED — WAITING FOR APPROVAL.
