from __future__ import annotations

from typing import Annotated

from fastapi import (
    APIRouter,
    File,
    Form,
    HTTPException,
    Request,
    Security,
    UploadFile,
    status,
)

from app.config import get_settings
from app.models.schemas import (
    IndexDocumentRequest,
    IndexingSuccessResponse,
    SearchRequest,
    SearchResponse,
    SearchResultItem,
    StandardErrorResponse,
)
from app.security import verify_api_key
from app.services.search.document_processor import DocumentProcessor
from app.services.search.text_extractor import DocumentTextExtractor
from app.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/api/v1",
    tags=["Semantic Search & Document Indexing"],
    dependencies=[Security(verify_api_key)],
)

ERROR_RESPONSES = {
    400: {"model": StandardErrorResponse, "description": "Invalid input or document validation failure."},
    401: {"model": StandardErrorResponse, "description": "Unauthorized - Missing or invalid API key."},
    422: {"model": StandardErrorResponse, "description": "Unprocessable request payload."},
    500: {"model": StandardErrorResponse, "description": "Internal server error during document processing."},
}


async def _handle_index_document(
    request: Request,
    document_id: str,
    case_id: str,
    file: UploadFile,
    document_type: str | None = None,
    version: str | None = None,
) -> IndexingSuccessResponse:
    settings = get_settings()
    try:
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error_code": "FILE_REQUIRED", "message": "File is required."},
            )

        extractor = getattr(request.app.state, "text_extractor", None)
        if not isinstance(extractor, DocumentTextExtractor):
            extractor = DocumentTextExtractor()

        payload = IndexDocumentRequest(
            document_id=document_id,
            case_id=case_id,
            document_type=document_type,
            version=version,
        )
        if not file.file:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error_code": "FILE_EMPTY", "message": "File content is empty."},
            )

        file_bytes = await file.read()
        if not file_bytes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error_code": "FILE_EMPTY", "message": "Uploaded file is empty."},
            )

        if len(file_bytes) > settings.max_file_size_mb * 1024 * 1024:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error_code": "FILE_TOO_LARGE",
                    "message": "File exceeds the maximum allowed size.",
                },
            )

        extractor.validate_file(file_bytes, file.filename, file.content_type)

        embedding_service = getattr(request.app.state, "embedding_service", None)
        vector_service = getattr(request.app.state, "vector_service", None)

        if embedding_service is None or vector_service is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "error_code": "SERVICE_UNAVAILABLE",
                    "message": "Semantic search service is not initialized.",
                },
            )

        processor = DocumentProcessor(
            embedding_service=embedding_service, text_extractor=extractor
        )
        chunks = await processor.process_document(
            file_bytes,
            file.filename,
            payload.document_id,
            payload.case_id,
            payload.document_type,
            payload.version,
        )

        await vector_service.ensure_collection()
        await vector_service.delete_document_points(payload.document_id)

        embeddings = await embedding_service.embed_texts(chunks)
        points = []
        for idx, chunk in enumerate(chunks):
            point_id = f"{payload.document_id}:{idx}"
            payload_item = {
                "document_id": payload.document_id,
                "case_id": payload.case_id,
                "chunk_id": point_id,
                "source_type": processor.source_type,
            }
            if payload.document_type:
                payload_item["document_type"] = payload.document_type
            if payload.version:
                payload_item["version"] = payload.version
            points.append(
                {
                    "id": point_id,
                    "vector": embeddings[idx],
                    "payload": payload_item,
                }
            )

        await vector_service.upsert_points(points)
        logger.info(
            "Indexed document %s in case %s with %s chunks.",
            payload.document_id,
            payload.case_id,
            len(points),
        )
        return IndexingSuccessResponse(
            success=True,
            document_id=payload.document_id,
            case_id=payload.case_id,
            chunks_indexed=len(points),
        )
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "INVALID_DOCUMENT", "message": str(exc)},
        ) from exc
    except Exception as exc:
        logger.exception("Indexing failed for document %s", document_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "INDEXING_FAILED", "message": "Indexing failed."},
        ) from exc


async def _handle_search(request: Request, payload: SearchRequest) -> SearchResponse:
    settings = get_settings()
    try:
        top_k = min(payload.top_k, settings.max_top_k)
        embedding_service = getattr(request.app.state, "embedding_service", None)
        vector_service = getattr(request.app.state, "vector_service", None)

        if embedding_service is None or vector_service is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "error_code": "SERVICE_UNAVAILABLE",
                    "message": "Search service is not initialized.",
                },
            )

        query_vector = await embedding_service.embed_text(payload.query)
        await vector_service.ensure_collection()

        hits = await vector_service.search(query_vector=query_vector, top_k=top_k)
        results = [
            SearchResultItem(
                document_id=item["document_id"],
                case_id=item["case_id"],
                score=item["score"],
            )
            for item in hits
            if item.get("document_id") and item.get("case_id")
        ]

        return SearchResponse(results=results)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Search failed for query: %s", payload.query)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "SEARCH_FAILED", "message": "Search operation failed."},
        ) from exc


# ---------------------------------------------------------------------------
# Primary Unified Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/documents/index",
    response_model=IndexingSuccessResponse,
    responses=ERROR_RESPONSES,
    summary="Index Document for Semantic Search",
    description="Extracts text/OCR, generates BGE-M3 embeddings, and stores vectors into Qdrant.",
)
async def index_document_unified(
    request: Request,
    document_id: Annotated[str, Form(...)],
    case_id: Annotated[str, Form(...)],
    file: UploadFile = File(...),
    document_type: Annotated[str | None, Form()] = None,
    version: Annotated[str | None, Form()] = None,
) -> IndexingSuccessResponse:
    return await _handle_index_document(
        request=request,
        document_id=document_id,
        case_id=case_id,
        file=file,
        document_type=document_type,
        version=version,
    )


@router.post(
    "/documents/search",
    response_model=SearchResponse,
    responses=ERROR_RESPONSES,
    summary="Search Documents Semantically",
    description="Computes BGE-M3 query vector and executes cosine similarity search in Qdrant.",
)
async def search_documents_unified(
    request: Request, payload: SearchRequest
) -> SearchResponse:
    return await _handle_search(request, payload)


# ---------------------------------------------------------------------------
# Backward-Compatible Endpoint Aliases
# ---------------------------------------------------------------------------

@router.post(
    "/index-document",
    response_model=IndexingSuccessResponse,
    responses=ERROR_RESPONSES,
    include_in_schema=True,
    summary="Index Document (Backward-Compatible Alias)",
)
async def index_document_legacy(
    request: Request,
    document_id: Annotated[str, Form(...)],
    case_id: Annotated[str, Form(...)],
    file: UploadFile = File(...),
    document_type: Annotated[str | None, Form()] = None,
    version: Annotated[str | None, Form()] = None,
) -> IndexingSuccessResponse:
    return await _handle_index_document(
        request=request,
        document_id=document_id,
        case_id=case_id,
        file=file,
        document_type=document_type,
        version=version,
    )


@router.post(
    "/search",
    response_model=SearchResponse,
    responses=ERROR_RESPONSES,
    include_in_schema=True,
    summary="Search Documents (Backward-Compatible Alias)",
)
async def search_documents_legacy(
    request: Request, payload: SearchRequest
) -> SearchResponse:
    return await _handle_search(request, payload)
