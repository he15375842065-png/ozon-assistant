"""Synthetic shape fixtures only: these are not live 1688 collection evidence."""

from copy import deepcopy
import json

import pytest

from app.core.errors import IntegrationError
from app.integrations.sources.alibaba1688_parser import parse_1688_snapshot


OFFER_ID = "123456789012"
URL = f"https://detail.1688.com/offer/{OFFER_ID}.html"


@pytest.fixture
def offer_data() -> dict:
    return {
        "offerId": OFFER_ID,
        "subject": "纯棉运动袜 三双装",
        "description": "<p>纯棉材质</p><p>三双一组</p>",
        "categoryName": "服饰 > 袜子",
        "supplier": {"companyName": "示例袜业（合成 fixture）"},
        "images": ["//cbu01.alicdn.com/img/ibank/fixture-socks.jpg"],
        "attributes": [{"attributeName": "材质", "value": "棉"}],
        "shippingInfo": {"unitWeight": "0.15"},
        "skuInfos": [
            {
                "skuId": "sku-white",
                "attributes": [
                    {"attributeDisplayName": "颜色", "attributeValue": "白色"},
                    {"attributeDisplayName": "尺码", "attributeValue": "36-38"},
                ],
                "price": "8.50",
                "amountOnSale": "25",
                "skuImageUrl": "//cbu01.alicdn.com/img/ibank/fixture-white.jpg",
            },
            {
                "skuId": "sku-black",
                "attributes": [
                    {"attributeDisplayName": "颜色", "attributeValue": "黑色"},
                    {"attributeDisplayName": "尺码", "attributeValue": "39-41"},
                ],
                "price": "9.20",
                "amountOnSale": 0,
            },
        ],
    }


def snapshot(data: dict) -> dict:
    return {"url": URL, "title": "商品页面", "text": "", "html": "", "globals": {"offerData": data}}


def test_extracts_observed_title_images_and_each_sku(offer_data: dict) -> None:
    result = parse_1688_snapshot(snapshot(offer_data), URL)

    assert result["title"] == "纯棉运动袜 三双装"
    assert "收纳" not in result["title"]
    assert result["offer_id"] == OFFER_ID
    assert result["url"] == URL
    assert result["images"] == ["https://cbu01.alicdn.com/img/ibank/fixture-socks.jpg"]
    assert result["attributes"] == {"材质": "棉"}
    assert result["weight_kg"] == 0.15
    assert result["data_mode"] == "real"
    assert result["source_provider"] == "browser"
    assert result["skus"][0] == {
        "sku_id": "sku-white", "name": "白色 / 36-38", "color": "白色", "size": "36-38",
        "price": 8.5, "stock": 25,
        "image": "https://cbu01.alicdn.com/img/ibank/fixture-white.jpg",
    }
    assert result["skus"][1]["stock"] == 0
    assert result["skus"][1]["price"] == 9.2


def test_reads_matching_offer_in_nested_response(offer_data: dict) -> None:
    observation = snapshot({})
    observation["responses"] = [{"data": {"result": {"productInfo": offer_data}}}]
    result = parse_1688_snapshot(observation, URL)
    assert result["title"] == offer_data["subject"]


def test_reads_json_script_without_evaluating_javascript(offer_data: dict) -> None:
    observation = snapshot({})
    observation["scripts"] = ["window.offerData = " + json.dumps(offer_data) + "; alert('ignored')"]
    result = parse_1688_snapshot(observation, URL)
    assert result["skus"][0]["stock"] == 25


def test_reads_json_script_in_observed_html(offer_data: dict) -> None:
    observation = snapshot({})
    observation["html"] = '<script type="application/json">' + json.dumps(offer_data) + '</script>'
    assert parse_1688_snapshot(observation, URL)["title"] == offer_data["subject"]


def test_reads_sibling_modules_and_sku_map(offer_data: dict) -> None:
    product = {key: value for key, value in offer_data.items() if key != "skuInfos"}
    observation = snapshot({"offerId": OFFER_ID, "baseInfo": product, "skuModel": {
        "skuMap": {
            "白色;36-38": {"skuId": "actual-1", "price": 8.5, "canBookCount": 3},
            "黑色;39-41": {"skuId": "actual-2", "price": 9.2, "canBookCount": 7},
        },
    }})
    result = parse_1688_snapshot(observation, URL)
    assert [sku["name"] for sku in result["skus"]] == ["白色;36-38", "黑色;39-41"]
    assert [sku["stock"] for sku in result["skus"]] == [3, 7]


@pytest.mark.parametrize("missing", ["price", "amountOnSale", "skuId"])
def test_missing_required_sku_fact_fails_without_default(offer_data: dict, missing: str) -> None:
    del offer_data["skuInfos"][0][missing]
    with pytest.raises(IntegrationError, match="未保存商品"):
        parse_1688_snapshot(snapshot(offer_data), URL)


@pytest.mark.parametrize("value", ["面议", "2.00-3.00", -1, float("nan"), True])
def test_rejects_non_concrete_or_invalid_price(offer_data: dict, value: object) -> None:
    offer_data["skuInfos"][0]["price"] = value
    with pytest.raises(IntegrationError, match="价格"):
        parse_1688_snapshot(snapshot(offer_data), URL)


def test_rejects_fractional_stock(offer_data: dict) -> None:
    offer_data["skuInfos"][0]["amountOnSale"] = "2.5"
    with pytest.raises(IntegrationError, match="库存不是整数"):
        parse_1688_snapshot(snapshot(offer_data), URL)


def test_never_uses_recommendation_product_instead_of_requested_offer(offer_data: dict) -> None:
    other = deepcopy(offer_data)
    other["offerId"] = "999999999999"
    observation = snapshot({"recommendOfferList": [other]})
    with pytest.raises(IntegrationError, match="匹配"):
        parse_1688_snapshot(observation, URL)


def test_never_fills_missing_requested_sku_stock_from_another_product(offer_data: dict) -> None:
    other = deepcopy(offer_data)
    other["offerId"] = "999999999999"
    del offer_data["skuInfos"][0]["amountOnSale"]
    observation = snapshot({"offer": offer_data, "recommendations": [other]})
    with pytest.raises(IntegrationError, match="库存"):
        parse_1688_snapshot(observation, URL)


@pytest.mark.parametrize("change, message", [
    ({"url": URL + "/_____tmd_____/punish"}, "验证"),
    ({"html": '<script>window._config_={"action":"captcha"}</script>'}, "验证"),
    ({"url": "https://login.1688.com/member/signin.htm"}, "登录"),
    ({"text": "该商品已下架"}, "下架"),
    ({"url": "https://detail.1688.com/offer/999999999999.html"}, "当前页面"),
])
def test_access_and_identity_failures_are_explicit(offer_data: dict, change: dict, message: str) -> None:
    observation = {**snapshot(offer_data), **change}
    with pytest.raises(IntegrationError, match=message):
        parse_1688_snapshot(observation, URL)


def test_dom_title_alone_is_not_enough_to_claim_collection() -> None:
    observation = {"url": URL, "title": "袜子详情", "html": "<h1>纯棉袜子</h1>", "text": "¥8.5"}
    with pytest.raises(IntegrationError, match="未保存商品"):
        parse_1688_snapshot(observation, URL)


def test_missing_image_fails(offer_data: dict) -> None:
    del offer_data["images"]
    with pytest.raises(IntegrationError, match="图片"):
        parse_1688_snapshot(snapshot(offer_data), URL)


def test_sku_price_tiers_use_first_quantity_tier(offer_data: dict) -> None:
    del offer_data["skuInfos"][0]["price"]
    offer_data["skuInfos"][0]["priceRanges"] = [
        {"startQuantity": 100, "price": 5.8}, {"startQuantity": 3, "price": 8.5},
    ]
    assert parse_1688_snapshot(snapshot(offer_data), URL)["skus"][0]["price"] == 8.5


def test_product_price_does_not_replace_missing_sku_price(offer_data: dict) -> None:
    del offer_data["skuInfos"][0]["price"]
    offer_data["saleInfo"] = {"priceRanges": [{"startQuantity": 1, "price": 1.2}]}
    with pytest.raises(IntegrationError, match="SKU 采购价格"):
        parse_1688_snapshot(snapshot(offer_data), URL)


def test_unrelated_header_title_does_not_replace_missing_product_title(offer_data: dict) -> None:
    del offer_data["subject"]
    observation = snapshot({"offer": offer_data, "title": "站点页面标题"})
    with pytest.raises(IntegrationError, match="商品标题"):
        parse_1688_snapshot(observation, URL)


def test_ancestor_sibling_skus_are_never_borrowed_for_target_offer() -> None:
    observation = snapshot({"page": {
        "product": {
            "offerId": OFFER_ID, "subject": "袜子",
            "images": ["https://example.invalid/socks.jpg"],
        },
        "suggestedCards": {"skuInfos": [{
            "skuId": "BOX-SKU", "name": "box", "price": 28, "amountOnSale": 200,
        }]},
    }})
    with pytest.raises(IntegrationError, match="未保存商品"):
        parse_1688_snapshot(observation, URL)


def test_unidentified_sibling_modules_are_unsupported(offer_data: dict) -> None:
    product = {key: value for key, value in offer_data.items() if key != "skuInfos"}
    observation = snapshot({"baseInfo": product, "skuModel": {"skuInfos": offer_data["skuInfos"]}})
    with pytest.raises(IntegrationError, match="未保存商品"):
        parse_1688_snapshot(observation, URL)


def test_unknown_suggestion_section_inside_offer_is_not_product_data() -> None:
    observation = snapshot({
        "offerId": OFFER_ID, "subject": "袜子",
        "images": ["https://example.invalid/socks.jpg"],
        "suggestedCards": {"skuInfos": [{
            "skuId": "BOX-SKU", "name": "box", "price": 28, "amountOnSale": 200,
        }]},
    })
    with pytest.raises(IntegrationError, match="未保存商品"):
        parse_1688_snapshot(observation, URL)


def test_missing_title_error_reports_observed_page() -> None:
    data = {
        "offerId": OFFER_ID,
        "images": ["//cbu01.alicdn.com/img/ibank/fixture-socks.jpg"],
        "skuInfos": [{"skuId": "sku-1", "price": "8.50", "amountOnSale": "25"}],
    }
    observation = snapshot(data)
    observation["title"] = "1688"
    with pytest.raises(IntegrationError) as exc_info:
        parse_1688_snapshot(observation, URL)
    message = str(exc_info.value)
    assert "未读取到真实 1688 商品标题" in message
    assert "页面标题为「1688」" in message
