"""Run the whole ML process: metadata -> download -> features -> training -> evaluation.

    python ml/run_all.py                      # 17 training videos, 13 test videos
    python ml/run_all.py --train 20 --test 10 --asr
"""

from __future__ import annotations

import argparse
import subprocess
import sys

from common import ML_DIR


def step(script: str, *args: str) -> None:
    print(f"\n=== {script} {' '.join(args)} ===", flush=True)
    subprocess.run([sys.executable, str(ML_DIR / script), *args], check=True)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--train", type=int, default=17)
    ap.add_argument("--test", type=int, default=13)
    ap.add_argument("--asr", action="store_true", help="utiliser aussi Whisper pour les silences (plus lent)")
    ap.add_argument("--skip-download", action="store_true", help="réutiliser ml/data/dataset.json")
    args = ap.parse_args()

    if not args.skip_download:
        step("fetch_queryd.py")
        step("download.py", "--train", str(args.train), "--test", str(args.test))
    step("features.py", *(["--asr"] if args.asr else []))
    step("train.py")
    step("evaluate.py")
    print("\nTerminé. Rapport : ml/reports/report.md - modèle : ml/artifacts/gap_scorer.joblib")
    print("Redémarrez Basira pour qu'il utilise le nouveau modèle.")


if __name__ == "__main__":
    main()
