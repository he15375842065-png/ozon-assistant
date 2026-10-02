from collections.abc import Generator
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.base import Base


class Database:
    """Owns an SQLAlchemy engine and request-scoped session factory."""

    def __init__(self, url: str) -> None:
        self.url = url
        self._ensure_sqlite_parent(url)
        engine_options: dict[str, object] = {"pool_pre_ping": True}
        if url.startswith("sqlite"):
            engine_options["connect_args"] = {"check_same_thread": False}
        if url in {"sqlite://", "sqlite+pysqlite:///:memory:", "sqlite:///:memory:"}:
            engine_options["poolclass"] = StaticPool
        self.engine = create_engine(url, **engine_options)
        if url.startswith("sqlite"):
            self._enable_sqlite_foreign_keys(self.engine)
        self.session_factory = sessionmaker(
            bind=self.engine,
            class_=Session,
            expire_on_commit=False,
            autoflush=False,
        )

    @staticmethod
    def _ensure_sqlite_parent(url: str) -> None:
        prefix = "sqlite:///"
        if not url.startswith(prefix) or ":memory:" in url:
            return
        database_path = Path(url.removeprefix(prefix))
        database_path.parent.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _enable_sqlite_foreign_keys(engine: Engine) -> None:
        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_connection: object, _: object) -> None:
            cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    def create_schema(self) -> None:
        # Imports register all mapped tables on Base.metadata.
        from app.models import entities  # noqa: F401

        Base.metadata.create_all(bind=self.engine)

    def migrate(self) -> None:
        """Apply committed Alembic revisions using this database connection."""

        backend_root = Path(__file__).resolve().parents[2]
        alembic_config = Config(str(backend_root / "alembic.ini"))
        alembic_config.set_main_option("script_location", str(backend_root / "alembic"))
        alembic_config.set_main_option("sqlalchemy.url", self.url)
        with self.engine.begin() as connection:
            alembic_config.attributes["connection"] = connection
            command.upgrade(alembic_config, "head")

    def session(self) -> Generator[Session, None, None]:
        db_session = self.session_factory()
        try:
            yield db_session
        finally:
            db_session.close()

    def dispose(self) -> None:
        self.engine.dispose()

