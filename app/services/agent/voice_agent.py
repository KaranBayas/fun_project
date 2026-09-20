from __future__ import annotations

from enum import Enum
from typing import Any, Dict, Optional

from app.models.agent_schemas import IncidentPayload
from app.utils.logging import get_logger

logger = get_logger(__name__)


class ConversationState(str, Enum):
    INTRO = "INTRO"
    INCIDENT_SUMMARY = "INCIDENT_SUMMARY"
    RECOMMENDED_ACTION = "RECOMMENDED_ACTION"
    WAITING_FOR_ACKNOWLEDGEMENT = "WAITING_FOR_ACKNOWLEDGEMENT"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    DECLINED = "DECLINED"
    NO_RESPONSE = "NO_RESPONSE"
    ENDED = "ENDED"


class VoiceAgent:
    """Deterministic security-incident conversation engine for AI voice calling.

    Note: Designed behind a clean boundary so this deterministic engine can be
    replaced or backed by an LLM-powered conversation engine in future iterations.
    """

    def generate_alert_speech(self, incident: IncidentPayload) -> str:
        risk_lvl = (
            incident.risk_level.value
            if hasattr(incident.risk_level, "value")
            else str(incident.risk_level).lower()
        )
        rec_act = (
            incident.recommended_action.value
            if hasattr(incident.recommended_action, "value")
            else str(incident.recommended_action).replace("_", " ").lower()
        )
        threat = incident.threat_type.replace("_", " ").lower()

        return (
            f"Security alert. Incident {incident.incident_id} requires your attention. "
            f"The current risk level is {risk_lvl}. "
            f"The detected threat is {threat}. "
            f"The recommended action is {rec_act}. "
            f"Please review the incident in the secure document management system."
        )

    def process_dtmf_input(
        self, digits: Optional[str], current_state: ConversationState, officer_id: str
    ) -> Dict[str, Any]:
        digits_str = str(digits).strip() if digits else ""

        if digits_str == "1":
            logger.info("Incident acknowledged via DTMF by officer %s", officer_id)
            return {
                "acknowledged": True,
                "acknowledged_by": officer_id,
                "state": ConversationState.ACKNOWLEDGED.value,
                "message": "Incident acknowledged by officer.",
            }
        elif digits_str == "2":
            logger.info("DTMF repeat requested by officer %s", officer_id)
            return {
                "acknowledged": False,
                "state": ConversationState.INCIDENT_SUMMARY.value,
                "repeat": True,
                "message": "Repeating security alert summary.",
            }
        elif digits_str == "3":
            logger.info("DTMF call ended by officer %s", officer_id)
            return {
                "acknowledged": False,
                "state": ConversationState.DECLINED.value,
                "message": "Call ended by officer.",
            }
        else:
            return {
                "acknowledged": False,
                "state": current_state.value,
                "message": "Invalid keypad selection.",
            }

    def generate_twiml(self, incident: IncidentPayload, action_url: Optional[str] = None) -> str:
        alert_text = self.generate_alert_speech(incident)
        action_attr = f' action="{action_url}"' if action_url else ""
        twiml = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<Response>\n'
            f'  <Gather numDigits="1"{action_attr} timeout="10">\n'
            f'    <Say voice="alice">{alert_text} Press 1 to acknowledge, 2 to repeat, or 3 to decline.</Say>\n'
            '  </Gather>\n'
            '  <Say voice="alice">No input received. Goodbye.</Say>\n'
            '</Response>'
        )
        return twiml
