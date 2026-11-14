"""FFmpeg mixing: AD track assembly, ducking of the original audio, final accessible MP4."""

from __future__ import annotations

from pathlib import Path

from .media import MediaError, run


def build_ad_track(clips: list[tuple[float, Path]], duration: float, out_wav: Path) -> Path:
    """Place each (start_time, wav) clip on a silent timeline of `duration` seconds."""
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-t", f"{duration:.3f}",
           "-i", "anullsrc=r=44100:cl=mono"]
    for _, clip in clips:
        cmd += ["-i", str(clip)]
    if not clips:
        cmd += ["-c:a", "pcm_s16le", str(out_wav)]
        run(cmd)
        return out_wav
    chains = []
    labels = ["[0:a]"]
    for i, (start, _) in enumerate(clips, start=1):
        ms = int(round(start * 1000))
        chains.append(f"[{i}:a]aresample=44100,aformat=channel_layouts=mono,adelay={ms}:all=1[c{i}]")
        labels.append(f"[c{i}]")
    graph = ";".join(chains) + ";" + "".join(labels) + f"amix=inputs={len(labels)}:duration=first:normalize=0[out]"
    cmd += ["-filter_complex", graph, "-map", "[out]", "-ac", "1", "-ar", "44100", "-c:a", "pcm_s16le", str(out_wav)]
    run(cmd)
    return out_wav


def duck_expression(intervals: list[tuple[float, float]], fade: float = 0.15) -> str:
    return "+".join(f"between(t,{max(0.0, a - fade):.3f},{b + fade:.3f})" for a, b in intervals) or "0"


def encode_mp3(wav: Path, out_mp3: Path) -> Path:
    run(["ffmpeg", "-y", "-v", "error", "-i", str(wav), "-c:a", "libmp3lame", "-q:a", "4", str(out_mp3)])
    return out_mp3


def mix_final(
    video: Path,
    ad_track: Path,
    intervals: list[tuple[float, float]],
    out_mp4: Path,
    has_audio: bool,
    duck_volume: float,
    metadata: dict[str, str],
) -> Path:
    meta = []
    for k, v in metadata.items():
        meta += ["-metadata", f"{k}={v}"]
    if has_audio:
        graph = (
            f"[0:a]aresample=44100,volume=enable='{duck_expression(intervals)}':volume={duck_volume}[duck];"
            f"[1:a]aresample=44100,aformat=channel_layouts=stereo[ad];"
            f"[duck][ad]amix=inputs=2:duration=first:normalize=0[mix]"
        )
        maps = ["-map", "0:v:0", "-map", "[mix]", "-map", "0:a:0"]
        track_meta = ["-metadata:s:a:0", "title=Audiodescription (mix)", "-metadata:s:a:1", "title=Original"]
    else:
        graph = "[1:a]aresample=44100[mix]"
        maps = ["-map", "0:v:0", "-map", "[mix]"]
        track_meta = ["-metadata:s:a:0", "title=Audiodescription"]

    def _cmd(vcodec: list[str]) -> list[str]:
        return (["ffmpeg", "-y", "-v", "error", "-i", str(video), "-i", str(ad_track), "-filter_complex", graph]
                + maps + vcodec + ["-c:a", "aac", "-b:a", "160k"] + track_meta + meta
                + ["-movflags", "+faststart", str(out_mp4)])

    try:
        run(_cmd(["-c:v", "copy"]))
    except MediaError:
        run(_cmd(["-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p"]))
    return out_mp4
