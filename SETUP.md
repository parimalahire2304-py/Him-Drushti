# Setup Guide

## Prerequisites

- Python 3.10 or later
- pip (Python package manager)
- Git

## Environment Setup

### 1. Clone the repository

```bash
git clone <repository-url>
cd Him-Drushti
```

### 2. Create a virtual environment

```bash
python -m venv .venv
```

Activate the virtual environment:

**Linux/macOS:**
```bash
source .venv/bin/activate
```

**Windows (PowerShell):**
```powershell
.venv\Scripts\Activate.ps1
```

**Windows (Git Bash):**
```bash
source .venv/Scripts/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` and fill in any required values (none required for Phase 0).

### 5. Verify installation

```bash
python -c "import yaml; print('PyYAML version:', yaml.__version__)"
```

## Project Structure

After setup, the project directory should contain:

```
Him-Drushti/
├── config/                  # YAML configuration files
├── src/                     # Source code (empty modules for Phase 0)
├── data/                    # Data directories
├── models_artifacts/        # Model artifacts (empty for Phase 0)
├── outputs/                 # Generated outputs (empty for Phase 0)
├── scripts/                 # Utility scripts (empty for Phase 0)
├── scenarios/               # Test scenarios (empty for Phase 0)
├── tests/                   # Test suite (empty for Phase 0)
├── .env.example             # Environment variable template
├── .gitignore               # Git ignore rules
├── requirements.txt         # Python dependencies
├── README.md                # Project overview
├── ARCHITECTURE.md          # System architecture
├── DATASETS.md              # Dataset documentation
├── MODEL_CARD.md            # Model card template
├── LIMITATIONS.md           # Known limitations
├── SETUP.md                 # This file
└── DEMO.md                  # Demo instructions
```

## Configuration

All system configuration lives in `config/` as YAML files. See the respective files for details:

| File | Purpose |
|------|---------|
| `config/region.yaml` | Geographic bounding box and CRS |
| `config/datasets.yaml` | Data source registry |
| `config/models.yaml` | ML model configuration |
| `config/routing.yaml` | Route optimization parameters |
| `config/vessel.yaml` | Vessel parameters |
| `config/mqtt.yaml` | MQTT communication settings |

## Development Workflow

Phase 0 establishes only the project skeleton. For subsequent phases:

1. Create a new branch for the phase
2. Implement the phase-specific functionality
3. Add tests in `tests/`
4. Update documentation as needed
5. Update `LIMITATIONS.md` with any new constraints discovered

## Troubleshooting

### YAML configuration loading

If you encounter YAML parsing errors, ensure PyYAML is installed:

```bash
pip install pyyaml
```

### Virtual environment issues

If the virtual environment fails to activate, try recreating it:

```bash
rm -rf .venv
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
```
