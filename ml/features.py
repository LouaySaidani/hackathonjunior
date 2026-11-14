"""Step 3 - run Basira's own analysis on each video and build the training table.

For every video of ml/data/dataset.json:
  audio 16 kHz -> VAD (+ optional Whisper) -> silences -> shot changes -> features per silence,
then label each silence with the human descriptions (1 = a human describer started a
description there).

This is exactly the code the app runs (backend/app/pipeline), so the model is trained on the
features it will see in production.

    python ml/features.py            # -> ml/data/features.csv + ml/data/video_stats.json
    python ml/features.py --asr      # also use Whisper like the app (slower, closer to production)
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from common import data_dir_arg, log, read_json, write_json

from app.config import get_settings
from app.pipeline import media
from app.pipeline.gapscore import FEATURES, MediaSignals, compute_gap_features, label_gaps
from app.pipeline.vad import combine_speech, compute_gaps, detect_speech, split_long_gaps

COLUMNS = ["video_id", "split", "gap_index", "start", "end", "n_ad", "label", *FEATURES]


def analyse_video(video: Path, work: Path, use_asr: bool, settings) -> dict:  # noqa: ANN001
    work.mkdir(parents=True, exist_ok=True)
    info = media.probe(video)
    duration = info["duration"]
    wav = work / "audio.wav"
    if not wav.is_file():
        media.extract_audio(video, wav)
    speech, engine = detect_speech(wav, settings.vad_engine)
    if use_asr:
        from app.providers import asr as asr_mod

        result = asr_mod.transcribe(settings, wav, None, None)
        speech = combine_speech(speech, [(s.start, s.end) for s in result.segments])
    gaps = compute_gaps(speech, duration, settings.min_gap_seconds, settings.gap_padding_seconds)
    cuts = media.detect_scene_changes(video, settings.scene_threshold)
    gaps = split_long_gaps(gaps, cuts, settings.max_slot_seconds, settings.min_gap_seconds)  # same as the app
    feats = compute_gap_features(gaps, MediaSignals.from_files(video, wav, duration, speech, cuts))
    return {"duration": duration, "vad": engine, "speech": speech, "gaps": gaps, "cuts": cuts, "features": feats}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    data_dir_arg(ap)
    ap.add_argument("--asr", action="store_true", help="ajouter la transcription Whisper (comme l'application)")
    ap.add_argument("--types", default="inline,extended",
                    help="types de descriptions humaines qui comptent comme positives (inline,extended)")
    ap.add_argument("--before", type=float, default=1.0, help="tolérance : description commencée jusqu'à N s avant")
    ap.add_argument("--refresh", action="store_true", help="recalculer même si le cache existe")
    args = ap.parse_args()

    settings = get_settings()
    types = {t.strip() for t in args.types.split(",") if t.strip()}
    dataset = read_json(args.data_dir / "dataset.json")
    rows, stats = [], []
    for i, item in enumerate(dataset, 1):
        vid = item["youtube_id"]
        video = args.data_dir / item["path"]
        if not video.is_file():
            log.warning("[%d/%d] %s : fichier manquant, ignoré", i, len(dataset), video)
            continue
        name = f"analysis{'_asr' if args.asr else ''}_slot{settings.max_slot_seconds:g}.json"
        cache = args.data_dir / "work" / vid / name
        if cache.is_file() and not args.refresh:
            res = read_json(cache)
            res["gaps"] = [tuple(g) for g in res["gaps"]]
        else:
            log.info("[%d/%d] analyse de %s (%s)", i, len(dataset), vid, item["split"])
            res = analyse_video(video, cache.parent, args.asr, settings)
            write_json(cache, res)

        clips = [c for c in item["clips"] if c["type"] in types]
        counts = label_gaps(res["gaps"], [c["start"] for c in clips], before=args.before)
        for gi, ((a, b), f, n) in enumerate(zip(res["gaps"], res["features"], counts, strict=True)):
            rows.append({"video_id": vid, "split": item["split"], "gap_index": gi, "start": a, "end": b,
                         "n_ad": n, "label": int(n > 0), **f})
        inline_starts = [c["start"] for c in item["clips"] if c["type"] == "inline"]
        stats.append({
            "video_id": vid, "title": item.get("title", ""), "category": item.get("category", ""),
            "split": item["split"], "duration": res["duration"], "vad": res["vad"],
            "gaps": len(res["gaps"]), "positive_gaps": sum(n > 0 for n in counts),
            "human_clips": len(item["clips"]), "inline_clips": len(inline_starts),
            "inline_in_a_gap": sum(1 for t in inline_starts if any(label_gaps(res["gaps"], [t], before=args.before))),
            "speech_seconds": round(sum(b - a for a, b in res["speech"]), 1), "scene_changes": len(res["cuts"]),
        })

    if not rows:
        raise SystemExit("Aucune vidéo analysée : lancez d'abord ml/download.py")
    out = args.data_dir / "features.csv"
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)
    write_json(args.data_dir / "video_stats.json",
               {"asr": args.asr, "types": sorted(types), "before": args.before, "videos": stats})
    pos = sum(r["label"] for r in rows)
    log.info("%d silences (%d positifs, %.0f %%) sur %d vidéos -> %s", len(rows), pos, 100 * pos / len(rows),
             len(stats), out)


if __name__ == "__main__":
    main()
