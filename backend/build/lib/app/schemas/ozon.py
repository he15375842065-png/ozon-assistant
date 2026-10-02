from pydantic import BaseModel, ConfigDict, Field


class OzonCheckRequest(BaseModel):
    """Connection test for the Ozon Seller API.

    Empty fields fall back to the current runtime settings, so the user can
    test credentials before saving them.
    """

    model_config = ConfigDict(extra="forbid")

    client_id: str | None = Field(default=None, max_length=120)
    api_key: str | None = Field(default=None, max_length=500)


class OzonCategoryRead(BaseModel):
    category_id: int
    name: str
    parent_category_id: int | None
    level: int
    attribute_count: int = 0


class OzonCategoryAttributeRead(BaseModel):
    attribute_id: int
    name: str
    is_required: bool
    attribute_type: str
    dictionary_size: int = 0
