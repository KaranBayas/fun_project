from __future__ import annotations

import hmac
from typing import Optional

from fastapi import HTTPException, Request, Security, status
from fastapi.security import APIKeyHeader

from app.config import get_settings
from app.utils.logging import get_logger

logger = get_logger(__name__)

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


async def verify_twilio_signature(request: Request) -> dict[str, str]:
    logger.error(

        "TWILIO WEBHOOK AUTH FUNCTION ENTERED | path=%s",

        request.url.path,

    )
    """
    Validates the X-Twilio-Signature header on incoming Twilio webhooks.
    Does NOT require X-API-Key.
    Returns the combined request parameters dict (query + post params) on success.
    Raises 401 Unauthorized if missing/invalid signature or unconfigured auth token.
    """
    settings = get_settings()
    auth_token = settings.twilio_auth_token

    if not auth_token or not auth_token.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "success": False,
                "error_code": "UNAUTHORIZED",
                "message": "Twilio Auth Token is not configured.",
            },
        )

    signature = request.headers.get("X-Twilio-Signature")
    logger.error(
    "TWILIO SIGNATURE RECEIVED | exists=%s | length=%d",
    bool(signature),
    len(signature) if signature else 0,
    )
    if not signature:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "success": False,
                "error_code": "UNAUTHORIZED",
                "message": "Missing X-Twilio-Signature header.",
            },
        )

    # 1. Reconstruct the external URL requested by Twilio
    # Support reverse proxies/tunnels (ngrok) via X-Forwarded-Proto and X-Forwarded-Host/Host headers
    raw_proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    scheme = raw_proto.split(",")[0].strip() if raw_proto else "http"

    raw_host = request.headers.get("x-forwarded-host", request.headers.get("host", request.url.netloc))
    host = raw_host.split(",")[0].strip() if raw_host else ""

    # Strip default ports (:443 for https, :80 for http) from host header
    if scheme == "https" and host.endswith(":443"):
        host = host[:-4]
    elif scheme == "http" and host.endswith(":80"):
        host = host[:-3]

    path = request.url.path
    url = f"{scheme}://{host}{path}"
    if request.url.query:
        url += f"?{request.url.query}"

    # 2. Extract POST body parameters ONLY for Twilio signature validation
    # Twilio RequestValidator computes signature over: URL (with query string) + POST body parameters ONLY.
    # Query string parameters must NOT be merged into post_params dictionary passed to validator.
    post_params: dict[str, str] = {}

    content_type = request.headers.get("content-type", "").lower()
    if "application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type:
        try:
            form_data = await request.form()
            for k, v in form_data.items():
                post_params[k] = str(v)
        except Exception:
            pass
    elif "application/json" in content_type:
        try:
            body_bytes = await request.body()
            if body_bytes:
                import json

                json_data = json.loads(body_bytes)
                if isinstance(json_data, dict):
                    for k, v in json_data.items():
                        if v is not None:
                            post_params[k] = str(v)
        except Exception:
            pass

    # 3. Validate signature with Twilio RequestValidator
    try:
        from twilio.request_validator import RequestValidator

        validator = RequestValidator(auth_token.strip())
        is_valid = validator.validate(url, post_params, signature)

        # Fallback check against voice_twiml_url if configured in .env
        if not is_valid and settings.voice_twiml_url and settings.voice_twiml_url.strip():
            twiml_url = settings.voice_twiml_url.strip()
            if request.url.query and "?" not in twiml_url:
                twiml_url += f"?{request.url.query}"
            is_valid = validator.validate(twiml_url, post_params, signature)
    except Exception as exc:
        logger.error(
            "Twilio signature validation exception | type=%s | message=%s",
            type(exc).__name__,
            str(exc),
        )
        is_valid = False

    if not is_valid:
        logger.error(
            "Twilio signature validation failed | method=%s | reconstructed_url=%s | raw_url=%s | x_forwarded_proto=%s | x_forwarded_host=%s | host_header=%s | path=%s | query=%s | post_param_names=%s | signature_exists=%s | signature_len=%d | is_valid=%s",
            request.method,
            url,
            str(request.url),
            request.headers.get("x-forwarded-proto"),
            request.headers.get("x-forwarded-host"),
            request.headers.get("host"),
            request.url.path,
            request.url.query,
            list(post_params.keys()),
            bool(signature),
            len(signature) if signature else 0,
            is_valid,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "success": False,
                "error_code": "UNAUTHORIZED",
                "message": "Invalid Twilio signature.",
            },
        )

    # 4. Return combined parameters (query + post params) for route handlers
    all_params: dict[str, str] = {**dict(request.query_params), **post_params}
    return all_params
