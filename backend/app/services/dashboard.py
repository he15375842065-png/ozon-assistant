from app.repositories.logs import LogRepository
from app.repositories.products import ProductRepository
from app.repositories.tasks import TaskRepository
from app.schemas.dashboard import DashboardRead
from app.services.presenters import present_log, present_product


class DashboardService:
    def __init__(
        self,
        products: ProductRepository,
        tasks: TaskRepository,
        logs: LogRepository,
        *,
        provider_status: dict[str, object],
    ) -> None:
        self.products = products
        self.tasks = tasks
        self.logs = logs
        self.provider_status = provider_status

    def get(self) -> DashboardRead:
        counts = self.products.counts()
        return DashboardRead(
            **counts,
            task_counts=self.tasks.status_counts(),
            recent_products=[present_product(item) for item in self.products.recent(5)],
            recent_errors=[present_log(item) for item in self.logs.recent_errors(5)],
            system_status=self.provider_status,
        )
