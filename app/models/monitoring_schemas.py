from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Task 1 Schemas & Taxonomies
# ---------------------------------------------------------------------------

class SecurityEventType(str, Enum):
    AUTH_LOGIN = "AUTH_LOGIN"
    AUTH_FAILURE = "AUTH_FAILURE"
    DOCUMENT_VIEW = "DOCUMENT_VIEW"
    DOCUMENT_DOWNLOAD = "DOCUMENT_DOWNLOAD"
    DOCUMENT_UPLOAD = "DOCUMENT_UPLOAD"
    DOCUMENT_UPDATE = "DOCUMENT_UPDATE"
    DOCUMENT_DELETE = "DOCUMENT_DELETE"
    CASE_ACCESS = "CASE_ACCESS"
    UNAUTHORIZED_ACCESS = "UNAUTHORIZED_ACCESS"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    FACE_VERIFICATION = "FACE_VERIFICATION"
    SEARCH_REQUEST = "SEARCH_REQUEST"


class SecuritySeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class SecurityEventRequest(BaseModel):
    event_id: Optional[str] = None
    timestamp: Optional[datetime] = None
    user_id: Optional[str] = None
    case_id: Optional[str] = None
    document_id: Optional[str] = None
    event_type: SecurityEventType
    action: Optional[str] = None
    source_ip: Optional[str] = None
    user_agent: Optional[str] = None
    success: bool = True
    severity: Optional[SecuritySeverity] = SecuritySeverity.LOW
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def populate_defaults(self) -> SecurityEventRequest:
        if not self.event_id or not self.event_id.strip():
            self.event_id = str(uuid.uuid4())
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc)
        return self


class SecurityEventResponse(BaseModel):
    success: bool = True
    message: str = "Security event received"
    event_id: str


# ---------------------------------------------------------------------------
# Task 2 & Task 3 & Task 6 Schemas, Taxonomies & Enums
# ---------------------------------------------------------------------------

class ActivityType(str, Enum):
    LOGIN = "LOGIN"
    DOCUMENT_ACCESS = "DOCUMENT_ACCESS"
    DOCUMENT_VIEW = "DOCUMENT_VIEW"
    DOCUMENT_DOWNLOAD = "DOCUMENT_DOWNLOAD"
    DOCUMENT_UPLOAD = "DOCUMENT_UPLOAD"
    DOCUMENT_UPDATE = "DOCUMENT_UPDATE"
    DOCUMENT_DELETE = "DOCUMENT_DELETE"
    CASE_ACCESS = "CASE_ACCESS"
    SEARCH = "SEARCH"
    FACE_VERIFICATION = "FACE_VERIFICATION"
    PERMISSION_CHECK = "PERMISSION_CHECK"


class AuthenticationStatus(str, Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class PermissionStatus(str, Enum):
    ALLOWED = "ALLOWED"
    DENIED = "DENIED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class DocumentSensitivity(str, Enum):
    PUBLIC = "PUBLIC"
    INTERNAL = "INTERNAL"
    CONFIDENTIAL = "CONFIDENTIAL"
    HIGHLY_CONFIDENTIAL = "HIGHLY_CONFIDENTIAL"


class AccessType(str, Enum):
    READ = "READ"
    WRITE = "WRITE"
    DOWNLOAD = "DOWNLOAD"
    DELETE = "DELETE"
    SHARE = "SHARE"


class ThreatType(str, Enum):
    NORMAL_ACTIVITY = "NORMAL_ACTIVITY"
    AUTHENTICATION_FAILURE = "AUTHENTICATION_FAILURE"
    UNAUTHORIZED_ACCESS = "UNAUTHORIZED_ACCESS"
    SUSPICIOUS_DOCUMENT_ACCESS = "SUSPICIOUS_DOCUMENT_ACCESS"
    SENSITIVE_DOCUMENT_ACTION = "SENSITIVE_DOCUMENT_ACTION"
    PERMISSION_VIOLATION = "PERMISSION_VIOLATION"
    SUSPICIOUS_DELETE = "SUSPICIOUS_DELETE"
    SUSPICIOUS_DOWNLOAD = "SUSPICIOUS_DOWNLOAD"
    FACE_VERIFICATION_FAILURE = "FACE_VERIFICATION_FAILURE"
    POSSIBLE_SECURITY_INCIDENT = "POSSIBLE_SECURITY_INCIDENT"


class RecommendedAction(str, Enum):
    ALLOW = "ALLOW"
    MONITOR = "MONITOR"
    REVIEW = "REVIEW"
    TRIGGER_ALERT = "TRIGGER_ALERT"
    BLOCK_AND_ALERT = "BLOCK_AND_ALERT"


class CurrentActivityRequest(BaseModel):
    user_id: Optional[str] = None
    case_id: Optional[str] = None
    document_id: Optional[str] = None
    activity_type: ActivityType
    action: Optional[str] = None
    timestamp: Optional[datetime] = None
    source_ip: Optional[str] = None
    user_agent: Optional[str] = None
    authentication_status: AuthenticationStatus = AuthenticationStatus.NOT_APPLICABLE
    permission_status: PermissionStatus = PermissionStatus.NOT_APPLICABLE
    document_sensitivity: DocumentSensitivity = DocumentSensitivity.INTERNAL
    access_type: Optional[AccessType] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("metadata", mode="before")
    @classmethod
    def validate_metadata(cls, v: Any) -> Dict[str, Any]:
        if v is None:
            return {}
        if not isinstance(v, dict):
            raise ValueError("metadata must be a key-value object")
        return v


class RiskReason(BaseModel):
    code: str
    message: str
    severity: SecuritySeverity
    contribution: int


class AnomalyAnalysis(BaseModel):
    available: bool = False
    anomaly_score: float = Field(default=0.0, ge=0.0, le=1.0)
    is_anomalous: bool = False


class RiskAnalysisResponse(BaseModel):
    success: bool = True
    user_id: Optional[str] = None
    risk_score: int = Field(ge=0, le=100)
    risk_level: SecuritySeverity
    suspicious: bool
    threat_type: ThreatType
    confidence: float = Field(ge=0.0, le=1.0)
    reasons: List[RiskReason] = Field(default_factory=list)
    recommended_action: RecommendedAction
    requires_calling_agent: bool
    anomaly: AnomalyAnalysis = Field(default_factory=AnomalyAnalysis)
