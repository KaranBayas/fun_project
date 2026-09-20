from __future__ import annotations

from pathlib import Path
from typing import Any, List, Optional

from app.models.monitoring_schemas import (
    AccessType,
    ActivityType,
    AnomalyAnalysis,
    AuthenticationStatus,
    CurrentActivityRequest,
    DocumentSensitivity,
    PermissionStatus,
)
from app.utils.logging import get_logger

logger = get_logger(__name__)

FEATURE_NAMES = [
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


def extract_features(activity: CurrentActivityRequest) -> List[float]:
    """Extract deterministic numerical feature vector from current activity payload.

    Note: Identifiers (user_id, document_id, case_id) and raw strings (IP addresses)
    are strictly excluded from numerical encoding.
    """
    is_delete = (
        activity.activity_type == ActivityType.DOCUMENT_DELETE
        or activity.access_type == AccessType.DELETE
        or (activity.action is not None and activity.action.upper() == "DELETE")
    )
    is_download = (
        activity.activity_type == ActivityType.DOCUMENT_DOWNLOAD
        or activity.access_type == AccessType.DOWNLOAD
        or (activity.action is not None and activity.action.upper() == "DOWNLOAD")
    )
    is_share = (
        activity.access_type == AccessType.SHARE
        or (activity.action is not None and activity.action.upper() == "SHARE")
    )
    is_write = (
        activity.access_type == AccessType.WRITE
        or (activity.action is not None and activity.action.upper() == "WRITE")
        or activity.activity_type in (ActivityType.DOCUMENT_UPDATE, ActivityType.DOCUMENT_UPLOAD)
    )

    return [
        1.0 if activity.authentication_status == AuthenticationStatus.FAILED else 0.0,
        1.0 if activity.permission_status == PermissionStatus.DENIED else 0.0,
        1.0 if activity.document_sensitivity == DocumentSensitivity.HIGHLY_CONFIDENTIAL else 0.0,
        1.0 if activity.document_sensitivity == DocumentSensitivity.CONFIDENTIAL else 0.0,
        1.0 if is_delete else 0.0,
        1.0 if is_download else 0.0,
        1.0 if is_share else 0.0,
        1.0 if is_write else 0.0,
        1.0 if activity.activity_type == ActivityType.FACE_VERIFICATION else 0.0,
        1.0 if activity.activity_type in (ActivityType.DOCUMENT_ACCESS, ActivityType.DOCUMENT_VIEW) else 0.0,
        1.0 if activity.activity_type == ActivityType.CASE_ACCESS else 0.0,
        1.0 if (activity.source_ip is None or len(activity.source_ip.strip()) > 0) else 0.0,
        1.0 if (activity.user_agent is None or len(activity.user_agent.strip()) > 0) else 0.0,
    ]


class AnomalyDetector:
    """Lightweight, local ML anomaly detector wrapper.

    Provides safe, lazy loading of fitted IsolationForest or compatible scikit-learn models.
    Fails gracefully to 'available=False' if no trained model is present.
    """

    def __init__(
        self,
        model: Optional[Any] = None,
        model_path: Optional[Path | str] = None,
    ) -> None:
        self.model = model
        if model_path is not None:
            self.model_path = Path(model_path)
        else:
            try:
                from app.config import get_settings
                self.model_path = get_settings().anomaly_model_path
            except Exception:
                repo_root = Path(__file__).resolve().parents[3]
                self.model_path = repo_root / "ml" / "monitoring" / "artifacts" / "monitoring_isolation_forest.joblib"

        if self.model is None and self.model_path and self.model_path.exists():
            self._load_model_from_disk()

    def _load_model_from_disk(self) -> None:
        if not self.model_path or not self.model_path.exists():
            self.model = None
            return
        try:
            import joblib
            self.model = joblib.load(self.model_path)
            logger.info("Successfully loaded anomaly detection model from %s", self.model_path)
        except Exception as exc:
            logger.warning("Could not load anomaly model from %s: %s", self.model_path, exc)
            self.model = None

    def detect_anomaly(self, activity: CurrentActivityRequest) -> AnomalyAnalysis:
        if self.model is None and self.model_path and self.model_path.exists():
            self._load_model_from_disk()

        if self.model is None:
            return AnomalyAnalysis(available=False, anomaly_score=0.0, is_anomalous=False)

        try:
            features = extract_features(activity)
            X = [features]

            predictions = self.model.predict(X)
            is_outlier = bool(predictions[0] == -1)

            if hasattr(self.model, "decision_function"):
                dec = float(self.model.decision_function(X)[0])
                # decision_function > 0 indicates normal/inlier, < 0 indicates anomaly/outlier.
                # Standard decision range for IsolationForest is roughly [-0.25, +0.15].
                # We map decision to anomaly_score in [0.0, 1.0] where decision=0 maps to 0.5:
                if dec > 0:
                    score = 0.5 * (1.0 - min(1.0, dec / 0.15))
                else:
                    score = 0.5 + 0.5 * min(1.0, abs(dec) / 0.25)
            else:
                raw_scores = self.model.score_samples(X)
                raw_score = float(raw_scores[0])
                score = 0.5 - raw_score

            anomaly_score = max(0.0, min(1.0, round(score, 2)))
            is_anomalous = bool(is_outlier and anomaly_score >= 0.70)

            return AnomalyAnalysis(
                available=True,
                anomaly_score=anomaly_score,
                is_anomalous=is_anomalous,
            )
        except Exception as exc:
            logger.warning("Error evaluating anomaly detection model: %s", exc)
            return AnomalyAnalysis(available=False, anomaly_score=0.0, is_anomalous=False)
