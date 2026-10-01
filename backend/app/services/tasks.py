from typing import Any

from app.core.errors import ConflictError
from app.core.security import sanitize_for_log
from app.database.base import utc_now
from app.models import Task
from app.repositories.tasks import TaskRepository


class TaskService:
    def __init__(self, repository: TaskRepository) -> None:
        self.repository = repository

    def create(self, task_type: str, payload: dict[str, Any]) -> Task:
        return self.repository.create(task_type, sanitize_for_log(payload))

    def start(self, task: Task, progress: int = 5) -> Task:
        task.status = "running"
        task.progress = progress
        task.started_at = utc_now()
        task.error = None
        return self.repository.save(task)

    def set_progress(self, task: Task, progress: int) -> Task:
        task.progress = max(0, min(100, progress))
        return self.repository.save(task)

    def succeed(self, task: Task, result: dict[str, Any]) -> Task:
        task.status = "success"
        task.progress = 100
        task.result = result
        task.finished_at = utc_now()
        return self.repository.save(task)

    def fail(self, task: Task, error: Exception | str) -> Task:
        task.status = "failed"
        task.error = str(sanitize_for_log(str(error)))
        task.finished_at = utc_now()
        return self.repository.save(task)

    def cancel(self, task_id: int) -> Task:
        task = self.repository.get(task_id)
        if task.status not in {"pending", "running"}:
            raise ConflictError("只能取消等待中或运行中的任务")
        task.status = "cancelled"
        task.finished_at = utc_now()
        return self.repository.save(task)

