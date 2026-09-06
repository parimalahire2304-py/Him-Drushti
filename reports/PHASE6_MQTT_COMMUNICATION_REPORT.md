# PHASE 6 — MQTT COMMUNICATION-RESILIENT LAYER — REPORT

**Prototype SATCOM emulation via MQTT** — not an operational deployment.

---

## 1. Objective

Build a communication-resilient MQTT layer on top of the completed forecasting → risk → routing pipeline. The layer connects:

- **Laptop 1 (Offshore / Polar AI Server)** — runs the full pipeline and publishes results over MQTT
- **MQTT Broker** — prototype SATCOM transport (Mosquitto on 127.0.0.1:1883)
- **Laptop 2 (Onboard Ship DSS)** — subscribes, validates, tracks message age, preserves the most recent valid state, degrades gracefully during loss, and replans on recovery

Demonstrate deterministically:

1. Normal transmission (FRESH)
2. Temporary degradation (STALE)
3. Communication loss (LAST_KNOWN_STATE)
4. Communication recovery (FRESH after loss)
5. New observation after recovery
6. Forecast / risk / route recomputation after recovery
7. Re-planning

All demonstrations are synthetic and clearly labelled as such.

## 2. Existing Architecture (before Phase 6)

```text
New observation
      |
      +--> Forecast eligibility check
      |       +-- predecessor available -> Motion-aware XGBoost (CANDIDATE, +5.04% on N=14)
      |       +-- otherwise             -> Persistence fallback (MANDATORY)
      v
  Forecast
      |
      +--> Risk Engine (Phase 4, deterministic, 22/22 PASS)
      |
      +--> Route Optimizer (Phase 5, deterministic A*, hard threshold 50, 19/19 PASS)
```

Phase 3G evidence, explicitly retained as a qualification:

- Motion-aware XGBoost: **18.13 km MAE** on N=14 predecessor-eligible drifting test
- Matched persistence: **19.09 km MAE** on the same N=14
- Improvement **+5.04%** on the matched predecessor-eligible subset only
- Full drifting population N=24: unavailable without a valid predecessor; C39 worsened
- Therefore the motion model is a **candidate improved forecast**, not a universally validated replacement

Persistence is retained globally. No datasets modified. No downloads. No retraining.

## 3. Phase 6 Architecture (new)

```text
Laptop 1                                 Mosquitto (127.0.0.1:1883)
Offshore AI Server                        Prototype SATCOM transport (MQTT v5)
--------------------------------         ------------------------------------
Existing pipeline
  |  forecast_iceberg(obs) --> ForecastResult
  |  RiskEngine.evaluate    --> RiskAssessment(s)
  |  RouteOptimizer.solve   --> RouteResult
  v
 OffshorePublisher
  |  build_* schemas (explicit forecast_method)
  |  publish to himdrushti/{observation,forecast,risk,route,status,replan}
  +==========================> transport.publish()
                                         |
                                         | broker relay (or InMemory synchronous relay)
                                         v
                                        OnboardReceiver  <---- Laptop 2 (Onboard Ship DSS)
                                        -----------------------------------------------
                                        transport.subscribe()
                                        validate_message() -> drop invalid
                                        CommunicationStateMachine (age-based FRESH/STALE/LAST_KNOWN_STATE)
                                        LatestState (most recent VALID per topic_key)
                                        Never fabricate during loss
                                        On new valid message -> recovery -> recompute fully
                                        -> replan via PHASE 3G -> 4 -> 5 path
```

The forecasting, risk, and routing algorithms were NOT rewritten. Phase 6 wraps their outputs.

MQTT is used explicitly as a **prototype communication / SATCOM emulation layer** over a local broker for laboratory validation. The `transport` abstraction keeps a single deployment path: replace `InMemoryTransport` with `PahoTransport` and the same code runs against a remote broker when the ship is at sea.

## 4. Broker / Client Design

- **Broker:** Mosquitto 2.1.2 on 127.0.0.1:1883 (winget, auto-start via Windows service; `netstat -ano | findstr :1883` shows LISTENING; loopback connectivity verified with `paho` subscribe/publish).
- **Client library:** paho-mqtt 2.1.0 (Python; `callback_api_version=VERSION2`; `loop_start()` network thread; 2-second CONNACK wait).
- **Transport abstraction (`scripts/communication/transport.py`):**
  - Abstract `Transport` interface (`connect` / `disconnect` / `publish` / `subscribe` / `is_connected`).
  - `InMemoryTransport` — synchronous in-memory pub/sub, exact-topic match (no wildcard), `_retained` store, ordered `log`. Fully deterministic; no broker needed.
  - `PahoTransport` — real Mosquitto-backed transport; pending subscriptions buffered until connected; reuses existing connection on repeated `connect()`.
  - `make_transport(prefer)` — `prefer="auto"`: try real broker, then deterministic fallback; `"memory"`: always InMemory; `"paho"`: require real broker.
- **Demo strategy:** deterministic by default (`make_transport("memory")`); real-broker mode via `python scripts/communication/run_communication_demo.py --broker`. Both produce identical scenarios.

Async determinism fix: `PahoTransport` delivers on a network thread, so `run_communication_demo.py` drains the receiver's `get_received_log()` after each publish batch (`_drain(receiver, expected)`). Without this, checking state immediately after `publish()` could observe incomplete delivery.

## 5. Topic Structure

All topics configured in `scripts/communication/communication_config.yaml` (YAML-driven, no hard-coding):

```yaml
topics:
  observation:  himdrushti/observation
  forecast:     himdrushti/forecast
  risk:         himdrushti/risk
  route:        himdrushti/route
  status:       himdrushti/status
  replan:       himdrushti/replan
qos:
  observation: 1
  forecast:    1
  risk:        1
  route:       1
  status:      0
  replan:      1
broker:
  host: localhost
  port: 1883
  keepalive_seconds: 60
```

Prefix `himdrushti` is the prototype namespace; changing it requires only the YAML, not code edits.

## 6. Message Schemas

Defined in `scripts/communication/schemas.py` — machine-readable JSON, shared by publisher and receiver:

- Every message has `message_type` and `timestamp` (ISO 8601 UTC with `timespec="seconds"`). Builders accept an optional `timestamp` override so synthetic demos can anchor message times to a scenario clock; when `None`, the current wall-clock time is used. No out-of-band schema is needed.
- **Observation** (`himdrushti/observation`): `iceberg_id`, `latitude`, `longitude` (Phase 6 geography), `data_source`, `observation_time`, plus optional `length_nm`/`width_nm` and Phase-3G eligibility fields `prev_delta_lat` / `prev_delta_lon` / `prev_speed` / `prev_bearing`; extra environmental features pass through (`iceberg_length_nm`, etc.). The demo's `_run_forecast_risk_route` adapts `latitude`/`longitude` to the Phase-3G interface's `lat`/`lon` without inventing data.
- **Forecast** (`himdrushti/forecast`): explicitly carries `forecast_method` (`MOTION_AWARE_XGBOOST` or `PERSISTENCE_FALLBACK`) and `fallback_reason` (`None` vs `NO_VALID_PREDECESSOR` vs `MODEL_UNAVAILABLE`) — never inferred from coordinates. Also `model_used`, `predecessor_available` (bool), `fallback` (bool), `forecast_latitude`/`forecast_longitude`, `forecast_horizon` (hours), `communication_state`, `data_freshness`.
- **Risk** (`himdrushti/risk`): `risk_level` (LOW/MODERATE/HIGH), `risk_score`, `communication_state`, `uncertainty_sigma_km`, `envelope_radius_km`, `corridor_radius_km` plus diagnostic `separation_km`, `separation_effective_km`, `anchor_tag`, `data_freshness`.
- **Route** (`himdrushti/route`): `route_status` (SAFE/CAUTION/NO_SAFE_ROUTE_FOUND), `route_label`, `communication_state`, `data_freshness`, `route_distance_km`, `direct_distance_km`, `distance_overhead_pct`, `estimated_travel_time_hours`, `max_risk_score_encountered`, `waypoints`, `replan_reason`.
- **Status** (`himdrushti/status`): `communication_state`, `last_message_timestamp`, `message_age_hours`, `reason`.
- **Replan** (`himdrushti/replan`): `replan_trigger` (e.g. `COMMUNICATION_RECOVERY`), `forecast_method`, `risk_level`, `route_status`, `iceberg_id`, `communication_state`, `data_freshness`.

Validators `validate_{observation,forecast,risk,route,status,replan}` and dispatched `validate_message` are source-of-truth for the receiver (invalid messages are dropped).

## 7. State Machine

Defined in `scripts/communication/state_manager.py` — pure function over message age.

- Thresholds from `communication_config.yaml`:
  - `stale_threshold_hours = 48.0`
  - `comm_loss_threshold_hours = 168.0` (one week)
- Transitions:
  - `FRESH -> STALE`: `age_hours >= 48.0`
  - `STALE -> LAST_KNOWN_STATE`: `age_hours >= 168.0`
  - `* -> FRESH`: a new valid message is received (`mark_received` / `recover(timestamp)`)
- `CommunicationStateMachine`:
  - `infer_state(asof: datetime) -> CommState` — pure inference; no side effects.
  - `recover(timestamp)` — deterministic recovery on a new valid message.
  - `status_dict(asof)` — snapshots `communication_state` / `last_message_timestamp` / `age_hours` / human `reason`.
  - Initial state (no messages yet) is `FRESH` with `age_hours == 0` (empty system, not a loss).
  - Phase 4 risk `freshness` thresholds use the same 48h/168h values but the Phase 6 machine owns the MQTT-layer `communication_state` separately.

The thresholds mirror the risk engine's staleness model so the corridor/envelope degradation and the MQTT-layer state remain aligned without coupling the code.

## 8. FRESH Behaviour

- An observation stamped at `ASOF` anchors the receiver clock.
- Queries at `ASOF` yield `FRESH` with `age_hours ≈ 0`, `status.reason == "within freshness window"`.
- New messages at FRESH continue to update `LatestState` and reset the clock.
- Scenario A (FRESH) proves: eligibility check passes, `Motion-aware XGBoost` is selected (valid predecessor), the risk assessment yields `MODERATE (score ~37)` at `sigma_total 50 km` (heuristic fallback), route is `SAFE (ROUTE, overhead 16.1%)`.

## 9. STALE Behaviour

- After 50 hours without a new message (`ASOF_STALE = ASOF + 50h`), the receiver reports:
  - `STALE`, `age_hours == 50`, `reason == "message age exceeds stale threshold"`.
- `LatestState` remains available; the last valid observation, forecast, risk, and route are still readable (no eviction, no mutation).
- No new MQTT messages are published in this window. The demo shows the stored state being reused.

## 10. LAST_KNOWN_STATE Behaviour

- After 170 hours without a new message (`ASOF_LOSS = ASOF + 170h > 168h`), the receiver reports:
  - `LAST_KNOWN_STATE`, `age_hours == 170`, `reason == "extended communication loss — using last known state"`.
- Explicit preservation contract:
  - `LatestState` retains the most recent valid observation/forecast/risk/route verbatim.
  - No synthetic observation is fabricated during the loss window.
  - The receiver does NOT call any forecasting, risk, or routing function with invented inputs.
  - `Last-known-state Route` is clearly distinguishable from a FRESH route (route carries `communication_state = LAST-KNOWN-STATE MODE` and `data_freshness`).

## 11. Recovery Behaviour

- A new valid observation at `ASOF_RECOVERY = ASOF + 180h` is published by the offshore publisher:
  - Receiver observes the message and calls `recover(timestamp_of_new_message)`.
  - State snaps back to `FRESH`, `age_hours == 0`.
  - `LatestState.observation` updates to the new observation (`iceberg_id == TEST-RECOV` in the validator; `DEMO-A` moved 0.01° in the demo).
- The recovery triggers a full Phase 3G -> 4 -> 5 recomputation:
  - `ForecastEngine` re-evaluates predecessor eligibility against the new observation (motion-aware re-selected).
  - `RiskEngine` recomputes separation, uncertainty (including stale growth if the engine is queried with the new `age`), and `RiskAssessment`.
  - `RouteOptimizer` recomputes the route on a fresh `navigation_layer`.
  - A `Replan` message is published with `replan_trigger = COMMUNICATION_RECOVERY`, preserving the forecast `forecast_method`, risk `risk_level`, and route `route_status`.
- No step of the Phase 3G -> 4/5 contract is bypassed on recovery.

## 12. Forecast Propagation (through MQTT)

- The forecast result's identity is NEVER inferred by the receiver:
  - Publisher sets `forecast_method` from `ForecastResult.forecast_method` exactly.
  - Fallback is set as `fallback = (forecast_method == "PERSISTENCE_FALLBACK")`.
  - The four eligibility fields are threaded unchanged into `build_forecast`.
  - Receiver stores the message as-is; `LatestState.forecast["forecast_method"]` equals the publisher's value.
- Two vetted paths are exercised:
  - **Motion-aware (CANDIDATE):** `MOTION_AWARE_XGBOOST` / `model_used = motion_aware_xgb` / `predecessor_available = true` / `fallback = false` / `fallback_reason = None` (Scenario A, D, F).
  - **Persistence fallback (MANDATORY):** `PERSISTENCE_FALLBACK` / `model_used = persistence` / `predecessor_available = false` / `fallback = true` / `fallback_reason = NO_VALID_PREDECESSOR` (Scenario E) and the hard MODEL_UNAVAILABLE path on load failure (integration check 6).
- The phase-3G feature ordering (19 env + 4 motion = 23) is verified once in `scripts/integration/validate_integration.py` and NOT rechecked per message.

## 13. Synthetic Demos

All values are synthetic and the output is labelled as such. Timebase:

- `ASOF = 2025-11-12T12:00:00Z` (within the Phase 3 dataset window)
- `ASOF_STALE = ASOF + 50h` (>48h)
- `ASOF_LOSS = ASOF + 170h` (>168h)
- `ASOF_RECOVERY = ASOF + 180h`

Iceberg synthetic geometry: `pt_at((-68.0,76.0), 95 km south, 190 deg)` yields ≈(-68.85, 75.5); iceberg 12 nm x 8 nm; environmental fields set to representative Antarctic values (sea_ice_concentration 0.3, wind speed/direction derived, etc.).

| Scenario | Label | Communication | Forecast | Fallback | Risk | Route |
|----------|-------|---------------|----------|----------|------|-------|
| A | FRESH synthesis | FRESH (age 0) | MOTION_AWARE_XGBOOST | None | MODERATE 37.4 | SAFE 164.3 km (overhead 16.1%) |
| B | STALE (no msgs) | STALE (age 50) | preserved | — | — | — |
| C | LAST_KNOWN_STATE | LAST_KNOWN_STATE (age 170) | preserved | — | — | — |
| D | RECOVERY | FRESH (age 0) | MOTION_AWARE_XGBOOST | None | MODERATE 38.8 | SAFE 164.3 km |
| E | FORECAST FALLBACK | FRESH | PERSISTENCE_FALLBACK | NO_VALID_PREDECESSOR | LOW 8.7 (empirical_drifting) | SAFE |
| F | AI FORECAST | FRESH | MOTION_AWARE_XGBOOST | None | MODERATE 37.4 | SAFE |

Full logs are printed to stdout and summarized in `outputs/communication/demo/communication_demo.json`.

B/C are introspection scenarios (their `state` and `age_hours` are queried on the same receiver without new publishes); D/E/F publish new decision cycles. The scenario table above does not collapse B/C's `n/a` forecast/risk/route — those are expected.

A latent bug in the first demo draft: `build_*` stamped real wall-clock 2026, so `infer_state(ASOF + 50h = 2025)` yielded negative age -> FRESH. The fix threads an optional `timestamp` parameter through every builder (default real-now, overrideable) and the demo anchors all synthetic messages to the scenario clock.

## 14. Validation

`scripts/communication/validate_communication.py` — 15 deterministic checks (see §§14.1-14.15):

- Pure unit/integration (no broker needed): uses `InMemoryTransport` everywhere so CI can run without Mosquitto.
- `communication_config.yaml` shape and thresholds check
- Publisher publishes to `himdrushti/observation`; receiver log and `LatestState` populated
- JSON schema suite: valid passes / missing-field fails / invalid `forecast_method` fails across all five other message types
- State machine: FRESH at ASOF, STALE at ASOF+50h, LAST_KNOWN_STATE at 170h, recovery to FRESH on a new message
- Forecast identity preserved for both Motion-aware and Persistence fallbacks (every flag verified)
- No fabricated observation during loss (log length stable, latest timestamp unchanged)
- Regressions delegated to their suites (see §§14.12-14.14)
- Protected-file guard: scans `git status --short` for any `M`/`D`/`R` line touching a data prefix; `??` (untracked) is excluded.

Target: **ALL 15 PASS**.

| # | Check | Status |
|---|-------|--------|
| 1 | mqtt_connection_config (YAML + transport) | PASS |
| 2 | publisher | PASS |
| 3 | subscriber | PASS |
| 4 | json_schema_validation | PASS |
| 5 | fresh | PASS |
| 6 | stale | PASS |
| 7 | last_known_state | PASS |
| 8 | recovery | PASS |
| 9 | forecast_metadata_preserved | PASS |
| 10 | persistence_fallback_metadata_preserved | PASS |
| 11 | no_fabricated_obs | PASS |
| 12 | phase4_regression (delegated 22/22) | PASS |
| 13 | phase5_regression (delegated 19/19) | PASS |
| 14 | phase3g_integration_intact (delegated 18/18) | PASS |
| 15 | protected_datasets_unchanged | PASS |

`sources:` `scripts/communication/validate_communication.py`

## 15. Regression — Phase 4

`scripts/risk/validate_risk_engine.py` — **22/22 PASS**.

No equations, thresholds, or heuristics of the risk engine were modified (growth cap 120 km, `comm_loss_growth_factor 1.5`, horizon circle, `sigma_total` composition, risk classes). The only new Phase 4 interaction is via the unchanged `Forecast`/`IcebergState`/`VesselState` datatypes consumed in `run_communication_demo.py`.

| Phase | Suite | Result |
|-------|-------|--------|
| Phase 4 | Risk engine validation | 22 passed, 0 failed |
| Phase 5 | Route optimizer validation | 19 passed, 0 failed |
| Phase 3G -> 4/5 integration | Integration validation | 18 passed, 0 failed |
| Phase 6 | Communication validation | 15 passed, 0 failed |

`sources:` `scripts/risk/validate_risk_engine.py`, `scripts/routing/validate_routing.py`, `scripts/integration/validate_integration.py`, `scripts/communication/validate_communication.py`

## 16. Regression — Phase 5

`scripts/routing/validate_routing.py` — **19/19 PASS**.

Deterministic A* (8-connected, 0.05 degree grid over [-70,-66]x[72,80], weighted safety10/distance1/time1/env1, hard threshold 50 impassable, snap radius 3) unchanged. Routes in scenarios A/D/F/E are identical modulo forecast position; reruns are deterministic (`route ==` and `metrics ==` on repeated `solve` with the same `navigation_layer`).

## 17. Protected-File Verification

Before/after `git status --short` (scanned in both the integration and communication validators):

- Allowed new files: `scripts/communication/*` (transport, schemas, state_manager, offshore_publisher, onboard_receiver, run_communication_demo, validate_communication, communication_config.yaml), `outputs/communication/demo/communication_demo.json`, `reports/PHASE6_MQTT_COMMUNICATION_REPORT.md`.
- Disallowed modifications: any `M`/`D`/`R` line under `data/processed/ml/expanded/`, `data/processed/ml/full.parquet`, `data/processed/ml/{train,val,test}.parquet`, `data/processed/ml/models/drifting_xgboost/`, `data/raw/`, `data/processed/icebergs|bathymetry|sea_ice|weather/`, `scripts/ml/train_xgboost*`, `scripts/ml/prepare_ml_dataset*`, etc.
- Secondary guard: `test.parquet` C39 count asserted to 9 (C39 zero-shot composition unchanged).
- Result: **PROTECTED FILE CHECK — UNCHANGED**.

## 18. Limitations

- MQTT is a **prototype SATCOM emulation** only; it does not emulate bandwidth, latency, message ordering, encryption, or SATCOM link budgets. QoS 1 ordering is not validated; the demo is single-hop localhost.
- Heuristic thresholds (`48h`, `168h`, growth cap) are prototype choices from the YAML; they are not calibrated to an operational SATCOM schedule.
- `InMemoryTransport` is deterministic but does not model disconnection, reconnect, or retained-message semantics — the real Paho path does, but only loopback has been tested on this laptop.
- `OnboardReceiver` is deliberately single-threaded with respect to `LatestState` updates (subscribe callbacks fire on the transport's thread; `_received_log` is thread-safe, but no further concurrency hardening is in place).
- No datasets were modified or merged; BYU remains independent; no 2026 data is introduced; no ML training occurred in Phase 6.

## 19. Explicit Statements

- Motion-aware XGBoost **is integrated as a candidate forecast model, not as a universally validated replacement for persistence.**
- Persistence remains the **mandatory fallback**; predecessor eligibility requires all four `prev_delta_lat`/`prev_delta_lon`/`prev_speed`/`prev_bearing` to be legitimately finite from a real t-7 to t predecessor. No interpolation, no estimation, no future information.
- Phase 6 adds a **communication-resilient MQTT delivery and state-tracking layer** on top of the pipeline. It does not change the scientific forecast, risk formulation, or route optimization.
- MQTT is used **as a prototype communication / SATCOM emulation layer** for laboratory validation on this machine (Laptop 1 -> broker -> Laptop 2 architecture via `Publisher -> Transport -> Receiver` with loopback verified). It does not claim an operational SATCOM deployment.
- **No new ML training occurred** in Phase 6. **No BYU data were merged.** **No 2026 data were introduced.** **No protected datasets were modified.**
- All scenarios are **synthetic** and labelled `SYNTHETIC DEMO — NOT real observations`.

## 20. Files Created / Modified

### Phase 6 — new (under `scripts/communication/`)

| File | Role |
|------|------|
| `communication_config.yaml` | YAML-driven thresholds, topics, broker, QoS |
| `transport.py` | Transport abstraction + InMemoryTransport + PahoTransport + factory |
| `schemas.py` | Build/validate for observation/forecast/risk/route/status/replan (+ optional timestamp anchor) |
| `state_manager.py` | Deterministic FRESH->STALE->LAST_KNOWN_STATE state machine (age-based) |
| `offshore_publisher.py` | Laptop-1 MQTT adapter (publish_* + publish_decision_cycle) |
| `onboard_receiver.py` | Laptop-2 MQTT receiver + LatestState + log + age + recovery |
| `run_communication_demo.py` | Deterministic 6-scenario demo (A-F; InMemory default, --broker for Mosquitto) |
| `validate_communication.py` | 15-check Phase-6 suite + delegated Phase 4/5/3G regressions + protected-file guard |

### Outputs

| File | Content |
|------|---------|
| `outputs/communication/demo/communication_demo.json` | Scenario summary + message_log_count |

### Report

| File | Content |
|------|---------|
| `reports/PHASE6_MQTT_COMMUNICATION_REPORT.md` | This report |

### Modified (bug fixes in Phase 6 code only)

- `schemas.py` — added optional `timestamp` threading and `_ts()` helper
- `run_communication_demo.py` — FRESH/RECOVERY timestamp anchoring; `_drain()` for async Paho determinism; `pipeline_obs` adapter (`latitude`/`longitude` -> `lat`/`lon`) so the Phase 6 MQTT schema interoperates with the Phase 3G forecast interface without editing `forecast.py`
- `transport.py` — cleaned unused imports / `MQTT_CONFIG` removal

### Excluded from modification

- `scripts/integration/forecast.py`, `scripts/risk/risk_engine.py`, `scripts/routing/route_optimizer.py` — unchanged.
- Phase 3C/3G models, datasets, configs — unchanged.

## 21. Validation Summary

```
InMemory (deterministic, no broker):
  scripts/communication/validate_communication.py   15/15 PASS
  scripts/risk/validate_risk_engine.py              22/22 PASS
  scripts/routing/validate_routing.py               19/19 PASS
  scripts/integration/validate_integration.py       18/18 PASS

Real broker (Mosquitto 127.0.0.1:1883, paho-mqtt 2.1.0):
  scripts/communication/run_communication_demo.py --broker
  Scenarios A-F identical to InMemory; all state transitions and
  forecast methods (MOTION_AWARE_XGBOOST / PERSISTENCE_FALLBACK)
  preserved end-to-end (Paho thread timing drained via _drain).

Protected-file check: UNCHANGED (no M/D/R in data/processed/ml/...,
  no BYU merge, C39 = 9)
```

Mosquitto 2.1.2 was provisioned via `winget install EclipseFoundation.Mosquitto`; service `Mosquitto Broker` is RUNNING; port 1883 is OPEN on 127.0.0.1. Real Paho subscribe helpers were used to verify loopback before the demo was declared complete.

---

*Phase 6 implementation subject: MQTT / risk / routing; no trajectory-model edits.*

*This is a prototype emulation. No C39 composition changes. No external data downloads.*
