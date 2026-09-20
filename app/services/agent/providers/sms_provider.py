from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from app.config import get_settings
from app.models.agent_schemas import CallAgentRequest, ChannelResult, ChannelStatus
from app.utils.logging import get_logger

logger = get_logger(__name__)


class BaseSMSProvider(ABC):
    @abstractmethod
    def send_sms(self, request: CallAgentRequest) -> ChannelResult:
        pass


class TwilioSMSProvider(BaseSMSProvider):
    def __init__(
        self,
        account_sid: Optional[str] = None,
        auth_token: Optional[str] = None,
        from_number: Optional[str] = None,
    ) -> None:
        settings = get_settings()
        self.account_sid = account_sid if account_sid is not None else settings.twilio_account_sid
        self.auth_token = auth_token if auth_token is not None else settings.twilio_auth_token
        self.from_number = from_number if from_number is not None else settings.twilio_from_number

    def is_configured(self) -> bool:
        return bool(
            self.account_sid
            and self.account_sid.strip()
            and self.auth_token
            and self.auth_token.strip()
            and self.from_number
            and self.from_number.strip()
        )

    def send_sms(self, request: CallAgentRequest) -> ChannelResult:
        if not self.is_configured():
            logger.info("SMS provider is missing configuration.")
            return ChannelResult(
                requested=True,
                status=ChannelStatus.CONFIGURATION_ERROR,
                message="SMS provider is not configured.",
            )

        try:
            from twilio.rest import Client

            client = Client(self.account_sid.strip(), self.auth_token.strip())
            risk_lvl = (
                request.incident.risk_level.value
                if hasattr(request.incident.risk_level, "value")
                else str(request.incident.risk_level)
            )
            rec_act = (
                request.incident.recommended_action.value
                if hasattr(request.incident.recommended_action, "value")
                else str(request.incident.recommended_action)
            )

            sms_body = (
                f"Security Alert: Incident {request.incident.incident_id} requires attention. "
                f"Risk: {risk_lvl}. Threat: {request.incident.threat_type}. Action: {rec_act}."
            )

            client.messages.create(
                body=sms_body,
                from_=self.from_number.strip(),
                to=request.officer.phone,
            )

            logger.info(
                "SMS sent successfully for incident %s",
                request.incident.incident_id,
            )
            return ChannelResult(
                requested=True,
                status=ChannelStatus.SENT,
            )
        except Exception as exc:
            from twilio.base.exceptions import TwilioRestException

            if isinstance(exc, TwilioRestException):
                status_code = getattr(exc, "status", None)
                code = getattr(exc, "code", None)
                msg = getattr(exc, "msg", None) or str(exc)
                uri = getattr(exc, "uri", None)

                if self.auth_token and isinstance(msg, str):
                    msg = msg.replace(self.auth_token, "[REDACTED]")

                logger.warning(
                    "SMS provider failed for incident %s: TwilioRestException [code=%s, status=%s, msg=%s, uri=%s]",
                    request.incident.incident_id,
                    code if code is not None else "N/A",
                    status_code if status_code is not None else "N/A",
                    msg,
                    uri if uri is not None else "N/A",
                )
            else:
                logger.warning(
                    "SMS provider failed to send message for incident %s: %s",
                    request.incident.incident_id,
                    exc.__class__.__name__,
                )

            return ChannelResult(
                requested=True,
                status=ChannelStatus.FAILED,
                message="Failed to send SMS notification.",
            )
