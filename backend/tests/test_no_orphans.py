"""A project creation that fails must not leave a copied video in data/projects/ (nothing references it)."""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from app.config import get_settings


def _folders():
    return {d.name for d in get_settings().projects_dir.iterdir()}


def _failing_commit(monkeypatch):
    def boom(self):  # noqa: ANN001 - same failure as the retired NOT NULL column
        raise IntegrityError("INSERT INTO project", {}, Exception("NOT NULL constraint failed"))

    monkeypatch.setattr(Session, "commit", boom)


def test_failed_sample_creation_leaves_no_folder(client, monkeypatch):
    before = _folders()
    _failing_commit(monkeypatch)

    with pytest.raises(IntegrityError):
        client.post("/api/projects/sample")

    assert _folders() == before


def test_failed_upload_leaves_no_folder(client, sample_video, monkeypatch):
    before = _folders()
    _failing_commit(monkeypatch)

    with sample_video.open("rb") as f, pytest.raises(IntegrityError):
        client.post("/api/projects", files={"file": ("film.mp4", f, "video/mp4")}, data={"title": "x", "consent": "true"})

    assert _folders() == before


def test_rejected_too_large_upload_leaves_no_folder(client, sample_video, monkeypatch):
    before = _folders()
    monkeypatch.setattr(get_settings(), "max_upload_mb", 0)

    with sample_video.open("rb") as f:
        r = client.post("/api/projects", files={"file": ("film.mp4", f, "video/mp4")}, data={"title": "x", "consent": "true"})

    assert r.status_code == 413
    assert _folders() == before
