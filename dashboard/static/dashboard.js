/* ================================================================
   HIM-DRUSHTI  —  PHASE 7B  DASHBOARD FRONTEND
   Real-time MQTT-fed maritime decision-support UI.
   ================================================================ */
(function () {
  "use strict";

  /* ── Constants ──────────────────────────────────────────────────────────── */
  const EAST_PRYDZ = { lat: -68, lon: 76 };
  const BOUNDS     = { south: -70, north: -66, west: 72, east: 80 };
  const RISK_COLORS = {
    low:  "#00e676", moderate: "#ffb300", medium: "#ffb300",
    high: "#ff3d4e", critical: "#ff0040",
  };

  /* ── DOM refs ───────────────────────────────────────────────────────────── */
  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => document.querySelectorAll(sel);
  const commBadge      = $("#commBadge");
  const commStateLabel = $("#commStateLabel");
  const commReason     = $("#commReason");
  const lastUpdateTxt  = $("#lastUpdateTxt");
  const modelBadge     = $("#modelBadge");

  /* ── State ──────────────────────────────────────────────────────────────── */
  let state = {};
  let map, trajMap;
  let markers = {};

  /* ── Navigation ─────────────────────────────────────────────────────────── */
  $$(".nav-item").forEach((btn) => {
    btn.addEventListener("click", () => {
      $$(".nav-item").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      $$(".view").forEach((v) => v.classList.remove("active"));
      const v = $(`#view-${btn.dataset.view}`);
      if (v) v.classList.add("active");
      // Resize map if switching to map views
      setTimeout(() => {
        if (map) map.invalidateSize();
        if (trajMap) trajMap.invalidateSize();
      }, 80);
    });
  });

  /* ── Map init ───────────────────────────────────────────────────────────── */
  function initMap() {
    map = L.map("map", {
      center: [EAST_PRYDZ.lat, EAST_PRYDZ.lon],
      zoom: 5, minZoom: 4, maxZoom: 10,
      zoomControl: true,
      attributionControl: false,
    });
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      subdomains: "abc",
      maxZoom: 19,
      attribution: "© OpenStreetMap contributors",
    }).addTo(map);
    L.rectangle(
      [[BOUNDS.south, BOUNDS.west], [BOUNDS.north, BOUNDS.east]],
      { color: "#2e7dff", weight: 1, fillOpacity: 0.03, dashArray: "5 5" }
    ).addTo(map);
  }

  function initTrajMap() {
    trajMap = L.map("mapTraj", {
      center: [EAST_PRYDZ.lat, EAST_PRYDZ.lon],
      zoom: 5, minZoom: 4, maxZoom: 10,
      zoomControl: true,
      attributionControl: false,
    });
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      subdomains: "abc", maxZoom: 19,
      attribution: "© OpenStreetMap contributors",
    }).addTo(trajMap);
    L.rectangle(
      [[BOUNDS.south, BOUNDS.west], [BOUNDS.north, BOUNDS.east]],
      { color: "#2e7dff", weight: 1, fillOpacity: 0.03, dashArray: "5 5" }
    ).addTo(trajMap);
  }

  /* ── Map helpers ────────────────────────────────────────────────────────── */
  /* Forecast payload field names (Phase 6 schema: forecast_latitude/_longitude,
     plus forecast_horizon). Accept both schema names and any aliases. */
  function fcPos(fc) {
    if (!fc) return null;
    const lat = fc.forecast_latitude ?? fc.forecast_lat;
    const lon = fc.forecast_longitude ?? fc.forecast_lon;
    return (lat != null && lon != null) ? { lat: lat, lon: lon } : null;
  }
  function fcHorizon(fc) {
    if (!fc) return null;
    return fc.forecast_horizon_hours ?? fc.forecast_horizon ?? (fc.horizon_days != null ? fc.horizon_days * 24 : null);
  }
  function clearMarkers() {
    Object.values(markers).forEach((m) => { if (m._layer) m._layer.remove(); });
    markers = {};
  }

  function icon(color, label) {
    return L.divIcon({
      className: "",
      html: `<div style="
        width:18px;height:18px;border-radius:50%;
        background:${color};border:2px solid rgba(255,255,255,0.85);
        box-shadow:0 0 10px ${color};
        display:flex;align-items:center;justify-content:center;
        font-size:9px;color:#000;font-weight:700;
        position:relative;top:-9px;left:-9px;
      ">${label}</div>`,
      iconSize: [0, 0],
    });
  }

  function updateMap(s) {
    if (!map) return;
    clearMarkers();
    const obs = s.observation;
    const fc  = s.forecast;
    const rt  = s.route;

    if (obs) {
      const lat = obs.latitude ?? obs.lat;
      const lon = obs.longitude ?? obs.lon;
      if (lat != null && lon != null) {
        const id = obs.iceberg_id || "ICE";
        markers.obs = L.marker([lat, lon], { icon: icon("#ffb300", id.charAt(0)) })
          .addTo(map)
          .bindPopup(`<b>${id}</b><br>Observed: ${lat.toFixed(4)}, ${lon.toFixed(4)}`);
      }
    }
    if (fc) {
      const fp = fcPos(fc);
      if (fp) {
        markers.fc = L.marker([fp.lat, fp.lon], { icon: icon("#00d4ff", "F") })
          .addTo(map)
          .bindPopup(`<b>Forecast</b><br>${fp.lat.toFixed(4)}, ${fp.lon.toFixed(4)}<br>Method: ${fc.forecast_method || "—"}`);
        // Draw forecast trajectory line if observation also present
        const oLat = obs.latitude ?? obs.lat;
        const oLon = obs.longitude ?? obs.lon;
        if (oLat != null && oLon != null) {
          markers.fcLine = L.polyline([[oLat, oLon], [fp.lat, fp.lon]], {
            color: "#00d4ff", weight: 2, dashArray: "6 4", opacity: 0.7,
          }).addTo(map);
        }
      }
    }
    if (rt && rt.waypoints && rt.waypoints.length > 1) {
      const pts = rt.waypoints.map((w) => [w.lat, w.lon]);
      markers.route = L.polyline(pts, {
        color: "#00e676", weight: 2.5, opacity: 0.85,
      }).addTo(map);
      pts.forEach((p, i) => {
        const lbl = i === 0 ? "S" : i === pts.length - 1 ? "D" : "";
        if (lbl) {
          markers[`wp${i}`] = L.marker(p, { icon: icon("#00e676", lbl) }).addTo(map);
        }
      });
    }
  }

  function updateTrajMap(s) {
    if (!trajMap) return;
    // Clear previous layers except base
    trajMap.eachLayer((l) => {
      if (l instanceof L.Polyline || l instanceof L.Marker) l.remove();
    });
    const obs = s.observation;
    const fc  = s.forecast;
    if (obs) {
      const lat = obs.latitude ?? obs.lat;
      const lon = obs.longitude ?? obs.lon;
      if (lat != null && lon != null) {
        L.marker([lat, lon], { icon: icon("#ffb300", "O") }).addTo(trajMap)
          .bindPopup(`Observed: ${lat.toFixed(4)}, ${lon.toFixed(4)}`);
      }
    }
    if (fc) {
      const fp = fcPos(fc);
      if (fp) {
        L.marker([fp.lat, fp.lon], { icon: icon("#00d4ff", "F") }).addTo(trajMap)
          .bindPopup(`Forecast: ${fp.lat.toFixed(4)}, ${fp.lon.toFixed(4)}`);
      }
      if (obs && fp) {
        const oLat = obs.latitude ?? obs.lat;
        const oLon = obs.longitude ?? obs.lon;
        if (oLat != null && oLon != null) {
          L.polyline([[oLat, oLon], [fp.lat, fp.lon]], {
            color: "#00d4ff", weight: 2, dashArray: "6 4", opacity: 0.7,
          }).addTo(trajMap);
        }
      }
    }
  }

  /* ── KV table helpers ───────────────────────────────────────────────────── */
  function kvRows(tbody, rows) {
    tbody.innerHTML = rows
      .map(([k, v, cls]) => `<tr><td class="k">${k}</td><td class="v${cls ? " " + cls : ""}">${v ?? "N/A"}</td></tr>`)
      .join("");
  }
  function kvVal(v, dp) { return v != null ? (typeof v === "number" ? v.toFixed(dp ?? 2) : v) : null; }

  /* ── Panel renderers ────────────────────────────────────────────────────── */
  function renderHeader(s) {
    const cs = s.comm_state || "FRESH";
    commBadge.dataset.state = cs;
    commStateLabel.textContent = cs.replace(/_/g, " ");
    commReason.textContent = s.status ? (s.status.reason || "") : "";
    lastUpdateTxt.textContent = s.last_update ? `Last update: ${s.last_update}` : "Waiting for MQTT data…";
    const fc = s.forecast;
    modelBadge.textContent = fc ? `Model: ${fc.forecast_method || "—"}` : "—";

    // Last-known banner on all views
    $$(".last-known-banner").forEach((b) => b.remove());
    if (cs === "LAST_KNOWN_STATE" || cs === "STALE") {
      const banner = document.createElement("div");
      banner.className = "last-known-banner";
      banner.textContent = cs === "LAST_KNOWN_STATE"
        ? "⛔  LAST-KNOWN-STATE  —  Communication lost; displaying last valid data"
        : "⚠  STALE  —  Data may be outdated";
      $$(".view.active").forEach((v) => v.prepend(banner));
    }
  }

  function renderOverview(s) {
    // Observation card
    const obs = s.observation;
    const liveObs = $("#liveObs");
    if (obs) {
      liveObs.classList.add("on");
      const id  = obs.iceberg_id || "—";
      const lat = kvVal(obs.latitude ?? obs.lat, 4);
      const lon = kvVal(obs.longitude ?? obs.lon, 4);
      const src = obs.data_source || "—";
      const ts  = obs.observation_time || obs.timestamp || "—";
      $("#kObsBody").innerHTML = `
        <div class="text-bright" style="font-size:14px;font-weight:600;margin-bottom:6px">${id}</div>
        <div class="text-sm text-dim mb-1">${src} &nbsp;|&nbsp; ${ts}</div>
        <div class="text-sm text-dim">${lat ?? "N/A"}°,  ${lon ?? "N/A"}°</div>`;
    } else {
      liveObs.classList.remove("on");
      $("#kObsBody").innerHTML = '<span class="muted">Waiting for observation…</span>';
    }

    // Forecast card
    const fc = s.forecast;
    const liveFc = $("#liveFc");
    if (fc) {
      liveFc.classList.add("on");
      const method = fc.forecast_method || "—";
      const isXgb  = method === "MOTION_AWARE_XGBOOST";
      const badge  = isXgb ? '<span class="text-cyan text-sm" style="font-weight:700">MOTION-AWARE XGBOOST</span>'
                            : '<span class="text-amber text-sm" style="font-weight:700">PERSISTENCE FALLBACK</span>';
      const fp = fcPos(fc);
      const fl = fp ? kvVal(fp.lat, 4) : null;
      const fo = fp ? kvVal(fp.lon, 4) : null;
      const hb = fc.fallback ? `<div class="text-xs text-amber mt-1">Fallback: ${fc.fallback_reason || "—"}</div>` : "";
      const pred = fc.predecessor_available != null
        ? `<div class="text-xs text-dim mt-1">Predecessor: ${fc.predecessor_available ? "Yes" : "No"}</div>`
        : "";
      $("#kFcBody").innerHTML = `
        <div class="mb-1">${badge}</div>
        <div class="text-sm text-dim">Position: ${fl ?? "N/A"}°,  ${fo ?? "N/A"}°</div>
        ${pred}${hb}`;
    } else {
      liveFc.classList.remove("on");
      $("#kFcBody").innerHTML = '<span class="muted">Waiting for forecast…</span>';
    }

    // Risk card
    const risk = s.risk;
    const liveRisk = $("#liveRisk");
    if (risk) {
      liveRisk.classList.add("on");
      const lvl = (risk.risk_level || "—").toUpperCase();
      const clr = RISK_COLORS[lvl.toLowerCase()] || "#6a7a94";
      const score = kvVal(risk.risk_score, 2);
      const sep   = kvVal(risk.separation_km, 2);
      $("#kRiskBody").innerHTML = `
        <div style="font-size:15px;font-weight:700;color:${clr};margin-bottom:4px">${lvl}</div>
        <div class="text-sm text-dim">Score: ${score ?? "N/A"} &nbsp;|&nbsp; Separation: ${sep ?? "N/A"} km</div>
        <div class="text-xs text-dim mt-1">σ: ${kvVal(risk.uncertainty_sigma_km,2) ?? "N/A"} km &nbsp;|&nbsp; Anchor: ${risk.anchor_tag || "—"}</div>`;
    } else {
      liveRisk.classList.remove("on");
      $("#kRiskBody").innerHTML = '<span class="muted">Waiting for risk…</span>';
    }

    // Route card
    const rt = s.route;
    const liveRoute = $("#liveRoute");
    if (rt) {
      liveRoute.classList.add("on");
      const st = rt.route_status || "—";
      const isNoRoute = st === "NO_SAFE_ROUTE_FOUND";
      const clr = isNoRoute ? "var(--red)" : "var(--green)";
      const label = rt.route_label || "—";
      const dist  = kvVal(rt.route_distance_km, 1);
      const time  = kvVal(rt.estimated_travel_time_hours, 1);
      const routeInfo = isNoRoute
        ? '<div class="text-red" style="font-weight:600">NO SAFE ROUTE FOUND</div>'
        : `<div class="text-sm text-dim">${dist ?? "N/A"} km  |  ${time ?? "N/A"} h  |  Max risk: ${kvVal(rt.max_risk_score_encountered, 2) ?? "—"}</div>`;
      $("#kRouteBody").innerHTML = `
        <div style="font-size:13px;font-weight:700;color:${clr};margin-bottom:4px">${st}</div>
        <div class="text-xs text-dim mb-1">Label: ${label}</div>
        ${routeInfo}`;
    } else {
      liveRoute.classList.remove("on");
      $("#kRouteBody").innerHTML = '<span class="muted">Waiting for route…</span>';
    }
  }

  function renderIceberg(s) {
    const obs = s.observation;
    const tb = $("#tIceberg");
    if (!obs) { tb.innerHTML = '<tr><td class="v dim" colspan="2">Waiting for observation…</td></tr>'; return; }
    kvRows(tb, [
      ["Iceberg ID",        obs.iceberg_id || "—"],
      ["Latitude",          kvVal(obs.latitude ?? obs.lat, 4)],
      ["Longitude",         kvVal(obs.longitude ?? obs.lon, 4)],
      ["Observation Time",  obs.observation_time || obs.timestamp || "—"],
      ["Data Source",       obs.data_source || "—"],
      ["Length (nm)",       kvVal(obs.length_nm ?? obs.iceberg_length_nm, 1)],
      ["Width (nm)",        kvVal(obs.width_nm ?? obs.iceberg_width_nm, 1)],
      ["Prev Δ Lat",        kvVal(obs.prev_delta_lat, 4)],
      ["Prev Δ Lon",        kvVal(obs.prev_delta_lon, 4)],
      ["Prev Speed (kn)",   kvVal(obs.prev_speed, 2)],
      ["Prev Bearing (°)",  kvVal(obs.prev_bearing, 1)],
      ["Wind U 10 m/s",     kvVal(obs.wind_u_10m, 2)],
      ["Wind V 10 m/s",     kvVal(obs.wind_v_10m, 2)],
      ["Wind Speed (m/s)",  kvVal(obs.wind_speed, 2)],
      ["Wind Dir (°)",      kvVal(obs.wind_dir, 1)],
      ["Temp 2 m (K)",      kvVal(obs.temperature_2m, 1)],
      ["MSL Pressure (Pa)", kvVal(obs.mean_sea_level_pressure, 0)],
      ["Ocean Speed (m/s)", kvVal(obs.ocean_speed, 3)],
      ["Ocean Dir (°)",     kvVal(obs.ocean_dir, 1)],
      ["Data Freshness",    s.comm_state || "—"],
    ]);
  }

  function renderTrajectory(s) {
    const fc  = s.forecast;
    const obs = s.observation;
    const banner = $("#trajMethodBanner");
    const tb = $("#tTraj");

    if (!fc) {
      banner.className = "traj-method-banner";
      banner.innerHTML = '<span class="muted">No forecast yet</span>';
      tb.innerHTML = '<tr><td class="v dim" colspan="2">Waiting for forecast…</td></tr>';
      return;
    }

    const method = fc.forecast_method || "—";
    const isXgb  = method === "MOTION_AWARE_XGBOOST";
    banner.className = `traj-method-banner ${isXgb ? "xgb" : "pers"}`;
    banner.innerHTML = isXgb
      ? '<span class="text-cyan" style="font-weight:700">FORECAST METHOD — MOTION-AWARE XGBOOST</span>'
      : '<span class="text-amber" style="font-weight:700">FORECAST METHOD — PERSISTENCE FALLBACK</span>';

    const fp2 = fcPos(fc);
    kvRows(tb, [
      ["Iceberg ID",             fc.iceberg_id || obs?.iceberg_id || "—"],
      ["Observed Position",      obs ? `${kvVal(obs.latitude ?? obs.lat, 4)}°, ${kvVal(obs.longitude ?? obs.lon, 4)}°` : "—"],
      ["Forecast Position",      fp2 ? `${kvVal(fp2.lat, 4)}°, ${kvVal(fp2.lon, 4)}°` : "—"],
      ["Forecast Method",        `<span class="${isXgb ? "text-cyan" : "text-amber"}" style="font-weight:700">${method}</span>`],
      ["Model Used",             fc.model_used || "—"],
      ["Horizon (hours)",        kvVal(fcHorizon(fc), 0)],
      ["Predecessor Available",  fc.predecessor_available != null ? (fc.predecessor_available ? "Yes" : "No") : "—"],
      ["Fallback",               fc.fallback != null ? (fc.fallback ? "Yes" : "No") : "—"],
      ["Fallback Reason",        fc.fallback_reason || "—"],
      ["Forecast Timestamp",     fc.timestamp || "—"],
    ]);

    setTimeout(() => updateTrajMap(s), 80);
  }

  function renderRisk(s) {
    const risk = s.risk;
    const badge = $("#riskBadge");
    const tb = $("#tRisk");

    if (!risk) {
      badge.className = "risk-badge";
      badge.textContent = "No risk data";
      tb.innerHTML = '<tr><td class="v dim" colspan="2">Waiting for risk…</td></tr>';
      return;
    }

    const lvl = (risk.risk_level || "—").toUpperCase();
    const clr = RISK_COLORS[lvl.toLowerCase()] || "#6a7a94";
    const cls = lvl === "LOW" ? "low" : (lvl === "MODERATE" || lvl === "MEDIUM") ? "med" : "high";
    badge.className = `risk-badge ${cls}`;
    badge.innerHTML = `RISK LEVEL — ${lvl}`;

    kvRows(tb, [
      ["Risk Level",                `<span style="color:${clr};font-weight:700">${lvl}</span>`],
      ["Risk Score",                kvVal(risk.risk_score, 4)],
      ["Uncertainty σ (km)",        kvVal(risk.uncertainty_sigma_km, 2)],
      ["Envelope Radius (km)",      kvVal(risk.envelope_radius_km, 2)],
      ["Corridor Radius (km)",      kvVal(risk.corridor_radius_km, 2)],
      ["Separation (km)",           kvVal(risk.separation_km, 2)],
      ["Effective Separation (km)", kvVal(risk.separation_effective_km, 2)],
      ["Anchor Tag",                risk.anchor_tag || "—"],
      ["Communication State",       risk.communication_state || s.comm_state || "—"],
      ["Data Freshness",            risk.data_freshness || "—"],
      ["Timestamp",                 risk.timestamp || "—"],
    ]);
  }

  function renderRoute(s) {
    const rt = s.route;
    const badge = $("#routeBadge");
    const tb = $("#tRoute");

    if (!rt) {
      badge.className = "route-badge";
      badge.textContent = "No route data";
      tb.innerHTML = '<tr><td class="v dim" colspan="2">Waiting for route…</td></tr>';
      return;
    }

    const st = rt.route_status || "—";
    const isNoRoute = st === "NO_SAFE_ROUTE_FOUND";
    badge.className = `route-badge ${isNoRoute ? "noroute" : "safe"}`;
    badge.innerHTML = isNoRoute
      ? "⛔  NO SAFE ROUTE FOUND"
      : `ROUTE STATUS — ${st}`;

    kvRows(tb, [
      ["Route Status",             st],
      ["Route Label",              rt.route_label || "—"],
      ["Route Distance (km)",      kvVal(rt.route_distance_km, 2)],
      ["Direct Distance (km)",     kvVal(rt.direct_distance_km, 2)],
      ["Distance Overhead (%)",    kvVal(rt.distance_overhead_pct, 1)],
      ["Travel Time (h)",          kvVal(rt.estimated_travel_time_hours, 2)],
      ["Max Risk Encountered",     kvVal(rt.max_risk_score_encountered, 2)],
      ["Communication State",      rt.communication_state || s.comm_state || "—"],
      ["Waypoints",                rt.waypoints ? `${rt.waypoints.length} points` : "—"],
      ["Replan Reason",            rt.replan_reason || "—"],
      ["Timestamp",                rt.timestamp || "—"],
    ]);
  }

  function renderComms(s) {
    const tb = $("#tComms");
    const note = $("#commsNote");
    const cs = s.comm_state || "FRESH";
    const age = s.message_age_hours;
    const st  = s.status || {};

    kvRows(tb, [
      ["Communication State",   `<span style="font-weight:700">${cs}</span>`],
      ["Last Message TS",       st.last_message_timestamp || st.timestamp || "—"],
      ["Message Age (hours)",   age != null ? age.toFixed(2) : "—"],
      ["Reason",                st.reason || "—"],
      ["Broker Connected",      s.connected ? '<span class="text-green">Yes</span>' : '<span class="text-red">No</span>'],
      ["Dashboard Status",      st.message_type === "status" ? "Valid" : "—"],
    ]);
    note.textContent = "MQTT is a prototype communication / SATCOM emulation transport — not a real satellite link.";
  }

  /* ── Master render ──────────────────────────────────────────────────────── */
  function render(s) {
    state = s;
    renderHeader(s);
    renderOverview(s);
    renderIceberg(s);
    renderTrajectory(s);
    renderRisk(s);
    renderRoute(s);
    renderComms(s);
    updateMap(s);
  }

  /* ── Initial load ───────────────────────────────────────────────────────── */
  async function loadInitial() {
    try {
      const res = await fetch("/api/state");
      const s = await res.json();
      render(s);
    } catch (e) {
      console.warn("initial load failed:", e);
    }
  }

  /* ── SSE real-time stream ───────────────────────────────────────────────── */
  function startSSE() {
    const es = new EventSource("/api/stream");
    es.onmessage = (evt) => {
      try {
        render(JSON.parse(evt.data));
      } catch (e) {
        console.warn("SSE parse error:", e);
      }
    };
    es.onerror = () => {
      console.warn("SSE connection lost — reconnecting…");
    };
  }

  /* ── Init ────────────────────────────────────────────────────────────────── */
  document.addEventListener("DOMContentLoaded", () => {
    initMap();
    initTrajMap();
    loadInitial();
    startSSE();
  });
})();
