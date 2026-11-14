from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import event, inspect, text
from sqlmodel import Session, SQLModel, create_engine

from .config import get_settings

_engine = None

# Columns removed from the models. Databases created before their removal still have them, often as
# NOT NULL without a default, which makes every INSERT fail: they are dropped at startup.
RETIRED_COLUMNS: dict[str, tuple[str, ...]] = {
    "project": ("voice_track_path",),  # full human voice track, removed with human voice recording
}


def get_engine():
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_engine(
            settings.db_url, connect_args={"check_same_thread": False, "timeout": 30}
        )

        @event.listens_for(_engine, "connect")
        def _pragma(dbapi_conn, _):  # noqa: ANN001
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA journal_mode=WAL")
            cur.close()

        from . import models  # noqa: F401 - register every table before create_all / migration

        SQLModel.metadata.create_all(_engine)
        _add_missing_columns(_engine)
        _drop_retired_columns(_engine)
    return _engine


def _add_missing_columns(engine) -> None:  # noqa: ANN001
    """Tiny forward-only migration: add columns introduced after a database was created."""
    insp = inspect(engine)
    with engine.begin() as conn:
        for table in SQLModel.metadata.sorted_tables:
            existing = {c["name"] for c in insp.get_columns(table.name)}
            for col in table.columns:
                if col.name in existing:
                    continue
                ddl = col.type.compile(dialect=engine.dialect)
                default = col.default.arg if col.default is not None and not callable(col.default.arg) else None
                suffix = f" DEFAULT {int(default) if isinstance(default, bool) else default!r}" if default is not None else ""
                conn.execute(text(f'ALTER TABLE "{table.name}" ADD COLUMN "{col.name}" {ddl}{suffix}'))


def _drop_retired_columns(engine) -> None:  # noqa: ANN001
    """Forward-only migration: drop the columns listed in RETIRED_COLUMNS (SQLite >= 3.35)."""
    insp = inspect(engine)
    tables = set(insp.get_table_names())
    with engine.begin() as conn:
        for table, columns in RETIRED_COLUMNS.items():
            if table not in tables:
                continue
            existing = {c["name"] for c in insp.get_columns(table)}
            for col in columns:
                if col in existing:
                    conn.execute(text(f'ALTER TABLE "{table}" DROP COLUMN "{col}"'))


def reset_engine() -> None:
    """Used by tests to point at a fresh data dir."""
    global _engine
    if _engine is not None:
        _engine.dispose()
    _engine = None


def get_session() -> Iterator[Session]:
    with Session(get_engine()) as session:
        yield session


@contextmanager
def session_scope() -> Iterator[Session]:
    with Session(get_engine()) as session:
        yield session
