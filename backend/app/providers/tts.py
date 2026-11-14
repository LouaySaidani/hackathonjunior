"""Text-to-speech providers: edge (neural, needs internet) | espeak (offline) | demo (tone placeholder).

Arabic / darija quality varies: the UI always offers a human-recorded voice upload as fallback.
"""

from __future__ import annotations

import asyncio
import logging
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from ..config import Settings
from ..pipeline.fit import estimate_seconds
from ..pipeline.media import run

log = logging.getLogger("tts")

ESPEAK_VOICES = {"fr": "fr", "ar": "ar", "aeb": "ar", "en": "en"}


@dataclass
class TTSResult:
    path: Path
    provider: str
    voice: str
    warning: str = ""


class TTSProvider:
    name = "base"

    def synthesize(self, text: str, language: str, out: Path) -> TTSResult:
        raise NotImplementedError


class EdgeTTS(TTSProvider):
    name = "edge"

    def __init__(self, settings: Settings):
        self.voices = {"fr": settings.tts_voice_fr, "ar": settings.tts_voice_ar,
                       "aeb": settings.tts_voice_ar, "en": settings.tts_voice_en}

    def synthesize(self, text: str, language: str, out: Path) -> TTSResult:
        import edge_tts

        voice = self.voices.get(language, self.voices["fr"])
        mp3 = out.with_suffix(".mp3")

        async def _go():
            await edge_tts.Communicate(text, voice).save(str(mp3))

        asyncio.run(asyncio.wait_for(_go(), timeout=40))
        if not mp3.exists() or mp3.stat().st_size < 500:
            raise RuntimeError("edge-tts n'a renvoyé aucun audio")
        warning = ""
        if language == "aeb":
            warning = ("Voix synthétique arabe tunisienne lisant du darija : la prononciation peut être "
                       "approximative. Une voix humaine enregistrée est recommandée.")
        return TTSResult(mp3, self.name, voice, warning)


class EspeakTTS(TTSProvider):
    name = "espeak"

    def synthesize(self, text: str, language: str, out: Path) -> TTSResult:
        exe = shutil.which("espeak-ng") or shutil.which("espeak")
        if not exe:
            raise RuntimeError("espeak-ng non installé")
        voice = ESPEAK_VOICES.get(language, "fr")
        wav = out.with_suffix(".wav")
        subprocess.run([exe, "-v", voice, "-s", "160", "-w", str(wav), text], check=True, capture_output=True, timeout=60)
        warning = "Voix robotique hors-ligne (espeak-ng)." + (
            " Qualité arabe limitée : une voix humaine est recommandée." if language in ("ar", "aeb") else "")
        return TTSResult(wav, self.name, f"espeak-ng:{voice}", warning)


class DemoTTS(TTSProvider):
    """Placeholder tone of the estimated spoken duration. Clearly labelled: no speech is produced."""

    name = "demo"

    def synthesize(self, text: str, language: str, out: Path) -> TTSResult:
        dur = estimate_seconds(text, language)
        wav = out.with_suffix(".wav")
        run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"sine=frequency=440:duration={dur:.2f}",
             "-af", "volume=0.15,afade=t=in:d=0.1,afade=t=out:st=" + f"{max(0.0, dur - 0.2):.2f}:d=0.2", str(wav)])
        return TTSResult(wav, self.name, "demo-tone",
                         "DEMO : bip de substitution (aucune synthèse vocale disponible). Enregistrez une voix humaine.")


def get_tts_chain(settings: Settings) -> list[TTSProvider]:
    p = settings.tts_provider.lower()
    if p == "edge":
        return [EdgeTTS(settings)]
    if p == "espeak":
        return [EspeakTTS()]
    if p == "demo":
        return [DemoTTS()]
    return [EdgeTTS(settings), EspeakTTS(), DemoTTS()]


def synthesize(settings: Settings, text: str, language: str, out: Path) -> TTSResult:
    errors = []
    for provider in get_tts_chain(settings):
        try:
            result = provider.synthesize(text, language, out)
            if errors and not result.warning:
                result.warning = "Repli : " + " | ".join(errors)
            return result
        except Exception as exc:  # noqa: BLE001
            log.warning("TTS %s failed: %s", provider.name, exc)
            errors.append(f"{provider.name}: {str(exc)[:120]}")
    raise RuntimeError("Aucune synthèse vocale disponible : " + " | ".join(errors))
