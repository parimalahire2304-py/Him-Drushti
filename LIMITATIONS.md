# Limitations

## Overview

This document records known limitations, constraints, and assumptions for the Antarctic Sea-Ice, Iceberg Trajectory, and Navigation Decision Support System. It should be updated as the system evolves through development phases.

---

## Prototype-1 (Phase 0) Limitations

### Geographic Coverage

- The Prototype-1 operational area is restricted to East Prydz Bay (-70.0° to -66.0° S, 72.0° to 80.0° E)
- This bounding box is a demonstration convenience, not an operational or geographic boundary
- The system has not been tested or validated outside this region
- Performance in other Antarctic regions is unknown

### Dataset Availability

- No datasets have been obtained, downloaded, or verified for availability
- All dataset specifications in `config/datasets.yaml` are placeholders based on commonly used products
- Actual data access may require registration, credentials, or usage agreements
- Data volume, format, and processing requirements are estimates only
- Some datasets may have coverage gaps in the East Prydz Bay region

### Spatial and Temporal Resolution

- Dataset resolutions listed in documentation are typical values for the product class, not verified specifications
- The relationship between data resolution and model output resolution has not been determined
- Downscaling or interpolation requirements are unknown

### Model Uncertainty

- No ML models have been implemented or trained
- Model architectures listed in `config/models.yaml` are candidates, not decisions
- Expected model performance is unknown
- Uncertainty estimation approaches have not been evaluated
- No baseline models have been established for comparison

### SAR Iceberg Detection

- No SAR iceberg detection model exists
- Sentinel-1 data availability and revisit frequency in the East Prydz Bay region have not been verified
- Labeled training data for iceberg segmentation has not been obtained
- Detection performance in varying sea-ice conditions is unknown

### Operational Validation

- The system has not been validated against real-world operational scenarios
- No vessel operators or ice navigators have reviewed the system
- User interface requirements have not been gathered from end users
- Alert thresholds and risk levels have not been calibrated

### Communication Assumptions

- MQTT communication between Laptop 1 and Laptop 2 has not been implemented or tested
- Network reliability assumptions in Antarctic operations have not been characterized
- Bandwidth limitations for real-time data transmission are unknown
- Last trusted state management strategy has not been implemented

### Route Optimization

- Multi-objective weight values in `config/routing.yaml` are placeholders
- No operational constraints have been validated with vessel operators
- Route feasibility has not been assessed against actual vessel capabilities
- Fuel consumption models are simplified placeholders

---

## General System Limitations

### Data Assumptions

- Reanalysis data (ERA5, GLORYS) represents model-based estimates, not direct observations
- Satellite data has inherent revisit limitations and potential coverage gaps
- Bathymetry resolution may be insufficient for nearshore navigation decisions
- Data latency from source providers may impact real-time operational use

### Model Assumptions

- ML models are expected to have degraded performance at the boundaries of their training domain
- Climate change may alter historical patterns that models are trained on
- Extreme events may not be well-represented in training data
- Model transferability to other Antarctic regions has not been assessed

### Operational Assumptions

- The system assumes reliable power and computing hardware on both laptops
- The system does not replace the judgment of trained navigators and ice pilots
- Predictions are advisory only — all navigation decisions remain with vessel command
- The system does not account for international maritime regulations or traffic separation schemes

---

## Version History

| Date | Phase | Changes |
|------|-------|---------|
| [Date] | Phase 0 | Initial limitations document |

---

## Review Checklist

When updating this document in future phases:

- [ ] Are new limitations from the current phase recorded?
- [ ] Are resolved limitations from previous phases marked as addressed?
- [ ] Are assumptions validated or invalidated with evidence?
- [ ] Is the geographic scope of limitations clearly stated?
- [ ] Are operational safety implications noted?
