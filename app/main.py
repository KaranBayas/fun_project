from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse

from app.api.routes.agent import router as agent_router
from app.api.routes.documents import router as documents_router
from app.api.routes.face import router as face_router
from app.api.routes.monitoring import router as monitoring_router
from app.config import get_settings
from app.db.qdrant_client import get_qdrant_client
from app.models.schemas import HealthResponse, StandardErrorResponse
from app.services.agent import get_calling_agent_service
from app.services.monitoring import get_monitoring_service
from app.services.search.embedding_service import EmbeddingService
from app.services.search.text_extractor import DocumentTextExtractor
from app.services.search.vector_service import QdrantVectorService
from app.utils.logging import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logger.info("Initializing unified AI Services API...")

    # Initialize and pre-warm Semantic Search Embedding Model
    embedding_service = EmbeddingService(model_name=settings.model_name)
    try:
        await embedding_service.load_model()
        logger.info("Semantic search embedding model loaded successfully.")
    except Exception as exc:
        logger.warning("Could not pre-load embedding model at startup: %s", exc)

    # Initialize Qdrant Client and Vector Service
    qdrant_client = get_qdrant_client(settings.qdrant_url)
    vector_service = QdrantVectorService(
        qdrant_client=qdrant_client,
        collection_name=settings.collection_name,
        vector_dimension=settings.vector_dimension,
    )
    try:
        await vector_service.ensure_collection()
        logger.info("Qdrant collection '%s' ready.", settings.collection_name)
    except Exception as exc:
        logger.warning("Could not connect to Qdrant at startup: %s", exc)

    text_extractor = DocumentTextExtractor()
    monitoring_service = get_monitoring_service()
    calling_agent_service = get_calling_agent_service()

    # Store shared services in application state
    app.state.embedding_service = embedding_service
    app.state.vector_service = vector_service
    app.state.text_extractor = text_extractor
    app.state.monitoring_service = monitoring_service
    app.state.calling_agent_service = calling_agent_service
    app.state.settings = settings

    logger.info("AI Services API startup complete. InsightFace configured for lazy loading.")
    yield

    # Clean shutdown
    logger.info("Shutting down AI Services API...")
    try:
        await vector_service.close()
    except Exception as exc:
        logger.warning("Error closing Qdrant client: %s", exc)


app = FastAPI(
    title="Secure Digital DMS - AI Services API",
    description=(
        "Centralized, high-performance AI services gateway for the Secure Digital "
        "Document Management System (SIH 2026). Combines ArcFace biometric face recognition "
        "and BGE-M3 semantic document search under unified X-API-Key authentication."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Configure CORS safely based on environment
settings = get_settings()
if settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

# Exception Handlers
@app.exception_handler(RequestValidationError)
async def request_validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    locations = {str(error.get("loc", ())) for error in exc.errors()}
    if any("user_id" in loc for loc in locations):
        error_code, message = "VALIDATION_ERROR", "User ID is required."
    elif any("image" in loc for loc in locations):
        error_code, message = "IMAGE_REQUIRED", "Image file is required."
    elif any("file" in loc for loc in locations):
        error_code, message = "FILE_REQUIRED", "Document file is required."
    elif any("query" in loc for loc in locations):
        error_code, message = "VALIDATION_ERROR", "Search query is required."
    else:
        error_code, message = "VALIDATION_ERROR", "Request validation failed."
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"success": False, "error_code": error_code, "message": message},
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    if isinstance(exc.detail, dict):
        error_code = exc.detail.get("error_code", "HTTP_ERROR")
        message = exc.detail.get("message", "An error occurred.")
        return JSONResponse(
            status_code=exc.status_code,
            headers=exc.headers,
            content={"success": False, "error_code": error_code, "message": message},
        )
    return JSONResponse(
        status_code=exc.status_code,
        headers=exc.headers,
        content={
            "success": False,
            "error_code": "HTTP_ERROR",
            "message": str(exc.detail),
        },
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled server exception at %s", request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error_code": "INTERNAL_SERVER_ERROR",
            "message": "An internal server error occurred. Please try again later.",
        },
    )


# Public Health Endpoint
@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["System"],
    summary="Service Health Check",
    description="Public liveness and health probe for container orchestrators and monitoring.",
)
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        service="Secure Digital DMS - AI Services API",
        version="1.0.0",
    )


# Register Protected Business Routers
app.include_router(face_router)
app.include_router(documents_router)
app.include_router(monitoring_router)
app.include_router(agent_router)


# Custom OpenAPI schema to ensure X-API-Key security scheme is properly displayed in Swagger
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    openapi_schema["components"] = openapi_schema.get("components", {})
    openapi_schema["components"]["securitySchemes"] = {
        "ApiKeyAuth": {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key",
            "description": "Enter your AI_SERVICES_API_KEY in this header",
        }
    }
    # Apply security requirement to all endpoints except /health, /api/v1/agent/voice/status, and /api/v1/agent/voice/twiml (secured via Twilio signature)
    for path, path_item in openapi_schema.get("paths", {}).items():
        if path in ("/health", "/api/v1/agent/voice/status", "/api/v1/agent/voice/twiml"):
            continue
        for method in path_item:
            if method.lower() in {"get", "post", "put", "delete", "patch"}:
                path_item[method]["security"] = [{"ApiKeyAuth": []}]

    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi
