from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from app.models.monitoring_schemas import (
    CurrentActivityRequest,
    RiskAnalysisResponse,
    SecurityEventRequest,
)
from app.services.monitoring.event_store import BaseEventStore, InMemoryEventStore
from app.services.monitoring.risk_analyzer import RiskAnalyzer
from app.utils.logging import get_logger

logger = get_logger(__name__)

SENSITIVE_KEYS = {
    "password",
    "api_key",
    "apikey",
    "secret",
    "token",
    "authorization",
    "biometric_data",
    "face_embedding",
    "embedding",
    "raw_image",
    "image_bytes",
    "document_content",
    "raw_content",
}


def _sanitize_value(key: str, value: Any) -> Any:
    if key.lower() in SENSITIVE_KEYS:
        return "[REDACTED]"
    if isinstance(value, dict):
        return {k: _sanitize_value(k, v) for k, v in value.items()}
    if isinstance(value, list):
        return [_sanitize_value(key, item) for item in value]
    return value


def sanitize_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Sanitize metadata dictionary to prevent logging sensitive data."""
    if not metadata:
        return {}
    return {k: _sanitize_value(k, v) for k, v in metadata.items()}


class MonitoringService:
    """Core service for managing security event ingestion and risk analysis."""

    def __init__(
        self,
        event_store: Optional[BaseEventStore] = None,
        risk_analyzer: Optional[RiskAnalyzer] = None,
    ) -> None:
        self.event_store = event_store or InMemoryEventStore()
        self.risk_analyzer = risk_analyzer or RiskAnalyzer()

    async def record_event(self, event: SecurityEventRequest) -> SecurityEventRequest:
        safe_meta = sanitize_metadata(event.metadata)
        event_type_str = (
            event.event_type.value
            if isinstance(event.event_type, Enum)
            else str(event.event_type)
        )
        severity_str = (
            event.severity.value
            if isinstance(event.severity, Enum)
            else str(event.severity)
        )

        logger.info(
            "Security Event: id=%s | type=%s | severity=%s | user_id=%s | case_id=%s | doc_id=%s | action=%s | success=%s | ip=%s | metadata=%s",
            event.event_id,
            event_type_str,
            severity_str,
            event.user_id,
            event.case_id,
            event.document_id,
            event.action,
            event.success,
            event.source_ip,
            safe_meta,
        )

        return await self.event_store.save_event(event)

    async def analyze_activity(
        self, activity: CurrentActivityRequest
    ) -> RiskAnalysisResponse:
        safe_meta = sanitize_metadata(activity.metadata)
        logger.info(
            "Analyzing Activity Risk: user_id=%s | activity_type=%s | action=%s | sensitivity=%s | auth_status=%s | perm_status=%s | metadata=%s",
            activity.user_id,
            activity.activity_type.value if isinstance(activity.activity_type, Enum) else activity.activity_type,
            activity.action,
            activity.document_sensitivity.value if isinstance(activity.document_sensitivity, Enum) else activity.document_sensitivity,
            activity.authentication_status.value if isinstance(activity.authentication_status, Enum) else activity.authentication_status,
            activity.permission_status.value if isinstance(activity.permission_status, Enum) else activity.permission_status,
            safe_meta,
        )

        analysis = self.risk_analyzer.analyze(activity)

        logger.info(
            "Risk Assessment Result: user_id=%s | score=%d | level=%s | threat_type=%s | action=%s | calling_agent=%s",
            analysis.user_id,
            analysis.risk_score,
            analysis.risk_level.value if isinstance(analysis.risk_level, Enum) else analysis.risk_level,
            analysis.threat_type.value if isinstance(analysis.threat_type, Enum) else analysis.threat_type,
            analysis.recommended_action.value if isinstance(analysis.recommended_action, Enum) else analysis.recommended_action,
            analysis.requires_calling_agent,
        )

        return analysis

    async def get_event(self, event_id: str) -> Optional[SecurityEventRequest]:
        return await self.event_store.get_event(event_id)

    async def list_events(self, limit: int = 100) -> List[SecurityEventRequest]:
        return await self.event_store.list_events(limit)


_default_monitoring_service: Optional[MonitoringService] = None


def get_monitoring_service() -> MonitoringService:
    global _default_monitoring_service
    if _default_monitoring_service is None:
        _default_monitoring_service = MonitoringService()
    return _default_monitoring_service
