from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Security, status

from app.models.monitoring_schemas import (
    CurrentActivityRequest,
    RiskAnalysisResponse,
    SecurityEventRequest,
    SecurityEventResponse,
)
from app.models.schemas import StandardErrorResponse
from app.security import verify_api_key
from app.services.monitoring.monitoring_service import (
    MonitoringService,
    get_monitoring_service,
)
from app.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/api/v1/monitoring",
    tags=["Security Monitoring"],
    dependencies=[Security(verify_api_key)],
)

ERROR_RESPONSES = {
    401: {"model": StandardErrorResponse, "description": "Unauthorized - Missing or invalid API key."},
    422: {"model": StandardErrorResponse, "description": "Unprocessable request payload."},
    500: {"model": StandardErrorResponse, "description": "Internal server error."},
}


def _service(request: Request) -> MonitoringService:
    return getattr(request.app.state, "monitoring_service", None) or get_monitoring_service()


@router.post(
    "/events",
    response_model=SecurityEventResponse,
    responses=ERROR_RESPONSES,
    summary="Ingest Security Event",
    description="Receives and processes a security audit event from downstream components.",
)
async def record_security_event(
    request: Request,
    event: SecurityEventRequest,
) -> SecurityEventResponse:
    try:
        service = _service(request)
        saved_event = await service.record_event(event)
        return SecurityEventResponse(
            success=True,
            message="Security event received",
            event_id=saved_event.event_id,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to process security event.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error_code": "INTERNAL_SERVER_ERROR",
                "message": "Failed to process security event.",
            },
        ) from exc


@router.post(
    "/analyze",
    response_model=RiskAnalysisResponse,
    responses=ERROR_RESPONSES,
    summary="Analyze Current Activity Risk",
    description="Evaluates details of a single current user activity and returns a structured risk assessment.",
)
async def analyze_activity_risk(
    request: Request,
    activity: CurrentActivityRequest,
) -> RiskAnalysisResponse:
    try:
        service = _service(request)
        return await service.analyze_activity(activity)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to perform activity risk analysis.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error_code": "INTERNAL_SERVER_ERROR",
                "message": "Failed to analyze activity risk.",
            },
        ) from exc
