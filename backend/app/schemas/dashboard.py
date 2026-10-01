from typing import Any

from pydantic import BaseModel

from app.schemas.logs import LogRead
from app.schemas.products import ProductRead


class DashboardRead(BaseModel):
    product_total: int
    pending_ai: int
    pending_review: int
    published: int
    task_counts: dict[str, int]
    recent_products: list[ProductRead]
    recent_errors: list[LogRead]
    system_status: dict[str, Any]
