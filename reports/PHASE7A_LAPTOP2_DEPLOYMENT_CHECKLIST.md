# PHASE 7A — LAPTOP-2 (SHIP / ONBOARD DSS) DEPLOYMENT CHECKLIST

Two-laptop MQTT deployment. Laptop-1 = **OFFSHORE AI SERVER** (runs Mosquitto
broker + Phase 3G→4→5 pipeline + publisher). Laptop-2 = **SHIP/ONBOARD DSS**
(runs the MQTT subscriber / onboard receiver only — no datasets, no ML models).

---

## 0. Broker enablement on Laptop-1 (ONCE, admin)

1. On **Laptop-1**, open an **elevated** PowerShell (Run as administrator).
2. Run the enablement script (appends `listener 1883` / `bind_address 0.0.0.0`
   to mosquitto.conf, restarts Mosquitto, adds a firewall inbound rule for
   TCP 1883 on the local subnet):
   ```
   powershell -ExecutionPolicy Bypass -File "C:\Users\parim\OneDrive\Desktop\Him-Drushti\scripts\communication\phase7a_enable_broker.ps1"
   ```
3. Verify the broker now listens on the LAN address (not just loopback):
   ```
   netstat -ano | findstr :1883
   ```
   Expected: a line showing the LAN IP (or `0.0.0.0`) `:1883  LISTENING`.

---

## 1. Files to copy to Laptop-2

Create a folder on Laptop-2, e.g. `C:\HimDrushti\communication\`, and copy
these **5 files** from Laptop-1's `scripts\communication\`:

| File | Purpose |
|------|---------|
| `communication_config.laptop2.yaml` | Laptop-2 deployment config (broker host = Laptop-1 LAN IP) |
| `run_ship_receiver.py` | Laptop-2 subscriber entry point |
| `onboard_receiver.py` | Phase 6 receiver / state manager (imports the 3 below) |
| `state_manager.py` | Communication state machine |
| `schemas.py` | Message schemas + validation |
| `transport.py` | MQTT transport abstraction (PahoTransport) |

> **Only these 6 files are needed on Laptop-2.** The publisher, the Phase 3G
> ML models, datasets, `forecast.py`, `risk_engine.py`, and `route_optimizer.py`
> stay on Laptop-1 — MQTT is transport only.

## 2. Python dependency on Laptop-2

Laptop-2 already has Python 3.13.14 and pip 26.1.2. Install **2** packages:

```
pip install paho-mqtt==2.1.0 pyyaml
```

(Verify: `pip show paho-mqtt` → version 2.1.0)

## 3. Broker address (Laptop-1)

- **Host:** `10.20.231.143`  ← Laptop-1's active Wi-Fi IPv4 (from `ipconfig`; **not guessed**)
- **Port:** `1883` (MQTT default)
- This is already set in `communication_config.laptop2.yaml` → `broker.host`.
- If Laptop-1's Wi-Fi IP changes, update that one value in the config.

> ⚠️ Laptop-1 and Laptop-2 must be on the **same network** (same Wi-Fi / the
> Laptop-1 hotspot). If using a hotspot, the broker IP is the hotspot host's IP.

## 4. Topics & QoS (identical to Phase 6)

| Topic | QoS |
|-------|-----|
| `himdrushti/observation` | 1 |
| `himdrushti/forecast` | 1 |
| `himdrushti/risk` | 1 |
| `himdrushti/route` | 1 |
| `himdrushti/status` | 0 |
| `himdrushti/replan` | 1 |

## 5. Start sequence (two machines)

**Step A — start the subscriber on Laptop-2 (FIRST, so it's already listening):**
```
cd C:\HimDrushti\communication
python run_ship_receiver.py
```
It prints `Connected: True` and waits for messages (default 60 s; add
`--timeout 0` to listen forever until Ctrl+C).

**Step B — publish from Laptop-1 (SECOND):**
```
cd C:\Users\parim\OneDrive\Desktop\Him-Drushti
python scripts\communication\run_offshore_publish.py
```
This runs the real Phase 3G→4→5 pipeline for a **synthetic** observation and
publishes observation / forecast / risk / route / status to the broker.

**Step C — observe on Laptop-2:** the subscriber prints each received message,
its topic, the communication-state transition (FRESH→…), and the final onboard
state summary. A FRESH forecast with `forecast_method` = `MOTION_AWARE_XGBOOST`
(or `PERSISTENCE_FALLBACK`) confirms end-to-end delivery and schema validity.

## 6. Single-machine reproducible test (pre-check, on Laptop-1)

Before the true two-machine run, verify the whole chain works against the LAN
broker address (subscriber connects over `10.20.231.143`, not localhost):
```
python scripts\communication\run_phase7a_test.py
```
This starts the validator, then runs the publisher, then reports 9 checks.
Expect `9/9 PASS`.

## 7. Validation (9 required checks)

`validate_phase7a.py` verifies:
1. Laptop-1 publishes via the real broker
2. Subscriber connects to Laptop-1 broker over the LAN
3. Subscribes to `himdrushti/*` topics
4. Receives real MQTT messages
5. Messages pass Phase 6 schema validation
6. `forecast_method` is explicit (`MOTION_AWARE_XGBOOST` / `PERSISTENCE_FALLBACK`)
7. State manager updates to the latest valid state
8. No fabricated observations created by the receiver
9. Phase 6 localhost regression config untouched

## 8. Notes / safety

- **No fabricated data as real:** every published observation is explicitly
  synthetic (client `DEMO-A`, `synthetic_label`/`demo_note` set). The receiver
  never creates a new observation.
- The Phase 6 **localhost** regression config (`communication_config.yaml`) is
  untouched; Laptop-2 uses the separate `communication_config.laptop2.yaml`.
- No AI forecasting/risk/routing runs on Laptop-2 — it only receives and
  displays. This is not a dashboard and not Phase 7B.
