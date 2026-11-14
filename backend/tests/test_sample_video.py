"""The sample project can use a local video (SAMPLE_VIDEO); only the bundled clip keeps its reference script."""

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


def test_default_sample_is_the_bundled_clip_with_its_script(client):
    settings = get_settings()
    assert settings.resolved_sample_video == settings.bundled_sample

    p = client.post("/api/projects/sample").json()

    assert p["filename"] == "sample_medina.mp4"
    with Session(get_engine()) as s:
        project = s.get(Project, p["id"])
        assert has_reference_script(project)
        assert sidecar_for(project, settings) == settings.samples_dir / "sample.transcript.json"
    client.delete(f"/api/projects/{p['id']}")


def test_missing_sample_video_returns_404(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "sample_video", "samples/local/introuvable.mp4")

    r = client.post("/api/projects/sample")

    assert r.status_code == 404 and "introuvable.mp4" in r.json()["detail"]
