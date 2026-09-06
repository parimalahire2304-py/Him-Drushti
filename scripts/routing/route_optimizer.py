#!/usr/bin/env python3
"""
PHASE 5 — DYNAMIC MULTI-OBJECTIVE ROUTE OPTIMIZER  (deterministic prototype)
================================================================================

Consumes the Phase 4 uncertainty-aware iceberg risk layer (the `navigation_layer`
grid of per-cell `max_score` / class) and generates a **safer vessel route**
balancing, in order of priority:

    1. Safety / iceberg risk            (primary objective)
    2. Route distance   (haversine km)
    3. Estimated travel time
    4. Environmental / navigation penalty (optional; NONE used in Phase 5 demos)

Properties (spec §4–§10, §22–§23):
  * Fully deterministic — no randomness anywhere; same inputs -> same route.
  * Grid-based A* on the East Prydz Bay region (EPSG:4326, lat -70..-66, lon 72..80);
    8-connected moves; cell resolution from config (0.05 deg ~ 5 km).
  * Multi-objective weighted-sum cost, weights read from routing_config.yaml and
    labelled PROTOTYPE CONFIGURATION (safety has the highest weight).
  * HARD SAFETY CONSTRAINT (PROTOTYPE DECISION-SUPPORT RULE): any cell whose
    Phase 4 risk score >= critical_risk_threshold is IMPASSABLE. The optimizer
    NEVER silently crosses a critical region for a shorter route.
  * A* heuristic is admissible (distance_weight x haversine), so the returned
    route is the true lowest-cost route under the configured weights; Dijkstra
    is available as a fallback (identical result).
  * Distances are great-circle (haversine, R = 6371.0088 km from Phase 4) — grid
    degrees are NEVER treated as equal-area Cartesian metres.
  * Travel time = route_distance / vessel_speed  (labelled PROTOTYPE TRAVEL-TIME
    ESTIMATE; no operational ETA claim).
  * Explicit failure state NO_SAFE_ROUTE_FOUND when no valid route exists.
  * Communication-resilient: accepts Phase 4 comm state; a route computed while
    data_freshness == "LAST-KNOWN-STATE MODE" is labelled LAST-KNOWN-STATE ROUTE.

    ************************************************************
    *  PROTOTYPE — NOT a certified maritime navigation system.  *
    *  No route produced here is guaranteed safe for navigation. *
    ************************************************************
"""

from __future__ import annotations

import heapq
import math
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = Path(__file__).resolve().parent / "routing_config.yaml"

# Reuse Phase 4 geodesy (single source of truth — Phase 4 code is NOT modified).
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "risk"))
from risk_engine import EARTH_RADIUS_KM, haversine_km  # noqa: E402

# Class encodings for fast numpy masks (values are ints, see RiskField.classes):
CLS_LOW = 0
CLS_MODERATE = 1
CLS_HIGH = 2


def _load_yaml(path: Path) -> dict:
    import yaml
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


# -----------------------------------------------------------------------------
# Risk field
# -----------------------------------------------------------------------------
@dataclass
class RiskField:
    """Rasterised Phase 4 navigation-layer over the region grid."""
    lat_min: float
    lat_max: float
    lon_min: float
    lon_max: float
    res: float
    scores: np.ndarray                 # (n_lat, n_lon) float 0-100
    classes: np.ndarray                # (n_lat, n_lon) int 0/1/2 (LOW/MODERATE/HIGH)
    covered: np.ndarray                # (n_lat, n_lon) bool (a Phase 4 corridor touched it)
    meta: dict = field(default_factory=dict)

    @property
    def n_lat(self) -> int:
        return self.scores.shape[0]

    @property
    def n_lon(self) -> int:
        return self.scores.shape[1]

    def lat_at(self, i: int) -> float:
        return self.lat_min + (i + 0.5) * self.res

    def lon_at(self, j: int) -> float:
        return self.lon_min + (j + 0.5) * self.res

    def cell_index(self, lat: float, lon: float) -> tuple[int, int]:
        i = int(round((lat - self.lat_min) / self.res - 0.5))
        j = int(round((lon - self.lon_min) / self.res - 0.5))
        return max(0, min(self.n_lat - 1, i)), max(0, min(self.n_lon - 1, j))

    def build_environment_layer(self, env_layer: dict | None) -> np.ndarray:
        """Return per-cell environment penalty array (0 where not supplied)."""
        pen = np.zeros((self.n_lat, self.n_lon), dtype=float)
        if not env_layer or not env_layer.get("cells"):
            return pen
        res = float(env_layer.get("grid_resolution_degrees", self.res))
        lat0 = float(env_layer.get("lat_min", self.lat_min))
        lon0 = float(env_layer.get("lon_min", self.lon_min))
        for c in env_layer["cells"]:
            li, lj = self.cell_index(float(c["lat"]), float(c["lon"]))
            if abs(float(c.get("lat", 0)) - self.lat_at(li)) <= res * 0.75 \
               and abs(float(c.get("lon", 0)) - self.lon_at(lj)) <= res * 0.75:
                pen[li, lj] = max(pen[li, lj], float(c["penalty"]))
        return pen


# -----------------------------------------------------------------------------
# Result object
# -----------------------------------------------------------------------------
@dataclass
class RouteResult:
    status: str                              # SAFE | CAUTION | NO_SAFE_ROUTE_FOUND
    route: list[tuple[float, float]]         # ordered waypoints (lat, lon)
    route_cells: list[tuple[int, int]]       # cell indices traversed
    metrics: dict                            # spec §10 metric dictionary
    communication_status: str = "NOMINAL"
    data_freshness: str = "FRESH"
    route_label: str = "ROUTE"
    no_route_reason: str = ""
    notes: list[str] = field(default_factory=list)
    inputs_used: dict = field(default_factory=dict)

    @property
    def is_no_route(self) -> bool:
        return self.status == "NO_SAFE_ROUTE_FOUND"

    def to_dict(self) -> dict:
        """Machine-readable record (spec §16)."""
        m = dict(self.metrics)
        return {
            "schema": "him_drushti.route_optimizer.v1",
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "route_status": self.status,
            "route_label": self.route_label,
            "communication_status": self.communication_status,
            "data_freshness": self.data_freshness,
            "route_coordinates": [{"lat": round(lat, 5), "lon": round(lon, 5)}
                                  for lat, lon in self.route],
            "no_route_reason": self.no_route_reason,
            **m,
            "notes": self.notes,
            "inputs_used": self.inputs_used,
        }

    def to_csv_row(self) -> dict:
        d = self.to_dict()
        d["route_coordinates"] = ";".join(
            f"{lat:.5f},{lon:.5f}" for lat, lon in self.route) or ""
        return d


def _route_length_km(route: list[tuple[float, float]]) -> float:
    return sum(haversine_km(route[i][0], route[i][1],
                            route[i + 1][0], route[i + 1][1])
               for i in range(len(route) - 1))


# -----------------------------------------------------------------------------
# Optimizer
# -----------------------------------------------------------------------------
class RouteOptimizer:
    """Deterministic multi-objective grid route optimizer (Phase 5)."""

    def __init__(self, config_path: Path | str | None = None) -> None:
        path = Path(config_path) if config_path else DEFAULT_CONFIG
        self.cfg = _load_yaml(path)
        self._cfg_path = path
        self._w = self.cfg["objectives"]
        self._crit = float(self.cfg["safety"]["critical_risk_threshold"])
        self._cls_mod = float(self.cfg["safety"]["moderate_class_min_score"])
        self._cls_high = float(self.cfg["safety"]["high_class_min_score"])

    # ---- field construction ------------------------------------------------
    def risk_field_from_layer(self, layer: dict) -> RiskField:
        """Rasterise a Phase 4 `navigation_layer` dict into a RiskField."""
        res = float(layer["grid_resolution_degrees"])
        lat0 = float(layer["lat_min"]); lat1 = float(layer["lat_max"])
        lon0 = float(layer["lon_min"]); lon1 = float(layer["lon_max"])
        n_lat = int(round((lat1 - lat0) / res)) + 1
        n_lon = int(round((lon1 - lon0) / res)) + 1
        scores = np.zeros((n_lat, n_lon), dtype=float)
        covered = np.zeros((n_lat, n_lon), dtype=bool)
        for c in layer["cells"]:
            i, j = self._cell_index_from_center(lat0, lon0, res, n_lat, n_lon,
                                                float(c["lat"]), float(c["lon"]))
            scores[i, j] = max(scores[i, j], float(c["max_score"]))
            covered[i, j] = True
        classes = np.zeros((n_lat, n_lon), dtype=np.int8)
        classes[scores >= self._cls_high] = CLS_HIGH
        classes[(scores >= self._cls_mod) & (scores < self._cls_high)] = CLS_MODERATE
        return RiskField(lat0, lat1, lon0, lon1, res, scores, classes, covered,
                         meta={k: v for k, v in layer.items() if k != "cells"})

    @staticmethod
    def _cell_index_from_center(lat0: float, lon0: float, res: float,
                                n_lat: int, n_lon: int,
                                lat: float, lon: float) -> tuple[int, int]:
        i = int(round((lat - lat0) / res - 0.5))
        j = int(round((lon - lon0) / res - 0.5))
        return max(0, min(n_lat - 1, i)), max(0, min(n_lon - 1, j))

    # ---- hard-constraint mask / snapping -----------------------------------
    def _impassable(self, field: RiskField) -> np.ndarray:
        return field.scores >= self._crit          # HARD SAFETY CONSTRAINT

    def _snap_navigable(self, field: RiskField, imp: np.ndarray,
                        lat: float, lon: float) -> tuple[tuple[int, int], int, str | None]:
        """Snap a point to the nearest navigable cell within snap radius."""
        j0, j1 = field.cell_index(lat, lon)
        max_r = int(self.cfg["grid"]["start_destination_snap_cells"])
        if not imp[j0, j1]:
            return (j0, j1), 0, None
        for r in range(1, max_r + 1):
            for di in range(-r, r + 1):
                for dj in range(-r, r + 1):
                    if max(abs(di), abs(dj)) != r:
                        continue
                    i = j0 + di; j = j1 + dj
                    if 0 <= i < field.n_lat and 0 <= j < field.n_lon and not imp[i, j]:
                        return (i, j), r, ("start/dest snapped %d cell(s) to nearest "
                                           "navigable cell (safety constraint)" % r)
        return (j0, j1), max_r, "NO_SAFE_ROUTE_FOUND: start/destination inside impassable region"

    # ---- A* / Dijkstra ------------------------------------------------------
    def _path(self, field: RiskField, imp: np.ndarray, env: np.ndarray,
              start: tuple[int, int], goal: tuple[int, int],
              speed_kmh: float, use_heuristic: bool) -> list[tuple[int, int]] | None:
        w = self._w
        n_lat, n_lon = field.n_lat, field.n_lon
        # deterministic neighbor order (8-connected)
        neigh = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
        g = np.full((n_lat, n_lon), np.inf)
        prev: dict[tuple[int, int], tuple[int, int]] = {}
        g[start] = 0.0
        open_heap: list[tuple[float, float, int, int]] = []
        goal_pt = (field.lat_at(goal[0]), field.lon_at(goal[1]))
        h0 = w["distance_weight"] * haversine_km(field.lat_at(start[0]),
                                                 field.lon_at(start[1]), *goal_pt) \
            if use_heuristic else 0.0
        heapq.heappush(open_heap, (h0, -0.0, start[0], start[1]))
        visited = {start}
        scale = float(w["risk_cost_scale"])
        while open_heap:
            f, _neg, i, j = heapq.heappop(open_heap)
            if (i, j) == goal:
                break
            gi = g[i, j]
            lat_i, lon_i = field.lat_at(i), field.lon_at(j)
            for di, dj in neigh:
                ni, nj = i + di, j + dj
                if not (0 <= ni < n_lat and 0 <= nj < n_lon):
                    continue
                if imp[ni, nj]:
                    continue
                # no U-turns / redundant revisits are naturally pruned by g-values
                d = haversine_km(lat_i, lon_i, field.lat_at(ni), field.lon_at(nj))
                t = d / speed_kmh
                step = (w["safety_weight"] * (field.scores[ni, nj] / scale)
                        + w["distance_weight"] * d
                        + w["time_weight"] * t
                        + w["environment_weight"] * env[ni, nj])
                ng = gi + step
                if ng < g[ni, nj]:
                    g[ni, nj] = ng
                    prev[(ni, nj)] = (i, j)
                    h = w["distance_weight"] * haversine_km(field.lat_at(ni),
                                                            field.lon_at(nj), *goal_pt) \
                        if use_heuristic else 0.0
                    heapq.heappush(open_heap, (ng + h, -ng, ni, nj))
        if not np.isfinite(g[goal]):
            return None
        # reconstruct deterministically
        path = [goal]
        cur = goal
        while cur != start:
            cur = prev[cur]
            path.append(cur)
        path.reverse()
        return path

    # ---- public API ---------------------------------------------------------
    def solve(self, start: tuple[float, float], destination: tuple[float, float],
              risk_layer: dict,
              *, vessel_speed_knots: float | None = None,
              environment_layer: dict | None = None,
              communication_status: str = "NOMINAL",
              data_freshness: str = "FRESH",
              header: str = "") -> RouteResult:
        """Compute the lowest-cost safe route (deterministic).

        start / destination  : (lat, lon) in EPSG:4326.
        risk_layer           : a Phase 4 `navigation_layer` dict (or a compatible
                               {cells:[{lat,lon,max_score}], grid_resolution_degrees,
                               lat_min,...} structure).
        """
        field = self.risk_field_from_layer(risk_layer)
        imp = self._impassable(field)
        env = field.build_environment_layer(environment_layer)
        speed_knots = float(vessel_speed_knots if vessel_speed_knots is not None
                            else self.cfg["vessel"]["speed_knots_default"])
        speed_kmh = speed_knots * float(self.cfg["vessel"]["knots_to_kmh"])

        (si, sj), s_off, s_note = self._snap_navigable(field, imp, start[0], start[1])
        (gi_i, gi_j), g_off, g_note = self._snap_navigable(field, imp,
                                                           destination[0], destination[1])
        notes = [n for n in (s_note, g_note) if n]
        bad = [n for n in notes if n and n.startswith("NO_SAFE_ROUTE_FOUND")]
        if bad or imp[si, sj] or imp[gi_i, gi_j]:
            return self._no_route(field, imp, si, sj, gi_i, gi_j,
                                  start, destination, speed_kmh,
                                  communication_status, data_freshness,
                                  bad[0] if bad else None, notes)

        algo = str(self.cfg["pathfinding"]["algorithm"]).lower()
        use_heuristic = (algo == "astar"
                         and bool(self.cfg["pathfinding"]["heuristic_weight_only_distance"]))
        path = self._path(field, imp, env, (si, sj), (gi_i, gi_j), speed_kmh, use_heuristic)
        if path is None:
            return self._no_route(field, imp, si, sj, gi_i, gi_j,
                                  start, destination, speed_kmh,
                                  communication_status, data_freshness,
                                  "NO_SAFE_ROUTE_FOUND: no route avoiding all impassable cells.",
                                  notes)
        waypoints = [(field.lat_at(i), field.lon_at(j)) for i, j in path]
        return self._finalize(field, path, waypoints, imp, env, start, destination,
                              speed_knots, speed_kmh, communication_status,
                              data_freshness, notes)

    # ---- result builders ----------------------------------------------------
    def _no_route(self, field: RiskField, imp: np.ndarray,
                  si: int, sj: int, gi_: int, gj: int,
                  start: tuple[float, float], destination: tuple[float, float],
                  speed_kmh: float, comm: str, fresh: str,
                  reason: str | None, notes: list[str]) -> RouteResult:
        direct = haversine_km(start[0], start[1], destination[0], destination[1])
        metrics = {
            "route_distance_km": 0.0, "direct_distance_km": round(direct, 4),
            "distance_overhead_pct": None, "estimated_travel_time_hours": 0.0,
            "n_high_risk_cells_encountered": 0, "n_moderate_risk_cells_encountered": 0,
            "min_vessel_to_risk_distance_km": None, "min_vessel_to_high_risk_distance_km": None,
            "max_risk_score_encountered": 0.0, "cumulative_risk_cost": 0.0,
            "environmental_cost": 0.0, "total_objective_cost": None,
        }
        return RouteResult(
            status="NO_SAFE_ROUTE_FOUND", route=[], route_cells=[],
            metrics=metrics, communication_status=comm, data_freshness=fresh,
            route_label="NO_SAFE_ROUTE_FOUND",
            no_route_reason=reason or "NO_SAFE_ROUTE_FOUND",
            notes=notes + [str(self.cfg["output"]["labels"]["decision_support_rule"])],
            inputs_used={"risk_layer": True, "environment_layer": False,
                         "vessel_speed_knots": round(speed_kmh / 1.852, 2), "header": ""},
        )

    def _finalize(self, field: RiskField, path: list[tuple[int, int]],
                  waypoints: list[tuple[float, float]], imp: np.ndarray, env: np.ndarray,
                  start: tuple[float, float], destination: tuple[float, float],
                  speed_knots: float, speed_kmh: float,
                  comm: str, fresh: str, notes: list[str]) -> RouteResult:
        route_km = _route_length_km(waypoints)
        direct_km = haversine_km(start[0], start[1], destination[0], destination[1])
        overhead = (route_km / direct_km - 1.0) * 100.0 if direct_km > 0 else 0.0
        travel_h = route_km / speed_kmh                      # PROTOTYPE TRAVEL-TIME ESTIMATE
        scores_on_route = [float(field.scores[i, j]) for i, j in path]
        classes_on_route = [int(field.classes[i, j]) for i, j in path]
        n_high = sum(1 for c in classes_on_route if c == CLS_HIGH)
        n_mod = sum(1 for c in classes_on_route if c == CLS_MODERATE)
        max_risk = max(scores_on_route) if scores_on_route else 0.0
        cum_risk = float(sum(scores_on_route))
        env_used = bool(env.max() > 0)
        env_cost = 0.0
        if env_used:
            env_cost = float(sum(env[i, j] for i, j in path))
        # minimum separation from risk cells (score >= MODERATE) and HIGH cells
        min_risk_sep, min_high_sep = self._min_separation(field, waypoints)

        status = (self.cfg["report"]["status_caution"]
                  if (n_high > 0 or n_mod > 0) else self.cfg["report"]["status_safe"])
        label_cfg = self.cfg["report"]["route_labels"]
        route_label = (label_cfg["last_known_state_route"]
                       if "LAST-KNOWN-STATE" in fresh else label_cfg["nominal_route"])
        # objective cost: sum over the same per-step costs used by the solver
        objective_cost = self._objective_cost(field, path, env, speed_kmh)

        metrics = {
            "route_distance_km": round(route_km, 4),
            "direct_distance_km": round(direct_km, 4),
            "distance_overhead_pct": round(overhead, 4),
            "estimated_travel_time_hours": round(travel_h, 4),
            "n_high_risk_cells_encountered": n_high,
            "n_moderate_risk_cells_encountered": n_mod,
            "min_vessel_to_risk_distance_km": (round(min_risk_sep, 4)
                                               if min_risk_sep is not None else None),
            "min_vessel_to_high_risk_distance_km": (round(min_high_sep, 4)
                                                    if min_high_sep is not None else None),
            "max_risk_score_encountered": round(max_risk, 4),
            "cumulative_risk_cost": round(cum_risk, 4),
            "environmental_cost": round(env_cost, 4),
            "total_objective_cost": round(objective_cost, 4),
        }
        note_block = [str(self.cfg["output"]["labels"]["prototype"]),
                      str(self.cfg["output"]["labels"]["travel_time"])]
        return RouteResult(
            status=status, route=waypoints, route_cells=path,
            metrics=metrics, communication_status=comm, data_freshness=fresh,
            route_label=route_label, notes=notes + note_block,
            inputs_used={"risk_layer": True, "environment_layer": env_used,
                         "vessel_speed_knots": round(speed_knots, 2),
                         "vessel_speed_kmh": round(speed_kmh, 4),
                         "algorithm": str(self.cfg["pathfinding"]["algorithm"]).lower()},
        )

    def _objective_cost(self, field: RiskField, path: list[tuple[int, int]],
                        env: np.ndarray, speed_kmh: float) -> float:
        """Recompute total step-cost along the route (identical weights/formula)."""
        w = self._w
        scale = float(w["risk_cost_scale"])
        # entering-cell terms (risk + environment) for every cell after the start
        cell_terms = sum(w["safety_weight"] * (field.scores[ci, cj] / scale)
                         + w["environment_weight"] * env[ci, cj]
                         for ci, cj in path[1:])
        # edge terms (distance + time) over every step
        edge_terms = 0.0
        for k in range(len(path) - 1):
            ci, cj = path[k]; ni, nj = path[k + 1]
            d = haversine_km(field.lat_at(ci), field.lon_at(cj),
                             field.lat_at(ni), field.lon_at(nj))
            edge_terms += w["distance_weight"] * d + w["time_weight"] * (d / speed_kmh)
        return cell_terms + edge_terms

    def _min_separation(self, field: RiskField,
                        waypoints: list[tuple[float, float]]) -> tuple[float | None, float | None]:
        risk_idx = np.argwhere(field.scores >= self._cls_mod)
        high_idx = np.argwhere(field.scores >= self._cls_high)
        if risk_idx.size == 0:
            return None, None
        risk_lat = field.lat_min + (risk_idx[:, 0] + 0.5) * field.res
        risk_lon = field.lon_min + (risk_idx[:, 1] + 0.5) * field.res
        min_r: float | None = None
        for lat, lon in waypoints:
            d = haversine_km_np(lat, lon, risk_lat, risk_lon)
            md = float(d.min())
            min_r = md if min_r is None else min(min_r, md)
        min_h: float | None = None
        if high_idx.size:
            high_lat = field.lat_min + (high_idx[:, 0] + 0.5) * field.res
            high_lon = field.lon_min + (high_idx[:, 1] + 0.5) * field.res
            for lat, lon in waypoints:
                d = haversine_km_np(lat, lon, high_lat, high_lon)
                md = float(d.min())
                min_h = md if min_h is None else min(min_h, md)
        return min_r, min_h


def haversine_km_np(lat1, lon1, lat2, lon2) -> np.ndarray:
    """Vectorised haversine (mirror of risk_engine.haversine_km)."""
    rlat1 = np.radians(np.asarray(lat1, dtype=float))
    rlat2 = np.radians(np.asarray(lat2, dtype=float))
    dphi = np.radians(np.asarray(lat2, dtype=float)) - rlat1
    dlambda = np.radians(np.asarray(lon2, dtype=float)) - np.radians(np.asarray(lon1, dtype=float))
    a = np.sin(dphi * 0.5) ** 2 + np.cos(rlat1) * np.cos(rlat2) * np.sin(dlambda * 0.5) ** 2
    return EARTH_RADIUS_KM * 2.0 * np.arctan2(np.sqrt(a), np.sqrt(1.0 - a))