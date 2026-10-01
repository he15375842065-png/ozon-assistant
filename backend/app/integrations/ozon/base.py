from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel


class OzonPublishResult(BaseModel):
    publication_id: str
    status: str
    response: dict[str, Any]


class OzonConnector(ABC):
    @abstractmethod
    def publish_draft(self, draft_id: int, payload: dict[str, Any]) -> OzonPublishResult:
        """Publish a reviewed draft. Callers must enforce human confirmation."""

