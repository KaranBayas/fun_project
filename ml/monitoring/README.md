# AI Security Monitoring — Offline Anomaly Detection Training Pipeline

> [!WARNING]
> **DEMONSTRATION DATA NOTICE**: All datasets generated and models trained by this pipeline use **synthetic demonstration data** generated purely for testing and proof-of-concept development. They do NOT contain real user activity, production telemetry, or private data.

## Overview

This directory contains the standalone offline training pipeline for the AI Security Monitoring anomaly detection model (`IsolationForest`). The pipeline generates synthetic user activity feature vectors and trains a scikit-learn model to identify statistical anomalies in single-activity events.

## Features (13 Numerical Features)

The model is trained on feature vectors of length 13, extracted strictly in the following order:

1. `authentication_failed` (0/1): Binary indicator if login authentication failed.
2. `permission_denied` (0/1): Binary indicator if action was denied due to permissions.
3. `highly_confidential` (0/1): Binary indicator if document sensitivity is HIGHLY_CONFIDENTIAL.
4. `confidential` (0/1): Binary indicator if document sensitivity is CONFIDENTIAL.
5. `is_delete` (0/1): Binary indicator for DELETE action.
6. `is_download` (0/1): Binary indicator for DOWNLOAD action.
7. `is_share` (0/1): Binary indicator for SHARE action.
8. `is_write` (0/1): Binary indicator for WRITE/EDIT action.
9. `is_face_verification` (0/1): Binary indicator for FACE_VERIFICATION activity type.
10. `is_document_access` (0/1): Binary indicator for DOCUMENT_ACCESS activity type.
11. `is_case_access` (0/1): Binary indicator for CASE_ACCESS activity type.
12. `has_source_ip` (0/1): Binary indicator if source IP address is present.
13. `has_user_agent` (0/1): Binary indicator if user agent header is present.

## Running the Pipeline

### 1. Generate Synthetic Dataset

```bash
python ml/monitoring/generate_demo_dataset.py
```

This generates `ml/monitoring/demo_training_data.csv` containing 1,000 synthetic activity rows (~95% typical user activities, ~5% synthetic suspicious/anomalous patterns).

### 2. Train Anomaly Model

```bash
python ml/monitoring/train_anomaly_model.py
```

This reads `demo_training_data.csv`, trains `scikit-learn`'s `IsolationForest(n_estimators=200, contamination="auto", random_state=42)`, and produces binary model artifacts in `ml/monitoring/artifacts/`.

## Generated Artifacts

- `ml/monitoring/artifacts/monitoring_isolation_forest.joblib`: Trained IsolationForest model binary.
- `ml/monitoring/artifacts/model_metadata.json`: Model metadata including version, algorithm, feature list, training timestamps, sample counts, and synthetic data label.

## Integration & Scope

This offline pipeline is completely decoupled from the runtime FastAPI application service. In Task 7B, the generated model artifact will be integrated into `app/services/monitoring/anomaly_detector.py` for lightweight runtime inference.
