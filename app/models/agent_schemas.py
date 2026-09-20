from __future__ import annotations

import re
from enum import Enum
from typing import Any, List, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from app.models.monitoring_schemas import RecommendedAction, SecuritySeverity

# Phone number regex matching international and local numbers (7 to 20 digits, allows +, space, -, ())
PHONE_REGEX = re.compile(r"^\+?[0-9\s\-()]{7,20}$")


class ChannelStatus(str, Enum):
    SIMULATED = "SIMULATED"
    SENT = "SENT"
    FAILED = "FAILED"
    CONFIGURATION_ERROR = "CONFIGURATION_ERROR"
    NOT_REQUESTED = "NOT_REQUESTED"
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"
    INITIATED = "INITIATED"
    ANSWERED = "ANSWERED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    DISABLED = "DISABLED"


class ChannelResult(BaseModel):
    requested: bool
    status: ChannelStatus
    message: Optional[str] = None


class ChannelsSummary(BaseModel):
    sms: ChannelResult
    email: ChannelResult
    voice_call: ChannelResult


class ReasonPayload(BaseModel):
    code: str
    message: str
    severity: SecuritySeverity


class IncidentPayload(BaseModel):
    incident_id: str
    user_id: str
    case_id: str
    document_id: Optional[str] = None
    risk_score: int = Field(ge=0, le=100)
    risk_level: SecuritySeverity
    suspicious: bool
    threat_type: str
    confidence: float = Field(ge=0.0, le=1.0)
    recommended_action: RecommendedAction
    requires_calling_agent: bool
    reasons: List[ReasonPayload] = Field(min_length=1)

    @field_validator("incident_id", "user_id", "case_id", mode="before")
    @classmethod
    def validate_non_empty_strings(cls, v: Any, info) -> str:
        if v is None or not isinstance(v, str) or not v.strip():
            raise ValueError(f"{info.field_name} must not be empty.")
        return v.strip()


class OfficerPayload(BaseModel):
    officer_id: str
    name: str
    phone: str
    email: EmailStr

    @field_validator("officer_id", "name", mode="before")
    @classmethod
    def validate_non_empty(cls, v: Any, info) -> str:
        if v is None or not isinstance(v, str) or not v.strip():
            raise ValueError(f"{info.field_name} must not be empty.")
        return v.strip()

    @field_validator("phone")
    @classmethod
    def validate_phone_number(cls, v: str) -> str:
        if not v or not PHONE_REGEX.match(v.strip()):
            raise ValueError("Invalid phone number format.")
        return v.strip()


class NotificationChannels(BaseModel):
    sms: bool = False
    email: bool = False
    voice_call: bool = False
    simulation: bool = True

    @model_validator(mode="after")
    def check_at_least_one_channel(self) -> NotificationChannels:
        if not (self.sms or self.email or self.voice_call):
            raise ValueError("At least one notification channel (sms, email, voice_call) must be enabled.")
        return self


class CallAgentRequest(BaseModel):
    incident: IncidentPayload
    officer: OfficerPayload
    notification: NotificationChannels


class CallAgentResponse(BaseModel):
    success: bool = True
    incident_id: str
    mode: str = "SIMULATION"
    message: str = "Incident notification simulated successfully."
    overall_status: str = "SIMULATED"
    channels: ChannelsSummary
    channels_requested: Optional[NotificationChannels] = None


class VoiceWebhookRequest(BaseModel):
    incident_id: str
    call_sid: Optional[str] = None
    call_status: str
    digits: Optional[str] = None
    officer_id: Optional[str] = None


class VoiceWebhookResponse(BaseModel):
    success: bool = True
    incident_id: str
    call_status: str
    conversation_state: str
    acknowledged: bool
    acknowledged_by: Optional[str] = None
