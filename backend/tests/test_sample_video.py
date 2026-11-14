"""The sample project video is configurable (SAMPLE_VIDEO); reference files are used only when they exist."""

import subprocess

from sqlmodel import Session

from app.config import get_settings
from app.db import get_engine
from app.models import Project
from app.service import has_reference_script, sidecar_for


def test_local_sample_video_replaces_the_bundled_clip(client, tmp_path, monkeypatch):
    video = tmp_path / "extrait.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc=size=160x120:rate=10:duration=3",
                    "-f", "lavfi", "-i", "sine=frequency=300:duration=3", "-shortest", str(video)], check=True)
    settings = get_settings()
    monkeypatch.setattr(settings, "sample_video", str(video))
    monkeypatch.setattr(settings, "sample_title", "Extrait de test")

    p = client.post("/api/projects/sample").json()

    assert p["title"] == "Extrait de test" and p["is_sample"] is True
    assert p["filename"] == "extrait.mp4" and 2.5 < p["duration"] < 3.5
    with Session(get_engine()) as s:
        project = s.get(Project, p["id"])
        # no hand-written transcript or script for a video they were not written for
        assert not has_reference_script(project)
        assert sidecar_for(project, settings) is None
    client.delete(f"/api/projects/{p['id']}")


def test_sample_with_reference_files_uses_them(client):
    """The test fixture ships <name>.transcript.json and <name>.script.json next to the video."""
    settings = get_settings()
    assert settings.resolved_sample_video.name == "sample_medina.mp4"

    p = client.post("/api/projects/sample").json()

    assert p["filename"] == "sample_medina.mp4"
    with Session(get_engine()) as s:
        project = s.get(Project, p["id"])
        assert has_reference_script(project)
        assert sidecar_for(project, settings) == settings.resolved_sample_video.with_suffix(".transcript.json")
    client.delete(f"/api/projects/{p['id']}")


def test_previous_sample_is_kept_as_an_ordinary_project(client, monkeypatch):
    """Changing SAMPLE_VIDEO never deletes the old sample: it becomes a normal project at startup."""
    from app.main import _startup

    old = client.post("/api/projects/sample").json()
    monkeypatch.setattr(get_settings(), "seed_sample", False)
    monkeypatch.setattr(get_settings(), "sample_video", "samples/vd_test.mp4")

    _startup()

    with Session(get_engine()) as s:
        project = s.get(Project, old["id"])
        assert project is not None and project.is_sample is False
    client.delete(f"/api/projects/{old['id']}")


def test_missing_sample_video_returns_404(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "sample_video", "samples/local/introuvable.mp4")

    r = client.post("/api/projects/sample")

    assert r.status_code == 404 and "introuvable.mp4" in r.json()["detail"]
