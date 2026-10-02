from copy import deepcopy
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.errors import IntegrationError
from app.integrations.ai import MockAIProvider
from app.integrations.sources import Alibaba1688Adapter, Browser1688Provider, Mock1688Provider
from app.models import SourceProduct
from app.repositories import ProductRepository


API = "/api/v1"
URL = "https://detail.1688.com/offer/123456789.html"


def socks_payload(url: str = URL) -> dict[str, Any]:
    """Synthetic extraction result: no network or live site is used in these tests."""
    return {
        "provider": "browser_1688",
        "mock": False,
        "source": "1688",
        "offer_id": "123456789",
        "url": url,
        "title": "纯棉运动袜",
        "description": "纯棉运动袜，黑色中筒",
        "supplier": "测试袜子供应商",
        "category": "服装 > 袜子",
        "currency": "CNY",
        "images": ["https://cbu01.alicdn.com/img/ibank/synthetic-socks.jpg"],
        "attributes": {"材质": "棉"},
        "skus": [{"sku_id": "sock-black", "name": "黑色 / 均码", "price": 2.5, "stock": 20}],
    }


def stub_browser(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Browser1688Provider, "fetch", lambda self, url: socks_payload(url))


def test_settings_default_to_real_browser() -> None:
    assert Settings(_env_file=None).source_provider == "browser"


def test_url_credentials_rejected_before_any_task_is_created(client: TestClient) -> None:
    response = client.post(f"{API}/products/collect", json={"url": "https://user:password@detail.1688.com/offer/123.html"})
    assert response.status_code == 422
    assert client.get(f"{API}/tasks").json()["total"] == 0
    assert client.get(f"{API}/logs").json()["total"] == 0


def test_tracking_query_not_persisted(client: TestClient) -> None:
    response = client.post(f"{API}/products/collect", json={"url": URL + "?token=synthetic-secret", "mode": "mock"})
    assert response.status_code == 201
    assert response.json()["product"]["source_url"] == URL
    assert "synthetic-secret" not in str(client.get(f"{API}/tasks").json())
    assert "synthetic-secret" not in str(client.get(f"{API}/logs").json())


def test_collect_defaults_to_real_even_when_settings_are_mock(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert client.app.state.settings.source_provider == "mock"
    stub_browser(monkeypatch)

    def forbid_mock(self: Mock1688Provider, url: str) -> dict[str, Any]:
        raise AssertionError("real request must never invoke Mock1688Provider")

    monkeypatch.setattr(Mock1688Provider, "fetch", forbid_mock)
    response = client.post(f"{API}/products/collect", json={"url": URL})

    assert response.status_code == 201, response.text
    result = response.json()
    assert result["collection_mode"] == "real"
    assert result["product"]["title_original"] == "纯棉运动袜"
    assert result["product"]["source"] == "1688"
    assert result["product"]["data_kind"] == "real"
    assert result["product"]["data_provider"] == "browser_1688"
    tasks = client.get(f"{API}/tasks").json()["items"]
    assert tasks[0]["payload"]["collection_mode"] == "real"
    assert tasks[0]["result"]["mock"] is False


def test_real_failure_does_not_fall_back_or_save_sample(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def unavailable(self: Browser1688Provider, url: str) -> dict[str, Any]:
        raise IntegrationError("请先在采集浏览器登录1688")

    def forbid_mock(self: Mock1688Provider, url: str) -> dict[str, Any]:
        raise AssertionError("a failure must not use sample data")

    monkeypatch.setattr(Browser1688Provider, "fetch", unavailable)
    monkeypatch.setattr(Mock1688Provider, "fetch", forbid_mock)
    response = client.post(f"{API}/products/collect", json={"url": URL, "mode": "real"})

    assert response.status_code == 502
    assert "登录" in response.json()["message"]
    assert client.get(f"{API}/products").json()["total"] == 0
    task = client.get(f"{API}/tasks").json()["items"][0]
    assert task["status"] == "failed"
    assert task["payload"]["mock"] is False


def test_real_request_rejects_sample_provenance(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    sample = Mock1688Provider().fetch(URL)
    monkeypatch.setattr(Browser1688Provider, "fetch", lambda self, url: deepcopy(sample))

    response = client.post(f"{API}/products/collect", json={"url": URL})

    assert response.status_code == 502
    assert "来源" in response.json()["message"]
    assert client.get(f"{API}/products").json()["total"] == 0


def test_real_and_mock_products_for_same_offer_are_isolated(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    sample = client.post(f"{API}/products/collect", json={"url": URL, "mode": "mock"}).json()["product"]
    stub_browser(monkeypatch)
    real = client.post(f"{API}/products/collect", json={"url": URL}).json()["product"]

    assert real["id"] != sample["id"]
    assert real["title_original"] == "纯棉运动袜"
    assert client.get(f"{API}/products/{sample['id']}").json() == sample
    assert client.get(f"{API}/products").json()["total"] == 2


def test_legacy_unmarked_mock_is_preserved_on_real_collection(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    legacy = Alibaba1688Adapter(Mock1688Provider()).collect(URL)
    legacy.source = "1688"
    legacy.raw_payload = {key: value for key, value in legacy.raw_payload.items() if key not in {"mock", "provider", "source"}}
    with client.app.state.database.session_factory() as session:
        sample_id = ProductRepository(session).save_collected(legacy).id
    before = client.get(f"{API}/products/{sample_id}").json()
    assert before["data_kind"] == "mock"
    assert before["data_provider"] == "mock_1688"
    stub_browser(monkeypatch)

    response = client.post(f"{API}/products/collect", json={"url": URL})

    assert response.status_code == 201, response.text
    assert response.json()["product"]["id"] != sample_id
    preserved = client.get(f"{API}/products/{sample_id}").json()
    assert preserved["source"] == "mock_1688"
    assert preserved["title_original"] == before["title_original"]
    assert preserved["variants"] == before["variants"]
    assert preserved["data_kind"] == "mock"
    assert client.get(f"{API}/products").json()["total"] == 2


def test_legacy_collision_fails_without_overwriting_either_sample(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    sample = client.post(f"{API}/products/collect", json={"url": URL, "mode": "mock"}).json()["product"]
    payload = Mock1688Provider().fetch(URL)
    with client.app.state.database.session_factory() as session:
        session.add(SourceProduct(source="1688", source_product_id="123456789", source_url=URL, raw_payload=payload))
        session.commit()
    stub_browser(monkeypatch)

    response = client.post(f"{API}/products/collect", json={"url": URL})

    assert response.status_code == 409
    assert "重复" in response.json()["message"]
    assert client.get(f"{API}/products/{sample['id']}").json() == sample
    assert client.get(f"{API}/tasks").json()["items"][0]["status"] == "failed"


def test_real_product_cannot_be_processed_by_mock_ai(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    stub_browser(monkeypatch)
    product = client.post(f"{API}/products/collect", json={"url": URL}).json()["product"]

    def forbid_generation(self: MockAIProvider, value: dict[str, Any]) -> None:
        raise AssertionError("mock AI must not fabricate translations for real products")

    monkeypatch.setattr(MockAIProvider, "generate_product", forbid_generation)
    response = client.post(f"{API}/products/{product['id']}/process")

    assert response.status_code == 409, response.text
    assert "模拟 AI" in response.json()["message"]
    saved = client.get(f"{API}/products/{product['id']}").json()
    assert saved["title_original"] == "纯棉运动袜"
    assert saved["ai_status"] == "failed"
    assert saved["ai_result"]["title_ru"] == ""
    assert client.get(f"{API}/drafts").json()["total"] == 0


def test_browser_login_endpoints_use_manager_without_launching_live_site(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    opened: list[str | None] = []

    class FakeManager:
        def open_browser(self, url: str | None) -> dict[str, str]:
            opened.append(url)
            return {"status": "opened", "message": "请手动登录"}

        def status(self) -> dict[str, str]:
            return {"status": "opened", "message": "已打开"}

    monkeypatch.setattr("app.integrations.sources.browser_1688.get_browser_manager", lambda settings: FakeManager())

    response = client.post(f"{API}/sources/1688/browser/open", json={})
    assert response.status_code == 200
    assert response.json()["status"] == "opened"
    assert opened == [None]
    assert client.get(f"{API}/sources/1688/browser/status").json()["status"] == "opened"


def test_browser_mode_can_be_selected_in_settings(client: TestClient) -> None:
    response = client.patch(f"{API}/settings", json={"source_provider": "browser"})
    assert response.status_code == 200
    assert response.json()["source_provider"] == "browser"
    assert response.json()["source_browser_profile"]
    assert "real_ai_providers" in client.get(f"{API}/features").json()["planned"]
