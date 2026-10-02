import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.database import Database
from app.main import create_app


@pytest.fixture
def client() -> TestClient:
    settings = Settings(
        source_provider="mock",
        database_url="sqlite+pysqlite:///:memory:",
        api_prefix="/api/v1",
        cors_origins=["http://localhost:1420"],
    )
    database = Database(settings.database_url)
    app = create_app(settings, database)
    with TestClient(app) as test_client:
        yield test_client

