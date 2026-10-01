from datetime import datetime
from typing import Any

from pydantic import BaseModel


class TaskRead(BaseModel):
    id: int
    type: str
    status: str
    progress: int
    payload: dict[str, Any]
    result: dict[str, Any] | None
    error: str | None
    retries: int
    created_at: datetime
    started_at: datetime | None
    ended_at: datetime | None


class TaskList(BaseModel):
    items: list[TaskRead]
    total: int

