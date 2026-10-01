from collections.abc import Sequence
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.models import Task


class TaskRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, task_type: str, payload: dict[str, Any]) -> Task:
        task = Task(task_type=task_type, payload=payload)
        self.session.add(task)
        self.session.commit()
        self.session.refresh(task)
        return task

    def get(self, task_id: int) -> Task:
        task = self.session.get(Task, task_id)
        if task is None:
            raise NotFoundError(f"任务 {task_id} 不存在")
        return task

    def list(
        self, *, status: str | None, task_type: str | None, limit: int
    ) -> tuple[Sequence[Task], int]:
        filters = []
        if status:
            filters.append(Task.status == status)
        if task_type:
            filters.append(Task.task_type == task_type)
        total = self.session.scalar(select(func.count(Task.id)).where(*filters)) or 0
        tasks = self.session.scalars(
            select(Task)
            .where(*filters)
            .order_by(Task.created_at.desc(), Task.id.desc())
            .limit(limit)
        ).all()
        return tasks, total

    def status_counts(self) -> dict[str, int]:
        rows = self.session.execute(
            select(Task.status, func.count(Task.id)).group_by(Task.status)
        ).all()
        counts = {status: 0 for status in ("pending", "running", "success", "failed", "cancelled")}
        counts.update({str(status): int(count) for status, count in rows})
        return counts

    def save(self, task: Task) -> Task:
        self.session.commit()
        self.session.refresh(task)
        return task

