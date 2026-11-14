import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
# Synthetic CC0 clip with a reference transcript and script: tests assert exact values on it.
FIXTURE_SAMPLE = Path(__file__).resolve().parent / "fixtures" / "sample_medina.mp4"


@pytest.fixture(scope="session", autouse=True)
def _env(tmp_path_factory):
    data = tmp_path_factory.mktemp("data")
    os.environ.update(
        DATA_DIR=str(data),
        MODELS_DIR=str(tmp_path_factory.mktemp("models")),
        ASR_PROVIDER="demo",
        VLM_PROVIDER="demo",
        TTS_PROVIDER="demo",
        SEED_SAMPLE="false",
        GEMINI_API_KEY="",
        OPENAI_API_KEY="",
        GAP_SELECTION="all",  # deterministic: a trained model in ml/artifacts must not change these tests
        SAMPLE_VIDEO=str(FIXTURE_SAMPLE),  # the app's own sample video (samples/) is for people, not tests
    )
    from app.config import get_settings
    from app.db import reset_engine

    get_settings.cache_clear()
    reset_engine()
    yield
    shutil.rmtree(data, ignore_errors=True)


@pytest.fixture(scope="session")
def client(_env):
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def sample_video() -> Path:
    return FIXTURE_SAMPLE


@pytest.fixture()
def tone_wav(tmp_path) -> Path:
    out = tmp_path / "voice.wav"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=300:duration=1.2", str(out)],
                   check=True)
    return out
