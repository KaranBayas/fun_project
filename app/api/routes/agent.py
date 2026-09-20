from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, Security, status

from app.models.agent_schemas import (
    CallAgentRequest,
    CallAgentResponse,
    VoiceWebhookRequest,
    VoiceWebhookResponse,
)
from app.models.schemas import StandardErrorResponse
from app.security import verify_api_key
from app.services.agent.calling_agent_service import (
    CallingAgentService,
    get_calling_agent_service,
)
from app.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/api/v1/agent",
    tags=["Calling Agent"],
)

ERROR_RESPONSES = {
    401: {"model": StandardErrorResponse, "description": "Unauthorized - Missing or invalid API key or Twilio signature."},
    422: {"model": StandardErrorResponse, "description": "Unprocessable request payload validation failure."},
    500: {"model": StandardErrorResponse, "description": "Internal server error."},
}


def _service(request: Request) -> CallingAgentService:
    return getattr(request.app.state, "calling_agent_service", None) or get_calling_agent_service()


@router.post(
    "/call",
    dependencies=[Security(verify_api_key)],
    response_model=CallAgentResponse,
    responses=ERROR_RESPONSES,
    summary="Queue Calling Agent Incident Notification",
    description="Accepts security incident assessment and officer contact details from Spring Boot backend to process incident notification.",
)
async def trigger_agent_call(
    request: Request,
    payload: CallAgentRequest,
) -> CallAgentResponse:
    try:
        service = _service(request)
        return await service.process_call_request(payload)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to process Calling Agent request.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error_code": "INTERNAL_SERVER_ERROR",
                "message": "Failed to process Calling Agent request.",
            },
        ) from exc


@router.post(
    "/voice/status",
    response_model=VoiceWebhookResponse,
    responses=ERROR_RESPONSES,
    summary="Receive Telephony Voice Call Webhook Status / DTMF Input",
    description="Accepts call status updates (initiated, ringing, answered, completed, busy, failed, no-answer) or DTMF keypad selections from telephony provider. Secured via Twilio request signature.",
)
async def process_voice_status_webhook(
    request: Request,
    params: dict[str, str] = {},
) -> VoiceWebhookResponse:
    try:
        service = _service(request)
        incident_id = params.get("incident_id") or params.get("IncidentId")
        if not incident_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error_code": "VALIDATION_ERROR",
                    "message": "incident_id is required.",
                },
            )

        payload = VoiceWebhookRequest(
            incident_id=incident_id,
            call_sid=params.get("call_sid") or params.get("CallSid"),
            call_status=params.get("call_status") or params.get("CallStatus") or "in-progress",
            digits=params.get("digits") or params.get("Digits"),
            officer_id=params.get("officer_id") or params.get("OfficerId"),
        )
        return service.process_voice_webhook(payload)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to process voice webhook.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error_code": "INTERNAL_SERVER_ERROR",
                "message": "Failed to process voice webhook status.",
            },
        ) from exc


@router.post(
    "/voice/twiml",
    response_class=Response,
    responses={
        200: {"content": {"application/xml": {}}, "description": "TwiML XML instructions for Twilio Voice."},
        401: {"model": StandardErrorResponse, "description": "Unauthorized - Missing or invalid Twilio signature."},
        500: {"model": StandardErrorResponse, "description": "Internal server error."},
    },
    summary="Generate TwiML XML Instructions for Twilio Outbound Voice Call",
    description="Twilio webhook endpoint that returns TwiML XML instructions for voice call execution. Secured via Twilio request signature.",
)
@router.post(
    "/voice/twiml",
    response_class=Response,
    responses={
        200: {
            "content": {"application/xml": {}},
            "description": "TwiML XML instructions for Twilio Voice.",
        },
        500: {
            "model": StandardErrorResponse,
            "description": "Internal server error.",
        },
    },
    summary="Generate TwiML XML Instructions for Twilio Outbound Voice Call",
    description="Twilio webhook endpoint that returns TwiML XML instructions for voice call execution.",
)
async def get_voice_twiml_webhook(
    request: Request,
) -> Response:
    try:
        # Read parameters sent by Twilio.
        # incident_id is currently passed through the query string.
        params = dict(request.query_params)

        service = _service(request)
        twiml_xml = service.generate_twiml(params)

        return Response(
            content=twiml_xml,
            media_type="application/xml",
        )

    except HTTPException:
        raise

    except Exception as exc:
        logger.exception("Failed to generate TwiML XML.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error_code": "INTERNAL_SERVER_ERROR",
                "message": "Failed to generate TwiML XML instructions.",
            },
        ) from exc