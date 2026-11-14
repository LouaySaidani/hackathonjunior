"""End-to-end API smoke test on the sample clip, in DEMO MODE (no network, no model download)."""

import time
import xml.etree.ElementTree as ET

from app.pipeline.fit import estimate_seconds
from app.pipeline.vad import overlaps


def _wait(client, job_id, timeout=120):
    t0 = time.time()
    while time.time() - t0 < timeout:
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["status"] in ("done", "error"):
            return job
        time.sleep(0.3)
    raise AssertionError("job timeout")


def test_health_and_system(client):
    assert client.get("/health").json()["status"] == "ok"
    sysinfo = client.get("/api/system").json()
    assert sysinfo["demo_mode"] is True
    assert "gemini_api_key" not in str(sysinfo)  # secrets never leak


def test_upload_requires_consent_and_valid_type(client, sample_video):
    with sample_video.open("rb") as f:
        r = client.post("/api/projects", files={"file": ("a.mp4", f, "video/mp4")}, data={"title": "x", "consent": "false"})
    assert r.status_code == 400
    r = client.post("/api/projects", files={"file": ("a.txt", b"hello", "text/plain")}, data={"title": "x", "consent": "true"})
    assert r.status_code == 415
    r = client.post("/api/projects", files={"file": ("a.mp4", b"not a video", "video/mp4")}, data={"title": "x", "consent": "true"})
    assert r.status_code == 415


def test_full_flow(client, tone_wav):
    # 1. sample project (rights-clear clip)
    p = client.post("/api/projects/sample").json()
    pid = p["id"]
    assert p["duration"] == 36.0 and p["consent"] is True

    # 2-4. analysis job
    job = _wait(client, client.post(f"/api/projects/{pid}/analyze").json()["id"])
    assert job["status"] == "done", job["error"]
    proj = client.get(f"/api/projects/{pid}").json()
    assert proj["status"] == "ready" and proj["demo_mode"] is True
    assert len(proj["transcript"]) == 4
    assert 4 <= len(proj["gaps"]) <= 6
    assert proj["keyframes"] and all(k["url"].startswith("/api/files/") for k in proj["keyframes"])
    assert any(k["reason"] == "scene_change" for k in proj["keyframes"])
    speech = [(s["start"], s["end"]) for s in proj["speech"]]
    descs = proj["descriptions"]
    assert descs
    for d in descs:
        assert d["status"] == "ai_draft"  # never auto-validated
        assert not overlaps((d["start"], d["end"]), speech)
        assert estimate_seconds(d["text"], d["language"]) <= d["end"] - d["start"] + 0.05 or "too_long" in d["flags"]
        assert "demo" in d["flags"]
    assert any(d["needs_review"] and "low_confidence" in d["flags"] for d in descs)
    assert client.get(proj["video_url"], headers={"Range": "bytes=0-99"}).status_code == 206

    first, second, third = descs[0], descs[1], descs[2]

    # 5. edit -> EDITED BY HUMAN
    r = client.patch(f"/api/descriptions/{first['id']}", json={"text": "Une porte bleue.", "editor": "Amira"})
    assert r.json()["status"] == "edited"
    # moving onto dialogue is refused
    s0 = proj["speech"][0]
    r = client.patch(f"/api/descriptions/{first['id']}", json={"start": s0["start"], "end": s0["end"]})
    assert r.status_code == 422
    # validation needs a human name
    assert client.post(f"/api/descriptions/{first['id']}/validate", json={"validator": ""}).status_code == 422
    v = client.post(f"/api/descriptions/{first['id']}/validate", json={"validator": "Amira"}).json()
    assert v["status"] == "validated" and v["validated_by"] == "Amira" and v["validated_at"]
    # regenerate -> back to AI draft
    rg = client.post(f"/api/descriptions/{second['id']}/regenerate", json={"hint": "plus court"}).json()
    assert rg["status"] == "ai_draft" and rg["text"]
    v2 = client.post(f"/api/descriptions/{second['id']}/validate", json={"validator": "Amira"}).json()
    assert v2["status"] == "validated"
    # reject
    assert client.post(f"/api/descriptions/{third['id']}/reject", json={"by": "Amira"}).json()["status"] == "rejected"
    # manual line in Arabic, inside the last gap
    g = proj["gaps"][-1]
    m = client.post(f"/api/projects/{pid}/descriptions",
                    json={"start": g["start"], "end": g["start"] + 2.5, "text": "ليل.", "language": "ar"}).json()
    assert m["origin"] == "human" and m["status"] == "edited"
    client.post(f"/api/descriptions/{m['id']}/validate", json={"validator": "Sami"})

    # persisted
    after = {d["id"]: d for d in client.get(f"/api/projects/{pid}").json()["descriptions"]}
    assert after[first["id"]]["status"] == "validated" and after[third["id"]]["status"] == "rejected"

    # 6. voice: TTS refused for unvalidated, demo TTS for validated, human upload
    assert client.post(f"/api/descriptions/{descs[3]['id']}/tts").status_code == 409
    t = client.post(f"/api/descriptions/{first['id']}/tts").json()
    assert t["audio_url"] and t["audio_source"] == "demo_tone"
    with tone_wav.open("rb") as f:
        h = client.post(f"/api/descriptions/{m['id']}/voice", files={"file": ("v.wav", f, "audio/wav")}).json()
    assert h["audio_source"] == "human" and h["audio_duration"] > 1
    job = _wait(client, client.post(f"/api/projects/{pid}/tts").json()["id"])
    assert job["status"] == "done"

    # 7. export
    job = _wait(client, client.post(f"/api/projects/{pid}/export").json()["id"])
    assert job["status"] == "done", job["error"]
    names = {f["name"] for f in client.get(f"/api/projects/{pid}/export").json()["files"]}
    assert {"film_audiodecrit.mp4", "ad_track.mp3", "ad_track.wav", "description.vtt", "description.ttml",
            "credits.txt", "script_ayant_droit.json", "export_complet.zip"} <= names
    vtt = client.get(f"/api/projects/{pid}/export/description.vtt").text
    assert vtt.startswith("WEBVTT") and "DEMO MODE" in vtt and "‏" in vtt
    assert vtt.count(" --> ") == 3  # only validated lines (rejected/unvalidated excluded)
    ET.fromstring(client.get(f"/api/projects/{pid}/export/description.ttml").content)
    credits = client.get(f"/api/projects/{pid}/export/credits.txt").text
    assert "audiodescription assistée par IA, validée par Amira, Sami" in credits
    assert client.get(f"/api/projects/{pid}/export/../app.db").status_code == 404


def test_feedback(client):
    assert client.post("/api/feedback", json={"comprehension": 4, "preferred_language": "darija",
                                              "consent": False}).status_code == 400
    assert client.post("/api/feedback", json={"comprehension": 4, "preferred_language": "darija",
                                              "consent": True, "comment": "واضح"}).status_code == 201
    client.post("/api/feedback", json={"comprehension": 2, "preferred_language": "msa", "consent": True})
    s = client.get("/api/feedback/summary").json()
    assert s["count"] == 2 and s["mean_comprehension"] == 3.0 and s["language_preference"]["darija"] == 1


def test_analysis_survives_exhausted_quota(client, monkeypatch):
    """A quota error on some slots must not throw away the analysis or the drafts already written."""
    from app import service
    from app.providers.vision import DemoVision, QuotaExceeded

    class HalfQuota(DemoVision):
        name, model = "gemini", "gemini-test"

        def draft_many(self, reqs, on_progress=None):
            half = len(reqs) // 2
            exc = QuotaExceeded("Quota Gemini épuisé pour tous les modèles.")
            return [self.draft(r) for r in reqs[:half]] + [exc] * (len(reqs) - half)

    monkeypatch.setattr(service, "get_vision", lambda settings: HalfQuota(settings))
    pid = client.post("/api/projects/sample").json()["id"]
    job = _wait(client, client.post(f"/api/projects/{pid}/analyze").json()["id"])
    assert job["status"] == "done", job["error"]
    assert any("sans brouillon" in n and "Rédiger ici" in n for n in job["result"]["notes"])
    proj = client.get(f"/api/projects/{pid}").json()
    assert proj["status"] == "ready"
    n_gaps = len(proj["gaps"])
    assert len(proj["descriptions"]) == n_gaps // 2 == job["result"]["drafts"]
