from typing import Any

from app.integrations.ai.base import AIProductOutput, AIProvider, RiskCheck


class MockAIProvider(AIProvider):
    name = "mock"

    def __init__(self, model: str = "mock-product-processor-v1") -> None:
        self.model = model

    def generate_product(self, product: dict[str, Any]) -> AIProductOutput:
        material = str(product.get("attributes", {}).get("材质", "полипропилен"))
        return AIProductOutput(
            title_ru="Органайзер для косметики и мелочей, настольный",
            description_ru=(
                "Практичный органайзер с секциями для косметики, канцелярии и "
                "домашних мелочей. Прочный материал, лаконичный дизайн и удобный "
                "размер для спальни, ванной комнаты или рабочего стола."
            ),
            category_suggestion="Органайзеры для хранения",
            category_id_suggestion="17028922",
            category_confidence=0.93,
            attributes_suggestion={
                "material": material,
                "style": "минимализм",
                "purpose": "хранение косметики и мелочей",
                "country_of_origin": "Китай",
            },
            risk_level="low",
            risk_checks=[
                RiskCheck(
                    code="brand_claims",
                    level="low",
                    message="Брендовые и неподтвержденные заявления не обнаружены.",
                ),
                RiskCheck(
                    code="restricted_goods",
                    level="low",
                    message="Признаки товара с ограничениями не обнаружены.",
                ),
            ],
        )

