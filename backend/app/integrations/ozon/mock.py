import hashlib
from typing import Any

from app.integrations.ozon.base import OzonConnector, OzonPublishResult


class MockOzonConnector(OzonConnector):
    def publish_draft(self, draft_id: int, payload: dict[str, Any]) -> OzonPublishResult:
        fingerprint = hashlib.sha256(
            f"{draft_id}:{payload.get('title', '')}".encode("utf-8")
        ).hexdigest()[:10].upper()
        publication_id = f"MOCK-OZON-{fingerprint}"
        return OzonPublishResult(
            publication_id=publication_id,
            status="published",
            response={
                "mock": True,
                "publication_id": publication_id,
                "accepted": True,
            },
        )

