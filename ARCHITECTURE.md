# System Architecture

## Overview

This document describes the planned architecture for the AI-Enabled Antarctic Sea-Ice, Iceberg Trajectory, and Navigation Decision Support System. The architecture is designed for a two-computer operational setup: an offshore AI server (Laptop 1) and an onboard ship DSS (Laptop 2).

## Architecture Layers

The system follows a layered architecture with clear data flow between components:

```
┌─────────────────────────────────────────────────────────┐
│                    DATA SOURCES                         │
│  NSIDC Sea-Ice │ ERA5 │ GLORYS │ GEBCO │ Sentinel-1   │
│  Iceberg Tracks│ Bathymetry │ Vessel GPS               │
└────────────────────────┬────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│                  PROCESSING LAYER                       │
│  Data Ingestion → Preprocessing → Feature Engineering  │
│  (src/data)        (src/preprocessing)                  │
└────────────────────────┬────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│                    AI/ML LAYER                          │
│  Sea-Ice Forecasting → SAR Iceberg Detection            │
│  Iceberg Trajectory Prediction                          │
│  (src/models)                                            │
└────────────────────────┬────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│              UNCERTAINTY / RISK LAYER                   │
│  Uncertainty Estimation → Probabilistic Risk Assessment │
│  (src/uncertainty)         (src/risk)                   │
└────────────────────────┬────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│              ROUTE OPTIMIZATION LAYER                   │
│  Vessel-Aware Multi-Objective Route Optimization        │
│  (src/routing)                                          │
└────────────────────────┬────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│               COMMUNICATION LAYER                       │
│  MQTT Publishing / Subscribing                          │
│  State Serialization / Validation                       │
│  (src/communication)                                    │
└────────────────────────┬────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│                   SHIP DSS LAYER                        │
│  Onboard Display: Maps, Ice, Icebergs, Routes, Risk,  │
│  Alerts, Fuel/ETA, Communication Status                 │
│  Last Trusted State Management                          │
└─────────────────────────────────────────────────────────┘
```

## Computing Nodes

### Laptop 1 — Offshore AI Server

This machine runs the computationally intensive components of the system.

**Responsibilities:**
- Ingest and preprocess multi-source polar data
- Run AI/ML models for sea-ice forecasting, iceberg detection, and trajectory prediction
- Perform uncertainty estimation
- Calculate probabilistic iceberg risk
- Generate vessel-aware optimized routes
- Publish system state via MQTT

**Key modules:**
- `src/data/` — Data ingestion and source management
- `src/preprocessing/` — Data cleaning, regridding, normalization
- `src/models/` — ML model training and inference
- `src/uncertainty/` — Uncertainty quantification
- `src/risk/` — Risk assessment computation
- `src/routing/` — Route optimization
- `src/communication/` — MQTT publishing

### Laptop 2 — Onboard Ship DSS

This machine runs the user-facing decision support interface.

**Responsibilities:**
- Receive server state via MQTT subscription
- Validate incoming data (schema, freshness, consistency)
- Maintain last trusted state when communication is interrupted
- Display operational information on an Antarctic map

**Key modules:**
- `src/communication/` — MQTT subscription and state management
- `src/api/` — Local API for dashboard data access

**Display elements:**
- Antarctic operational map with bounding box overlay
- Sea-ice concentration and extent
- Iceberg observations and predicted trajectories
- Uncertainty fields and risk heatmap
- Recommended routes with waypoints
- Fuel consumption and ETA estimates
- Active alerts (icebergs, sea-ice, weather)
- Communication link status

## Data Flow

### Primary Flow (Normal Operations)

```
New satellite/reanalysis data arrives
    → Ingestion (src/data)
    → Preprocessing (src/preprocessing)
    → Sea-ice forecast model (src/models)
    → Iceberg detection model (src/models)
    → Iceberg trajectory model (src/models)
    → Uncertainty estimation (src/uncertainty)
    → Risk assessment (src/risk)
    → Route optimization (src/routing)
    → State serialization
    → MQTT publish (src/communication)
    → MQTT receive on Laptop 2
    → State validation
    → Dashboard update
```

### Reactive Flow (New Observation)

```
New observation received
    → Update affected models
    → Recalculate risk
    → Re-optimize route if needed
    → Publish updated state
    → Dynamic replanning on DSS
```

## Design Principles

1. **Modularity** — Each layer is an independent module with well-defined interfaces
2. **Configuration-driven** — All parameters externalized in `config/` YAML files
3. **Separation of concerns** — Raw data is never modified; processing stages produce separate outputs
4. **Reproducibility** — Model training must be reproducible with fixed seeds and versioned configs
5. **Graceful degradation** — The DSS must function with last trusted state during communication outages
6. **No premature optimization** — Simple, defensible implementations preferred over unnecessary complexity

## Configuration Architecture

All system parameters are managed through YAML files in `config/`:

| File | Purpose |
|------|---------|
| `region.yaml` | Geographic bounding box and CRS |
| `datasets.yaml` | Data source registry |
| `models.yaml` | ML model configuration |
| `routing.yaml` | Route optimization weights and constraints |
| `vessel.yaml` | Vessel parameters |
| `mqtt.yaml` | Communication broker and topic configuration |

## Future Considerations

- Containerization for deployment on both laptops
- Model versioning and artifact management
- Real-time data streaming pipeline
- Dashboard technology selection (Phase 9)
- Inter-laptop synchronization and failover strategies
