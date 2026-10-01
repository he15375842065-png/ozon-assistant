from datetime import datetime
from typing import Any

from pydantic import BaseModel


class LogRead(BaseModel):
    id: int
    level: str
    module: str
    message: str
    context: dict[str, Any]
    created_at: datetime


class LogList(BaseModel):
    items: list[LogRead]
    total: int

