"""Step 5 - evaluate on the test videos (never seen during training) and write the report.

Compares the model with two baselines:
  - "tous les silences": what Wasf did before ML (every silence >= 1.5 s gets a draft)
  - "règle de durée": silences longer than a duration threshold learned on the training videos
Reports precision / recall / F1, average precision, the share of silences drafted, how many human
descriptions fall in a selected silence, 95 % bootstrap intervals (resampling test videos), the
feature importance (permutation) and a timeline per test video.

    python ml/evaluate.py      # -> ml/reports/report.md, metrics.json, *.png
"""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path

import numpy as np
from common import MODEL_PATH, REPORTS_DIR, data_dir_arg, log, read_json, write_json

from app.pipeline.gapscore import FEATURES, GapScorer, label_gaps


def prf(y: np.ndarray, sel: np.ndarray) -> dict:
    tp = int((sel & (y == 1)).sum())
    p = tp / max(1, int(sel.sum()))
    r = tp / max(1, int((y == 1).sum()))
    return {"precision": p, "recall": r, "f1": 2 * p * r / max(p + r, 1e-9), "selected_share": float(sel.mean())}


def read_split(path, split: str):  # noqa: ANN001
    with path.open(encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r["split"] == split]
    X = np.array([[float(r[k]) for k in FEATURES] for r in rows])
    y = np.array([int(r["label"]) for r in rows])
    return rows, X, y


def duration_rule(rows_train, y_train) -> float:  # noqa: ANN001
    d = np.array([float(r["duration"]) for r in rows_train])
    best, best_f1 = 1.5, -1.0
    for t in np.unique(np.round(d, 1)):
        f1 = prf(y_train, d >= t)["f1"]
        if f1 > best_f1:
            best, best_f1 = float(t), f1
    return best


def bootstrap(rows, y, p, sel, n: int = 1000, seed: int = 0) -> dict:  # noqa: ANN001
    from sklearn.metrics import average_precision_score

    by_video = defaultdict(list)
    for i, r in enumerate(rows):
        by_video[r["video_id"]].append(i)
    vids = list(by_video)
    rng = np.random.default_rng(seed)
    aps, f1s = [], []
    for _ in range(n):
        idx = np.concatenate([by_video[v] for v in rng.choice(vids, size=len(vids), replace=True)])
        if y[idx].min() == y[idx].max():
            continue
        aps.append(average_precision_score(y[idx], p[idx]))
        f1s.append(prf(y[idx], sel[idx])["f1"])
    q = lambda a: [float(np.percentile(a, 2.5)), float(np.percentile(a, 97.5))]  # noqa: E731
    return {"average_precision_95ci": q(aps), "f1_95ci": q(f1s)}


def figures(rows, y, p, sel, base_rate, rule_pt, model_pt, importance, dataset, out) -> None:  # noqa: ANN001
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from sklearn.metrics import precision_recall_curve

    ink, teal, orange, grey = "#1f2937", "#0f766e", "#c2410c", "#9ca3af"
    # 1. precision / recall
    prec, rec, _ = precision_recall_curve(y, p)
    fig, ax = plt.subplots(figsize=(6, 4.2))
    ax.plot(rec, prec, color=teal, lw=2, label="Modèle ML")
    ax.scatter([model_pt["recall"]], [model_pt["precision"]], color=teal, zorder=3, label="Modèle (seuil retenu)")
    ax.scatter([1.0], [base_rate], color=grey, marker="s", zorder=3, label="Tous les silences (avant ML)")
    ax.scatter([rule_pt["recall"]], [rule_pt["precision"]], color=orange, marker="^", zorder=3, label="Règle de durée")
    ax.set_xlabel("Rappel (silences décrits par un humain retrouvés)")
    ax.set_ylabel("Précision")
    ax.set_xlim(0, 1.02)
    ax.set_ylim(0, 1.02)
    ax.grid(alpha=0.3)
    ax.legend(loc="lower left", fontsize=8)
    ax.set_title("Vidéos de test : précision / rappel", color=ink)
    fig.tight_layout()
    fig.savefig(out / "pr_curve.png", dpi=150)
    plt.close(fig)

    # 2. permutation importance
    top = sorted(importance.items(), key=lambda kv: kv[1])[-12:]
    fig, ax = plt.subplots(figsize=(6, 4.2))
    ax.barh([k for k, _ in top], [v for _, v in top], color=teal)
    ax.set_xlabel("Perte de précision moyenne si la variable est brouillée")
    ax.set_title("Variables les plus utiles (permutation, test)", color=ink)
    ax.grid(axis="x", alpha=0.3)
    fig.tight_layout()
    fig.savefig(out / "feature_importance.png", dpi=150)
    plt.close(fig)

    # 3. timelines of the test videos
    by_video = defaultdict(list)
    for i, r in enumerate(rows):
        by_video[r["video_id"]].append(i)
    clips = {d["youtube_id"]: d for d in dataset}
    vids = list(by_video)
    fig, axes = plt.subplots(len(vids), 1, figsize=(10, 0.75 * len(vids) + 1.2), squeeze=False)
    for ax, v in zip(axes[:, 0], vids, strict=True):
        dur = clips[v]["duration"] if v in clips else max(float(rows[i]["end"]) for i in by_video[v])
        ax.add_patch(plt.Rectangle((0, 0.35), dur, 0.3, color="#e5e7eb"))
        for i in by_video[v]:
            a, b = float(rows[i]["start"]), float(rows[i]["end"])
            ax.add_patch(plt.Rectangle((a, 0.35), b - a, 0.3, fc=teal if sel[i] else "#e2e8f0",
                                       hatch=None if sel[i] else "///", ec="white" if sel[i] else "#64748b",
                                       lw=0.5))
        for c in clips.get(v, {}).get("clips", []):
            ax.plot([c["start"]], [0.85], marker="v", color=orange, ms=5)
        ax.set_xlim(0, dur)
        ax.set_ylim(0, 1)
        ax.set_yticks([])
        ax.set_ylabel(v, rotation=0, ha="right", va="center", fontsize=7)
        ax.tick_params(axis="x", labelsize=7)
        for s in ("top", "right", "left"):
            ax.spines[s].set_visible(False)
    axes[0, 0].set_title("Test : silences retenus par le modèle (plein) / écartés (hachuré), "
                         "▼ = description humaine", fontsize=9, color=ink)
    axes[-1, 0].set_xlabel("temps (s)")
    fig.tight_layout()
    fig.savefig(out / "timelines.png", dpi=150)
    plt.close(fig)


def pct(x: float) -> str:
    return f"{100 * x:.0f} %"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    data_dir_arg(ap)
    ap.add_argument("--model", type=Path, default=MODEL_PATH, help="fichier du modèle (défaut : ml/artifacts)")
    ap.add_argument("--reports", type=Path, default=REPORTS_DIR, help="dossier du rapport (défaut : ml/reports)")
    args = ap.parse_args()
    out = args.reports

    from sklearn.inspection import permutation_importance
    from sklearn.metrics import average_precision_score, roc_auc_score

    scorer = GapScorer.load(args.model)
    feats_csv = args.data_dir / "features.csv"
    rows_tr, _, y_tr = read_split(feats_csv, "train")
    rows, X, y = read_split(feats_csv, "test")
    if not rows or y.min() == y.max():
        raise SystemExit("Le jeu de test doit contenir des silences positifs et négatifs.")

    p = scorer.model.predict_proba(X)[:, 1]
    sel = p >= scorer.threshold
    base_rate = float(y.mean())
    t_rule = duration_rule(rows_tr, y_tr)
    rule_sel = np.array([float(r["duration"]) for r in rows]) >= t_rule
    model_m = {**prf(y, sel), "average_precision": float(average_precision_score(y, p)),
               "roc_auc": float(roc_auc_score(y, p))}
    all_m = prf(y, np.ones(len(y), dtype=bool))
    rule_m = prf(y, rule_sel)
    ci = bootstrap(rows, y, p, sel)
    imp = permutation_importance(scorer.model, X, y, scoring="average_precision", n_repeats=15, random_state=0)
    importance = {k: float(v) for k, v in zip(FEATURES, imp.importances_mean, strict=True)}

    # how many human descriptions fall into a drafted silence?
    dataset = {d["youtube_id"]: d for d in read_json(args.data_dir / "dataset.json")}
    stats = read_json(args.data_dir / "video_stats.json")
    types = set(stats.get("types") or ["inline", "extended"])
    before = stats.get("before", 1.0)
    per_video, human_total, in_any, in_sel = [], 0, 0, 0
    by_video = defaultdict(list)
    for i, r in enumerate(rows):
        by_video[r["video_id"]].append(i)
    for v, idx in by_video.items():
        gaps = [(float(rows[i]["start"]), float(rows[i]["end"])) for i in idx]
        chosen = [g for g, i in zip(gaps, idx, strict=True) if sel[i]]
        starts = [c["start"] for c in dataset.get(v, {}).get("clips", []) if c["type"] in types]
        human_total += len(starts)
        in_any += sum(1 for t in starts if any(label_gaps(gaps, [t], before=before)))
        in_sel += sum(1 for t in starts if any(label_gaps(chosen, [t], before=before)))
        m = prf(y[idx], sel[idx])
        per_video.append({"video_id": v, "title": dataset.get(v, {}).get("title", ""), "gaps": len(idx),
                          "human_gaps": int(y[idx].sum()), "selected": int(sel[idx].sum()), **m})

    report = {
        "model": scorer.meta.get("model"), "threshold": scorer.threshold,
        "test_videos": len(by_video), "test_gaps": len(y), "test_positive_rate": base_rate,
        "model_metrics": model_m, "baseline_all_gaps": all_m,
        "baseline_duration_rule": {**rule_m, "min_duration": t_rule}, "bootstrap": ci,
        "human_descriptions": {"total": human_total, "in_any_gap": in_any, "in_selected_gap": in_sel},
        "feature_importance": dict(sorted(importance.items(), key=lambda kv: -kv[1])),
        "per_video": per_video, "cv_train": scorer.meta.get("cv"),
    }
    out.mkdir(parents=True, exist_ok=True)
    write_json(out / "metrics.json", report)
    figures(rows, y, p, sel, base_rate, rule_m, model_m, importance, list(dataset.values()), out)

    # expose test metrics to the app (shown on the Analysis page)
    meta_path = args.model.with_suffix(".json")
    meta = read_json(meta_path)
    meta["test_metrics"] = {"videos": len(by_video), "gaps": len(y), "precision": model_m["precision"],
                            "recall": model_m["recall"], "f1": model_m["f1"],
                            "average_precision": model_m["average_precision"],
                            "selected_share": model_m["selected_share"], "baseline_f1_all_gaps": all_m["f1"]}
    write_json(meta_path, meta)

    write_markdown(report, scorer, out)
    log.info("Test : précision %.2f  rappel %.2f  F1 %.2f (tous les silences : F1 %.2f)  AP %.2f",
             model_m["precision"], model_m["recall"], model_m["f1"], all_m["f1"], model_m["average_precision"])
    log.info("Rapport : %s", out / "report.md")


def write_markdown(r: dict, scorer: GapScorer, out: Path) -> None:
    m, a, d, h = r["model_metrics"], r["baseline_all_gaps"], r["baseline_duration_rule"], r["human_descriptions"]
    ci = r["bootstrap"]
    lines = [
        "# Rapport d'évaluation : sélection des silences à décrire",
        "",
        f"Modèle **{r['model']}**, seuil **{r['threshold']:.3f}**, entraîné sur "
        f"{scorer.meta.get('train_videos')} vidéos ({scorer.meta.get('train_gaps')} silences), "
        f"évalué sur **{r['test_videos']} vidéos de test jamais vues** ({r['test_gaps']} silences, "
        f"{pct(r['test_positive_rate'])} décrits par un humain).",
        "",
        "Question posée au modèle : *un·e audiodescripteur·rice humain·e aurait-il·elle placé une description "
        "dans ce silence ?* Vérité terrain : descriptions bénévoles QuerYD / YouDescribe.",
        "",
        "## Résultats sur le test",
        "",
        "| Méthode | Précision | Rappel | F1 | Silences rédigés |",
        "|---|---|---|---|---|",
        f"| Tous les silences (Wasf avant ML) | {pct(a['precision'])} | {pct(a['recall'])} | {a['f1']:.2f} | "
        f"{pct(a['selected_share'])} |",
        f"| Règle de durée (≥ {d['min_duration']:.1f} s, apprise) | {pct(d['precision'])} | {pct(d['recall'])} | "
        f"{d['f1']:.2f} | {pct(d['selected_share'])} |",
        f"| **Modèle ML** | **{pct(m['precision'])}** | **{pct(m['recall'])}** | **{m['f1']:.2f}** | "
        f"**{pct(m['selected_share'])}** |",
        "",
        f"- Précision moyenne (AP) : **{m['average_precision']:.2f}** "
        f"(IC 95 % par rééchantillonnage des vidéos : {ci['average_precision_95ci'][0]:.2f} – "
        f"{ci['average_precision_95ci'][1]:.2f}) ; ROC-AUC : {m['roc_auc']:.2f}.",
        f"- F1 du modèle : IC 95 % {ci['f1_95ci'][0]:.2f} – {ci['f1_95ci'][1]:.2f}.",
        f"- Descriptions humaines du test : {h['total']} ; {h['in_any_gap']} tombent dans un silence détecté, "
        f"dont **{h['in_selected_gap']}** dans un silence retenu par le modèle. Les autres sont des descriptions "
        "« extended » (la vidéo est mise en pause) ou posées sur de la parole.",
        "",
        "![Précision / rappel](pr_curve.png)",
        "",
        "![Frises des vidéos de test](timelines.png)",
        "",
        "## Variables les plus utiles",
        "",
        "![Importance des variables](feature_importance.png)",
        "",
        "| Variable | Importance (perte d'AP) |",
        "|---|---|",
        *[f"| `{k}` | {v:.3f} |" for k, v in list(r["feature_importance"].items())[:10]],
        "",
        "## Validation croisée sur l'entraînement (par vidéo)",
        "",
        "| Modèle | AP | ROC-AUC |",
        "|---|---|---|",
        *[f"| {k} | {v['average_precision']:.3f} | {v['roc_auc']:.3f} |" for k, v in (r["cv_train"] or {}).items()],
        "",
        "## Détail par vidéo de test",
        "",
        "| Vidéo | Silences | Décrits (humain) | Retenus (modèle) | Précision | Rappel |",
        "|---|---|---|---|---|---|",
        *[f"| [{v['video_id']}](https://www.youtube.com/watch?v={v['video_id']}) {v['title'][:40]} | {v['gaps']} | "
          f"{v['human_gaps']} | {v['selected']} | {pct(v['precision'])} | {pct(v['recall'])} |"
          for v in r["per_video"]],
        "",
        "## Limites",
        "",
        "- Peu de vidéos : les intervalles de confiance sont larges ; à présenter comme une preuve de concept.",
        "- Descriptions bénévoles, en anglais, sur YouTube : le modèle apprend *où* décrire, pas *quoi* ni "
        "dans quelle langue. La rédaction reste faite par le VLM et validée par un humain.",
        "- Les bénévoles ne décrivent pas tous les silences utiles : un silence « non décrit » n'est pas "
        "forcément un mauvais endroit. La précision est donc une estimation prudente.",
        "- Dans l'application, l'humain peut toujours rédiger dans un silence écarté par le modèle.",
        "",
    ]
    (out / "report.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
