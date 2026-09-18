from __future__ import annotations

import hmac
from typing import Optional

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

from app.config import get_settings

API_KEY_HEADER_NAME = "X-API-Key"

api_key_header = APIKeyHeader(
    name=API_KEY_HEADER_NAME,
    auto_error=False,
    description="API Key for accessing Secure-DMS AI Services",
)


async def verify_api_key(
    api_key: Optional[str] = Security(api_key_header),
) -> str:
    settings = get_settings()
    expected_key = settings.ai_services_api_key

    if not expected_key or not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "success": False,
                "error_code": "UNAUTHORIZED",
                "message": "Invalid or missing API key.",
            },
        )

    # Constant-time comparison to prevent timing attacks
    if not hmac.compare_digest(api_key.strip(), expected_key.strip()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "success": False,
                "error_code": "UNAUTHORIZED",
                "message": "Invalid or missing API key.",
            },
        )

    return api_key
