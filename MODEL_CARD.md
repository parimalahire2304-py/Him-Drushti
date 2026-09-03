# Model Card Template

## Overview

This document provides a template for documenting ML models used in the Antarctic Sea-Ice, Iceberg Trajectory, and Navigation Decision Support System. Each model should have a completed instance of this template before deployment.

---

## Model: [MODEL NAME]

### Model Details

| Field | Value |
|-------|-------|
| **Model Name** | [e.g. Sea-Ice Forecast Net] |
| **Version** | [e.g. v0.1.0] |
| **Date** | [Training date] |
| **Type** | [e.g. ConvLSTM, U-Net, YOLO, physics-informed NN] |
| **Task** | [e.g. Sea-ice concentration forecasting] |
| **Framework** | [e.g. PyTorch, TensorFlow] |
| **Config File** | [e.g. config/models.yaml → sea_ice_forecasting] |

### Intended Use

- **Primary use case:** [Description of intended application]
- **Intended users:** [e.g. Vessel operators, ice navigators, system operators]
- **Out-of-scope uses:** [What this model should NOT be used for]

### Training Data

| Field | Value |
|-------|-------|
| **Datasets used** | [List of training datasets] |
| **Training period** | [Temporal range of training data] |
| **Spatial coverage** | [Geographic coverage of training data] |
| **Preprocessing** | [Key preprocessing steps] |
| **Data volume** | [Number of samples / volume] |
| **Train/Val/Test split** | [Split strategy and ratios] |

### Model Architecture

- **Architecture summary:** [Brief description]
- **Input shape:** [Expected input tensor shape]
- **Output shape:** [Expected output tensor shape]
- **Parameter count:** [Total trainable parameters]
- **Key hyperparameters:** [List important hyperparameters]

### Training Procedure

- **Loss function:** [Used loss function]
- **Optimizer:** [Optimizer and learning rate schedule]
- **Training duration:** [Epochs, wall-clock time]
- **Hardware:** [GPU/TPU used for training]
- **Reproducibility:** [Random seeds, deterministic settings]

### Evaluation Results

| Metric | Training | Validation | Test |
|--------|----------|------------|------|
| [Metric 1] | [Value] | [Value] | [Value] |
| [Metric 2] | [Value] | [Value] | [Value] |
| [Metric 3] | [Value] | [Value] | [Value] |

**Validation approach:** [e.g. Chronological split, spatial hold-out]

### Limitations and Biases

- [Known limitations of the model]
- [Geographic or temporal biases in training data]
- [Scenarios where model performance degrades]
- [Assumptions made during training]

### Ethical Considerations

- [Safety considerations for navigation decisions]
- [Model predictions must not be treated as ground truth]
- [Human-in-the-loop requirement for operational decisions]

### References

- [Relevant papers or documentation]
- [Dataset documentation references]

---

## Completed Model Cards

No models have been trained yet. Completed model cards will be added as models are developed in future phases.

| Model | Version | Status |
|-------|---------|--------|
| Sea-Ice Forecasting | — | Not implemented |
| Iceberg Detection (SAR) | — | Not implemented |
| Iceberg Trajectory Prediction | — | Not implemented |
| Uncertainty Estimation | — | Not implemented |
