from threading import get_ident
from unittest.mock import Mock

import pytest

from app.core.errors import IntegrationError, ValidationError
from app.integrations.sources.browser_1688 import Alibaba1688BrowserManager, validate_offer_url


@pytest.mark.parametrize("url", [
    "https://example.com/offer/123.html",
    "https://detail.1688.com.evil.example/offer/123.html",
    "https://user:password@detail.1688.com/offer/123.html",
    "https://detail.1688.com/offer/123.html:bad",
    "https://detail.1688.com:bad/offer/123.html",
    "https://detail.1688.com:8001/offer/123.html",
    "https://detail.1688.com/offer/not-a-number.html",
    "https://detail.1688.com/",
    "file:///offer/123.html",
])
def test_rejects_non_product_urls_without_browser_launch(url: str) -> None:
    with pytest.raises(ValidationError):
        validate_offer_url(url)


def test_offer_url_removes_tracking_parameters() -> None:
    assert validate_offer_url("http://detail.1688.com/offer/123.html?spm=tracking#sku") == "https://detail.1688.com/offer/123.html"


def test_browser_work_is_serialized_on_one_thread(tmp_path, monkeypatch) -> None:
    manager = Alibaba1688BrowserManager(str(tmp_path))
    main_thread = get_ident()
    calls = []

    def capture(url):
        calls.append((url, get_ident()))
        return {"offer_id": "123", "mock": False}

    monkeypatch.setattr(manager, "_fetch", capture)
    try:
        manager.fetch("https://detail.1688.com/offer/123.html")
        manager.fetch("https://detail.1688.com/offer/456.html")
        assert calls[0][1] == calls[1][1]
        assert calls[0][1] != main_thread
    finally:
        manager.close()


def test_browser_failure_never_returns_mock(tmp_path, monkeypatch) -> None:
    manager = Alibaba1688BrowserManager(str(tmp_path))
    fail = Mock(side_effect=IntegrationError("需要手动登录"))
    monkeypatch.setattr(manager, "_fetch", fail)
    try:
        with pytest.raises(IntegrationError, match="手动登录"):
            manager.fetch("https://detail.1688.com/offer/123.html")
        assert manager.status()["status"] == "closed"
        assert fail.call_count == 1
    finally:
        manager.close()


def test_status_recovers_after_window_closed(tmp_path, monkeypatch) -> None:
    manager = Alibaba1688BrowserManager(str(tmp_path))
    page = Mock()
    page.wait_for_timeout.side_effect = RuntimeError("window closed")
    manager._page = page
    manager._opened = True
    try:
        assert manager.status()["status"] == "closed"
        assert manager._page is None
    finally:
        manager.close()
