# HIM-DRUSHTI — Phase 7B Onboard Dashboard

**Antarctic Maritime Decision-Support Dashboard** — real-time, MQTT-fed,
displaying live iceberg observation, trajectory forecast, risk assessment,
route decision, and communication state for the Him-Drushti prototype.

---

## Architecture

```
Laptop-1 (Offshore AI Server)           Laptop-2 (Onboard DSS)
┌─────────────────────────────────┐     ┌──────────────────────────────────────┐
│  Phase 3G ForecastEngine        │     │                                      │
│         ↓                       │     │  dashboard/backend.py                │
│  Phase 4 RiskEngine             │     │   ├─ OnboardReceiver (Phase 6)       │
│         ↓                       │ MQTT│   │   ├─ PahoTransport               │
│  Phase 5 RouteOptimizer         │────▶│   │   ├─ CommunicationStateMachine   │
│         ↓                       │     │   │   └─ LatestState (thread-safe)   │
│  OffshorePublisher (Phase 6)    │     │   └─ Flask SSE /api/stream           │
│   publishes 5 topics:           │     │                                      │
│   himdrushti/observation        │     │  dashboard/templates/index.html      │
│   himdrushti/forecast           │     │  dashboard/static/dashboard.css      │
│   himdrushti/risk               │     │  dashboard/static/dashboard.js       │
│   himdrushti/route              │     │   └─ Leaflet map, SSE renderer       │
│   himdrushti/status             │     └──────────────────────────────────────┘
└─────────────────────────────────┘
         Mosquitto 2.1.2 broker
         10.20.231.143 : 1883
```

**Key point:** The dashboard is a **display layer only**. No forecasting,
risk calculation, or routing logic runs inside it. All state is fed
from the real Phase 3G → 4 → 5 pipeline via MQTT.

---

## File Structure

```
dashboard/
├── backend.py                  # Flask app + MQTT receiver (PahoTransport)
├── templates/
│   └── index.html              # Dark maritime UI (header/nav/map/cards)
├── static/
│   ├── dashboard.css           # CSS variables, dark theme, Leaflet overrides
│   └── dashboard.js            # SSE rendering, Leaflet maps, forecast banners
├── __pycache__/                # auto-generated, ignored by git
└── README.md                   # this file
```

**Standalone launcher:**  
`start_himdrushti_onboard.bat` — launches backend.py, connects to broker
at 10.20.231.143:1883, serves dashboard on port 5000.

---

## How to Run

### Laptop-1 (Offshore AI Server) — publish live data

```bash
# Ensure Mosquitto is running on port 1883
cd C:\Users\<you>\OneDrive\Desktop\Him-Drushti
python scripts\communication\run_offshore_publish.py
```

Or use the one-click launcher:

```
start_himdrushti_offshore.bat
```

### Laptop-2 (Onboard / Ship DSS) — view the dashboard

```bash
cd C:\Him-Drushti-Onboard
python dashboard\backend.py --broker 10.20.231.143 --listen-port 5000
```

Or use the one-click launcher:

```
start_himdrushti_onboard.bat
```

Then open a browser to: **http://localhost:5000**

---

## Dashboard Sections

| Nav Item | What It Shows |
|----------|---------------|
| **Overview** | East Prydz Bay map (−70→−66 lat, 72→80 lon) + 4 side cards: obs, forecast, risk, route |
| **Iceberg Intelligence** | Full observation table: id, lat/lon, time, source, length/width, prev_* motion, env features |
| **Trajectory Forecast** | Forecast method banner (**MOTION-AWARE XGBOOST** cyan / **PERSISTENCE FALLBACK** amber), forecast table, trajectory map |
| **Risk & Uncertainty** | Risk level badge (LOW/MODERATE/HIGH), score, σ, envelope, corridor, separation, anchor tag |
| **Route Decision** | Route status badge (SAFE / NO_SAFE_ROUTE_FOUND), distances, travel time, waypoints, replan reason |
| **Communication** | State machine (FRESH/STALE/LAST_KNOWN_STATE/RECOVERY/REPLAN), message age, broker connected |

---

## Forecast Method Display

The dashboard explicitly shows which forecast method produced the current
trajectory — **never a generic "AI Prediction"**:

- **MOTION-AWARE XGBOOST** (cyan banner) — 23-feature XGBoost model, 18.13 km MAE
  on 14 predecessor-eligible drifting icebergs. Used when `predecessor_available=True`.
- **PERSISTENCE FALLBACK** (amber banner) — constant-velocity extrapolation, 19.09 km
  MAE on the matched subset. Used when `predecessor_available=False`.

Conditional accuracy note: 18.13 km < 19.09 km **only on the predecessor-eligible
drifting subset** — not a global superiority claim.

---

## Communication State Display

| State | Badge | Meaning |
|-------|-------|---------|
| FRESH | 🟢 green dot | New message received within 48h window |
| STALE | 🟡 amber dot | Message age ≥ 48h but < 168h |
| LAST_KNOWN_STATE | 🔴 red dot + ⛔ banner | Communication lost ≥ 168h; last data shown clearly |
| RECOVERY | 🔵 cyan pulsing | Transitioning back to FRESH after loss |
| REPLAN | 🔵 cyan | Route recomputed after state change |

State is computed live from `CommunicationStateMachine.infer_state(now)` —
it drifts automatically during silent gaps without waiting for a new message.

---

## Real-Time Updates

- **SSE** (Server-Sent Events) at `/api/stream` — full snapshot pushed on every
  MQTT message, every comm-state change, or every ~15s heartbeat.
- **Initial load** via `GET /api/state` on page open.
- No manual refresh required; no fake periodic values.

---

## NO_SAFE_ROUTE_FOUND Handling

When Phase 5 finds no safe route, the dashboard shows:
- Red badge: **⛔ NO SAFE ROUTE FOUND**
- No fabricated waypoints, no fake route line on the map
- Route waypoints table shows 0 points

---

## LAST_KNOWN_STATE Handling

When communication drops for ≥ 168 hours:
- Red ⛔ banner at top of every view
- Last valid observation/forecast/risk/route remain visible
- "LAST-KNOWN-STATE" clearly marked in header and comms section
- No new data is fabricated

---

## Prerequisites

- **Python 3.13+** with Flask ≥ 3.1, paho-mqtt ≥ 2.1, PyYAML
- **Mosquitto 2.1.2** running on Laptop-1 (port 1883, bound to 0.0.0.0)
- Phase 6 transport.py, onboard_receiver.py, state_manager.py, schemas.py
  (all unchanged from Phase 6)

No additional packages installed — uses only existing project dependencies.

---

## Startup Automation (Windows)

### Adding to Windows Startup (manual)

1. Press `Win + R`, type `shell:startup`, Enter — opens the Startup folder.
2. Create shortcuts to:
   - **Laptop-1:** `start_himdrushti_offshore.bat`
   - **Laptop-2:** `start_himdrushti_onboard.bat`
3. Both scripts auto-start their respective pipeline on Windows login.

The scripts:
- Check for duplicate processes before launching
- Verify Mosquitto is running (Laptop-1 only)
- Set PYTHONPATH automatically
- Pause on error with clear diagnostic messages

---

## Laptop-2 Deployment Checklist

Copy these files to `C:\Him-Drushti-Onboard\`:

| Source | Destination | Required |
|--------|-------------|----------|
| `scripts/communication/transport.py` | `scripts/communication/transport.py` | Yes |
| `scripts/communication/schemas.py` | `scripts/communication/schemas.py` | Yes |
| `scripts/communication/state_manager.py` | `scripts/communication/state_manager.py` | Yes |
| `scripts/communication/onboard_receiver.py` | `scripts/communication/onboard_receiver.py` | Yes |
| `scripts/communication/offshore_publisher.py` | `scripts/communication/offshore_publisher.py` | No (Laptop-1 only) |
| `scripts/communication/communication_config.laptop2.yaml` | `scripts/communication/communication_config.laptop2.yaml` | Yes |
| `scripts/communication/communication_config.yaml` | `scripts/communication/communication_config.yaml` | Yes (default config) |
| `dashboard/` | `dashboard/` (full folder) | Yes |
| `start_himdrushti_onboard.bat` | `start_himdrushti_onboard.bat` | Yes |

**Do NOT copy:**
- Training datasets or reports
- Phase 3G/4/5 scripts (those run on Laptop-1 only)
- Jupyter notebooks
- `run_offshore_publish.py` (Laptop-1 only)

---

## What the Dashboard Does NOT Do

- ❌ Forecast iceberg trajectories (Phase 3G does that)
- ❌ Calculate risk (Phase 4 does that)
- ❌ Optimize routes (Phase 5 does that)
- ❌ Fabricate observations during communication loss
- ❌ Show generic "AI Prediction" — always shows the explicit method name
- ❌ Display unsupported fields (Sea-Ice confidence, Visibility, Wave Height, etc.)
- ❌ Modify any Phase 1/2/3/3C/3G/4/5/6 files
