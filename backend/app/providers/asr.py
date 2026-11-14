"""Speech recognition providers. Swap via ASR_PROVIDER / WHISPER_MODEL without touching the app.

WHISPER_MODEL accepts a faster-whisper size (tiny, base, small, medium, large-v3) or a
CTranslate2 Hugging Face repo id - e.g. a Tunisian/darija fine-tune converted with ct2.
"""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass, field
from pathlib import Path

from ..config import Settings

log = logging.getLogger("asr")


@dataclass
class ASRSegment:
    start: float
    end: float
    text: str


@dataclass
class ASRResult:
    segments: list[ASRSegment]
    language: str
    provider: str
    model: str
    notes: list[str] = field(default_factory=list)


class ASRProvider:
    name = "base"

    def transcribe(self, wav: Path, language: str | None = None, sidecar: Path | None = None) -> ASRResult:
        raise NotImplementedError


class DemoASR(ASRProvider):
    """Reads the reference transcript shipped next to the sample video, if any. Never invents dialogue."""

    name = "demo"

    def transcribe(self, wav: Path, language: str | None = None, sidecar: Path | None = None) -> ASRResult:
        if sidecar and sidecar.exists():
            data = json.loads(sidecar.read_text(encoding="utf-8"))
            segs = [ASRSegment(s["start"], s["end"], s["text"]) for s in data["segments"]]
            return ASRResult(segs, data.get("language", "fr"), "demo", "sidecar-transcript",
                             ["DEMO : transcription de référence du clip d'exemple (pas de modèle ASR)."])
        return ASRResult([], language or "und", "demo", "none",
                         ["DEMO : aucune transcription réelle disponible ; seuls les silences VAD sont utilisés."])


_model_lock = threading.Lock()
_models: dict[str, object] = {}


class WhisperASR(ASRProvider):
    name = "whisper"

    def __init__(self, settings: Settings):
        self.settings = settings

    def _model(self):
        from faster_whisper import WhisperModel

        key = f"{self.settings.whisper_model}:{self.settings.whisper_compute_type}"
        with _model_lock:
            if key not in _models:
                self.settings.models_dir.mkdir(parents=True, exist_ok=True)
                _models[key] = WhisperModel(
                    self.settings.whisper_model,
                    device=self.settings.whisper_device,
                    compute_type=self.settings.whisper_compute_type,
                    download_root=str(self.settings.models_dir / "whisper"),
                )
            return _models[key]

    def transcribe(self, wav: Path, language: str | None = None, sidecar: Path | None = None) -> ASRResult:
        model = self._model()
        lang = None if language in (None, "", "auto") else language
        segments, info = model.transcribe(str(wav), language=lang, vad_filter=True, beam_size=1, word_timestamps=True)
        segs = []
        for s in segments:
            if not s.text.strip():
                continue
            # word timestamps give much tighter boundaries than segment timestamps
            start = s.words[0].start if s.words else s.start
            end = s.words[-1].end if s.words else s.end
            segs.append(ASRSegment(round(start, 3), round(end, 3), s.text.strip()))
        return ASRResult(segs, info.language, "whisper", self.settings.whisper_model)


def get_asr(settings: Settings) -> list[ASRProvider]:
    """Ordered list of providers to try."""
    p = settings.asr_provider.lower()
    if p == "demo":
        return [DemoASR()]
    if p == "whisper":
        return [WhisperASR(settings)]
    return [WhisperASR(settings), DemoASR()]


def transcribe(settings: Settings, wav: Path, language: str | None, sidecar: Path | None) -> ASRResult:
    errors = []
    for provider in get_asr(settings):
        try:
            result = provider.transcribe(wav, language, sidecar)
            if errors:
                result.notes.insert(0, "Repli : " + " | ".join(errors))
            return result
        except Exception as exc:  # noqa: BLE001
            log.warning("ASR provider %s failed: %s", provider.name, exc)
            errors.append(f"{provider.name} indisponible ({str(exc)[:160]})")
    raise RuntimeError("Aucun fournisseur ASR disponible : " + " | ".join(errors))
