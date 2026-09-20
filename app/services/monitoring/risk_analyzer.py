from __future__ import annotations

from typing import List, Optional

from app.models.monitoring_schemas import (
    AccessType,
    ActivityType,
    AnomalyAnalysis,
    AuthenticationStatus,
    CurrentActivityRequest,
    DocumentSensitivity,
    PermissionStatus,
    RecommendedAction,
    RiskAnalysisResponse,
    RiskReason,
    SecuritySeverity,
    ThreatType,
)
from app.services.monitoring.anomaly_detector import AnomalyDetector

# Configurable score threshold bounds
LOW_THRESHOLD_MAX = 24
MEDIUM_THRESHOLD_MAX = 49
HIGH_THRESHOLD_MAX = 74


class RiskAnalyzer:
    """Domain-specific rule-based risk analysis engine for assessing single current user activity."""

    def __init__(self, anomaly_detector: Optional[AnomalyDetector] = None) -> None:
        self.anomaly_detector = anomaly_detector or AnomalyDetector()

    def calculate_authentication_risk(self, activity: CurrentActivityRequest) -> List[RiskReason]:
        reasons: List[RiskReason] = []
        if activity.authentication_status == AuthenticationStatus.FAILED:
            if activity.activity_type == ActivityType.FACE_VERIFICATION:
                reasons.append(
                    RiskReason(
                        code="FACE_VERIFICATION_FAILED",
                        message="Facial biometric verification failed.",
                        severity=SecuritySeverity.HIGH,
                        contribution=45,
                    )
                )
            else:
                reasons.append(
                    RiskReason(
                        code="AUTHENTICATION_FAILED",
                        message="User authentication failed for the attempted action.",
                        severity=SecuritySeverity.HIGH,
                        contribution=40,
                    )
                )
        return reasons

    def calculate_permission_risk(self, activity: CurrentActivityRequest) -> List[RiskReason]:
        reasons: List[RiskReason] = []
        if activity.permission_status == PermissionStatus.DENIED:
            reasons.append(
                RiskReason(
                    code="PERMISSION_DENIED",
                    message="Attempted access was denied by the authorization layer.",
                    severity=SecuritySeverity.HIGH,
                    contribution=30,
                )
            )
        return reasons

    def calculate_document_sensitivity_risk(self, activity: CurrentActivityRequest) -> List[RiskReason]:
        reasons: List[RiskReason] = []
        if activity.document_sensitivity == DocumentSensitivity.HIGHLY_CONFIDENTIAL:
            reasons.append(
                RiskReason(
                    code="HIGH_SENSITIVITY",
                    message="Activity targets a highly confidential document.",
                    severity=SecuritySeverity.HIGH,
                    contribution=20,
                )
            )
        elif activity.document_sensitivity == DocumentSensitivity.CONFIDENTIAL:
            reasons.append(
                RiskReason(
                    code="MEDIUM_HIGH_SENSITIVITY",
                    message="Activity targets a confidential document.",
                    severity=SecuritySeverity.MEDIUM,
                    contribution=10,
                )
            )
        return reasons

    def calculate_action_risk(self, activity: CurrentActivityRequest) -> List[RiskReason]:
        reasons: List[RiskReason] = []
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

        if is_delete:
            if activity.document_sensitivity == DocumentSensitivity.HIGHLY_CONFIDENTIAL:
                reasons.append(
                    RiskReason(
                        code="DELETE_HIGHLY_CONFIDENTIAL",
                        message="Attempted DELETE operation on a highly confidential document.",
                        severity=SecuritySeverity.CRITICAL,
                        contribution=30,
                    )
                )
            elif activity.document_sensitivity == DocumentSensitivity.CONFIDENTIAL:
                reasons.append(
                    RiskReason(
                        code="DELETE_CONFIDENTIAL",
                        message="Attempted DELETE operation on a confidential document.",
                        severity=SecuritySeverity.HIGH,
                        contribution=20,
                    )
                )
            else:
                reasons.append(
                    RiskReason(
                        code="DOCUMENT_DELETION_ATTEMPT",
                        message="Document deletion action performed.",
                        severity=SecuritySeverity.MEDIUM,
                        contribution=15,
                    )
                )

        if is_download:
            if activity.document_sensitivity == DocumentSensitivity.HIGHLY_CONFIDENTIAL:
                reasons.append(
                    RiskReason(
                        code="DOWNLOAD_HIGHLY_CONFIDENTIAL",
                        message="Attempted download of a highly confidential document.",
                        severity=SecuritySeverity.HIGH,
                        contribution=25,
                    )
                )
            elif activity.document_sensitivity == DocumentSensitivity.CONFIDENTIAL:
                reasons.append(
                    RiskReason(
                        code="DOWNLOAD_CONFIDENTIAL",
                        message="Attempted download of a confidential document.",
                        severity=SecuritySeverity.MEDIUM,
                        contribution=15,
                    )
                )

        if is_share and activity.document_sensitivity in (
            DocumentSensitivity.CONFIDENTIAL,
            DocumentSensitivity.HIGHLY_CONFIDENTIAL,
        ):
            reasons.append(
                RiskReason(
                    code="SHARE_SENSITIVE_DOCUMENT",
                    message="Attempt to share a sensitive document.",
                    severity=SecuritySeverity.HIGH,
                    contribution=25,
                )
            )

        return reasons

    def calculate_access_risk(self, activity: CurrentActivityRequest) -> List[RiskReason]:
        reasons: List[RiskReason] = []
        is_denied = activity.permission_status == PermissionStatus.DENIED
        is_failed_auth = activity.authentication_status == AuthenticationStatus.FAILED
        is_sensitive = activity.document_sensitivity in (
            DocumentSensitivity.CONFIDENTIAL,
            DocumentSensitivity.HIGHLY_CONFIDENTIAL,
        )
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

        if is_denied and is_sensitive:
            reasons.append(
                RiskReason(
                    code="UNAUTHORIZED_SENSITIVE_ACCESS",
                    message="Unauthorized access attempt on a sensitive document.",
                    severity=SecuritySeverity.HIGH,
                    contribution=20,
                )
            )

        if is_denied and is_delete:
            reasons.append(
                RiskReason(
                    code="UNAUTHORIZED_DELETE_ATTEMPT",
                    message="Unauthorized attempt to delete a document or resource.",
                    severity=SecuritySeverity.CRITICAL,
                    contribution=25,
                )
            )

        if is_failed_auth and is_delete:
            reasons.append(
                RiskReason(
                    code="UNAUTHENTICATED_DELETE_ATTEMPT",
                    message="Unauthenticated attempt to delete a document or resource.",
                    severity=SecuritySeverity.CRITICAL,
                    contribution=25,
                )
            )

        if is_failed_auth and is_download:
            reasons.append(
                RiskReason(
                    code="UNAUTHENTICATED_DOWNLOAD_ATTEMPT",
                    message="Unauthenticated attempt to download a document or resource.",
                    severity=SecuritySeverity.HIGH,
                    contribution=20,
                )
            )

        if is_failed_auth and is_denied:
            reasons.append(
                RiskReason(
                    code="FAILED_AUTH_AND_DENIED",
                    message="Action attempt with failed authentication and denied permissions.",
                    severity=SecuritySeverity.HIGH,
                    contribution=20,
                )
            )

        return reasons

    def analyze(self, activity: CurrentActivityRequest) -> RiskAnalysisResponse:
        reasons: List[RiskReason] = []
        reasons.extend(self.calculate_authentication_risk(activity))
        reasons.extend(self.calculate_permission_risk(activity))
        reasons.extend(self.calculate_document_sensitivity_risk(activity))
        reasons.extend(self.calculate_action_risk(activity))
        reasons.extend(self.calculate_access_risk(activity))

        # Check ML anomaly detector if available
        anomaly_res = (
            self.anomaly_detector.detect_anomaly(activity)
            if self.anomaly_detector
            else AnomalyAnalysis()
        )

        if anomaly_res.available and anomaly_res.is_anomalous:
            reasons.append(
                RiskReason(
                    code="ML_ANOMALY_DETECTED",
                    message="The activity pattern was flagged as anomalous by the local anomaly detector.",
                    severity=SecuritySeverity.MEDIUM,
                    contribution=10,
                )
            )

        raw_score = sum(r.contribution for r in reasons)
        risk_score = max(0, min(100, raw_score))

        # Determine Risk Level based on configurable thresholds
        if risk_score <= LOW_THRESHOLD_MAX:
            risk_level = SecuritySeverity.LOW
        elif risk_score <= MEDIUM_THRESHOLD_MAX:
            risk_level = SecuritySeverity.MEDIUM
        elif risk_score <= HIGH_THRESHOLD_MAX:
            risk_level = SecuritySeverity.HIGH
        else:
            risk_level = SecuritySeverity.CRITICAL

        suspicious = risk_level in (SecuritySeverity.HIGH, SecuritySeverity.CRITICAL)

        # Determine Threat Classification
        threat_type = self._classify_threat(activity, risk_score, risk_level)

        # Determine Recommended Action
        recommended_action = self._determine_action(risk_level, threat_type, risk_score)

        # Determine Calling Agent Requirement
        requires_calling_agent = self._requires_calling_agent(risk_level, threat_type, risk_score, activity)

        # Calculate Confidence based on field completeness
        confidence = self._calculate_confidence(activity)

        return RiskAnalysisResponse(
            success=True,
            user_id=activity.user_id,
            risk_score=risk_score,
            risk_level=risk_level,
            suspicious=suspicious,
            threat_type=threat_type,
            confidence=confidence,
            reasons=reasons,
            recommended_action=recommended_action,
            requires_calling_agent=requires_calling_agent,
            anomaly=anomaly_res,
        )

    def _classify_threat(
        self, activity: CurrentActivityRequest, risk_score: int, risk_level: SecuritySeverity
    ) -> ThreatType:
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
        is_sensitive = activity.document_sensitivity in (
            DocumentSensitivity.CONFIDENTIAL,
            DocumentSensitivity.HIGHLY_CONFIDENTIAL,
        )
        is_failed_auth = activity.authentication_status == AuthenticationStatus.FAILED
        is_denied = activity.permission_status == PermissionStatus.DENIED

        # Priority 1: SUSPICIOUS_DELETE (Delete + denied permission / failed auth / sensitive)
        if is_delete and (is_denied or is_failed_auth or is_sensitive):
            return ThreatType.SUSPICIOUS_DELETE

        # Priority 2: SUSPICIOUS_DOWNLOAD (Download + denied permission / failed auth / highly confidential)
        if is_download and (
            is_denied
            or is_failed_auth
            or activity.document_sensitivity == DocumentSensitivity.HIGHLY_CONFIDENTIAL
        ):
            return ThreatType.SUSPICIOUS_DOWNLOAD

        # Priority 3: FACE_VERIFICATION_FAILURE
        if is_failed_auth and activity.activity_type == ActivityType.FACE_VERIFICATION:
            return ThreatType.FACE_VERIFICATION_FAILURE

        # Priority 4: PERMISSION_VIOLATION / UNAUTHORIZED_ACCESS
        if is_denied and is_sensitive:
            return ThreatType.UNAUTHORIZED_ACCESS

        if is_denied:
            return ThreatType.PERMISSION_VIOLATION

        # Priority 5: AUTHENTICATION_FAILURE
        if is_failed_auth:
            return ThreatType.AUTHENTICATION_FAILURE

        # Priority 6: SENSITIVE_DOCUMENT_ACTION
        if activity.document_sensitivity == DocumentSensitivity.HIGHLY_CONFIDENTIAL:
            return ThreatType.SENSITIVE_DOCUMENT_ACTION

        # Priority 7: CRITICAL/HIGH/MEDIUM SUSPICIOUS ACCESS
        if risk_level == SecuritySeverity.CRITICAL:
            return ThreatType.POSSIBLE_SECURITY_INCIDENT

        if risk_level in (SecuritySeverity.HIGH, SecuritySeverity.MEDIUM):
            return ThreatType.SUSPICIOUS_DOCUMENT_ACCESS

        # Priority 8: NORMAL_ACTIVITY
        return ThreatType.NORMAL_ACTIVITY

    def _determine_action(
        self, risk_level: SecuritySeverity, threat_type: ThreatType, risk_score: int
    ) -> RecommendedAction:
        if risk_level == SecuritySeverity.CRITICAL:
            return RecommendedAction.BLOCK_AND_ALERT
        if risk_level == SecuritySeverity.HIGH:
            if (
                threat_type
                in (
                    ThreatType.SUSPICIOUS_DELETE,
                    ThreatType.SUSPICIOUS_DOWNLOAD,
                    ThreatType.UNAUTHORIZED_ACCESS,
                    ThreatType.AUTHENTICATION_FAILURE,
                    ThreatType.FACE_VERIFICATION_FAILURE,
                )
                or risk_score >= 60
            ):
                return RecommendedAction.TRIGGER_ALERT
            return RecommendedAction.REVIEW
        if risk_level == SecuritySeverity.MEDIUM:
            return RecommendedAction.MONITOR
        return RecommendedAction.ALLOW

    def _requires_calling_agent(
        self,
        risk_level: SecuritySeverity,
        threat_type: ThreatType,
        risk_score: int,
        activity: CurrentActivityRequest,
    ) -> bool:
        if risk_level == SecuritySeverity.CRITICAL:
            return True
        if risk_level == SecuritySeverity.HIGH:
            if (
                risk_score >= 60
                or activity.permission_status == PermissionStatus.DENIED
                or activity.authentication_status == AuthenticationStatus.FAILED
                or activity.document_sensitivity == DocumentSensitivity.HIGHLY_CONFIDENTIAL
                or threat_type
                in (
                    ThreatType.SUSPICIOUS_DELETE,
                    ThreatType.SUSPICIOUS_DOWNLOAD,
                    ThreatType.UNAUTHORIZED_ACCESS,
                    ThreatType.FACE_VERIFICATION_FAILURE,
                )
            ):
                return True
        return False

    def _calculate_confidence(self, activity: CurrentActivityRequest) -> float:
        confidence = 0.70
        if activity.user_id:
            confidence += 0.05
        if activity.activity_type:
            confidence += 0.05
        if activity.authentication_status != AuthenticationStatus.NOT_APPLICABLE:
            confidence += 0.05
        if activity.permission_status != PermissionStatus.NOT_APPLICABLE:
            confidence += 0.05
        if activity.document_sensitivity:
            confidence += 0.05
        if activity.action or activity.access_type:
            confidence += 0.05
        return round(min(1.0, confidence), 2)
