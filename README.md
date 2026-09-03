# AI-Enabled Antarctic Sea-Ice, Iceberg Trajectory, and Navigation Decision Support System

## Smart India Hackathon — Prototype-1

### Project Objective

This project develops an AI-enabled decision support system (DSS) for safe vessel navigation in Antarctic waters. The system integrates multi-source polar data — satellite imagery, ocean reanalysis, atmospheric forcing, and bathymetry — to provide:

- Sea-ice forecasting
- SAR-based iceberg detection
- Iceberg trajectory prediction with uncertainty quantification
- Probabilistic iceberg risk assessment
- Vessel-aware multi-objective route optimization
- A resilient onboard decision support display

### Prototype-1 Scope

Prototype-1 establishes the **project architecture, configuration foundation, and documentation** for the full system. It does **not** implement any datasets, ML models, or operational functionality.

The operational region for Prototype-1 is **East Prydz Bay, East Antarctica**, defined by a configurable bounding box:

| Parameter | Value |
|-----------|-------|
| South | -70.0° |
| North | -66.0° |
| West | 72.0° |
| East | 80.0° |

This bounding box is for demonstration purposes only and is **not** an official geographic or operational boundary.

### Two-Laptop Architecture

The system is designed around two logical computing nodes:

**Laptop 1 — Offshore AI Server**
- Data ingestion and preprocessing
- AI/ML model inference (sea-ice forecasting, iceberg detection, trajectory prediction)
- Uncertainty estimation
- Probabilistic risk calculation
- Vessel-aware route optimization
- MQTT message publishing

**Laptop 2 — Onboard Ship DSS**
- Receives server state via MQTT
- Validates incoming data and maintains last trusted state
- Displays operational maps, sea-ice, iceberg observations, trajectories, risk, recommended routes, fuel/ETA, alerts, and communication status

### Development Phases

| Phase | Focus | Status |
|-------|-------|--------|
| Phase 0 | Project architecture and configuration foundation | **Current** |
| Phase 1 | Data ingestion and preprocessing pipeline | Planned |
| Phase 2 | Sea-ice forecasting model | Planned |
| Phase 3 | SAR-based iceberg detection | Planned |
| Phase 4 | Iceberg trajectory prediction | Planned |
| Phase 5 | Uncertainty estimation | Planned |
| Phase 6 | Probabilistic risk assessment | Planned |
| Phase 7 | Vessel-aware route optimization | Planned |
| Phase 8 | MQTT communication layer | Planned |
| Phase 9 | Onboard Ship DSS dashboard | Planned |
| Phase 10 | Integration, testing, and demonstration | Planned |

### Repository Structure

```
Him-Drushti/
├── config/                  # YAML configuration files
├── src/                     # Source code modules
│   ├── data/                # Data ingestion
│   ├── preprocessing/       # Data preprocessing
│   ├── models/              # ML models
│   ├── uncertainty/         # Uncertainty quantification
│   ├── risk/                # Risk assessment
│   ├── routing/             # Route optimization
│   ├── communication/       # MQTT layer
│   ├── api/                 # API endpoints
│   └── utils/               # Shared utilities
├── data/                    # Data directories
│   ├── raw/                 # Original, unmodified data
│   ├── interim/             # Intermediate processing outputs
│   └── processed/           # Final processed data
├── models_artifacts/        # Trained model artifacts
├── outputs/                 # Generated outputs
├── scripts/                 # Utility scripts
├── scenarios/               # Test/demo scenarios
└── tests/                   # Test suite
```

### Getting Started

See [SETUP.md](SETUP.md) for installation and environment setup instructions.

### Architecture Details

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed system architecture documentation.

### Dataset Documentation

See [DATASETS.md](DATASETS.md) for planned dataset specifications.

### Limitations

See [LIMITATIONS.md](LIMITATIONS.md) for known limitations and constraints.

### License

TBD
