from collections.abc import Sequence
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import sanitize_for_log
from app.models import AppLog


class LogRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(
        self, level: str, source: str, message: str, context: dict[str, Any] | None = None
    ) -> AppLog:
        log = AppLog(
            level=level.upper(),
            source=source,
            message=str(sanitize_for_log(message)),
            context=sanitize_for_log(context or {}),
        )
        self.session.add(log)
        self.session.commit()
        self.session.refresh(log)
        return log

    def list(
        self, *, level: str | None, source: str | None, limit: int
    ) -> tuple[Sequence[AppLog], int]:
        filters = []
        if level:
            filters.append(AppLog.level == level.upper())
        if source:
            filters.append(AppLog.source == source)
        total = self.session.scalar(select(func.count(AppLog.id)).where(*filters)) or 0
        logs = self.session.scalars(
            select(AppLog)
            .where(*filters)
            .order_by(AppLog.created_at.desc(), AppLog.id.desc())
            .limit(limit)
        ).all()
        return logs, total

    def recent_errors(self, limit: int = 5) -> Sequence[AppLog]:
        return self.session.scalars(
            select(AppLog)
            .where(AppLog.level == "ERROR")
            .order_by(AppLog.created_at.desc(), AppLog.id.desc())
            .limit(limit)
        ).all()
