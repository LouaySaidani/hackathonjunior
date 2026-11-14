"""Step 4 - train the gap-relevance model on the training videos only.

Three small, explainable scikit-learn models are compared with cross-validation *grouped by
video* (a video is never in both the fitting and the validation fold):
  - logistic regression (linear baseline)
  - random forest
  - gradient boosting (HistGradientBoosting)
The best one (average precision) is refitted on all training videos. The decision threshold is
chosen on the out-of-fold predictions (max F-beta), never on the test videos.

    python ml/train.py               # -> ml/artifacts/gap_scorer.joblib + gap_scorer.json
"""

from __future__ import annotations

import argparse
import csv
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
from common import MODEL_PATH, data_dir_arg, log, read_json, write_json

from app.pipeline.gapscore import FEATURES


def load_rows(path, split: str):  # noqa: ANN001
    with path.open(encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r["split"] == split]
    X = np.array([[float(r[k]) for k in FEATURES] for r in rows], dtype=np.float64)
    y = np.array([int(r["label"]) for r in rows])
    groups = np.array([r["video_id"] for r in rows])
    return rows, X, y, groups


def candidates(seed: int) -> dict:
    from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    return {
        "logistic_regression": make_pipeline(
            StandardScaler(), LogisticRegression(C=0.5, class_weight="balanced", max_iter=5000)),
        "random_forest": RandomForestClassifier(
            n_estimators=400, min_samples_leaf=4, max_features="sqrt", class_weight="balanced_subsample",
            random_state=seed, n_jobs=-1),
        "gradient_boosting": HistGradientBoostingClassifier(
            max_depth=3, learning_rate=0.05, max_iter=250, l2_regularization=1.0, min_samples_leaf=10,
            class_weight="balanced", random_state=seed),
    }


def best_threshold(y: np.ndarray, p: np.ndarray, beta: float) -> tuple[float, dict]:
    from sklearn.metrics import precision_recall_curve

    prec, rec, thr = precision_recall_curve(y, p)
    prec, rec = prec[:-1], rec[:-1]
    fb = (1 + beta**2) * prec * rec / np.maximum(beta**2 * prec + rec, 1e-9)
    i = int(np.nanargmax(fb))
    return float(thr[i]), {"precision": float(prec[i]), "recall": float(rec[i]), f"f{beta:g}": float(fb[i])}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    data_dir_arg(ap)
    ap.add_argument("--beta", type=float, default=1.0,
                    help="F-beta pour le seuil (>1 favorise le rappel : moins de silences oubliés)")
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--model", type=Path, default=MODEL_PATH, help="fichier du modèle (défaut : ml/artifacts)")
    args = ap.parse_args()

    import joblib
    import sklearn
    from sklearn.base import clone
    from sklearn.metrics import average_precision_score, roc_auc_score
    from sklearn.model_selection import GroupKFold

    _, X, y, groups = load_rows(args.data_dir / "features.csv", "train")
    n_videos = len(set(groups))
    if n_videos < 2 or y.min() == y.max():
        raise SystemExit("Il faut au moins 2 vidéos d'entraînement avec des silences positifs ET négatifs.")
    folds = min(args.folds, n_videos)
    log.info("Entraînement : %d silences, %d vidéos, %.0f %% positifs, validation croisée %d plis par vidéo",
             len(y), n_videos, 100 * y.mean(), folds)

    cv = GroupKFold(n_splits=folds)
    results, oof = {}, {}
    for name, model in candidates(args.seed).items():
        p = np.zeros(len(y))
        for tr, va in cv.split(X, y, groups):
            if y[tr].min() == y[tr].max():
                p[va] = y[tr].mean()
                continue
            p[va] = clone(model).fit(X[tr], y[tr]).predict_proba(X[va])[:, 1]
        oof[name] = p
        results[name] = {"average_precision": float(average_precision_score(y, p)),
                         "roc_auc": float(roc_auc_score(y, p))}
        log.info("  %-20s AP %.3f   ROC-AUC %.3f", name, results[name]["average_precision"], results[name]["roc_auc"])

    best = max(results, key=lambda k: results[k]["average_precision"])
    threshold, at_thr = best_threshold(y, oof[best], args.beta)
    final = clone(candidates(args.seed)[best]).fit(X, y)
    log.info("Modèle retenu : %s, seuil %.3f (précision %.2f, rappel %.2f en validation croisée)",
             best, threshold, at_thr["precision"], at_thr["recall"])

    stats_path = args.data_dir / "video_stats.json"
    stats = read_json(stats_path) if stats_path.is_file() else {}
    meta = {
        "model": best,
        "features": FEATURES,
        "threshold": round(threshold, 4),
        "threshold_beta": args.beta,
        "cv": results,
        "cv_at_threshold": at_thr,
        "train_videos": n_videos,
        "train_gaps": int(len(y)),
        "train_positive_rate": float(y.mean()),
        "label": {"types": stats.get("types"), "before": stats.get("before"), "asr": stats.get("asr")},
        "dataset": "QuerYD / YouDescribe (descriptions humaines bénévoles, anglais)",
        "sklearn": sklearn.__version__,
        "trained_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    args.model.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": final, "meta": meta}, args.model)
    write_json(args.model.with_suffix(".json"), meta)
    log.info("Modèle enregistré : %s", args.model)


if __name__ == "__main__":
    main()
