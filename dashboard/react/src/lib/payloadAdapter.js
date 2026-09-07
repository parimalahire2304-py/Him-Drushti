/**
 * payloadAdapter.js — normalises Him-Drushti MQTT payload field aliases
 * so components always read a single canonical name.
 *
 * The observation payload uses `latitude`/`longitude`; the pipeline uses
 * `lat`/`lon`.  Forecast uses `forecast_latitude`/`forecast_longitude` but
 * some paths emit `forecast_lat`/`forecast_lon`.  This module resolves
 * both forms into one stable API shape.
 */

/* ── Observation adapter ────────────────────────────────────────────── */
export function adaptObs(raw) {
  if (!raw) return null;
  return {
    icebergId:      raw.iceberg_id          ?? "—",
    lat:            raw.latitude             ?? raw.lat,
    lon:            raw.longitude            ?? raw.lon,
    obsTime:        raw.observation_time     ?? raw.timestamp ?? "—",
    dataSource:     raw.data_source         ?? "—",
    lengthNm:       raw.length_nm           ?? raw.iceberg_length_nm,
    widthNm:        raw.width_nm            ?? raw.iceberg_width_nm,
    prevDeltaLat:   raw.prev_delta_lat,
    prevDeltaLon:   raw.prev_delta_lon,
    prevSpeed:      raw.prev_speed,
    prevBearing:    raw.prev_bearing,
    // environment fields (all from obs payload)
    seaIceConc:     raw.sea_ice_concentration,
    windU:          raw.wind_u_10m,
    windV:          raw.wind_v_10m,
    windSpeed:      raw.wind_speed,
    windDir:        raw.wind_dir,
    temp2m:         raw.temperature_2m,       // Kelvin — air temp
    mslp:           raw.mean_sea_level_pressure,
    precip:         raw.total_precipitation,
    bathy:          raw.bathymetry_elevation,
    oceanU:         raw.ocean_current_u,
    oceanV:         raw.ocean_current_v,
    oceanSpeed:     raw.ocean_speed,
    oceanDir:       raw.ocean_dir,
    exposedWater:   raw.exposed_water_fraction,
    // historical replay marker (prototype feeds real historical obs)
    historicalReplay: raw.historical_replay === true,
    historicalLabel:  raw.historical_label,
    // keep raw for any extra keys
    _raw: raw,
  };
}

/* ── Forecast adapter ───────────────────────────────────────────────── */
export function adaptFc(raw) {
  if (!raw) return null;
  return {
    icebergId:       raw.iceberg_id,
    method:          raw.forecast_method    ?? "—",
    modelUsed:       raw.model_used         ?? "—",
    predecessor:     raw.predecessor_available,
    fallback:        raw.fallback,
    fallbackReason:  raw.fallback_reason,
    fcLat:           raw.forecast_latitude  ?? raw.forecast_lat,
    fcLon:           raw.forecast_longitude ?? raw.forecast_lon,
    horizonHrs:      raw.forecast_horizon   ?? raw.forecast_horizon_hours,
    comms:           raw.communication_state,
    freshness:       raw.data_freshness,
    _raw:            raw,
  };
}

/* ── Risk adapter ───────────────────────────────────────────────────── */
export function adaptRisk(raw) {
  if (!raw) return null;
  return {
    icebergId:    raw.iceberg_id,
    level:        raw.risk_level            ?? "—",
    score:        raw.risk_score,
    sigmaKm:      raw.uncertainty_sigma_km,
    envelopeKm:   raw.envelope_radius_km,
    corridorKm:   raw.corridor_radius_km,
    separationKm: raw.separation_km,
    separationEff:raw.separation_effective_km,
    anchorTag:    raw.anchor_tag            ?? "—",
    comms:        raw.communication_state,
    freshness:    raw.data_freshness,
    _raw:         raw,
  };
}

/* ── Route adapter ──────────────────────────────────────────────────── */
export function adaptRoute(raw) {
  if (!raw) return null;
  return {
    status:          raw.route_status                ?? "—",
    label:           raw.route_label                 ?? "—",
    comms:           raw.communication_state,
    freshness:       raw.data_freshness,
    distKm:          raw.route_distance_km,
    directKm:        raw.direct_distance_km,
    overheadPct:     raw.distance_overhead_pct,
    travelHrs:       raw.estimated_travel_time_hours,
    maxRisk:         raw.max_risk_score_encountered,
    waypoints:       raw.waypoints                    ?? [],
    routeVariants:   raw.route_variants               ?? null,  // Phase 7F
    _raw:            raw,
  };
}

/* ── Route options adapter (Phase 7F: three weight variants) ────────── */
export function adaptRouteOptions(raw) {
  if (!raw?.route_variants) return null;
  return raw.route_variants.map(v => ({
    variant:     v.variant,        // "SAFEST" | "TIME" | "FUEL"
    status:      v.status,
    distKm:      v.distance_km,
    travelHrs:   v.travel_hrs,
    maxRisk:     v.max_risk,
    overheadPct: v.overhead_pct,
    waypoints:   v.waypoints ?? [],
  }));
}

/* ── Status adapter ─────────────────────────────────────────────────── */
export function adaptStatus(raw) {
  if (!raw) return null;
  return {
    comms:   raw.communication_state   ?? "—",
    lastTs:  raw.last_message_timestamp ?? "—",
    ageHrs:  raw.message_age_hours,
    reason:  raw.reason                ?? "—",
    _raw:    raw,
  };
}

/* ── Snapshot adapter (wraps backend /api/state shape) ──────────────── */
export function adaptSnapshot(snap) {
  if (!snap) return null;
  return {
    obs:          adaptObs(snap.observation),
    fc:           adaptFc(snap.forecast),
    risk:         adaptRisk(snap.risk),
    route:        adaptRoute(snap.route),
    status:       adaptStatus(snap.status),
    commState:    snap.comm_state    ?? "—",
    connected:    snap.connected     ?? false,
    lastUpdate:   snap.last_update   ?? "—",
    ageHrs:       snap.message_age_hours,
    updateSeq:    snap.update_seq    ?? 0,
  };
}

/* ── Unit helpers ───────────────────────────────────────────────────── */
export function kelvinToC(k) {
  return k != null && !isNaN(k) ? (k - 273.15).toFixed(1) : null;
}
export function speedMsToKt(ms) {
  return ms != null && !isNaN(ms) ? (ms * 1.9438).toFixed(1) : null;
}
export function degToDir(d) {
  if (d == null || isNaN(d)) return null;
  const dirs = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
                "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"];
  return dirs[Math.round(d / 22.5) % 16];
}
export function fracToPct(f) {
  return f != null && !isNaN(f) ? (f * 100).toFixed(0) + "%" : null;
}
export function fmt(val, unit, fallback = "N/A") {
  if (val == null || val === "" || (typeof val === "number" && isNaN(val)))
    return fallback;
  return `${val} ${unit ?? ""}`.trim();
}
