"""Voice activity detection and description-gap computation.

`compute_gaps` is a pure function (unit-tested): descriptions are only ever placed
inside these gaps, so they can never overlap dialogue.
"""

from __future__ import annotations

import wave
from pathlib import Path

Interval = tuple[float, float]


def merge_intervals(intervals: list[Interval], join_within: float = 0.0) -> list[Interval]:
    """Sort and merge overlapping (or nearly touching) intervals."""
    cleaned = sorted((min(a, b), max(a, b)) for a, b in intervals if a != b)
    merged: list[list[float]] = []
    for start, end in cleaned:
        if merged and start <= merged[-1][1] + join_within:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return [(round(a, 3), round(b, 3)) for a, b in merged]


def compute_gaps(
    speech: list[Interval],
    duration: float,
    min_gap: float = 1.5,
    padding: float = 0.25,
) -> list[Interval]:
    """Return silent intervals >= min_gap, shrunk by `padding` on each side touching speech.

    The padding is a safety margin so a description never starts/ends on top of a word.
    """
    if duration <= 0:
        return []
    speech = merge_intervals([(max(0.0, a), min(duration, b)) for a, b in speech])
    gaps: list[Interval] = []
    cursor = 0.0
    for s_start, s_end in speech + [(duration, duration)]:
        g_start = cursor + (padding if cursor > 0 else 0.0)
        g_end = s_start - (padding if s_start < duration else 0.0)
        if g_end - g_start >= min_gap:
            gaps.append((round(g_start, 3), round(g_end, 3)))
        cursor = max(cursor, s_end)
    return gaps


def overlaps(interval: Interval, speech: list[Interval], tolerance: float = 0.05) -> bool:
    a, b = interval
    return any(a < s_end - tolerance and b > s_start + tolerance for s_start, s_end in speech)


def _read_wav_mono16(path: Path) -> tuple[bytes, int]:
    with wave.open(str(path), "rb") as w:
        if w.getnchannels() != 1 or w.getsampwidth() != 2:
            raise ValueError("WAV mono 16-bit attendu")
        return w.readframes(w.getnframes()), w.getframerate()


def detect_speech_silero(wav_path: Path) -> list[Interval]:
    """Silero VAD (ONNX build shipped with faster-whisper, CPU, ~2 MB)."""
    import numpy as np
    from faster_whisper.vad import VadOptions, get_speech_timestamps

    pcm, sr = _read_wav_mono16(wav_path)
    audio = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
    if sr != 16000:
        raise ValueError("Silero attend du 16 kHz")
    opts = VadOptions(threshold=0.5, min_speech_duration_ms=200, min_silence_duration_ms=300, speech_pad_ms=100)
    stamps = get_speech_timestamps(audio, opts)
    return merge_intervals([(s["start"] / sr, s["end"] / sr) for s in stamps], join_within=0.2)


def detect_speech_webrtc(wav_path: Path, aggressiveness: int = 2) -> list[Interval]:
    import webrtcvad

    pcm, sr = _read_wav_mono16(wav_path)
    vad = webrtcvad.Vad(aggressiveness)
    frame_ms = 30
    n = int(sr * frame_ms / 1000) * 2
    voiced: list[Interval] = []
    for i in range(0, len(pcm) - n + 1, n):
        if vad.is_speech(pcm[i : i + n], sr):
            t = i / 2 / sr
            voiced.append((t, t + frame_ms / 1000))
    # smooth: join frames separated by < 300 ms, drop blips < 200 ms
    merged = merge_intervals(voiced, join_within=0.3)
    return [(a, b) for a, b in merged if b - a >= 0.2]


def detect_speech(wav_path: Path, engine: str = "silero") -> tuple[list[Interval], str]:
    if engine == "silero":
        try:
            return detect_speech_silero(wav_path), "silero"
        except Exception:  # noqa: BLE001 - fall back to webrtc
            pass
    return detect_speech_webrtc(wav_path), "webrtcvad"
