"""Step 2 - download the videos and split them by video into train / test.

Goes through ml/data/candidates.json in order and downloads with yt-dlp (480p max) until
`--train + --test` videos are available. Deleted / private videos are skipped and the next
candidate is used. The split is done per video (never per clip), with a fixed seed.

Videos are only used locally, for research, to train and evaluate the model. They are never
redistributed. Check YouTube's terms and each video's licence before any other use.

    python ml/download.py --train 17 --test 13    # -> ml/data/videos/*.mp4 + ml/data/dataset.json
"""

from __future__ import annotations

import argparse
import random

from common import data_dir_arg, log, read_json, write_json


def download_one(youtube_id: str, out_dir) -> bool:  # noqa: ANN001
    import yt_dlp

    target = out_dir / f"{youtube_id}.mp4"
    if target.is_file() and target.stat().st_size > 0:
        return True
    opts = {
        "format": "bv*[height<=480][ext=mp4]+ba[ext=m4a]/b[height<=480][ext=mp4]/bv*[height<=480]+ba/b",
        "merge_output_format": "mp4",
        "outtmpl": str(out_dir / "%(id)s.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "noprogress": True,
        "no_warnings": True,
        "retries": 2,
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([f"https://www.youtube.com/watch?v={youtube_id}"])
    except Exception as exc:  # noqa: BLE001 - unavailable, private, region-locked...
        log.warning("  indisponible (%s)", str(exc).splitlines()[0][:120])
        return False
    return target.is_file()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    data_dir_arg(ap)
    ap.add_argument("--train", type=int, default=17, help="nombre de vidéos d'entraînement")
    ap.add_argument("--test", type=int, default=13, help="nombre de vidéos de test")
    ap.add_argument("--seed", type=int, default=13)
    args = ap.parse_args()

    candidates = read_json(args.data_dir / "candidates.json")
    out_dir = args.data_dir / "videos"
    out_dir.mkdir(parents=True, exist_ok=True)
    wanted = args.train + args.test

    ok = []
    for c in candidates:
        if len(ok) >= wanted:
            break
        log.info("[%d/%d] %s - %s (%s, %.0f s)", len(ok) + 1, wanted, c["youtube_id"], c["title"][:60],
                 c["category"], c["duration"])
        if download_one(c["youtube_id"], out_dir):
            ok.append(c)
    if len(ok) < wanted:
        log.warning("Seulement %d vidéos téléchargées sur %d demandées.", len(ok), wanted)
    if len(ok) < 3:
        raise SystemExit("Pas assez de vidéos pour entraîner et tester.")

    rng = random.Random(args.seed)
    rng.shuffle(ok)
    n_train = min(args.train, len(ok) - max(1, round(len(ok) * args.test / wanted)))
    for j, c in enumerate(ok):
        c["split"] = "train" if j < n_train else "test"
        c["path"] = f"videos/{c['youtube_id']}.mp4"
    write_json(args.data_dir / "dataset.json", ok)
    log.info("Jeu de données : %d entraînement, %d test -> %s", n_train, len(ok) - n_train,
             args.data_dir / "dataset.json")


if __name__ == "__main__":
    main()
