"""Step 1 - download QuerYD metadata and select candidate videos with human audio description.

QuerYD (Oncescu et al., ICASSP 2021, https://www.robots.ox.ac.uk/~vgg/data/queryd/) is built on
YouDescribe: volunteers recorded audio descriptions for YouTube videos. For each description clip
the metadata gives the video time where it starts and whether it is `inline` (spoken over the
video, exactly Basira's case) or `extended` (the video is paused).

Only timings, playback type and transcript text are kept. Describer names, e-mails and account
ids present in the raw metadata are dropped on purpose.

    python ml/fetch_queryd.py                 # -> ml/data/candidates.json
"""

from __future__ import annotations

import argparse
import json
import random
import urllib.request
import zipfile

from common import data_dir_arg, log, write_json

META_URL = "https://www.robots.ox.ac.uk/~vgg/research/collaborative-experts/data/QuerYD/json_metadata-v2.zip"
# Closest categories to films first.
CATEGORY_RANK = {"Film & Animation": 0, "Entertainment": 1, "Comedy": 1, "Shows": 1, "Music": 2,
                 "People & Blogs": 3, "Education": 3, "Nonprofits & Activism": 3}


def download_metadata(dest) -> None:  # noqa: ANN001
    if dest.is_file() and dest.stat().st_size > 1_000_000:
        log.info("Métadonnées déjà présentes : %s", dest)
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    log.info("Téléchargement des métadonnées QuerYD (~68 Mo)…")
    tmp = dest.with_suffix(".part")
    urllib.request.urlretrieve(META_URL, tmp)  # noqa: S310 - fixed https URL
    tmp.replace(dest)


def clip_text(clip: dict) -> str:
    return " ".join(s.get("sentence", "").strip() for s in clip.get("transcript") or []).strip()


def best_description(video: dict, min_clips: int, min_inline: float) -> dict | None:
    """Pick the English, published description with the most inline clips."""
    duration = float(video.get("duration") or 0)
    best = None
    for ad in video.get("audio_descriptions") or []:
        if not str(ad.get("language", "")).startswith("en") or ad.get("status") != "published":
            continue
        clips = [c for c in ad.get("audio_clips") or []
                 if isinstance(c.get("start_time"), int | float) and 0 <= c["start_time"] < duration]
        if len(clips) < min_clips:
            continue
        inline = sum(c.get("playback_type") == "inline" for c in clips)
        if inline < min_inline * len(clips):
            continue
        if best is None or inline > best[0]:
            best = (inline, ad.get("language"), clips)
    if best is None:
        return None
    _, lang, clips = best
    return {
        "ad_language": lang,
        "clips": sorted(
            ({"start": round(float(c["start_time"]), 3), "duration": round(float(c.get("duration") or 0), 3),
              "type": c.get("playback_type", "inline"), "text": clip_text(c)} for c in clips),
            key=lambda c: c["start"],
        ),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    data_dir_arg(ap)
    ap.add_argument("--min-duration", type=float, default=60, help="durée minimale des vidéos (s)")
    ap.add_argument("--max-duration", type=float, default=300, help="durée maximale des vidéos (s)")
    ap.add_argument("--min-clips", type=int, default=6, help="nombre minimal de descriptions humaines")
    ap.add_argument("--min-inline", type=float, default=0.6, help="part minimale de descriptions « inline »")
    ap.add_argument("--seed", type=int, default=13)
    args = ap.parse_args()

    zpath = args.data_dir / "queryd_metadata.zip"
    download_metadata(zpath)

    candidates = []
    with zipfile.ZipFile(zpath) as z:
        for name in z.namelist():
            if not name.endswith(".json"):
                continue
            video = json.loads(z.read(name)).get("result") or {}
            dur = float(video.get("duration") or 0)
            if video.get("youtube_status") != "available" or not (args.min_duration <= dur <= args.max_duration):
                continue
            ad = best_description(video, args.min_clips, args.min_inline)
            if ad:
                candidates.append({"youtube_id": video["youtube_id"], "title": video.get("title", ""),
                                   "category": video.get("category", ""), "duration": dur, **ad})

    rng = random.Random(args.seed)
    rng.shuffle(candidates)
    candidates.sort(key=lambda c: CATEGORY_RANK.get(c["category"], 4))  # stable: random within a rank
    write_json(args.data_dir / "candidates.json", candidates)
    cats: dict[str, int] = {}
    for c in candidates:
        cats[c["category"]] = cats.get(c["category"], 0) + 1
    log.info("%d vidéos candidates -> %s", len(candidates), args.data_dir / "candidates.json")
    log.info("Catégories : %s", dict(sorted(cats.items(), key=lambda kv: -kv[1])))


if __name__ == "__main__":
    main()
