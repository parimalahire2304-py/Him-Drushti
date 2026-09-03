# Demo Guide

## Overview

This document describes how to demonstrate the Prototype-1 project architecture. Phase 0 establishes the project foundation — there is no operational functionality to demo yet.

## Current Demo Capabilities (Phase 0)

### 1. Project Structure Verification

Demonstrate the clean, scalable project architecture:

```bash
# Show directory tree
find . -not -path './.git/*' -not -path './.git' | sort
```

### 2. Configuration Validation

Demonstrate that all configuration files load correctly:

```bash
python -c "
import yaml
config_files = [
    'config/region.yaml',
    'config/datasets.yaml',
    'config/models.yaml',
    'config/routing.yaml',
    'config/vessel.yaml',
    'config/mqtt.yaml'
]
for f in config_files:
    with open(f) as fp:
        data = yaml.safe_load(fp)
    print(f'✓ {f} — loaded successfully')
print('All configuration files validated.')
"
```

### 3. Bounding Box Verification

Show the Prototype-1 operational region:

```bash
python -c "
import yaml
with open('config/region.yaml') as f:
    region = yaml.safe_load(f)
bb = region['bounding_box']
print(f'Region: {region[\"region_name\"]}')
print(f'Bounding box: {bb[\"south\"]}° to {bb[\"north\"]}° S, {bb[\"west\"]}° to {bb[\"east\"]}° E')
print(f'CRS: {region[\"coordinate_reference_system\"]}')
"
```

### 4. Routing Weights Verification

Show the multi-objective configuration:

```bash
python -c "
import yaml
with open('config/routing.yaml') as f:
    routing = yaml.safe_load(f)
objectives = routing['routing']['objectives']
print('Routing objective weights (PLACEHOLDER values):')
for name, params in objectives.items():
    print(f'  {name}: {params[\"weight\"]}')
total = sum(p['weight'] for p in objectives.values())
print(f'Total weight: {total}')
"
```

## Future Demo Phases

| Phase | Demo Content |
|-------|-------------|
| Phase 1 | Data ingestion from sample files |
| Phase 2 | Sea-ice forecast visualization |
| Phase 3 | SAR iceberg detection on sample imagery |
| Phase 4 | Iceberg trajectory prediction demo |
| Phase 5 | Uncertainty visualization |
| Phase 6 | Risk map generation |
| Phase 7 | Route optimization demo |
| Phase 8 | MQTT message flow between laptops |
| Phase 9 | Full DSS dashboard demo |
| Phase 10 | End-to-end integration demo |

## Important Notes

- Phase 0 demonstrates architecture and configuration only
- No simulated or fake results should be presented as operational
- All configuration values are placeholders unless explicitly marked otherwise
- The bounding box is for demonstration purposes and is not an operational boundary
