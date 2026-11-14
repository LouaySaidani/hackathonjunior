"""A database created by an older version must keep working after columns are removed from the models."""

import sqlite3

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, SQLModel, create_engine

from app import db
from app.models import Project


def _old_database(path):
    """Current schema plus the retired column, NOT NULL without default, as older versions created it."""
    engine = create_engine(f"sqlite:///{path.as_posix()}")
    SQLModel.metadata.create_all(engine)
    with sqlite3.connect(path) as con:
        sql = con.execute("SELECT sql FROM sqlite_master WHERE name = 'project'").fetchone()[0]
        con.execute("DROP TABLE project")
        con.execute(sql.replace("(", "(voice_track_path VARCHAR NOT NULL, ", 1))  # columns before constraints
    return engine


def test_retired_not_null_column_is_dropped(tmp_path):
    engine = _old_database(tmp_path / "old.db")
    with Session(engine) as s, pytest.raises(IntegrityError):  # the bug: every new project failed
        s.add(Project(title="avant migration"))
        s.commit()

    db._drop_retired_columns(engine)

    with Session(engine) as s:
        s.add(Project(title="après migration"))
        s.commit()
    with sqlite3.connect(tmp_path / "old.db") as con:
        assert "voice_track_path" not in [r[1] for r in con.execute("PRAGMA table_info(project)")]


def test_dropping_is_a_no_op_on_a_current_database(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'new.db').as_posix()}")
    SQLModel.metadata.create_all(engine)

    db._drop_retired_columns(engine)
    db._drop_retired_columns(engine)  # idempotent
