from pathlib import Path

__path__ = [
    str(Path(__file__).resolve().parents[2] / "doc-generation" / "app")
]

from .main import app, create_app
from .service import DocumentGenerationService, DocumentService

__all__ = ["DocumentGenerationService", "DocumentService", "app", "create_app"]
