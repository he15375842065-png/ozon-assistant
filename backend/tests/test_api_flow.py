from collections.abc import Callable
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from app.core.errors import IntegrationError
from app.integrations.ai import MockAIProvider
from app.integrations.sources import Mock1688Provider


API = "/api/v1"
PRODUCT_URL = "https://detail.1688.com/offer/123456789.html"


def test_complete_mock_vertical_flow(client: TestClient) -> None:
    assert client.get(f"{API}/health").json()["status"] == "ok"
    initial = client.get(f"{API}/dashboard").json()
    assert initial["product_total"] == 0

    collected_response = client.post(f"{API}/products/collect", json={"url": PRODUCT_URL})
    assert collected_response.status_code == 201, collected_response.text
    collected = collected_response.json()
    product = collected["product"]
    product_id = product["id"]
    assert collected["task_id"] > 0
    assert product["source"] == "1688"
    assert product["source_product_id"] == "123456789"
    assert product["ai_status"] == "pending"
    assert product["ozon_status"] == "not_created"
    assert len(product["variants"]) == 2

    processed_response = client.post(f"{API}/products/{product_id}/process")
    assert processed_response.status_code == 200, processed_response.text
    processed = processed_response.json()
    draft_id = processed["draft_id"]
    assert processed["product"]["draft_id"] == draft_id
    assert processed["product"]["ai_status"] == "completed"
    assert processed["product"]["ozon_status"] == "review"
    assert processed["product"]["ai_result"]["title_ru"].startswith("Органайзер")
    assert processed["product"]["ai_result"]["attributes"]
    assert processed["product"]["ai_result"]["risks"]
    assert processed["product"]["estimated_price"] > 0
    assert processed["product"]["estimated_margin"] >= 25

    draft = client.get(f"{API}/drafts/{draft_id}").json()
    assert draft["status"] == "review"
    assert draft["category_id"] == "17028922"
    assert draft["suggested_price"] > draft["pricing"]["minimum_price_rub"]
    assert draft["profit_margin"] >= 25
    assert len(draft["skus"]) == 2
    assert draft["skus"][0]["sku"].startswith("OA-")

    update_response = client.patch(
        f"{API}/drafts/{draft_id}",
        json={
            "title_ru": "Органайзер настольный, 2 цвета",
            "suggested_price": 1999,
            "stock": 120,
        },
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["title_ru"] == "Органайзер настольный, 2 цвета"
    assert updated["suggested_price"] == 1999
    assert updated["status"] == "review"

    blocked = client.post(
        f"{API}/drafts/{draft_id}/publish", json={"confirmed": False}
    )
    assert blocked.status_code == 409
    assert "确认" in blocked.json()["error"]["message"]

    published_response = client.post(
        f"{API}/drafts/{draft_id}/publish", json={"confirmed": True}
    )
    assert published_response.status_code == 200, published_response.text
    published = published_response.json()["draft"]
    assert published["status"] == "published"
    assert published["publication_id"].startswith("MOCK-OZON-")
    assert published["published_at"] is not None

    final_dashboard = client.get(f"{API}/dashboard").json()
    assert final_dashboard["product_total"] == 1
    assert final_dashboard["pending_ai"] == 0
    assert final_dashboard["pending_review"] == 0
    assert final_dashboard["published"] == 1
    assert final_dashboard["task_counts"]["success"] == 3

    task_list = client.get(f"{API}/tasks").json()
    assert task_list["total"] == 3
    assert {item["type"] for item in task_list["items"]} == {
        "collect_product",
        "process_product",
        "publish_ozon",
    }
    log_list = client.get(f"{API}/logs").json()
    assert log_list["total"] >= 4
    assert all("api_key" not in item["message"].lower() for item in log_list["items"])


def test_recollect_updates_in_place_and_product_filters_work(client: TestClient) -> None:
    first = client.post(f"{API}/products/collect", json={"url": PRODUCT_URL}).json()
    second = client.post(f"{API}/products/collect", json={"url": PRODUCT_URL}).json()

    assert first["product"]["id"] == second["product"]["id"]
    products = client.get(f"{API}/products?search=收纳&page=1&page_size=10").json()
    assert products["total"] == 1
    assert products["pages"] == 1
    assert len(products["items"][0]["variants"]) == 2

    filtered_out = client.get(f"{API}/products?ai_status=completed").json()
    assert filtered_out["total"] == 0


def test_product_edit_delete_and_expected_errors(client: TestClient) -> None:
    invalid = client.post(
        f"{API}/products/collect", json={"url": "https://example.com/item/1"}
    )
    assert invalid.status_code == 422

    product = client.post(f"{API}/products/collect", json={"url": PRODUCT_URL}).json()[
        "product"
    ]
    product_id = product["id"]
    updated = client.patch(
        f"{API}/products/{product_id}",
        json={"title_original": "更新后的标题", "stock": 88},
    )
    assert updated.status_code == 200
    assert updated.json()["title_original"] == "更新后的标题"
    assert updated.json()["stock"] == 88

    deleted = client.delete(f"{API}/products/{product_id}")
    assert deleted.status_code == 204
    assert client.get(f"{API}/products/{product_id}").status_code == 404


def test_settings_never_expose_credentials(client: TestClient) -> None:
    settings = client.get(f"{API}/settings")
    assert settings.status_code == 200
    payload = settings.json()
    assert "ai_api_key" not in payload
    assert "ozon_api_key" not in payload
    assert payload["ai_api_key_configured"] is False

    update = client.patch(
        f"{API}/settings",
        json={
            "ai_model": "mock-v2",
            "ai_temperature": 0.4,
            "ai_api_key": "runtime-secret",
            "exchange_rate": 13.0,
            "target_margin": 30,
        },
    )
    assert update.status_code == 200
    assert update.json()["ai_model"] == "mock-v2"
    assert update.json()["ai_api_key_configured"] is True
    assert update.json()["exchange_rate"] == 13.0
    assert update.json()["target_margin"] == 30
    assert "runtime-secret" not in update.text


def test_settings_reject_impossible_pricing_atomically(client: TestClient) -> None:
    before = client.get(f"{API}/settings").json()

    update = client.patch(
        f"{API}/settings",
        json={
            "ai_model": "must-not-be-applied",
            "ozon_commission_rate": 90,
            "target_margin": 20,
        },
    )

    assert update.status_code == 422
    assert "定价设置无效" in update.json()["error"]["message"]
    assert client.get(f"{API}/settings").json() == before


def test_settings_reject_unimplemented_provider_modes(client: TestClient) -> None:
    before = client.get(f"{API}/settings").json()

    update = client.patch(
        f"{API}/settings",
        json={"ai_provider": "gemini", "source_provider": "browser", "ozon_mode": "real"},
    )

    assert update.status_code == 422
    assert client.get(f"{API}/settings").json() == before


def test_processing_uses_updated_runtime_pricing_settings(client: TestClient) -> None:
    product = client.post(f"{API}/products/collect", json={"url": PRODUCT_URL}).json()[
        "product"
    ]
    settings_update = client.patch(
        f"{API}/settings",
        json={
            "exchange_rate": 13,
            "domestic_shipping": 10,
            "international_shipping": 30,
            "ozon_commission_rate": 10,
            "target_margin": 20,
        },
    )
    assert settings_update.status_code == 200, settings_update.text

    processed = client.post(f"{API}/products/{product['id']}/process")
    assert processed.status_code == 200, processed.text
    draft = client.get(f"{API}/drafts/{processed.json()['draft_id']}").json()
    pricing = draft["pricing"]

    highest_variant_cost = max(item["purchase_price"] for item in product["variants"])
    expected_fixed_cny = highest_variant_cost + 10 + 30 + 2
    assert pricing["fixed_cost_cny"] == pytest.approx(expected_fixed_cny)
    assert pricing["fixed_cost_rub"] == pytest.approx(expected_fixed_cny * 13)
    assert pricing["variable_cost_rate"] == pytest.approx(0.24)
    assert pricing["target_profit_margin"] == pytest.approx(0.20)
    assert draft["profit_margin"] >= 20


def test_draft_price_and_stock_updates_remain_consistent(client: TestClient) -> None:
    product = client.post(f"{API}/products/collect", json={"url": PRODUCT_URL}).json()[
        "product"
    ]
    processed = client.post(f"{API}/products/{product['id']}/process").json()
    draft = client.get(f"{API}/drafts/{processed['draft_id']}").json()
    skus = deepcopy(draft["skus"])
    skus[0]["stock"] = 2
    skus[1]["stock"] = 5

    update = client.patch(
        f"{API}/drafts/{draft['id']}",
        json={"skus": skus, "suggested_price": 1999, "stock": 7},
    )
    assert update.status_code == 200, update.text
    updated = update.json()

    assert updated["suggested_price"] == 1999
    assert updated["stock"] == 7
    assert [sku["stock"] for sku in updated["skus"]] == [2, 5]
    assert all(sku["price"] == 1999 for sku in updated["skus"])

    pricing = updated["pricing"]
    expected_cost = pricing["fixed_cost_rub"] + 1999 * pricing["variable_cost_rate"]
    expected_profit = 1999 - expected_cost
    expected_margin = expected_profit / 1999
    assert pricing["suggested_price_rub"] == 1999
    assert pricing["estimated_total_cost_rub"] == pytest.approx(expected_cost, abs=0.01)
    assert pricing["estimated_profit_rub"] == pytest.approx(expected_profit, abs=0.01)
    assert pricing["estimated_profit_margin"] == pytest.approx(
        expected_margin, abs=0.0001
    )

    refreshed_product = client.get(f"{API}/products/{product['id']}").json()
    assert refreshed_product["estimated_price"] == 1999
    assert refreshed_product["estimated_margin"] == pytest.approx(
        round(pricing["estimated_profit_margin"] * 100, 2)
    )


def test_draft_rejects_inconsistent_total_and_sku_stock(client: TestClient) -> None:
    product = client.post(f"{API}/products/collect", json={"url": PRODUCT_URL}).json()[
        "product"
    ]
    draft_id = client.post(f"{API}/products/{product['id']}/process").json()["draft_id"]
    draft = client.get(f"{API}/drafts/{draft_id}").json()
    skus = deepcopy(draft["skus"])
    skus[0]["stock"] = 2
    skus[1]["stock"] = 5

    update = client.patch(
        f"{API}/drafts/{draft_id}", json={"skus": skus, "stock": 11}
    )

    assert update.status_code == 422
    assert "SKU 库存之和" in update.json()["error"]["message"]
    unchanged = client.get(f"{API}/drafts/{draft_id}").json()
    assert unchanged["skus"] == draft["skus"]
    assert unchanged["stock"] == draft["stock"]


@pytest.mark.parametrize(
    ("endpoint", "payload"),
    [
        ("product", {"title_original": None}),
        ("product", {"images": None}),
        ("draft", {"title_ru": None}),
        ("draft", {"skus": None}),
        ("settings", {"ai_model": None}),
        ("settings", {"target_margin": None}),
    ],
)
def test_patch_endpoints_reject_null_for_required_fields(
    client: TestClient, endpoint: str, payload: dict[str, object]
) -> None:
    product = client.post(f"{API}/products/collect", json={"url": PRODUCT_URL}).json()[
        "product"
    ]
    draft_id = client.post(f"{API}/products/{product['id']}/process").json()["draft_id"]
    target = {
        "product": f"{API}/products/{product['id']}",
        "draft": f"{API}/drafts/{draft_id}",
        "settings": f"{API}/settings",
    }[endpoint]

    response = client.patch(target, json=payload)

    assert response.status_code == 422


def test_publish_rejects_incomplete_review_draft(client: TestClient) -> None:
    product = client.post(f"{API}/products/collect", json={"url": PRODUCT_URL}).json()[
        "product"
    ]
    draft_id = client.post(f"{API}/products/{product['id']}/process").json()["draft_id"]
    cleared = client.patch(
        f"{API}/drafts/{draft_id}", json={"attributes": {}, "images": []}
    )
    assert cleared.status_code == 200, cleared.text

    publish = client.post(
        f"{API}/drafts/{draft_id}/publish", json={"confirmed": True}
    )

    assert publish.status_code == 422
    assert "属性" in publish.json()["error"]["message"]
    assert "图片" in publish.json()["error"]["message"]
    assert client.get(f"{API}/tasks").json()["total"] == 2


@pytest.mark.parametrize(
    ("endpoint", "payload"),
    [
        ("product", {"images": ["javascript:alert(1)"]}),
        ("draft", {"images": ["/relative/image.jpg"]}),
        ("settings", {"ai_base_url": "file:///tmp/provider"}),
        ("settings", {"ai_base_url": "https://key:secret@example.com/v1"}),
    ],
)
def test_patch_endpoints_reject_invalid_external_urls(
    client: TestClient, endpoint: str, payload: dict[str, object]
) -> None:
    product = client.post(f"{API}/products/collect", json={"url": PRODUCT_URL}).json()[
        "product"
    ]
    draft_id = client.post(f"{API}/products/{product['id']}/process").json()["draft_id"]
    target = {
        "product": f"{API}/products/{product['id']}",
        "draft": f"{API}/drafts/{draft_id}",
        "settings": f"{API}/settings",
    }[endpoint]

    response = client.patch(target, json=payload)

    assert response.status_code == 422


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        ("post", f"{API}/products/collect", {"url": PRODUCT_URL, "mode": "real"}),
        ("patch", f"{API}/settings", {"unknown_setting": True}),
    ],
)
def test_request_schemas_reject_unknown_fields(
    client: TestClient,
    method: str,
    path: str,
    payload: dict[str, object],
) -> None:
    response = client.request(method, path, json=payload)

    assert response.status_code == 422


@pytest.mark.parametrize(
    "mutate_skus",
    [
        lambda skus: [],
        lambda skus: [{**skus[0], "stock": -1}, *skus[1:]],
        lambda skus: [{**skus[0], "price": 0}, *skus[1:]],
        lambda skus: [{**skus[0]}, {**skus[1], "sku": skus[0]["sku"]}],
    ],
    ids=["empty", "negative-stock", "zero-price", "duplicate-sku"],
)
def test_draft_rejects_invalid_sku_updates(
    client: TestClient,
    mutate_skus: Callable[[list[dict[str, object]]], list[dict[str, object]]],
) -> None:
    product = client.post(f"{API}/products/collect", json={"url": PRODUCT_URL}).json()[
        "product"
    ]
    draft_id = client.post(f"{API}/products/{product['id']}/process").json()["draft_id"]
    draft = client.get(f"{API}/drafts/{draft_id}").json()

    invalid_skus = mutate_skus(deepcopy(draft["skus"]))
    update = client.patch(f"{API}/drafts/{draft_id}", json={"skus": invalid_skus})

    assert update.status_code == 422
    unchanged = client.get(f"{API}/drafts/{draft_id}").json()
    assert unchanged["skus"] == draft["skus"]
    assert unchanged["stock"] == draft["stock"]


def test_sku_only_update_cannot_diverge_from_global_draft_price(
    client: TestClient,
) -> None:
    product = client.post(f"{API}/products/collect", json={"url": PRODUCT_URL}).json()[
        "product"
    ]
    draft_id = client.post(f"{API}/products/{product['id']}/process").json()["draft_id"]
    draft = client.get(f"{API}/drafts/{draft_id}").json()
    skus = deepcopy(draft["skus"])
    skus[0]["price"] = draft["suggested_price"] + 500
    skus[1]["price"] = draft["suggested_price"] + 900

    update = client.patch(f"{API}/drafts/{draft_id}", json={"skus": skus})

    assert update.status_code == 200, update.text
    updated = update.json()
    assert updated["suggested_price"] == draft["suggested_price"]
    assert all(
        sku["price"] == draft["suggested_price"] for sku in updated["skus"]
    )


def test_unchanged_recollect_preserves_variant_identity_used_by_draft(
    client: TestClient,
) -> None:
    first = client.post(f"{API}/products/collect", json={"url": PRODUCT_URL}).json()[
        "product"
    ]
    initial_variant_ids = [variant["id"] for variant in first["variants"]]
    draft_id = client.post(f"{API}/products/{first['id']}/process").json()["draft_id"]
    draft_variant_ids = [
        sku["variant_id"]
        for sku in client.get(f"{API}/drafts/{draft_id}").json()["skus"]
    ]
    assert draft_variant_ids == initial_variant_ids

    other_url = "https://detail.1688.com/offer/987654321.html"
    other = client.post(f"{API}/products/collect", json={"url": other_url})
    assert other.status_code == 201, other.text

    recollected = client.post(f"{API}/products/collect", json={"url": PRODUCT_URL})
    assert recollected.status_code == 201, recollected.text
    current_variant_ids = [
        variant["id"] for variant in recollected.json()["product"]["variants"]
    ]

    assert current_variant_ids == initial_variant_ids
    assert [
        sku["variant_id"]
        for sku in client.get(f"{API}/drafts/{draft_id}").json()["skus"]
    ] == initial_variant_ids


def test_published_draft_is_immutable(client: TestClient) -> None:
    product = client.post(f"{API}/products/collect", json={"url": PRODUCT_URL}).json()[
        "product"
    ]
    draft_id = client.post(f"{API}/products/{product['id']}/process").json()["draft_id"]
    published = client.post(
        f"{API}/drafts/{draft_id}/publish", json={"confirmed": True}
    ).json()["draft"]

    update = client.patch(
        f"{API}/drafts/{draft_id}",
        json={"title_ru": "不应修改", "suggested_price": 999, "stock": 1},
    )

    assert update.status_code == 409
    unchanged = client.get(f"{API}/drafts/{draft_id}").json()
    for field in (
        "title_ru",
        "suggested_price",
        "stock",
        "skus",
        "pricing",
        "status",
        "publication_id",
    ):
        assert unchanged[field] == published[field]


def test_source_change_does_not_mutate_published_draft(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    product = client.post(f"{API}/products/collect", json={"url": PRODUCT_URL}).json()[
        "product"
    ]
    draft_id = client.post(f"{API}/products/{product['id']}/process").json()["draft_id"]
    published = client.post(
        f"{API}/drafts/{draft_id}/publish", json={"confirmed": True}
    ).json()["draft"]
    original_fetch = Mock1688Provider.fetch

    def changed_fetch(provider: Mock1688Provider, url: str) -> dict[str, object]:
        payload = original_fetch(provider, url)
        payload["title"] = f"{payload['title']}（新版）"
        payload["skus"][0]["stock"] += 7
        return payload

    monkeypatch.setattr(Mock1688Provider, "fetch", changed_fetch)
    recollected = client.post(f"{API}/products/collect", json={"url": PRODUCT_URL})
    assert recollected.status_code == 201, recollected.text
    refreshed_product = recollected.json()["product"]

    assert refreshed_product["ai_status"] == "pending"
    assert refreshed_product["ozon_status"] == "published"
    unchanged = client.get(f"{API}/drafts/{draft_id}").json()
    for field in (
        "title_ru",
        "suggested_price",
        "stock",
        "skus",
        "pricing",
        "status",
        "publication_id",
    ):
        assert unchanged[field] == published[field]


def test_reprocessing_published_product_keeps_published_and_review_visibility(
    client: TestClient,
) -> None:
    product = client.post(f"{API}/products/collect", json={"url": PRODUCT_URL}).json()[
        "product"
    ]
    published_draft_id = client.post(
        f"{API}/products/{product['id']}/process"
    ).json()["draft_id"]
    published = client.post(
        f"{API}/drafts/{published_draft_id}/publish", json={"confirmed": True}
    ).json()["draft"]

    reprocessed = client.post(f"{API}/products/{product['id']}/process")
    assert reprocessed.status_code == 200, reprocessed.text
    review_draft_id = reprocessed.json()["draft_id"]
    assert review_draft_id != published_draft_id
    assert reprocessed.json()["product"]["draft_id"] == review_draft_id
    assert reprocessed.json()["product"]["ozon_status"] == "published"
    assert client.get(f"{API}/drafts/{review_draft_id}").json()["status"] == "review"

    dashboard = client.get(f"{API}/dashboard").json()
    assert dashboard["published"] == 1
    assert dashboard["pending_review"] == 1
    assert client.get(f"{API}/products?ozon_status=published").json()["total"] == 1
    assert client.get(f"{API}/products?ozon_status=review").json()["total"] == 1

    unchanged = client.get(f"{API}/drafts/{published_draft_id}").json()
    for field in (
        "title_ru",
        "suggested_price",
        "stock",
        "skus",
        "pricing",
        "status",
        "publication_id",
    ):
        assert unchanged[field] == published[field]


def test_recollect_only_invalidates_downstream_when_source_facts_change(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    collected = client.post(f"{API}/products/collect", json={"url": PRODUCT_URL}).json()
    product_id = collected["product"]["id"]
    draft_id = client.post(f"{API}/products/{product_id}/process").json()["draft_id"]

    unchanged = client.post(f"{API}/products/collect", json={"url": PRODUCT_URL}).json()[
        "product"
    ]
    assert unchanged["ai_status"] == "completed"
    assert unchanged["ozon_status"] == "review"
    assert unchanged["draft_id"] == draft_id
    assert client.get(f"{API}/drafts/{draft_id}").json()["status"] == "review"

    original_fetch = Mock1688Provider.fetch

    def reordered_fetch(provider: Mock1688Provider, url: str) -> dict[str, object]:
        payload = original_fetch(provider, url)
        payload["skus"].reverse()
        return payload

    monkeypatch.setattr(Mock1688Provider, "fetch", reordered_fetch)
    reordered = client.post(f"{API}/products/collect", json={"url": PRODUCT_URL})
    assert reordered.status_code == 201, reordered.text
    assert reordered.json()["product"]["ai_status"] == "completed"
    assert reordered.json()["product"]["ozon_status"] == "review"
    assert client.get(f"{API}/drafts/{draft_id}").json()["status"] == "review"

    def changed_fetch(provider: Mock1688Provider, url: str) -> dict[str, object]:
        payload = original_fetch(provider, url)
        payload["title"] = f"{payload['title']}（供应商已更新）"
        return payload

    monkeypatch.setattr(Mock1688Provider, "fetch", changed_fetch)
    changed = client.post(f"{API}/products/collect", json={"url": PRODUCT_URL})
    assert changed.status_code == 201, changed.text
    changed_product = changed.json()["product"]

    assert changed_product["ai_status"] == "pending"
    assert changed_product["ozon_status"] == "not_created"
    assert changed_product["estimated_price"] is None
    assert changed_product["estimated_margin"] is None
    assert client.get(f"{API}/drafts/{draft_id}").json()["status"] == "stale"

    stale_update = client.patch(
        f"{API}/drafts/{draft_id}", json={"title_ru": "不能复用的过期草稿"}
    )
    stale_publish = client.post(
        f"{API}/drafts/{draft_id}/publish", json={"confirmed": True}
    )
    assert stale_update.status_code == 409
    assert stale_publish.status_code == 409

    reprocessed = client.post(f"{API}/products/{product_id}/process")
    assert reprocessed.status_code == 200, reprocessed.text
    assert reprocessed.json()["draft_id"] != draft_id
    assert client.get(f"{API}/drafts/{draft_id}").json()["status"] == "stale"


def test_product_stock_edit_keeps_variant_stock_in_sync(client: TestClient) -> None:
    product = client.post(f"{API}/products/collect", json={"url": PRODUCT_URL}).json()[
        "product"
    ]

    update = client.patch(f"{API}/products/{product['id']}", json={"stock": 11})

    assert update.status_code == 200, update.text
    updated = update.json()
    variant_stocks = [variant["stock"] for variant in updated["variants"]]
    assert updated["stock"] == 11
    assert sum(variant_stocks) == 11
    assert max(variant_stocks) - min(variant_stocks) <= 1

    processed = client.post(f"{API}/products/{product['id']}/process")
    assert processed.status_code == 200, processed.text
    draft = client.get(f"{API}/drafts/{processed.json()['draft_id']}").json()
    assert draft["stock"] == 11
    assert sum(sku["stock"] for sku in draft["skus"]) == 11


def test_ai_failure_is_auditable_without_exposing_credentials(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    product = client.post(f"{API}/products/collect", json={"url": PRODUCT_URL}).json()[
        "product"
    ]

    def fail_generation(
        provider: MockAIProvider, product_input: dict[str, object]
    ) -> None:
        del provider, product_input
        raise IntegrationError("provider rejected api_key=super-secret")

    monkeypatch.setattr(MockAIProvider, "generate_product", fail_generation)

    response = client.post(f"{API}/products/{product['id']}/process")

    assert response.status_code == 502
    assert "super-secret" not in response.text
    assert "***REDACTED***" in response.text
    refreshed = client.get(f"{API}/products/{product['id']}").json()
    assert refreshed["ai_status"] == "failed"
    assert refreshed["ai_result"]["status"] == "failed"
    assert "super-secret" not in refreshed["ai_result"]["error"]
    assert "***REDACTED***" in refreshed["ai_result"]["error"]

    tasks = client.get(f"{API}/tasks?task_type=process_product").json()["items"]
    assert tasks[0]["status"] == "failed"
    assert "super-secret" not in tasks[0]["error"]

    logs = client.get(f"{API}/logs?module=AI").json()["items"]
    assert logs[0]["level"] == "ERROR"
    assert "super-secret" not in str(logs[0]["context"])

