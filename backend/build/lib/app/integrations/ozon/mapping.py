from typing import Any

from app.integrations.ai.base import AIProductOutput


class OzonCategoryMapper:
    """Maps an AI suggestion to an editable Ozon category proposal."""

    def map(self, ai_output: AIProductOutput) -> tuple[str, str]:
        return ai_output.category_id_suggestion, ai_output.category_suggestion


class OzonAttributeMapper:
    _KEYS = {
        "material": "Материал",
        "style": "Стиль",
        "purpose": "Назначение",
        "country_of_origin": "Страна-изготовитель",
    }

    def map(self, ai_output: AIProductOutput) -> dict[str, Any]:
        return {
            self._KEYS.get(key, key): value
            for key, value in ai_output.attributes_suggestion.items()
        }

