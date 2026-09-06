# PHASE 4 — UNCERTAINTY-AWARE ICEBERG RISK ENGINE

**Project:** Him-Drushti  
**Date:** 2026-09-06  
**Status:** COMPLETE — Validation 22/22 PASS  
**Prerequisite phases:** Phase 1 (data acquisition) → Phase 2 (preprocessing) → Phase 3 (ML baseline + expanded dataset + model comparison) → Phase 3F (sub-weekly feasibility audit) — all preserved and untouched.

---

## 1. Objective

Build the first operational decision-support layer of Him-Drushti:

**Iceberg Forecast → Forecast Uncertainty → Spatiotemporal Risk Corridor → Vessel-Specific Risk Score → Navigation Alert**

The engine is **uncertainty-aware by design**: it does NOT claim trajectory models are accurate. The reference forecast source is the persistence baseline (Phase 3C finding: persistence MAE 9.05 km / RMSE 24.00 km overall at 168 h; no ML model beats persistence). All uncertainty quantities are explicitly labelled as EMPIRICAL (derived from Phase 3C validation residuals), HEURISTIC (documented prototype choices), or SYNTHETIC DEMO (only inside the labelled demonstration). No heuristic is presented as statistically validated.

---

## 2. Existing Phase 3 Findings Used

| Item | Source | Role in Phase 4 |
|------|--------|-----------------|
| Region bbox / CRS / TZ / 72 h default horizon | `config/region.yaml` | Spatial/temporal domain |
| Prototype vessel defaults (RV-DEMO) | `config/vessel.yaml` | Vessel profile when caller omits one |
| Routing constraint `min_distance_from_iceberg_km: 5.0` | `config/routing.yaml` | Safety buffer in risk formula |
| Persistence baseline metrics (expanded test, n=54) | `data/processed/ml/expanded/models/persistence_metrics.json` | **EMPIRICAL** uncertainty anchors |
| Comparison summary (no model beats persistence) | `…/comparison_summary.json` | Documents that persistence is the reference source |
| Iceberg trajectories (796 obs, 11 icebergs) | `data/processed/icebergs/east_prydz_bay_icebergs.csv` | Real anchor positions (demo context only) |
| Feature stacks (8 annual NetCDFs, 9 vars) | `data/processed/integration/` | Described as available env context; not loaded by engine |
| Geodesy (`haversine_km`, `EARTH_RADIUS_KM = 6371.0088`) | `scripts/ml/baseline_model.py`, `scripts/ml/eval_metrics_expanded.py` | Distance math |
| Region utilities (`BoundingBox`, `load_region`) | `src/utils/region.py` | Bbox / CRS helpers |
| ML dataset feature extraction | `scripts/ml/prepare_ml_dataset.py` | Documented; not called by engine |

**Key Phase 3C numbers (EMPIRICAL anchors at reference_horizon_hours = 168 h):**

| Group | n | pos_RMSE (km) | pos_MAE (km) |
|-------|---|---------------|--------------|
| Overall | 54 | 24.003 | 9.053 |
| Drifting (non-D23) | 24 | 36.004 | 20.304 |
| Grounded (D23) | 30 | 0.175 | 0.052 |
| C39 zero-shot | 9 | 23.870 | 15.720 |

*Source: `persistence_metrics.json`, Phase 3C expanded test set.*

---

## 3. Input Data

The engine accepts only these input records (all optional fields have documented defaults in `risk_config.yaml`):

| Record | Required fields | Optional / defaults |
|--------|----------------|---------------------|
| **IcebergState** | `iceberg_id`, `lat`, `lon`, `observed_at`, `length_nm`, `width_nm` | `drifting` (default True), `uncertainty_mode` (None → inferred from `drifting`), `synthetic` (False), `source_note` |
| **Forecast** | `iceberg_id`, `pred_lat`, `pred_lon`, `valid_at`, `horizon_hours` | `source` (default "persistence"), `source_note` |
| **VesselState** | — (all defaults from config) | `vessel_id`, `lat`, `lon`, `at`, `draft_m`, `speed_knots`, `heading_deg`, `synthetic` |
| **Environmental uncertainty** | — | `sigma_env_km` (default 0.0; caller may supply) |

**No new datasets are downloaded.** The engine reads only `risk_config.yaml` and the empirical anchor file `persistence_metrics.json`. No model training or retraining occurs.

---

## 4. Risk Formulation (Deterministic, Config-Driven)

For each iceberg–vessel pair at a forecast cycle:

1. **Separation**  
   `sep_km = haversine_km(vessel.lat, vessel.lon, forecast.pred_lat, forecast.pred_lon)`

2. **Effective separation (safety margin)**  
   `sep_eff_km = max(sep_km - safety_buffer_km, 0.0)`  where `safety_buffer_km = 5.0` from `config/routing.yaml`.

3. **Total uncertainty (std, km)**  
   `sigma_total = sqrt( sigma_forecast² + sigma_obs² + sigma_env² + sigma_stale² )`  
   Components:
   - `sigma_forecast`: EMPIRICAL anchor × `(horizon / 168) ** gamma`  
     Anchors from Phase 3C persistence residuals (see §2). `gamma = 0.5` (HEURISTIC, random-walk analogue).
   - `sigma_obs = 1.0 km` (HEURISTIC, ~1.2 km scatterometer jitter from Phase 3E).
   - `sigma_env`: caller-supplied (default 0.0).
   - `sigma_stale`: staleness growth (see §7).

4. **Normalised separation**  
   `n_units = sep_eff_km / max(sigma_total, 1e-9)`

5. **Size scaling**  
   `size_norm = sqrt(length_nm × width_nm) / reference_size_nm`  (reference = 5.0 nm, HEURISTIC)  
   `size_scaling = min(1 + log2(size_norm), size_scaling_cap)`  (cap = 3.0, HEURISTIC).

6. **Raw exposure**  
   `raw = size_scaling × exp( -0.5 × n_units² )`

7. **Risk score (0–100)**  
   `risk_score = 100 × min(raw, 1)`

**Directional properties (validated):**
- risk ↑ when separation ↓
- risk ↑ when uncertainty ↑
- risk ↑ when size ↑ (larger iceberg ⇒ risk ≥ smaller at same geometry)
- risk ↑ when horizon ↑ (via `sigma_forecast` horizon scaling)
- risk ↑ when `sigma_env` ↑
- risk ↓ when `safety_buffer_km` ↑

All parameters live in `scripts/risk/risk_config.yaml` with EMPIRICAL / HEURISTIC / SYNTHETIC DEMO labels.

---

## 5. Uncertainty Formulation

The total uncertainty standard deviation is built from four independent components (quadrature sum):

| Component | Origin | Label |
|-----------|--------|-------|
| `sigma_forecast` | Phase 3C persistence validation pos-RMSE at 168 h, scaled to requested horizon by `h^gamma` | **EMPIRICAL** (drifting / grounded / zero-shot anchors) |
| `sigma_obs` | Fixed 1.0 km floor | **HEURISTIC** (≈ scatterometer jitter, Phase 3E) |
| `sigma_env` | Caller-supplied; default 0 | **CALLER** |
| `sigma_stale` | Prototype growth rule: `min(rate × stale_hours, cap)`; ×1.5 when COMMUNICATION LOST | **HEURISTIC** |

**Horizon scaling:** `sigma(h) = sigma_ref × (h / h_ref)^gamma`, `gamma = 0.5` (HEURISTIC, not a validated diffusion law).

**Fallback for unsupported forecast sources:** `fallback_sigma_km = 50.0` with an explicit warning note in the output. The engine flags every `heuristic_fallback` anchor with the note: *"HEURISTIC conservative fallback for a forecast source that has no Phase 3C validation record. Not statistically validated."*

**Envelope radius:** `k_sigma × sigma_total` where `k_sigma = 1.645` (HEURISTIC analogue of 90th percentile of Normal). The envelope is a **prototype decision-support region** — the legend and every output carry the note: *"NOT an exact physical boundary and NOT a statistically validated confidence interval."*

---

## 6. Risk Thresholds (Prototype Classes)

| Class | Minimum Score | Note |
|-------|---------------|------|
| LOW | 0 | Prototype class. Separation several sigma above envelope edge. |
| MODERATE | 25 | Prototype class. Vessel within ~1–1.5 sigma of the envelope edge. |
| HIGH | 50 | Prototype class. Vessel inside or near the uncertainty corridor. |

The thresholds 25 / 50 are prototype choices placing HIGH↔MODERATE near `n_units ~ 1` and MODERATE↔LOW near `n_units ~ 1.65` at unit size scaling. The config field `class_boundary_note` explicitly states: *"Thresholds 25 / 50 are prototype choices… Tunable; not a certified maritime-risk scale."* They are NOT COLREGS / IAMSAR / Polar Code categories.

---

## 7. Data Freshness Handling (State Machine)

```
FRESH  (age < freshness_hours = 48 h)
   │
   ├── sigma_stale = 0
   ├── communication_status = "NOMINAL"
   └── data_freshness = "FRESH"
   │
   ▼ (age ≥ 48 h)
STALE  (48 h ≤ age < comm_loss_hours = 168 h)
   │
   ├── sigma_stale = min(stale_growth_rate_km_per_h × stale_hours, stale_growth_cap_km)
   │   (rate = 0.5 km/h, cap = 120 km — HEURISTIC)
   ├── communication_status = "DEGRADED"
   └── data_freshness = "STALE"
   │
   ▼ (age ≥ 168 h)
COMMUNICATION LOST → LAST-KNOWN-STATE MODE
   │
   ├── sigma_stale grows with comm_loss_growth_factor = 1.5 (HEURISTIC)
   ├── NO invented observations
   ├── Engine continues forecasting from last valid state
   ├── communication_status = "COMMUNICATION LOST"
   └── data_freshness = "LAST-KNOWN-STATE MODE"
   │
   ▼ (new observation arrives)
RECOVERY → FRESH (recompute with new obs)
   ├── data_freshness = "FRESH"
   ├── sigma_stale = 0
   └── risk recomputed with updated state
```

All state transitions are deterministic and driven solely by `age_hours = (asof - observed_at).total_seconds() / 3600`.

---

## 8. Communication-Loss Handling

**LAST-KNOWN-STATE MODE** is the engine's communication-resilient mode:

- **No invented observations** — the engine never fabricates a position.
- **Last valid state continues** — the forecast is propagated from the last known position.
- **Explicit flagging** — every output record carries `data_freshness: "LAST-KNOWN-STATE MODE"` and `communication_status: "COMMUNICATION LOST"`.
- **Uncertainty grows** — `sigma_stale` accumulates at the accelerated rate (`comm_loss_growth_factor = 1.5`), capping at `stale_growth_cap_km = 120 km`.
- **Recovery** — when a new `IcebergState` with a recent `observed_at` is supplied, the engine returns to `FRESH`, `sigma_stale = 0`, and the risk is recomputed.

---

## 9. Multi-Iceberg Handling & Navigation Risk Layer

For a forecast cycle with multiple icebergs:

1. **Individual assessment** — each iceberg gets a `RiskAssessment` (risk_score, risk_class, corridor_radius, etc.).
2. **Sorting** — assessments sorted descending by `risk_score`; the highest-risk iceberg is flagged in the output.
3. **Overlapping corridors** — combined into a **navigation risk layer** on a regular grid (resolution 0.05°, matching `config/routing.yaml`):
   - Each grid cell receives `max_score` = max risk_score over all icebergs whose corridor covers that cell.
   - `nav_class` = highest class present (LOW < MODERATE < HIGH).
4. **Output** — the layer is included in the JSON payload under `navigation_layer`, designed for downstream routing engines.

---

## 10. Synthetic Demonstration (Scenarios A–E)

A single deterministic synthetic demo runs at `asof = 2025-11-12 12:00 UTC`. All data is fabricated and labelled **DEMO / SYNTHETIC SCENARIO — NOT real observations**.

| Scenario | Intent | Key Parameters | Expected Outcome |
|----------|--------|----------------|------------------|
| **A** | SAFE SEPARATION | Two icebergs; forecasts at 100 km & 44 km from vessel | LOW (score 0.03), MODERATE (41.6) |
| **B** | ICEBERG APPROACHES | Forecast 5.5 km from vessel, large iceberg | HIGH (score 100) |
| **C** | UNCERTAINTY EXPANDS | Same geometry, horizon 72 h vs 168 h | Corridor 43.8 km → 64.2 km (both HIGH) |
| **D** | COMMUNICATION LOST | Iceberg obs 400 h old (>168 h) | LAST-KNOWN-STATE MODE, corridor 206.2 km, HIGH |
| **E** | COMMUNICATION RETURNS | New obs 6 h old, same iceberg | FRESH, corridor 43.8 km, HIGH (recomputed) |

Outputs written to `outputs/risk/demo/scenario_{A..E}.json` / `.csv` and figures to `outputs/risk/figures/scenario_{A..E}.png` plus summary `risk_demo_summary.png`. Every figure legend distinguishes: **OBSERVED POSITION / FORECAST POSITION / UNCERTAINTY ENVELOPE / RISK CORRIDOR / VESSEL**, and carries the synthetic label.

---

## 11. Validation Results

Automated validation script: `scripts/risk/validate_risk_engine.py`  
**Result: 22 / 22 checks PASS**

| # | Check | Result |
|---|-------|--------|
| 1 | Phase 1/2/3/3C files untouched | PASS |
| 2 | No new dataset downloads | PASS |
| 3 | No model training / retraining | PASS |
| 4 | BYU unchanged / not merged | PASS |
| 5 | No 2026 data introduced | PASS |
| 6 | No fabricated observations outside demo | PASS |
| 7 | Demo separated & labelled | PASS |
| 8 | Risk ↑ when separation ↓ | PASS |
| 9 | Risk ↑ when uncertainty ↑ | PASS |
| 10 | Larger iceberg ⇒ risk ≥ smaller | PASS |
| 11 | Multi-iceberg handled; highest_risk returns max | PASS |
| 12 | STALE mode → sigma_stale > 0 | PASS |
| 13 | COMM_LOSS → LAST-KNOWN-STATE MODE flag | PASS |
| 14 | Recovery → FRESH, sigma_stale=0, recompute | PASS |
| 15 | Reproducible outputs (deterministic engine) | PASS |
| 16 | C39 zero-shot composition unchanged | PASS |
| 17 | Persistence remains best baseline | PASS |
| 18 | Output schema has all required fields | PASS |
| 19 | Corridor = envelope + safety_buffer_km | PASS |
| 20 | Uncertainty labelled empirical / fallback / heuristic | PASS |
| 21 | Risk classes documented as prototype | PASS |
| 22 | Navigation layer generated with cells above threshold | PASS |

---

## 12. Limitations

| Limitation | Mitigation / Note |
|------------|-------------------|
| Persistence is the reference forecast; no ML model beats it (Phase 3C). | Engine explicitly uses persistence anchors; other sources flagged as `heuristic_fallback`. |
| Uncertainty anchors are for **one horizon (168 h)** and **one dataset split**; extrapolation via `h^gamma` is HEURISTIC. | Configurable `gamma`, documented fallback, explicit labels. |
| `sigma_obs = 1.0 km` is a prototype floor, not a calibrated sensor model. | Labelled HEURISTIC; separate env uncertainty slot for caller. |
| Staleness growth (0.5 km/h, cap 120 km) is a documented prototype rule. | Tunable in config; never presented as physical law. |
| Risk thresholds (25 / 50) are prototype choices, not maritime standards. | `class_boundary_note` in every output; config-driven. |
| Navigation layer is a max-class grid, not a full routing solution. | Designed for Phase 4+ consumption; documented in output. |
| No real-time data ingestion; synthetic demo only. | Demo explicitly labelled; engine interface accepts real caller data. |
| Bathymetry / grounding not directly used in risk (only via empirical D23 anchor). | Could be added as env feature in future phases. |
| Single forecast per iceberg per cycle; no ensemble. | Config `k_sigma` and `gamma` partly cover spread; ensemble support later. |

---

## 13. Reproducibility

- **Config-driven**: All parameters in `scripts/risk/risk_config.yaml` (YAML, human-readable).
- **Deterministic engine**: No randomness; fixed `EARTH_RADIUS_KM = 6371.0088`.
- **Fixed demo timestamp**: `2025-11-12 12:00 UTC` (inside Phase 3C test window; no 2026).
- **Run command**: `python scripts/risk/run_risk_demo.py` → identical outputs every run.
- **Validation**: `python scripts/risk/validate_risk_engine.py` → 22/22 PASS.
- **Dependencies**: Python 3.13, numpy, pandas, xarray, pyyaml, matplotlib (all already in project env).
- **Outputs**: JSON / CSV written to `outputs/risk/`; figures to `outputs/risk/figures/`.

---

## 14. Files Created

| File | Purpose |
|------|---------|
| `scripts/risk/risk_config.yaml` | All tunable parameters with EMPIRICAL/HEURISTIC/SYNTHETIC labels |
| `scripts/risk/risk_engine.py` | Core deterministic engine (RiskEngine, dataclasses, geodesy) |
| `scripts/risk/visualize_risk.py` | Matplotlib figure generator (5-layer legend, synthetic label) |
| `scripts/risk/run_risk_demo.py` | Scenarios A–E driver; writes demo JSON/CSV/PNG + manifest |
| `scripts/risk/validate_risk_engine.py` | 22 automated checks (22/22 PASS) |
| `outputs/risk/demo/scenario_{A..E}.json` | Full payloads (incl. navigation layer) |
| `outputs/risk/demo/scenario_{A..E}_risk_output.csv` | Machine-readable rows |
| `outputs/risk/demo/demo_manifest.json` | Demo index with intents & summary |
| `outputs/risk/figures/scenario_{A..E}.png` | Per-scenario maps |
| `outputs/risk/figures/risk_demo_summary.png` | 2×3 summary figure with legend |
| `reports/PHASE4_RISK_ENGINE_REPORT.md` | This report |

**No existing files modified.** No dataset, model, or report from Phases 1–3/3C/3F was changed.

---

## 15. Files Modified

**NONE.**  
Git status before and after Phase 4 shows only new untracked files under `scripts/risk/`, `outputs/risk/`, and this report. All protected paths (Phase 1/2/3 data, configs, reports) have identical mtimes and content.

---

## Final Statement

**PHASE 4 COMPLETE — UNCERTAINTY-AWARE RISK ENGINE.  
NO EXISTING DATASETS MODIFIED. NO TRAJECTORY MODELS RETRAINED.  
VALIDATION: 22/22 PASS.  
STOPPING FOR EXPLICIT APPROVAL.**