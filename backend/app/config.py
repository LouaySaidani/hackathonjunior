"""Application settings, read exclusively from environment variables (.env supported).

Secrets (API keys) live only here, on the server side. They are never sent to the frontend.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    # Root .env first, then the CWD one (later files take priority), so `cd backend && uvicorn ...` works too.
    model_config = SettingsConfigDict(env_file=(ROOT_DIR / ".env", ".env"), env_file_encoding="utf-8", extra="ignore")

    # --- storage ---
    data_dir: Path = ROOT_DIR / "data"
    models_dir: Path = ROOT_DIR / "models"
    samples_dir: Path = ROOT_DIR / "samples"
    frontend_dist: Path = ROOT_DIR / "frontend" / "dist"
    max_upload_mb: int = 500
    seed_sample: bool = True
    # Video of the sample project (relative to the repo root). If <name>.transcript.json and
    # <name>.script.json sit next to it, DEMO MODE uses them instead of a generic placeholder.
    sample_video: str = "samples/vd_test.mp4"
    sample_title: str = "Exemple — extrait de film (test)"

    # --- AI providers ---
    # ASR: whisper | demo | auto (whisper, fallback to demo if the model cannot be loaded)
    asr_provider: str = "auto"
    whisper_model: str = "small"  # any faster-whisper size or a HF repo id (e.g. a Tunisian fine-tune)
    whisper_compute_type: str = "int8"
    whisper_device: str = "cpu"

    # VLM / LLM for drafting: gemini | openai | demo | auto (gemini if key, openai if key, else demo)
    vlm_provider: str = "auto"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.6-flash"
    # tried in order when the previous model's daily quota is exhausted (free tier: ~20 requests/day/model)
    gemini_fallback_models: str = "gemini-3.5-flash-lite,gemini-flash-lite-latest"
    vlm_batch_size: int = 8  # silent slots described per request (saves quota)
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"

    # TTS: edge | espeak | demo | auto (edge -> espeak -> demo)
    tts_provider: str = "auto"
    tts_voice_fr: str = "fr-FR-DeniseNeural"
    tts_voice_ar: str = "ar-TN-ReemNeural"

    # --- pipeline tuning ---
    vad_engine: str = "silero"  # silero | webrtc
    min_gap_seconds: float = 1.5
    gap_padding_seconds: float = 0.25
    max_slot_seconds: float = 10.0  # long silences are split into slots (at shot changes); 0 = never split
    scene_threshold: float = 0.3
    max_keyframes_per_gap: int = 3
    duck_volume: float = 0.25
    confidence_threshold: float = 0.6

    # --- ML gap selection (model trained by ml/train.py on human audio descriptions) ---
    # auto: use the model if a trained file exists, otherwise draft every gap | model | all
    gap_selection: str = "auto"
    gap_model_path: Path = ROOT_DIR / "ml" / "artifacts" / "gap_scorer.joblib"
    gap_score_threshold: float = 0.0  # 0 = use the threshold chosen during training

    @property
    def resolved_sample_video(self) -> Path:
        path = Path(self.sample_video)
        return path if path.is_absolute() else ROOT_DIR / path

    @property
    def sample_transcript(self) -> Path:
        """Hand-written reference transcript of the sample video, used by the `demo` ASR provider."""
        return self.resolved_sample_video.with_suffix(".transcript.json")

    @property
    def sample_script(self) -> Path:
        """Hand-written reference audio description of the sample video, used by the `demo` VLM."""
        return self.resolved_sample_video.with_suffix(".script.json")

    @property
    def projects_dir(self) -> Path:
        return self.data_dir / "projects"

    @property
    def db_url(self) -> str:
        return f"sqlite:///{(self.data_dir / 'app.db').as_posix()}"

    def resolved_vlm_provider(self) -> str:
        p = self.vlm_provider.lower()
        if p != "auto":
            return p
        if self.gemini_api_key:
            return "gemini"
        if self.openai_api_key:
            return "openai"
        return "demo"

    @property
    def demo_mode(self) -> bool:
        """DEMO MODE = the visual-understanding/drafting model is mocked."""
        return self.resolved_vlm_provider() == "demo"


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    s.data_dir.mkdir(parents=True, exist_ok=True)
    s.projects_dir.mkdir(parents=True, exist_ok=True)
    return s
