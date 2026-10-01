from app.core.config import Settings
from app.core.security import sanitize_for_log
from app.models import AppLog
from app.repositories.logs import LogRepository
from app.repositories.tasks import TaskRepository
from app.services.tasks import TaskService


def test_log_sanitizer_redacts_nested_credentials() -> None:
    payload = {
        "api_key": "secret-value",
        "nested": {"access_token": "token-value", "safe": "visible"},
        "items": [{"password": "hidden"}],
    }

    sanitized = sanitize_for_log(payload)

    assert sanitized["api_key"] == "***REDACTED***"
    assert sanitized["nested"]["access_token"] == "***REDACTED***"
    assert sanitized["nested"]["safe"] == "visible"
    assert sanitized["items"][0]["password"] == "***REDACTED***"


def test_log_sanitizer_redacts_credentials_embedded_in_text() -> None:
    message = (
        "provider failed api_key=secret-value; "
        "Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.payload.signature"
    )

    sanitized = sanitize_for_log(message)

    assert "secret-value" not in sanitized
    assert "eyJhbGciOiJIUzI1NiJ9" not in sanitized
    assert sanitized.count("***REDACTED***") == 2


def test_default_cors_origins_include_tauri_webview() -> None:
    settings = Settings(_env_file=None)

    assert "http://tauri.localhost" in settings.cors_origins
    assert "tauri://localhost" in settings.cors_origins


def test_log_and_task_services_sanitize_all_persisted_text(client) -> None:
    with client.app.state.database.session_factory() as session:
        log = LogRepository(session).add(
            "ERROR",
            "AI",
            "request failed password=hunter2",
            {"detail": "Authorization: Bearer task-token"},
        )
        task = TaskService(TaskRepository(session)).create(
            "security_test",
            {"api_key": "payload-secret", "safe": "visible"},
        )

        stored_log = session.get(AppLog, log.id)
        assert stored_log is not None
        assert "hunter2" not in stored_log.message
        assert "task-token" not in str(stored_log.context)
        assert task.payload["api_key"] == "***REDACTED***"
        assert task.payload["safe"] == "visible"
