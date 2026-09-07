# PHASE 7D — FINAL REPORT
## HIM-DRUSHTI Decision-Support Dashboard (React + Tailwind CSS + Leaflet)

**Date:** 2026-09-07
**Scope:** Phase 7D — replace the Phase 7B vanilla-JS dashboard front-end with a
professional React/Tailwind/Leaflet presentation layer, served by the existing
Flask backend. Phase 3G/4/5/6 code is untouched. DEMO-A iceberg is **not**
replaced (deferred — handled separately after candidate selection).

---

## 1. Architecture

```
Browser (React SPA)
  └─ useSSE (EventSource + /api/state) ──► Flask backend: :5000
        ├─ /                       → React SPA (built)  |  legacy Jinja fallback
        ├─ /api/state              → JSON snapshot
        ├─ /api/stream             → SSE snapshots (~15s heartbeat)
        └─ MQTT broker (from Phase 6) ──► OnboardReceiver ──► payload adapters
```

- **React is the presentation layer ONLY.** No XGBoost, no risk math, no route
  optimization, no MQTT transport, no state-machine logic runs in the browser.
  The browser renders whatever the backend pushes; every value shown is a real
  field from the live MQTT payload stream.
- **Payloads are adapted, never fabricated.** `payloadAdapter.js` resolves field
  aliases (`latitude`/`lat`, `forecast_latitude`/`forecast_lat`); any field the
  payload does not carry renders as **N/A — DATA NOT AVAILABLE** (e.g.
  Visibility, Wave Height, Sea Temperature — not present in any payload).
- **Data integrity:** the Vite dev server proxies `/api` and `/stream` to the
  Flask backend (no CORS layer added); the built bundle is served **by the
  existing Flask backend** over HTTP — no separate static server.

## 2. Files Created / Modified

### Created — `dashboard/react/` (new, 18 source files)
| File | Purpose |
|---|---|
| `package.json` | deps: react 18.3.1, react-dom, react-leaflet 4.2.1, leaflet 1.9.4 · dev: vite 6, tailwind 3.4.17, postcss, autoprefixer, @vitejs/plugin-react |
| `vite.config.js` | base `./`, proxy `/api`+`/stream`→:5000, outDir `dist` |
| `tailwind.config.js` | `hds` maritime palette (#070c14 bg / #0f1724 panel / #1e2d44 border / #2e7dff · #00d4ff · #00e676 · #ffb300 · #ff3d4e) |
| `index.html` · `postcss.config.js` | Vite entry + Tailwind pipeline |
| `src/main.jsx` · `src/App.jsx` · `src/index.css` | App mount, layout orchestrator, dark-theme + Leaflet overrides + divIcon + legend CSS |
| `src/hooks/useSSE.js` | EventSource with auto-reconnect + initial `/api/state` fetch |
| `src/lib/payloadAdapter.js` | canonical adapters: obs / forecast / risk / route / status / snapshot + unit helpers |
| `src/components/Header.jsx` | title, XGBOOST/PERSISTENCE badge, comm state, last-update + age (color-graded) |
| `src/components/Sidebar.jsx` | 6-section nav (Overview / Iceberg / Forecast / Risk / Comms / Route) with scroll-to |
| `src/components/EnvironmentConditions.jsx` | real obs-payload env fields; missing → N/A · DATA NOT AVAILABLE |
| `src/components/IcebergCard.jsx` · `ForecastCard.jsx` · `RiskCard.jsx` · `RouteCard.jsx` · `CommunicationCard.jsx` | decision panels |
| `src/components/StatusBadge.jsx` · `RiskBadge.jsx` | FRESH/STALE/LAST-KNOWN-STATE and LOW/MODERATE/HIGH badges |
| `src/components/OperationalMap.jsx` | Leaflet map (divIcon markers, trajectory line, envelope/corridor circles, route polyline) |
| `src/components/QuickLayers.jsx` · `MapLegend.jsx` | overlay toggles (disabled until real data) + legend |

### Modified — `dashboard/backend.py` (+14 / −1)
Serves the built React bundle at `/` when `react/dist/index.html` exists;
otherwise falls back to the Phase 7B Jinja template (rollback intact). Added
`/assets/<path>` route for the hashed bundle files. **No Phase 6 import or
logic was touched.**

### Deleted
None.

### Untouched (verified via `git status`)
`scripts/ml/*` (Phase 3G), `scripts/risk/*` / risk engine (Phase 4),
`scripts/routing/*` (Phase 5), `scripts/communication/*` (Phase 6),
`data/*`, `config/*`, `dashboard/static/*`, `dashboard/templates/index.html`.

---

## 3. Validation — 24-item Checklist (A–X)

| # | Check | Result |
|---|---|---|
| A | React is presentation layer only — no engine imports (grep for `xgboost|pandas|numpy|sklearn|paho|mqtt|StateMachine`) | **PASS** — no matches |
| B | No fabricated data — missing fields render N/A | **PASS** (Visibility/Wave/SeaTemp → "DATA NOT AVAILABLE") |
| C | Payload aliases normalized (`latitude`/`lat`, `forecast_latitude`/`forecast_lat`) | **PASS** (payloadAdapter) |
| D | Phase 3G/4/5/6 sources unmodified | **PASS** — `git status` clean outside `backend.py` + `react/` |
| E | No MQTT/risk/route/state-machine logic in frontend | **PASS** (see A) |
| F | Existing Flask backend serves the React build | **PASS** — HTTP 200 on `/`, `/assets/*`, `/api/state` |
| G | Production build compiles | **PASS** — 87 modules, 328 kB JS (gzip 99.6 kB) |
| H | `base: "./"` — assets resolve from any mount path | **PASS** (vite.config.js) |
| I | Legacy rollback preserved | **PASS** — `templates/index.html` + `static/dashboard.js` intact; `/` falls back when `dist` absent |
| J | SSE real-time updates wired to live payloads | **PASS** (useSSE → EventSource `/api/stream`) |
| K | Initial snapshot from `/api/state` | **PASS** — 200, shape `{observation, forecast, risk, route, status, comm_state, connected, last_update, update_seq, message_age_hours}` |
| L | Communication states map correctly | **PASS** — FRESH/STALE/LAST_KNOWN_STATE (underscore→dash display) |
| M | REPLAN/RECOVERY not conflated with comm state | **PASS** |
| N | Temperature shown properly (ERA5 2m **air** temp, K→°C) | **PASS** (kelvinToC) |
| O | No visibility/wave/SST fields fabricated | **PASS** (rendered N/A) |
| P | Leaflet markers use divIcon (no broken bundle assets) | **PASS** |
| Q | Risk circles use envelope/corridor radii (km→m) | **PASS** |
| R | NO_SAFE_ROUTE_FOUND — nothing drawn, clear red warning | **PASS** (RouteCard) |
| S | Quick Layers toggle only when real data present | **PASS** (disabled until any layer data) |
| T | Tailwind palette + JetBrains Mono/Inter consistent | **PASS** |
| U | Dark map theme overrides applied | **PASS** (leaflet-container/zoom/attribution) |
| V | Deps limited to presentation stack (§26 approved) | **PASS** — only react/react-dom/react-leaflet/leaflet |
| W | No project files created outside approved scope | **PASS** — smoke-test logs kept in `%TEMP%`, removed |
| X | DEMO-A iceberg NOT replaced (§34) | **PASS** — no data/model edits |

---

## 4. How to Run

```bat
:: production (Flask serves the built React bundle)
python dashboard/backend.py                :: http://localhost:5000
:: or with LAN broker
python dashboard/backend.py --broker <ip>  :: e.g. 10.20.231.143

:: dev mode (live reload, proxies to :5000)
cd dashboard/react
npm run dev                                :: http://localhost:5173

:: rebuild after a source change
cd dashboard/react && npm run build
```

### Portability to Laptop-2 (see PHASE7A checklist)
1. Copy the whole `dashboard/` folder (includes `react/` with built `dist/`).
2. Flask backend auto-detects the Phase 6 modules in the copied layout
   (`_find_comm_dir()` walks upward for `onboard_receiver.py`).
3. The built SPA needs no node_modules at runtime — `dist/` is self-contained
   JS/CSS served by Flask. (node/npm only required to rebuild.)

---

## 5. Absolute Stop Confirmations (§34)

- ✅ **No** dataset or model file modified.
- ✅ **No** Phase 3G / Phase 4 / Phase 5 / Phase 6 code modified.
- ✅ **No** MQTT schema or communication-state logic changed.
- ✅ **No** risk logic or route logic changed.
- ✅ DEMO-A iceberg **not** replaced — real historical candidate replacement is a
  separate, subsequent task (wired to Phase 7C candidate search).