#!/usr/bin/env python3
"""==============================================================================
OFFLINE ANOMALY DETECTION MODEL TRAINING PIPELINE
==============================================================================
This script trains an IsolationForest anomaly detection model on synthetic
demonstration feature data and saves the model artifact and metadata.

Notice: This is an offline training pipeline. Training occurs separately from
the FastAPI application lifecycle.
==============================================================================
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import IsolationForest

FEATURE_COLUMNS = [
    "authentication_failed",
    "permission_denied",
    "highly_confidential",
    "confidential",
    "is_delete",
    "is_download",
    "is_share",
    "is_write",
    "is_face_verification",
    "is_document_access",
    "is_case_access",
    "has_source_ip",
    "has_user_agent",
]


def load_dataset(csv_path: Path) -> np.ndarray:
    """Load training dataset from CSV."""
    if not csv_path.exists():
        raise FileNotFoundError(f"Training dataset not found at {csv_path}")
    data = np.genfromtxt(csv_path, delimiter=",", skip_header=1)
    if data.ndim == 1:
        data = data.reshape(1, -1)
    if data.shape[1] != len(FEATURE_COLUMNS):
        raise ValueError(
            f"Dataset feature count ({data.shape[1]}) does not match expected ({len(FEATURE_COLUMNS)})"
        )
    return data


def train_isolation_forest(
    X: np.ndarray, n_estimators: int = 200, random_state: int = 42
) -> IsolationForest:
    """Fit scikit-learn IsolationForest on feature matrix X."""
    clf = IsolationForest(
        n_estimators=n_estimators,
        contamination="auto",
        random_state=random_state,
    )
    clf.fit(X)
    return clf


def save_model_artifacts(
    model: IsolationForest,
    output_dir: Path,
    random_state: int = 42,
    version: str = "demo-v1",
) -> tuple[Path, Path]:
    """Save trained IsolationForest model and JSON metadata artifact."""
    output_dir.mkdir(parents=True, exist_ok=True)
    model_path = output_dir / "monitoring_isolation_forest.joblib"
    metadata_path = output_dir / "model_metadata.json"

    joblib.dump(model, model_path)

    metadata = {
        "model_type": "IsolationForest",
        "model_version": version,
        "feature_count": len(FEATURE_COLUMNS),
        "feature_names": FEATURE_COLUMNS,
        "random_state": random_state,
        "training_data_type": "synthetic_demo",
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "warning": "Synthetic demonstration model. Not trained on real user activity.",
    }

    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    return model_path, metadata_path


def main() -> None:
    base_dir = Path(__file__).resolve().parent
    csv_path = base_dir / "demo_training_data.csv"
    artifacts_dir = base_dir / "artifacts"

    print(f"Loading synthetic dataset from {csv_path}...")
    X = load_dataset(csv_path)

    print(f"Training IsolationForest model on {len(X)} samples...")
    model = train_isolation_forest(X, n_estimators=200, random_state=42)

    model_path, metadata_path = save_model_artifacts(
        model, artifacts_dir, random_state=42, version="demo-v1"
    )
    print(f"Model saved to: {model_path}")
    print(f"Metadata saved to: {metadata_path}")


if __name__ == "__main__":
    main()
