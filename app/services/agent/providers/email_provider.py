from __future__ import annotations

from abc import ABC, abstractmethod
from email.message import EmailMessage
import smtplib
from typing import Optional

from app.config import get_settings
from app.models.agent_schemas import CallAgentRequest, ChannelResult, ChannelStatus
from app.utils.logging import get_logger

logger = get_logger(__name__)


class BaseEmailProvider(ABC):
    @abstractmethod
    def send_email(self, request: CallAgentRequest) -> ChannelResult:
        pass


class SMTPEmailProvider(BaseEmailProvider):
    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        from_email: Optional[str] = None,
        use_tls: Optional[bool] = None,
    ) -> None:
        settings = get_settings()
        self.host = host if host is not None else settings.smtp_host
        self.port = port if port is not None else settings.smtp_port
        self.username = username if username is not None else settings.smtp_username
        self.password = password if password is not None else settings.smtp_password
        self.from_email = from_email if from_email is not None else settings.smtp_from_email
        self.use_tls = use_tls if use_tls is not None else settings.smtp_use_tls

    def is_configured(self) -> bool:
        return bool(
            self.host
            and self.host.strip()
            and self.from_email
            and self.from_email.strip()
        )

    def send_email(self, request: CallAgentRequest) -> ChannelResult:
        if not self.is_configured():
            logger.info("Email provider is missing configuration.")
            return ChannelResult(
                requested=True,
                status=ChannelStatus.CONFIGURATION_ERROR,
                message="Email provider is not configured.",
            )

        try:
            msg = EmailMessage()
            msg["Subject"] = f"Security Alert - Incident {request.incident.incident_id}"
            msg["From"] = self.from_email.strip()
            msg["To"] = request.officer.email

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

            reasons_text = "\n".join(
                f"- [{r.severity.value if hasattr(r.severity, 'value') else r.severity}] {r.message}"
                for r in request.incident.reasons
            )

            body_text = (
                f"Security Alert Notice\n"
                f"---------------------\n"
                f"Incident ID: {request.incident.incident_id}\n"
                f"Case ID: {request.incident.case_id}\n"
                f"Risk Level: {risk_lvl}\n"
                f"Risk Score: {request.incident.risk_score}\n"
                f"Threat Type: {request.incident.threat_type}\n"
                f"Recommended Action: {rec_act}\n\n"
                f"Reasons:\n"
                f"{reasons_text}\n\n"
                f"Please review this incident in the Document Management System (DMS).\n"
            )
            msg.set_content(body_text)

            with smtplib.SMTP(self.host.strip(), self.port, timeout=10) as server:
                if self.use_tls:
                    server.starttls()
                if self.username and self.username.strip() and self.password:
                    server.login(self.username.strip(), self.password)
                server.send_message(msg)

            logger.info(
                "Email sent successfully for incident %s",
                request.incident.incident_id,
            )
            return ChannelResult(
                requested=True,
                status=ChannelStatus.SENT,
            )
        except Exception as exc:
            logger.warning(
                "Email provider failed to send email for incident %s: %s",
                request.incident.incident_id,
                exc.__class__.__name__,
            )
            return ChannelResult(
                requested=True,
                status=ChannelStatus.FAILED,
                message="Failed to send email notification.",
            )
