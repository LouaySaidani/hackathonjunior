"""Shared paths and helpers for the ML scripts. Every script can be run as `python ml/<script>.py`."""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

ML_DIR = Path(__file__).resolve().parent
ROOT = ML_DIR.parent
DATA_DIR = ML_DIR / "data"          # downloaded metadata, videos, features (git-ignored)
ARTIFACTS_DIR = ML_DIR / "artifacts"  # trained model, loaded by the app
REPORTS_DIR = ML_DIR / "reports"    # evaluation report + figures
MODEL_PATH = ARTIFACTS_DIR / "gap_scorer.joblib"

# Make the Wasf backend importable so training and the app share the exact same feature code.
sys.path.insert(0, str(ROOT / "backend"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("ml")


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def data_dir_arg(parser) -> None:  # noqa: ANN001
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR, help="dossier des données (défaut : ml/data)")
