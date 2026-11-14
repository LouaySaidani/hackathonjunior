"""Gap relevance scoring: which silences deserve an audio description?

A small supervised model, trained on human audio descriptions (QuerYD / YouDescribe, see `ml/`),
scores every silence Basira finds. The *same* feature code runs at training time and inside the
app, so the model never sees features computed differently from the ones it was trained on.

Features are cheap and explainable (duration, surrounding dialogue, shot changes, motion,
sound level, spectral centroid). No faces, no identities: only 32x18 grayscale thumbnails and
frame-level audio energy are used.
"""

from __future__ import annotations

import json
import math
import subprocess
import wave
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import numpy as np

from .media import _bin

Interval = tuple[float, float]

FEATURES: list[str] = [
    # timing
    "duration", "log_duration", "duration_rank", "rel_position", "is_first", "is_last",
    # dialogue context
    "speech_before", "speech_after", "speech_density_30s", "prev_gap_duration", "next_gap_duration",
    # shot changes
    "cuts_in_gap", "cuts_per_sec", "cut_near_start", "cuts_prev_10s",
    # visual activity (32x18 grayscale thumbnails at 2 fps)
    "motion_mean", "motion_max", "brightness", "brightness_change", "visual_novelty",
    # sound inside the silence (music / effects / ambience)
    "audio_rms_db", "audio_rms_rel", "audio_active_frac", "audio_centroid",
]

FRAME_FPS = 2.0
THUMB_W, THUMB_H = 32, 18
AUDIO_HOP = 0.025  # 25 ms analysis frames


# ------------------------------------------------------------------ signal helpers -------------------

def gray_thumbnails(video: Path, fps: float = FRAME_FPS) -> np.ndarray:
    """(n, 18, 32) float32 in [0, 1]; frame i is at t = i / fps. Empty array if no video stream."""
    proc = subprocess.run(
        [_bin("ffmpeg"), "-v", "error", "-i", str(video), "-an", "-vf",
         f"fps={fps},scale={THUMB_W}:{THUMB_H},format=gray", "-f", "rawvideo", "-"],
        capture_output=True, timeout=3600,
    )
    size = THUMB_W * THUMB_H
    if proc.returncode != 0 or len(proc.stdout) < size:
        return np.zeros((0, THUMB_H, THUMB_W), dtype=np.float32)
    arr = np.frombuffer(proc.stdout, dtype=np.uint8)
    n = len(arr) // size
    return arr[: n * size].reshape(n, THUMB_H, THUMB_W).astype(np.float32) / 255.0


def audio_frames(wav_path: Path, hop_s: float = AUDIO_HOP) -> tuple[np.ndarray, np.ndarray]:
    """Per-frame RMS level (dBFS) and normalised spectral centroid (0..1), streamed in blocks."""
    rms_parts: list[np.ndarray] = []
    cen_parts: list[np.ndarray] = []
    with wave.open(str(wav_path), "rb") as w:
        if w.getnchannels() != 1 or w.getsampwidth() != 2:
            raise ValueError("WAV mono 16-bit attendu")
        sr = w.getframerate()
        hop = max(1, int(sr * hop_s))
        window = np.hanning(hop).astype(np.float32)
        freqs = np.fft.rfftfreq(hop, 1.0 / sr).astype(np.float32)
        while raw := w.readframes(hop * 4000):
            x = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
            m = len(x) // hop
            if m == 0:
                break
            fr = x[: m * hop].reshape(m, hop)
            rms_parts.append(np.sqrt((fr ** 2).mean(axis=1) + 1e-12))
            spec = np.abs(np.fft.rfft(fr * window, axis=1))
            cen_parts.append((spec * freqs).sum(axis=1) / (spec.sum(axis=1) + 1e-9) / (sr / 2))
    if not rms_parts:
        return np.zeros(0, dtype=np.float32), np.zeros(0, dtype=np.float32)
    return 20 * np.log10(np.concatenate(rms_parts)), np.concatenate(cen_parts)


def _covered(intervals: list[Interval], a: float, b: float) -> float:
    """Total length of `intervals` inside [a, b]."""
    return sum(max(0.0, min(b, e) - max(a, s)) for s, e in intervals)


def _slice(arr: np.ndarray, a: float, b: float, rate: float) -> np.ndarray:
    i, j = int(math.floor(a * rate)), int(math.ceil(b * rate))
    return arr[max(0, i): max(0, min(len(arr), j))]


# ------------------------------------------------------------------ features -------------------------

@dataclass
class MediaSignals:
    """Pre-computed per-video signals, so features for every gap come from one pass over the file."""

    duration: float
    speech: list[Interval]
    cuts: list[float]
    thumbs: np.ndarray = field(default_factory=lambda: np.zeros((0, THUMB_H, THUMB_W), dtype=np.float32))
    rms_db: np.ndarray = field(default_factory=lambda: np.zeros(0, dtype=np.float32))
    centroid: np.ndarray = field(default_factory=lambda: np.zeros(0, dtype=np.float32))

    @classmethod
    def from_files(cls, video: Path, wav: Path, duration: float, speech: list[Interval], cuts: list[float]):
        rms, cen = audio_frames(wav)
        return cls(duration, speech, cuts, gray_thumbnails(video), rms, cen)


def compute_gap_features(gaps: list[Interval], sig: MediaSignals) -> list[dict[str, float]]:
    """One feature dict per gap, keys = FEATURES (all finite floats)."""
    if not gaps:
        return []
    dur_all = np.array([b - a for a, b in gaps])
    order = dur_all.argsort().argsort()
    n = len(gaps)
    T = max(sig.duration, 1e-3)
    frame_rate = 1.0 / AUDIO_HOP
    level_ref = float(np.median(sig.rms_db)) if len(sig.rms_db) else -60.0
    noise_floor = float(np.percentile(sig.rms_db, 10)) if len(sig.rms_db) else -90.0
    thumbs = sig.thumbs
    diffs = np.abs(np.diff(thumbs, axis=0)).mean(axis=(1, 2)) if len(thumbs) > 1 else np.zeros(0)

    out: list[dict[str, float]] = []
    for i, (a, b) in enumerate(gaps):
        d = b - a
        mid = (a + b) / 2
        prev_end = gaps[i - 1][1] if i > 0 else 0.0
        next_start = gaps[i + 1][0] if i + 1 < n else T
        f: dict[str, float] = {
            "duration": d,
            "log_duration": math.log1p(d),
            "duration_rank": float(order[i]) / max(1, n - 1),
            "rel_position": mid / T,
            "is_first": float(i == 0),
            "is_last": float(i == n - 1),
            "speech_before": _covered(sig.speech, prev_end, a),
            "speech_after": _covered(sig.speech, b, next_start),
            "speech_density_30s": _covered(sig.speech, mid - 15, mid + 15) / 30.0,
            "prev_gap_duration": gaps[i - 1][1] - gaps[i - 1][0] if i > 0 else 0.0,
            "next_gap_duration": gaps[i + 1][1] - gaps[i + 1][0] if i + 1 < n else 0.0,
        }
        in_gap = [c for c in sig.cuts if a <= c <= b]
        f["cuts_in_gap"] = float(len(in_gap))
        f["cuts_per_sec"] = len(in_gap) / max(d, 1e-3)
        f["cut_near_start"] = float(any(a - 1.5 <= c <= a + 1.0 for c in sig.cuts))
        f["cuts_prev_10s"] = float(sum(1 for c in sig.cuts if a - 10 <= c < a))

        # visual activity
        mot = _slice(diffs, a, b, FRAME_FPS)
        fr = _slice(thumbs, a, b, FRAME_FPS)
        f["motion_mean"] = float(mot.mean()) if len(mot) else 0.0
        f["motion_max"] = float(mot.max()) if len(mot) else 0.0
        f["brightness"] = float(fr.mean()) if len(fr) else 0.0
        f["brightness_change"] = float(abs(fr[-1].mean() - fr[0].mean())) if len(fr) > 1 else 0.0
        mi, pi = int(mid * FRAME_FPS), int((mid - 5) * FRAME_FPS)
        if len(thumbs) and 0 <= pi and mi < len(thumbs):
            f["visual_novelty"] = float(np.abs(thumbs[mi] - thumbs[pi]).mean())
        else:
            f["visual_novelty"] = 0.0

        # sound inside the silence
        lv = _slice(sig.rms_db, a, b, frame_rate)
        cn = _slice(sig.centroid, a, b, frame_rate)
        if len(lv):
            active = lv > noise_floor + 10
            f["audio_rms_db"] = float(lv.mean())
            f["audio_rms_rel"] = float(lv.mean() - level_ref)
            f["audio_active_frac"] = float(active.mean())
            f["audio_centroid"] = float(cn[active].mean()) if active.any() else 0.0
        else:
            f.update(audio_rms_db=-90.0, audio_rms_rel=0.0, audio_active_frac=0.0, audio_centroid=0.0)

        out.append({k: (float(v) if math.isfinite(v) else 0.0) for k, v in f.items()})
    return out


def label_gaps(gaps: list[Interval], ad_starts: list[float], before: float = 1.0, after: float = 0.0) -> list[int]:
    """Number of human descriptions starting in each gap (tolerance: `before` s early, `after` s late)."""
    return [sum(1 for t in ad_starts if a - before <= t <= b + after) for a, b in gaps]


# ------------------------------------------------------------------ model ----------------------------

class GapScorer:
    """Wraps the trained scikit-learn pipeline saved by `ml/train.py`."""

    def __init__(self, model, meta: dict):
        self.model = model
        self.meta = meta
        self.features: list[str] = meta.get("features", FEATURES)
        self.threshold: float = float(meta.get("threshold", 0.5))

    @classmethod
    def load(cls, path: Path) -> GapScorer:
        import joblib  # scikit-learn dependency; imported lazily so the app runs without a model

        bundle = joblib.load(path)  # trusted local artifact produced by ml/train.py
        return cls(bundle["model"], bundle["meta"])

    def score(self, feats: list[dict[str, float]]) -> list[float]:
        if not feats:
            return []
        X = np.array([[f.get(k, 0.0) for k in self.features] for f in feats], dtype=np.float64)
        return [round(float(p), 4) for p in self.model.predict_proba(X)[:, 1]]


def select(scores: list[float], threshold: float) -> list[bool]:
    """Gaps at or above the threshold. Never returns an empty selection when gaps exist."""
    chosen = [s >= threshold for s in scores]
    if scores and not any(chosen):
        chosen[int(np.argmax(scores))] = True
    return chosen


@lru_cache(maxsize=4)
def _load_cached(path: str, mtime: float) -> GapScorer | None:
    try:
        return GapScorer.load(Path(path))
    except Exception:  # noqa: BLE001 - missing scikit-learn, corrupt or incompatible file: run without ML
        return None


def get_gap_scorer(model_path: Path) -> GapScorer | None:
    if not model_path.is_file():
        return None
    return _load_cached(str(model_path), model_path.stat().st_mtime)


def model_info(model_path: Path) -> dict | None:
    """Training metadata (sidecar JSON) for the UI, without loading the model."""
    meta = model_path.with_suffix(".json")
    if not model_path.is_file() or not meta.is_file():
        return None
    try:
        return json.loads(meta.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
