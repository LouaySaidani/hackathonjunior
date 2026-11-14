"""FFmpeg / ffprobe helpers. Only the audio track, speech gaps and a few keyframes are processed."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

ALLOWED_EXTENSIONS = {".mp4", ".mov", ".mkv", ".m4v"}


class MediaError(RuntimeError):
    pass


def _bin(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise MediaError(f"{name} introuvable : installez FFmpeg.")
    return path


def run(cmd: list[str], timeout: int = 900) -> subprocess.CompletedProcess:
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        raise MediaError(f"{Path(cmd[0]).name} a échoué : {proc.stderr.strip()[-600:]}")
    return proc


def probe(path: Path) -> dict:
    proc = run([_bin("ffprobe"), "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)])
    data = json.loads(proc.stdout or "{}")
    streams = data.get("streams", [])
    v = next((s for s in streams if s.get("codec_type") == "video"), None)
    a = next((s for s in streams if s.get("codec_type") == "audio"), None)
    if v is None:
        raise MediaError("Aucune piste vidéo détectée dans ce fichier.")
    fps = 0.0
    rate = v.get("avg_frame_rate") or v.get("r_frame_rate") or "0/1"
    try:
        num, den = rate.split("/")
        fps = round(float(num) / float(den), 3) if float(den) else 0.0
    except (ValueError, ZeroDivisionError):
        fps = 0.0
    duration = float(data.get("format", {}).get("duration") or v.get("duration") or 0.0)
    return {
        "duration": round(duration, 3),
        "width": int(v.get("width") or 0),
        "height": int(v.get("height") or 0),
        "fps": fps,
        "video_codec": v.get("codec_name", ""),
        "audio_codec": a.get("codec_name", "") if a else "",
        "has_audio": a is not None,
    }


def extract_audio(video: Path, out_wav: Path) -> Path:
    """16 kHz mono WAV - the only input ASR/VAD ever see."""
    run([_bin("ffmpeg"), "-y", "-v", "error", "-i", str(video), "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(out_wav)])
    return out_wav


def detect_scene_changes(video: Path, threshold: float = 0.3) -> list[float]:
    """Scene-cut timestamps using ffmpeg's scene score on a downscaled stream."""
    proc = subprocess.run(
        [_bin("ffmpeg"), "-v", "info", "-i", str(video), "-an", "-vf",
         f"scale=160:-2,select='gt(scene,{threshold})',showinfo", "-f", "null", "-"],
        capture_output=True, text=True, timeout=900, encoding="utf-8", errors="replace",
    )
    times = [float(m) for m in re.findall(r"pts_time:([0-9.]+)", proc.stderr)]
    return sorted(set(round(t, 3) for t in times))


def extract_frame(video: Path, t: float, out_jpg: Path, width: int = 640) -> Path:
    run([_bin("ffmpeg"), "-y", "-v", "error", "-ss", f"{max(0.0, t):.3f}", "-i", str(video),
         "-frames:v", "1", "-vf", f"scale={width}:-2", "-q:v", "4", str(out_jpg)])
    return out_jpg


def audio_duration(path: Path) -> float:
    proc = run([_bin("ffprobe"), "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path)])
    try:
        return round(float(proc.stdout.strip()), 3)
    except ValueError:
        return 0.0


def normalize_clip(src: Path, dst: Path, max_duration: float | None = None, tempo: float = 1.0) -> Path:
    """Convert any audio clip to 44.1 kHz mono WAV, optionally speed it up (atempo) to fit a slot."""
    filters = []
    if tempo and abs(tempo - 1.0) > 0.01:
        filters.append(f"atempo={tempo:.3f}")
    cmd = [_bin("ffmpeg"), "-y", "-v", "error", "-i", str(src), "-ac", "1", "-ar", "44100"]
    if filters:
        cmd += ["-af", ",".join(filters)]
    if max_duration:
        cmd += ["-t", f"{max_duration:.3f}"]
    cmd += [str(dst)]
    run(cmd)
    return dst
