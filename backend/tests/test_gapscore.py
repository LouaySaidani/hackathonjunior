"""ML gap selection: shared features, labelling, model loading, and the app integration."""

import json
import math
import time

import joblib
import numpy as np
import pytest
from sklearn.linear_model import LogisticRegression

from app import service
from app.config import get_settings
from app.pipeline import media
from app.pipeline.gapscore import (
    FEATURES,
    GapScorer,
    MediaSignals,
    compute_gap_features,
    label_gaps,
    select,
)
from app.pipeline.vad import compute_gaps, detect_speech


@pytest.fixture(scope="module")
def sample_analysis(sample_video, tmp_path_factory):
    work = tmp_path_factory.mktemp("ml")
    wav = media.extract_audio(sample_video, work / "a.wav")
    speech, _ = detect_speech(wav, "silero")
    duration = media.probe(sample_video)["duration"]
    gaps = compute_gaps(speech, duration)
    cuts = media.detect_scene_changes(sample_video)
    sig = MediaSignals.from_files(sample_video, wav, duration, speech, cuts)
    return {"wav": wav, "speech": speech, "duration": duration, "gaps": gaps, "cuts": cuts, "sig": sig}


def _toy_model(path, threshold=0.5):
    """Logistic regression where longer silences score higher (like real describers)."""
    rng = np.random.default_rng(0)
    X = rng.uniform(0, 1, size=(200, len(FEATURES)))
    d = rng.uniform(1.5, 8, size=200)
    X[:, FEATURES.index("duration")] = d
    y = (d > 3.5).astype(int)
    model = LogisticRegression(max_iter=1000).fit(X, y)
    meta = {"model": "logistic_regression", "features": FEATURES, "threshold": threshold, "train_videos": 2}
    joblib.dump({"model": model, "meta": meta}, path)
    path.with_suffix(".json").write_text(json.dumps(meta), encoding="utf-8")
    return path


def test_features_are_complete_and_finite(sample_analysis):
    sig = sample_analysis["sig"]
    assert sig.thumbs.shape[1:] == (18, 32) and len(sig.thumbs) >= 60  # 36 s at 2 fps
    assert len(sig.rms_db) > 1000
    feats = compute_gap_features(sample_analysis["gaps"], sig)
    assert len(feats) == len(sample_analysis["gaps"]) > 0
    for f in feats:
        assert list(f) == FEATURES
        assert all(math.isfinite(v) for v in f.values())
        assert 0 <= f["rel_position"] <= 1 and f["duration"] >= 1.5
    assert sum(f["is_first"] for f in feats) == 1 and sum(f["is_last"] for f in feats) == 1
    assert any(f["motion_mean"] > 0 for f in feats)  # the sample clip pans / cuts


def test_label_gaps_tolerance():
    gaps = [(2.0, 5.0), (10.0, 12.0)]
    assert label_gaps(gaps, [1.2, 3.0, 12.5]) == [2, 0]
    assert label_gaps(gaps, [12.5], after=0.6) == [0, 1]


def test_select_never_empty():
    assert select([0.1, 0.7, 0.4], 0.5) == [False, True, False]
    assert select([0.1, 0.3], 0.9) == [False, True]
    assert select([], 0.5) == []


def test_scorer_roundtrip_and_service(sample_analysis, sample_video, tmp_path, monkeypatch):
    path = _toy_model(tmp_path / "gap_scorer.joblib")
    scorer = GapScorer.load(path)
    feats = compute_gap_features(sample_analysis["gaps"], sample_analysis["sig"])
    scores = scorer.score(feats)
    assert len(scores) == len(feats) and all(0 <= s <= 1 for s in scores)
    longest = int(np.argmax([f["duration"] for f in feats]))
    assert scores[longest] == max(scores)

    st = get_settings()
    monkeypatch.setattr(st, "gap_model_path", path)
    args = (st, sample_video, sample_analysis["wav"], sample_analysis["duration"], sample_analysis["speech"],
            sample_analysis["cuts"], sample_analysis["gaps"])
    monkeypatch.setattr(st, "gap_selection", "auto")
    sc, rec, mode = service.score_gaps(*args)
    assert mode == "model" and sc == scores and rec == select(scores, 0.5)
    monkeypatch.setattr(st, "gap_selection", "all")
    sc, rec, mode = service.score_gaps(*args)
    assert mode == "all" and all(s is None for s in sc) and all(rec)
    monkeypatch.setattr(st, "gap_selection", "model")
    monkeypatch.setattr(st, "gap_model_path", tmp_path / "missing.joblib")
    with pytest.raises(ValueError):
        service.score_gaps(*args)


def test_api_drafts_only_selected_gaps_and_human_override(client, tmp_path, monkeypatch):
    st = get_settings()
    monkeypatch.setattr(st, "gap_model_path", _toy_model(tmp_path / "gap_scorer.joblib"))
    monkeypatch.setattr(st, "gap_selection", "auto")
    monkeypatch.setattr(st, "gap_score_threshold", 0.9999)  # keep (almost) nothing: only the best gap

    info = client.get("/api/system").json()["gap_model"]
    assert info["active"] is True and info["threshold"] == 0.9999

    pid = client.post("/api/projects/sample").json()["id"]
    job_id = client.post(f"/api/projects/{pid}/analyze").json()["id"]
    for _ in range(400):
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["status"] in ("done", "error"):
            break
        time.sleep(0.3)
    assert job["status"] == "done", job["error"]
    assert job["result"]["gap_selection"] == "model"

    proj = client.get(f"/api/projects/{pid}").json()
    gaps = proj["gaps"]
    assert all(g["score"] is not None for g in gaps)
    assert sum(g["recommended"] for g in gaps) == 1 < len(gaps)
    assert len(proj["descriptions"]) == 1
    assert proj["descriptions"][0]["gap_id"] == next(g["id"] for g in gaps if g["recommended"])

    # the human can still draft in a silence the model left out
    skipped = next(g for g in gaps if not g["recommended"])
    r = client.post(f"/api/gaps/{skipped['id']}/draft")
    assert r.status_code == 201, r.text
    d = r.json()
    assert d["gap_id"] == skipped["id"] and d["status"] == "ai_draft"
    assert skipped["start"] <= d["start"] < d["end"] <= skipped["end"]
    assert "pertinence ML" in d["history"][0]["detail"]
    assert client.post(f"/api/gaps/{skipped['id']}/draft").status_code == 409
    assert client.post("/api/gaps/999999/draft").status_code == 404
