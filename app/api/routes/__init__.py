"""API routers."""
from app.api.routes.documents import router as documents_router
from app.api.routes.face import router as face_router

__all__ = ["documents_router", "face_router"]
