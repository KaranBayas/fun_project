from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from app.config import get_settings
from app.models.agent_schemas import CallAgentRequest, ChannelResult, ChannelStatus
from app.services.agent.voice_agent import VoiceAgent
from app.utils.logging import get_logger

logger = get_logger(__name__)


class BaseVoiceProvider(ABC):
    @abstractmethod
    def place_call(self, request: CallAgentRequest) -> ChannelResult:
        pass


class TwilioVoiceProvider(BaseVoiceProvider):
    def __init__(
        self,
        account_sid: Optional[str] = None,
        auth_token: Optional[str] = None,
        from_number: Optional[str] = None,
        enabled: Optional[bool] = None,
        voice_agent: Optional[VoiceAgent] = None,
        twiml_url: Optional[str] = None,
    ) -> None:
        settings = get_settings()
        self.account_sid = account_sid if account_sid is not None else settings.twilio_account_sid
        self.auth_token = auth_token if auth_token is not None else settings.twilio_auth_token
        self.from_number = from_number if from_number is not None else settings.twilio_from_number
        self.enabled = enabled if enabled is not None else settings.voice_agent_enabled
        self.twiml_url = twiml_url if twiml_url is not None else settings.voice_twiml_url
        self.voice_agent = voice_agent or VoiceAgent()

    def is_enabled(self) -> bool:
        return bool(self.enabled)

    def is_configured(self) -> bool:
        return bool(
            self.account_sid
            and self.account_sid.strip()
            and self.auth_token
            and self.auth_token.strip()
            and self.from_number
            and self.from_number.strip()
        )

    def place_call(self, request: CallAgentRequest) -> ChannelResult:
        if not self.is_enabled():
            logger.info("Voice agent is disabled.")
            return ChannelResult(
                requested=True,
                status=ChannelStatus.DISABLED,
                message="Voice agent is disabled.",
            )

        if not self.is_configured():
            logger.info("Voice provider is missing configuration.")
            return ChannelResult(
                requested=True,
                status=ChannelStatus.CONFIGURATION_ERROR,
                message="Voice provider is not configured.",
            )

        try:
            from twilio.rest import Client

            client = Client(self.account_sid.strip(), self.auth_token.strip())
            twiml_text = self.voice_agent.generate_twiml(request.incident)

            if self.twiml_url and self.twiml_url.strip():
                target_url = self.twiml_url.strip()
                if "incident_id" not in target_url:
                    sep = "&" if "?" in target_url else "?"
                    target_url += f"{sep}incident_id={request.incident.incident_id}"

                call = client.calls.create(
                    to=request.officer.phone,
                    from_=self.from_number.strip(),
                    url=target_url,
                )
            else:
                call = client.calls.create(
                    to=request.officer.phone,
                    from_=self.from_number.strip(),
                    twiml=twiml_text,
                )

            call_sid = getattr(call, "sid", None)
            logger.info(
                "Voice call initiated for incident %s (call_sid=%s)",
                request.incident.incident_id,
                call_sid or "SIMULATED_SID",
            )
            return ChannelResult(
                requested=True,
                status=ChannelStatus.INITIATED,
                message=f"Voice call initiated (SID: {call_sid})" if call_sid else "Voice call initiated.",
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
                    "Voice provider failed for incident %s: TwilioRestException [code=%s, status=%s, msg=%s, uri=%s]",
                    request.incident.incident_id,
                    code if code is not None else "N/A",
                    status_code if status_code is not None else "N/A",
                    msg,
                    uri if uri is not None else "N/A",
                )
            else:
                logger.warning(
                    "Voice provider failed to initiate call for incident %s: %s",
                    request.incident.incident_id,
                    exc.__class__.__name__,
                )

            return ChannelResult(
                requested=True,
                status=ChannelStatus.FAILED,
                message="Failed to initiate voice call.",
            )
