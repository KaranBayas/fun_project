#!/usr/bin/env python3
"""==============================================================================
SYNTHETIC DEMONSTRATION DATA — NOT REAL USER ACTIVITY
==============================================================================
This script generates a synthetic demonstration dataset for offline training of
the AI Security Monitoring anomaly detection model for the SIH 2026 project.

Notice: No real user activity, personal data, IP addresses, credentials, or document
contents are collected or processed.
==============================================================================
"""

from __future__ import annotations

from pathlib import Path
import numpy as np

# Exact 13 numerical feature columns in required order
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


def generate_synthetic_dataset(
    num_samples: int = 1000, random_seed: int = 42
) -> np.ndarray:
    """Generate a synthetic matrix of 13 security-context feature vectors."""
    np.random.seed(random_seed)

    num_normal = int(num_samples * 0.85)
    num_anomalous = num_samples - num_normal

    # --- Normal Security Activities (85%) ---
    normal_data = np.zeros((num_normal, len(FEATURE_COLUMNS)), dtype=np.float64)
    # authentication_failed = 0 (rarely 0.02)
    normal_data[:, 0] = np.random.choice([0.0, 1.0], size=num_normal, p=[0.98, 0.02])
    # permission_denied = 0 (rarely 0.03)
    normal_data[:, 1] = np.random.choice([0.0, 1.0], size=num_normal, p=[0.97, 0.03])
    # highly_confidential = 0.1
    normal_data[:, 2] = np.random.choice([0.0, 1.0], size=num_normal, p=[0.90, 0.10])
    # confidential = 0.25
    normal_data[:, 3] = np.random.choice([0.0, 1.0], size=num_normal, p=[0.75, 0.25])
    # is_delete = 0.03
    normal_data[:, 4] = np.random.choice([0.0, 1.0], size=num_normal, p=[0.97, 0.03])
    # is_download = 0.25
    normal_data[:, 5] = np.random.choice([0.0, 1.0], size=num_normal, p=[0.75, 0.25])
    # is_share = 0.05
    normal_data[:, 6] = np.random.choice([0.0, 1.0], size=num_normal, p=[0.95, 0.05])
    # is_write = 0.20
    normal_data[:, 7] = np.random.choice([0.0, 1.0], size=num_normal, p=[0.80, 0.20])
    # is_face_verification = 0.05
    normal_data[:, 8] = np.random.choice([0.0, 1.0], size=num_normal, p=[0.95, 0.05])
    # is_document_access = 0.60
    normal_data[:, 9] = np.random.choice([0.0, 1.0], size=num_normal, p=[0.40, 0.60])
    # is_case_access = 0.35
    normal_data[:, 10] = np.random.choice([0.0, 1.0], size=num_normal, p=[0.65, 0.35])
    # has_source_ip = 1.0
    normal_data[:, 11] = 1.0
    # has_user_agent = 1.0
    normal_data[:, 12] = 1.0

    # --- Anomalous / Suspicious Security Activities (15%) ---
    anomalous_data = np.zeros((num_anomalous, len(FEATURE_COLUMNS)), dtype=np.float64)
    # authentication_failed = 0.50
    anomalous_data[:, 0] = np.random.choice([0.0, 1.0], size=num_anomalous, p=[0.50, 0.50])
    # permission_denied = 0.65
    anomalous_data[:, 1] = np.random.choice([0.0, 1.0], size=num_anomalous, p=[0.35, 0.65])
    # highly_confidential = 0.55
    anomalous_data[:, 2] = np.random.choice([0.0, 1.0], size=num_anomalous, p=[0.45, 0.55])
    # confidential = 0.35
    anomalous_data[:, 3] = np.random.choice([0.0, 1.0], size=num_anomalous, p=[0.65, 0.35])
    # is_delete = 0.40
    anomalous_data[:, 4] = np.random.choice([0.0, 1.0], size=num_anomalous, p=[0.60, 0.40])
    # is_download = 0.50
    anomalous_data[:, 5] = np.random.choice([0.0, 1.0], size=num_anomalous, p=[0.50, 0.50])
    # is_share = 0.35
    anomalous_data[:, 6] = np.random.choice([0.0, 1.0], size=num_anomalous, p=[0.65, 0.35])
    # is_write = 0.15
    anomalous_data[:, 7] = np.random.choice([0.0, 1.0], size=num_anomalous, p=[0.85, 0.15])
    # is_face_verification = 0.25
    anomalous_data[:, 8] = np.random.choice([0.0, 1.0], size=num_anomalous, p=[0.75, 0.25])
    # is_document_access = 0.40
    anomalous_data[:, 9] = np.random.choice([0.0, 1.0], size=num_anomalous, p=[0.60, 0.40])
    # is_case_access = 0.20
    anomalous_data[:, 10] = np.random.choice([0.0, 1.0], size=num_anomalous, p=[0.80, 0.20])
    # has_source_ip = 0.70
    anomalous_data[:, 11] = np.random.choice([0.0, 1.0], size=num_anomalous, p=[0.30, 0.70])
    # has_user_agent = 0.70
    anomalous_data[:, 12] = np.random.choice([0.0, 1.0], size=num_anomalous, p=[0.30, 0.70])

    data = np.vstack([normal_data, anomalous_data])
    np.random.shuffle(data)
    return data


def save_dataset_to_csv(data: np.ndarray, output_path: Path) -> Path:
    """Save feature array to CSV file with standard header."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    header_line = ",".join(FEATURE_COLUMNS)
    np.savetxt(
        output_path,
        data,
        delimiter=",",
        header=header_line,
        comments="",
        fmt="%.1f",
    )
    return output_path


def main() -> None:
    base_dir = Path(__file__).resolve().parent
    output_path = base_dir / "demo_training_data.csv"
    print("Generating synthetic demonstration dataset...")
    data = generate_synthetic_dataset(num_samples=1000, random_seed=42)
    save_dataset_to_csv(data, output_path)
    print(f"Saved synthetic dataset with {len(data)} rows to {output_path}")


if __name__ == "__main__":
    main()
