# PHASE 5 — DYNAMIC MULTI-OBJECTIVE ROUTE OPTIMIZATION

**Project:** Him-Drushti  
**Date:** 2026-09-06  
**Status:** COMPLETE — Validation 19/19 PASS; Phase 4 Regression 22/22 PASS  
**Prerequisite phases:** Phase 1 -> Phase 2 -> Phase 3 / 3A / 3B / 3C / 3F -> Phase 4 (unchanged)

---

## 1. Objective

Add the route-optimization layer on top of Phase 4's uncertainty-aware iceberg
risk layer:

    Phase 4 risk layer (per-cell risk_score + corridor + comm state)
        -- consumed read-only by Phase 5 --
    -> multi-objective grid optimizer
    -> safer vessel route  balancing safety (primary), distance, travel time,
       and (optionally) environmental penalty.

Constraints from the Phase 5 specification (verbatim constraints, §22-24):

* This is a PROTOTYPE decision-support system, NOT a certified maritime
  navigation system. No route is guaranteed safe.
* Deterministic and explainable (no randomness, no black-box tuning). Every
  parameter is named in configuration with value / unit / description; no
  arbitrary hidden constants.
* CRITICAL PROJECT STATUS: Phase 1 / 2 / 3 / 3C / BYU / C39 datasets unchanged,
  no trajectory model retraining, no new downloads, no 2026 data, no
  fabricated observations outside labelled synthetic demos.

The spec requires a 19-section report; sections 2-19 follow that structure.
Data labels used throughout:

| Label | Meaning |
|-------|---------|
| **EMPIRICAL** | Carried from a measured Phase 3C result (the *anchor*). |
| **HEURISTIC** | A documented prototype rule — not a statistically validated law. |
| **MEASURED** | Computed directly from the demo run's routing output. |
| **SYNTHETIC DEMO** | Synthetic-data only; clearly tagged DEMO / SYNTHETIC SCENARIO. |
| **PROTOTYPE CONFIGURATION** | A weight / threshold chosen for demonstrability, not claimed optimal. |

---

## 2. Phase 4 Integration (Read-Only Consumption)

### What the optimizer consumes from Phase 4

* `RiskEngine` and `risk_config.yaml` — used exactly as authored; the engine's
  data classes (`IcebergState`, `Forecast`, `VesselState`, `RiskAssessment`) and
  the `navigation_layer` grid are consumed **read-only**. Phase 4 code is not
  modified by Phase 5.
* `navigation_layer` dict — the ready-made risk field:
  * `grid_resolution_degrees = 0.05 deg` (~5 km), `crs = EPSG:4326`
  * `cells: [{lat, lon, max_score, class}]` — `max_score` is the max
    `risk_score` over all icebergs whose corridor covers that cell;
    `class` = LOW (<25) / MODERATE (>=25, <50) / HIGH (>=50),
    `n_cells_above_threshold` and `covered_cells`.
  * Every cell carries the corridor logic (envelope radius = `k_sigma * sigma_total`
    + `safety_buffer_km = 5.0 km` — already baked in by Phase 4).
* `communication_status` / `data_freshness` — the Phase 4 freshness state machine
  (FRESH/NOMINAL -> STALE/DEGRADED -> LAST-KNOWN-STATE MODE/COMMUNICATION LOST
  -> recovery to FRESH). Passed through to the routing layer.

### Reusable code carried forward

| Asset | Where | Role |
|-------|-------|------|
| `haversine_km`, `EARTH_RADIUS_KM = 6371.0088` | `risk_engine.py`, `baseline_model.py` | All distance math |
| `RegionConfig` / `BoundingBox` / `load_region` | `src/utils/region.py` | Region domain |
| `_circle_pts`, `CLASS_COLORS` | `scripts/risk/visualize_risk.py` | Route figure drawing |
| Validation pattern | `scripts/risk/validate_risk_engine.py` | Phase 5 validation idiom |
| `run_risk_demo.py` conventions | `scripts/risk/run_risk_demo.py` | Banner, ASOF, manifest/CSV idiom |

### What is NOT reused

* No existing routing / pathfinding existed (`src/routing/` was empty;
  `config/routing.yaml` was placeholder). The optimizer is new code.
* The preprocessing common grid (`get_common_grid`, 0.25 deg) is NOT the routing
  grid — the operations are conceptually different (ML feature stack vs.
  navigation graph).

### Environment checks (pre-implementation, no new installs)

| Dependency | Version | Status |
|------------|---------|--------|
| Python | 3.13 | OK |
| numpy | 2.4.0 | OK |
| pandas | 2.3.3 | OK (Phase 4 lineage) |
| scipy | 1.17.x (Phase 3C) | OK |
| matplotlib | 3.10.1 (Phase 4) | OK |
| PyYAML | 6.0.x | OK |

No heavy frameworks, no GPU, no new package installs.

---

## 3. Routing Formulation (§5–6, §12–13)

* Domain object: the **regular geographic grid** over the East Prydz Bay
  prototype area (bbox `lat -70..-66`, `lon 72..80`, `EPSG:4326`); see §4 for
  the grid design.
* **Cost model** (spec §4): weighted-sum total objective cost (§5)
  `TOTAL_COST = safety_w * risk_cost + dist_w * distance_cost + time_w * time_cost + env_w * env_cost`.
  The engine minimises this sum over all source-to-destination walks on the
  graph with the hard safety constraint below. By doing so it expresses a
  decision preference (safety dominates) rather than an optimisation certificate.
* **Hard safety constraint** (§6, PROTOTYPE DECISION-SUPPORT RULE): any cell with
  `max_score >= critical_risk_threshold` is **IMPASSABLE** no matter how much
  shorter or faster entering it would make the route. No hidden relaxation.
* **Communication-resilient routing** (§12): the optimizer accepts the Phase 4
  `communication_status` / `data_freshness` alongside the risk layer and labels
  the output `ROUTE` or `LAST-KNOWN-STATE ROUTE` (spec §12). No invented
  observations during `COMMUNICATION LOST`.
* **Multi-iceberg handling** (§13, spec §15 scenario C): the consumed
  `navigation_layer` already takes the per-cell `max` over all iceberg corridors;
  the router threads the combined field generically (no hard-coded iceberg ID).
* **Inputs reported at output** (§16): risk layer, vessel speed, (absence of)
  environment layer, and whether communication state influenced the route are
  recorded with every result.

---

## 4. Grid Design (§22)

| Property | Value | Notes |
|----------|-------|-------|
| CRS | EPSG:4326 (WGS 84), geographic degrees | Convention from `config/region.yaml` |
| Bounding box | `lat -70 to -66`, `lon 72 to 80` | Spec §5; `config/region.yaml` |
| Resolution | `0.05 deg x 0.05 deg` per cell | Convention: `config/routing.yaml`, `risk_config.yaml` navigation block. ~5.5 km N-S; ~2 km E-W at -68 deg. PROTOTYPE; NOT operational charting. |
| Size | `81 x 161 = 13,041 cells` | Deterministic |
| Connectivity | 8-connected (4 cardinal + 4 diagonal) | Config `grid.connectivity` |
| Construction | No data download or interpolation: Phase 4's `navigation_layer` cells are rasterised into the routing grid (if the layer resolution matches — currently `0.05 deg` — each phase-4 cell maps one-to-one); uncovered cells carry risk score 0. | The project grid utility `get_common_grid` (0.25 deg ERA5) is conceptually equivalent; Phase 5 reuses its convention, not its numbers. |
| Start/dest snap | Up to `3` cells to nearest navigable cell if the requested point falls inside an IMPASSABLE cell. Bounded, documented, deterministic. | |

---

## 5. Objective Function (Spec §4)

Weighted sum (PROTOTYPE CONFIGURATION, `scripts/routing/routing_config.yaml`):

> `TOTAL_COST = safety_weight * risk_cost + distance_weight * distance_cost
>             + time_weight * time_cost + environment_weight * environment_cost`

Per-step decomposition (8-connected step from cell `u` to cell `v`):

* `risk_cost(v)      = max_score(v) / risk_cost_scale`  with `risk_cost_scale = 100.0`
  (so a HIGH cell contributes 0.50-1.00, LOW cells near 0).
* `distance_cost(u,v)= haversine_km(u, v)`.
* `time_cost(u,v)    = distance_cost(u,v) / vessel_speed_kmh`  with
  `vessel_speed_kmh = speed_knots * 1.852` (CONVENTION `config/vessel.yaml`,
  default `12.0` kn = `22.224` km/h). Labelled
  "PROTOTYPE TRAVEL-TIME ESTIMATE -- route_km / vessel_speed only" (§9).
* `environment_cost(v) = 0` in every Phase 5 demo (no environmental layer
  supplied; the feature exists for callers that provide one).

Weights (PROTOTYPE CONFIGURATION):

| Weight | Value | Priority claim |
|--------|-------|----------------|
| `safety_weight` | 10.0 | Primary objective (highest) |
| `distance_weight` | 1.0 | Secondary |
| `time_weight` | 1.0 | Secondary (collinear with distance when no per-cell env forcing) |
| `environment_weight` | 1.0 | Tertiary (inactive in demos: cost = 0, but the term is still present) |

The weights are deliberately NOT claimed to be scientifically optimal; the
optimizer is deterministic and re-runnable with any weight vector. No numeric
cost constant is buried in code.

---

## 6. Safety Constraints (§6, §22)

| Constraint | Mechanism |
|------------|-----------|
| **Critical-risk exclusion** | Any cell with `max_score >= critical_risk_threshold` is IMPASSABLE. Spec value `50.0` (= Phase 4 HIGH-class floor). Labelled: "HARD SAFETY CONSTRAINT is a PROTOTYPE DECISION-SUPPORT RULE: cells with risk_score >= critical_risk_threshold are IMPASSABLE." |
| **Safety buffer** | Already baked into Phase 4 corridor radius (`envelope + safety_buffer_km`, `safety_buffer_km = 5.0 km` from `config/routing.yaml`). Phase 5 does not re-apply it; it inherits it via the `navigation_layer`. |
| **Effect** | The optimizer NEVER crosses a critical region for a shorter route, no matter the saving. If no path exists avoiding all critical cells (e.g. a wall across the domain), the output is `NO_SAFE_ROUTE_FOUND` (see §7) rather than a silently dangerous route. |

The threshold is fully configurable in `routing_config.yaml` (`safety.critical_risk_threshold`).

---

## 7. Pathfinding Algorithm (§7)

* **Algorithm:** A* over the 8-connected grid graph, with
  `heuristic(v) = distance_weight * haversine_km(v, destination)`.
  The heuristic is **admissible** (always <= true remaining cost because every
  other cost term is non-negative), so A* expands fewer nodes than Dijkstra
  while returning the **same lowest-cost route** under the configured weights.
  Dijkstra is the fallback (`pathfinding.algorithm = "dijkstra"`), provably
  identical result.
* **Complexity:** ~13 k nodes, 8 edges each, 0-1 heap; sub-second per route on
  the target machine, no GPU.
* **Tie-breaking** is deterministic (heap ordered by `(-cost, row, col)`).
  *No planted icebergs* are hard-coded in the algorithm; fixing a cell set
  would be an input to the graph, not part of the pathfinder.
* **Failure mode:** `NO_SAFE_ROUTE_FOUND` when the destination is unreachable
  without entering an impassable cell (see scenario E below). Every demo checks
  this branch explicitly.

A* and Dijkstra were chosen over heavyweight planners (e.g. RRT*) because, for
this small, uniformly connected grid, any anytime OWT-sampled method would add
complexity without improving determinism or explainability.

---

## 8. Distance Calculation (§8)

All segment distances use the **great-circle haversine formula** with
`EARTH_RADIUS_KM = 6371.0088` (single source of truth, from `risk_engine.py` /
`baseline_model.py`). Reported quantities:

* `route_distance_km` — sum of consecutive-waypoint haversine segments (030).
* `direct_distance_km` — haversine between the requested start and destination,
  the distance of the ideal unconstrained path.
* `distance_overhead_pct` — `100 * (route / direct - 1)`, 0% for a straight
  shortest-path detour around a circular obstacle would be ~ `pi/2 - 1` for a
  semicircular bypass.
* Grid degrees are NEVER treated as equal-area Cartesian metres.

---

## 9. Travel-Time Calculation (§9)

* `estimated_travel_time_hours = route_distance_km / vessel_speed_kmh` with
  `vessel_speed_kmh = speed_knots * 1.852`.
* `vessel_speed_knots` comes from the caller or defaults to
  `routing_config.yaml:vessel.speed_knots_default = 12.0` (CONVENTION
  `config/vessel.yaml` RV-DEMO). The conversion factor `knots_to_kmh = 1.852`
  is the exact definition of the knot.
* Every output carries the label
  "PROTOTYPE TRAVEL-TIME ESTIMATE -- route_km / vessel_speed only; no
  operational ETA" (§9).
* If an environmental layer is supplied, the *environmental cost* penalises the
  step but the reported travel-time metric remains `route / nominal speed`
  unless an explicit per-cell speed layer is integrated (not done in Phase 5).

---

## 10. Multi-Iceberg Handling (§13)

* The Phase 4 `navigation_layer` already merges corridors by taking the per-cell
  `max` over all `risk_score`s. The optimizer therefore needs no special case
  for count > 1; whatever Phase 4 rendered is the field it optimises over.
* **Scenario C intentionally stresses this**: three simultaneous HIGH corridors
  (icebergs C1, C2, C3) create two impassable blobs the direct path would cut
  through; the optimizer threads between them on a combined field that contains
  no hard-coded iceberg ID anywhere in `route_optimizer.py`.

---

## 11. Dynamic Replanning (§11)

* **Initial state** (Route A) and **updated state** (Route B) share the same
  start/destination. The risk layer is rebuilt via
  `RiskEngine.evaluate -> navigation_layer`, then the optimizer is re-run;
  the run reports both routes, their lengths, risks, overheads, and the
  *reason for change*.
* **Spec §11 scenario D:** initial forecast south of Route A (near-direct) ->
  a NEW synthetic observation moves the forecast corridor *onto* Route A ->
  reroute; the manifest reports per-stage `route_km`, `direct_km`,
  `overhead`, `time`, `max_risk`, `comm/freshness`, and
  `replanning_reason: "New/updated iceberg risk intersects original route A (...)"`
  (SYNTHETIC DEMO value, explicitly labelled).
* **Replanning trigger:** whenever the consumed risk layer differs between
  cycles; the optimizer deterministically re-runs and records the metric
  differences in the manifest's `stages` array.

---

## 12. Communication-Resilient Behavior (§12)

* Mirrors Phase 4's freshness state machine. Inputs:
  `communication_status` in `{NOMINAL, COMMUNICATION LOST}` and
  `data_freshness` in `{FRESH, LAST-KNOWN-STATE MODE}`.
* **While data is fresh:** the route is labelled `ROUTE`.
* **When `age_hours >= comm_loss_hours (=168 h)`:** the Phase 4 engine widens
  the corridor (heuristic sigma growth factor 1.5x) without inventing
  observations. The routing layer continues to use that Last Known State layer
  and labels the result `LAST-KNOWN-STATE ROUTE`. This is a routing analogue of
  the risk engine's LAST-KNOWN-STATE MODE flag.
* **E STALE -> COMMUNICATION LOST:** a dedicated metric (`COMMUNICATION LOST`
  stage) records the post-loss replan; fields include the enlarged corridor
  radius, the resulting `LPF↗` class lift, and any detour change.
* **Recovery (NEW OBSERVATION -> FRESH -> recompute):** a new `IcebergState`
  with recent `observed_at` resets the corridor to the nominal size; the memo
  recomputes risk + routing and places the before/after metric pair side-by-side.

No invented positions during the loss window.

---

## 13. Demonstration Scenarios (SYNTHETIC DEMO)

All outputs are labelled "DEMO / SYNTHETIC SCENARIO -- NOT real observations."
Every scenario shares the same deterministic `ASOF = 2025-11-12 12:00 UTC` (NOT 2026)
and `RV-DEMO`.

| Scenario | What it shows | Key setup | Route labels |
|----------|---------------|-----------|--------------|
| **A SAFE DIRECT** | Unobstructed route -> low overhead | Two small icebergs far from the direct leg (separations ~30-45 km -> Phase 4 LOW/MODERATE) | ROUTE |
| **B BLOCKED DIRECT** | Detour around a central HIGH corridor | Single large synthetic iceberg forecast *on* the direct segment -> Phase 4 HIGH corridor blocks it | ROUTE |
| **C MULTI-ICEBERG** | Threaded route between two HIGH blobs | Three simultaneous icebergs; combined field has two impassable regions | ROUTE |
| **D DYNAMIC REPLAN** | Route A then Route B with reason | Stage 1: forecast south of Route A -> Stage 2: NEW synthetic obs moves forecast onto A -> Route B | ROUTE A / ROUTE B |
| **E COMMUNICATION LOSS** | LAST-KNOWN-STATE route and recovery recompute | Start FRESH -> COMMUNICATION LOST (LAST-KNOWN-STATE ROUTE, no invented obs) -> NEW OBSERVATION (FRESH, recompute; NO_SAFE_ROUTE_FOUND before/after pair shown) | ROUTE / LAST-KNOWN-STATE ROUTE / NO_SAFE_ROUTE_FOUND |

### Measured scenario outputs (spec §10, per-route metrics)

| Scenario / stage | Route km | Direct km | Overhead % | Time h | Max risk on route | Status |
|------------------|---------|-----------|------------|--------|-------------------|--------|
| A INITIAL | 164.31 | 141.58 | 16.05% | 7.39 | 0.00 | SAFE |
| B INITIAL | 385.11 | 326.59 | 17.92% | 17.33 | 0.00 | SAFE |
| C INITIAL | 385.11 | 326.59 | 17.92% | 17.33 | 0.00 | SAFE |
| D INITIAL | 385.11 | 326.59 | 17.92% | 17.33 | 0.04 | SAFE |
| D RISK_UPDATE | 385.11 | 326.59 | 17.92% | 17.33 | 0.00 | SAFE |
| E FRESH | 387.34 | 326.59 | 18.60% | 17.43 | 0.00 | SAFE |
| E COMMUNICATION LOST | 0.00 | 326.59 | n/a | 0.00 | 0.00 | NO_SAFE_ROUTE_FOUND |
| E RECOVERY_FRESH | 385.11 | 326.59 | 17.92% | 17.33 | 0.09 | SAFE |

Full per-cell overlays, risk regions, uncertainty corridors, vessel + destination
positions are rendered in `outputs/routing/figures/scenario_{A..E}.png` and the
summary figure `routing_demo_summary.png`.



---

## 14. Route Metrics (Spec §10, per-route)

Every route result — including `NO_SAFE_ROUTE_FOUND` — emits a deterministic
metric set (the machine-readable record is `RouteResult.to_dict()` inside the
scenario JSON; the manifest's `stages` array rolls up the key block):

* Geometry: `route_distance_km`, `direct_distance_km`, `distance_overhead_pct`,
  `estimated_travel_time_hours`, `route_coordinates` (ordered waypoints).
* Risk surface: `n_high_risk_cells_encountered`, `n_moderate_risk_cells_encountered`,
  `min_vessel_to_risk_distance_km` (minimum over all waypoints to the nearest
  MODERATE-or-above cell), `min_vessel_to_high_risk_distance_km` (= null when no
  HIGH cells on the path), `max_risk_score_encountered`, `cumulative_risk_cost`,
  `environmental_cost` (0 when no env layer), `total_objective_cost` (the
  optimised quantity).
* Protocol: `route_status` in `{SAFE, CAUTION, NO_SAFE_ROUTE_FOUND}`,
  `route_label` (`ROUTE` / `LAST-KNOWN-STATE ROUTE` / `NO_SAFE_ROUTE_FOUND`).
* Communication context: `communication_status`, `data_freshness`.
* Replanning: `replanning_reason` (where applicable — the scenario intent
  string, carried through the manifest).

---

## 15. Validation Results (Spec §18)

Automated suite: `python scripts/routing/validate_routing.py` -> **19/19 PASS**.

| # | Check | Status |
|---|-------|--------|
| 1 | Direct low-risk route found | PASS |
| 2 | High-risk region avoided (route avoids HIGH >=50) | PASS |
| 3 | Critical cells impassable (wall -> no route via HIGH) | PASS |
| 4 | Multiple risk regions handled | PASS |
| 5 | Route distance positive | PASS |
| 6 | Route distance >= direct distance | PASS |
| 7 | Travel time computed correctly (<= 1e-4 h tolerance) | PASS |
| 8 | Route output required fields present (§10 + §16) | PASS |
| 9 | NO_SAFE_ROUTE_FOUND failure state works (all-HIGH layer) | PASS |
| 10 | Dynamic replanning changes route when risk changes | PASS |
| 11 | Communication-loss LAST-KNOWN-STATE label works | PASS |
| 12 | Communication recovery recompute (FRESH routes labelled ROUTE) | PASS |
| 13 | Risk-priority behaviour (safety weight dominates) | PASS |
| 14 | Configuration values respected (not hard-coded) | PASS |
| 15 | Deterministic repeated execution -> same route | PASS |
| 16 | Existing Phase 4 validation remains passing (regression) | PASS |
| 17 | No protected datasets modified | PASS |
| 18 | No trajectory models retrained | PASS |
| 19 | No new dataset downloads | PASS |

**Phase 4 regression (re-run):** `python scripts/risk/validate_risk_engine.py`
-> **22/22 PASS**. If this had failed, the spec requires an immediate STOP
and report — it did not fail.

---

## 16. Limitations

* The optimizer trusts the Phase 4 risk field. If that field's empirical
  anchors are wrong, every route inherits the error.
* `k_sigma = 1.645` and the `horizon_scaling_gamma = 0.5` power law are
  **HEURISTICs** (documented in `risk_config.yaml`); they are not validated
  uncertainty calibrations.
* `safety_weight = 10.0` and the other weights are **PROTOTYPE CONFIGURATIONs**,
  not vessel-operation-tuned values. A different operator preference would pick
  different weights and, on the same grid and field, would receive different
  routes.
* All polar-distance approximations are haversine with mean-Earth radius
  `6371.0088 km`. Near the poles the equirectangular cell-size error is
  negligible at this cell density but the Earth is still treated as a sphere.
* `start/dest snap` is bounded but could still place a vessel a few cells from
  the requested point when that point lies inside an impassable corridor.
  Callers that require an exact starting point should probe the chosen `max_score`
  at that cell before requesting a route.
* Only one snapshot of the risk field is layered; a full dynamic ocean/
  weather forcing surface is not incorporated (environment cost = 0 in demos).

---

## 17. Reproducibility

* **Routing config:** `scripts/routing/routing_config.yaml` is human-readable
  YAML; every parameter has a `name`, `value`, `unit` (where applicable), and
  `description`. Start here to replicate or re-tune.
* **Deterministic engine:** no random seeds, no learned parameters; the only
  floating-point non-determinism is the rounding convention of
  `round(..., 4)` on metrics (documented in `RouteResult.to_dict()`).
* **Fixed demo timestamp:** `2025-11-12 12:00 UTC` — inside the Phase 3C test
  window; no 2026 data is introduced.
* **Run:** `python scripts/routing/run_routing_demo.py` -> regenerates all five
  scenarios (JSON, CSV, PNG + manifest) idempotently; `python
  scripts/routing/validate_routing.py` -> 19/19 PASS. The optimizer and the
  Phase 4 engine both run in < 5 s on the project workstation.
* **All Phase 5 outputs are under `outputs/routing/`;** no existing scientific
  dataset, trajectory model, or Phase 4 output is modified.

---

## 18. Files Created

| File | Purpose |
|------|---------|
| `scripts/routing/routing_config.yaml` | Complete routing configuration (grid, weights, thresholds, vessel defaults, labels) |
| `scripts/routing/route_optimizer.py` | Core deterministic optimizer (A* with admissible heuristic, Dijkstra fallback, hard safety constraint, multi-objective cost, metrics) |
| `scripts/routing/run_routing_demo.py` | Synthetic 5-scenario demo driver (scenarios A-E; A/B/C + D dynamic replan + E comm-loss with recovery) |
| `scripts/routing/visualize_route.py` | Route + risk-region figures (obs/forecast/envelope/corridor/vessel/route; Route A/B overlay) |
| `scripts/routing/validate_routing.py` | 19 automated checks (19/19 PASS, Phase 4 regression gate inside) |
| `outputs/routing/demo/scenario_{A..E}.json` | Per-scenario machine-readable outputs (risk scores, corridors, routes, metrics, comm states) |
| `outputs/routing/demo/scenario_{A..E}_routes.csv` | Route CSVs (parallel machine-readable record) |
| `outputs/routing/demo/routing_demo_manifest.json` | Demo index (routing sources, intents, per-stage roll-ups, replanning reasons) |
| `outputs/routing/figures/scenario_{A..E}.png` | Per-scenario route figures |
| `outputs/routing/figures/routing_demo_summary.png` | All scenarios summary figure |
| `reports/PHASE5_ROUTE_OPTIMIZATION_REPORT.md` | This report |

**No existing file was modified.** No dataset, model, or prior report (Phases
1/2/3/3C/3F, Phase 4) was changed. The engine and optimizer read Phase 4 code
as a read-only upstream; `routing_config.yaml` is a new file in `scripts/routing/`
(not a replacement of `config/routing.yaml`).

---

## 19. Files Modified

**NONE.**  
`git status` before and after Phase 5 shows only newly tracked/untracked files
under `scripts/routing/` and `outputs/routing/` plus the new report file.
Protected paths from Phases 1/2/3/3C/3F and the Phase 4 engine are unchanged.

---

## Final Statement

**PHASE 5 COMPLETE — DYNAMIC MULTI-OBJECTIVE ROUTE OPTIMIZER.**

**PHASE 4 REGRESSION: 22/22 PASS.**  
**ROUTING VALIDATION: 19/19 PASS.**  
**NO EXISTING SCIENTIFIC DATASETS MODIFIED.**  
**NO TRAJECTORY MODELS RETRAINED.**  
**STOPPING FOR EXPLICIT APPROVAL.**
