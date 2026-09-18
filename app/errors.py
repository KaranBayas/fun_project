from __future__ import annotations


class AIServiceError(Exception):
    """Base class for all AI service domain errors."""


# ---------------------------------------------------------------------------
# Face Recognition Domain Exceptions
# ---------------------------------------------------------------------------

class FaceError(AIServiceError):
    """Base class for expected face-service failures."""


class ImageError(FaceError):
    pass


class UnsupportedImageFormatError(ImageError):
    pass


class EmptyImageError(ImageError):
    pass


class InvalidImageError(ImageError):
    pass


class NoFaceDetectedError(FaceError):
    pass


class MultipleFacesDetectedError(FaceError):
    pass


class FaceProcessingError(FaceError):
    pass


class DuplicateUserError(FaceError):
    pass


class UserNotFoundError(FaceError):
    pass


class EncryptionError(FaceError):
    pass


class DecryptionError(FaceError):
    pass


class DatabaseError(FaceError):
    pass


class ComparisonError(FaceError):
    pass


# ---------------------------------------------------------------------------
# Semantic Search & Document Processing Domain Exceptions
# ---------------------------------------------------------------------------

class DocumentError(AIServiceError):
    """Base class for document processing failures."""


class UnsupportedDocumentFormatError(DocumentError):
    pass


class DocumentExtractionError(DocumentError):
    pass


class CorruptedDocumentError(DocumentError):
    pass


class EmptyDocumentError(DocumentError):
    pass


class VectorDatabaseError(AIServiceError):
    pass


class EmbeddingError(AIServiceError):
    pass
