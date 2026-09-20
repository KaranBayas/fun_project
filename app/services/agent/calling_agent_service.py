from __future__ import annotations

from typing import Optional

from app.models.agent_schemas import (
    CallAgentRequest,
    CallAgentResponse,
    ChannelResult,
    ChannelStatus,
    ChannelsSummary,
    VoiceWebhookRequest,
    VoiceWebhookResponse,
)
from app.services.agent.providers.email_provider import BaseEmailProvider, SMTPEmailProvider
from app.services.agent.providers.sms_provider import BaseSMSProvider, TwilioSMSProvider
from app.services.agent.providers.voice_provider import BaseVoiceProvider, TwilioVoiceProvider
from app.utils.logging import get_logger

logger = get_logger(__name__)


class CallingAgentService:
    """Service for handling Calling Agent incident notification requests.

    Supports simulation mode (Level 1), SMS + Email providers (Level 2), and AI Voice calling (Level 3).
    """

    def __init__(
        self,
        sms_provider: Optional[BaseSMSProvider] = None,
        email_provider: Optional[BaseEmailProvider] = None,
        voice_provider: Optional[BaseVoiceProvider] = None,
    ) -> None:
        self.sms_provider = sms_provider or TwilioSMSProvider()
        self.email_provider = email_provider or SMTPEmailProvider()
        self.voice_provider = voice_provider or TwilioVoiceProvider()

    async def process_call_request(self, request: CallAgentRequest) -> CallAgentResponse:
        logger.info(
            "Calling Agent Request Received: incident_id=%s | user_id=%s | case_id=%s | threat_type=%s | risk_score=%d | risk_level=%s | officer_id=%s | channels=(sms=%s, email=%s, voice_call=%s, simulation=%s)",
            request.incident.incident_id,
            request.incident.user_id,
            request.incident.case_id,
            request.incident.threat_type,
            request.incident.risk_score,
            request.incident.risk_level.value if hasattr(request.incident.risk_level, "value") else request.incident.risk_level,
            request.officer.officer_id,
            request.notification.sms,
            request.notification.email,
            request.notification.voice_call,
            request.notification.simulation,
        )

        if request.notification.simulation:
            return self._process_simulation(request)
        else:
            return self._process_production(request)

    def _process_simulation(self, request: CallAgentRequest) -> CallAgentResponse:
        sms_result = ChannelResult(
            requested=request.notification.sms,
            status=ChannelStatus.SIMULATED if request.notification.sms else ChannelStatus.NOT_REQUESTED,
        )
        email_result = ChannelResult(
            requested=request.notification.email,
            status=ChannelStatus.SIMULATED if request.notification.email else ChannelStatus.NOT_REQUESTED,
        )
        voice_result = ChannelResult(
            requested=request.notification.voice_call,
            status=ChannelStatus.SIMULATED if request.notification.voice_call else ChannelStatus.NOT_REQUESTED,
        )

        channels_summary = ChannelsSummary(
            sms=sms_result,
            email=email_result,
            voice_call=voice_result,
        )

        return CallAgentResponse(
            success=True,
            incident_id=request.incident.incident_id,
            mode="SIMULATION",
            message="Incident notification simulated successfully.",
            overall_status="SIMULATED",
            channels=channels_summary,
            channels_requested=request.notification,
        )

    def _process_production(self, request: CallAgentRequest) -> CallAgentResponse:
        sms_result = (
            self.sms_provider.send_sms(request)
            if request.notification.sms
            else ChannelResult(requested=False, status=ChannelStatus.NOT_REQUESTED)
        )

        email_result = (
            self.email_provider.send_email(request)
            if request.notification.email
            else ChannelResult(requested=False, status=ChannelStatus.NOT_REQUESTED)
        )

        voice_result = (
            self.voice_provider.place_call(request)
            if request.notification.voice_call
            else ChannelResult(requested=False, status=ChannelStatus.NOT_REQUESTED)
        )

        requested_results = [r for r in (sms_result, email_result, voice_result) if r.requested]

        successful_statuses = {
            ChannelStatus.SENT,
            ChannelStatus.INITIATED,
            ChannelStatus.ANSWERED,
            ChannelStatus.ACKNOWLEDGED,
        }

        if not requested_results:
            overall_status = "NO_CHANNELS"
        elif all(r.status in successful_statuses for r in requested_results):
            overall_status = "SUCCESS"
        elif all(r.status == ChannelStatus.DISABLED for r in requested_results):
            overall_status = "DISABLED"
        elif all(r.status == ChannelStatus.NOT_IMPLEMENTED for r in requested_results):
            overall_status = "NOT_IMPLEMENTED"
        elif all(r.status in (ChannelStatus.FAILED, ChannelStatus.CONFIGURATION_ERROR) for r in requested_results):
            overall_status = "FAILED"
        elif any(r.status in successful_statuses for r in requested_results):
            overall_status = "PARTIAL_FAILURE"
        else:
            overall_status = "FAILED"

        channels_summary = ChannelsSummary(
            sms=sms_result,
            email=email_result,
            voice_call=voice_result,
        )

        return CallAgentResponse(
            success=True,
            incident_id=request.incident.incident_id,
            mode="PRODUCTION",
            message="Incident notification processed in production mode.",
            overall_status=overall_status,
            channels=channels_summary,
            channels_requested=request.notification,
        )

    def process_voice_webhook(self, payload: VoiceWebhookRequest) -> VoiceWebhookResponse:
        from app.services.agent.voice_agent import ConversationState, VoiceAgent

        voice_agent = VoiceAgent()
        officer_id = payload.officer_id or "OFFICER"

        if payload.digits:
            result = voice_agent.process_dtmf_input(
                digits=payload.digits,
                current_state=ConversationState.WAITING_FOR_ACKNOWLEDGEMENT,
                officer_id=officer_id,
            )
            conv_state = result["state"]
            acknowledged = result["acknowledged"]
            acknowledged_by = result.get("acknowledged_by")
        else:
            status_lower = payload.call_status.lower()
            if status_lower in ("completed", "answered"):
                conv_state = ConversationState.WAITING_FOR_ACKNOWLEDGEMENT.value
            elif status_lower in ("busy", "failed", "no-answer"):
                conv_state = ConversationState.NO_RESPONSE.value
            else:
                conv_state = ConversationState.INTRO.value
            acknowledged = False
            acknowledged_by = None

        logger.info(
            "Voice Webhook Handled: incident_id=%s | call_status=%s | digits=%s | state=%s | acknowledged=%s",
            payload.incident_id,
            payload.call_status,
            payload.digits,
            conv_state,
            acknowledged,
        )

        return VoiceWebhookResponse(
            success=True,
            incident_id=payload.incident_id,
            call_status=payload.call_status,
            conversation_state=conv_state,
            acknowledged=acknowledged,
            acknowledged_by=acknowledged_by,
        )

    def generate_twiml(self, params: dict[str, str]) -> str:
        from app.models.agent_schemas import IncidentPayload, ReasonPayload
        from app.models.monitoring_schemas import RecommendedAction, SecuritySeverity
        from app.services.agent.voice_agent import VoiceAgent

        incident_id = params.get("incident_id") or params.get("IncidentId") or "INC-2026-00001"
        user_id = params.get("user_id") or params.get("UserId") or "USR-SYSTEM"
        case_id = params.get("case_id") or params.get("CaseId") or "CASE-SYSTEM"

        risk_level_str = (params.get("risk_level") or params.get("RiskLevel") or "CRITICAL").upper()
        try:
            risk_level = SecuritySeverity(risk_level_str)
        except Exception:
            risk_level = SecuritySeverity.CRITICAL

        rec_act_str = (params.get("recommended_action") or params.get("RecommendedAction") or "BLOCK_AND_ALERT").upper()
        try:
            recommended_action = RecommendedAction(rec_act_str)
        except Exception:
            recommended_action = RecommendedAction.BLOCK_AND_ALERT

        threat_type = params.get("threat_type") or params.get("ThreatType") or "SUSPICIOUS_ACTIVITY"

        try:
            risk_score = int(params.get("risk_score") or params.get("RiskScore") or 90)
        except Exception:
            risk_score = 90

        try:
            confidence = float(params.get("confidence") or params.get("Confidence") or 0.95)
        except Exception:
            confidence = 0.95

        incident = IncidentPayload(
            incident_id=incident_id,
            user_id=user_id,
            case_id=case_id,
            risk_score=risk_score,
            risk_level=risk_level,
            suspicious=True,
            threat_type=threat_type,
            confidence=confidence,
            recommended_action=recommended_action,
            requires_calling_agent=True,
            reasons=[
                ReasonPayload(
                    code="TWILIO_WEBHOOK",
                    message=f"TwiML generated for threat {threat_type}",
                    severity=risk_level,
                )
            ],
        )

        voice_agent = VoiceAgent()
        action_url = f"/api/v1/agent/voice/status?incident_id={incident_id}"
        return voice_agent.generate_twiml(incident, action_url=action_url)


_default_calling_agent_service: Optional[CallingAgentService] = None


def get_calling_agent_service() -> CallingAgentService:
    global _default_calling_agent_service
    if _default_calling_agent_service is None:
        _default_calling_agent_service = CallingAgentService()
    return _default_calling_agent_service
