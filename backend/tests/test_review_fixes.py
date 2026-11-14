"""Too-long lines, re-running the analysis, and which files the API may serve."""

import time

from app.models import Description, DescriptionStatus
from app.service import compute_flags


def _wait(client, job_id, timeout=120):
    t0 = time.time()
    while time.time() - t0 < timeout:
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["status"] in ("done", "error"):
            return job
        time.sleep(0.3)
    raise AssertionError("job timeout")


def _analysed_sample(client) -> dict:
    pid = client.post("/api/projects/sample").json()["id"]
    assert _wait(client, client.post(f"/api/projects/{pid}/analyze").json()["id"])["status"] == "done"
    return client.get(f"/api/projects/{pid}").json()


def _empty_gap(client, proj, gap):
    for d in proj["descriptions"]:
        if gap["start"] - 0.01 <= d["start"] <= gap["end"]:
            client.delete(f"/api/descriptions/{d['id']}")


def test_database_and_other_data_files_are_never_served(client):
    proj = _analysed_sample(client)

    assert client.get("/api/files/app.db").status_code == 404
    assert client.get("/api/files/../backend/app/config.py").status_code == 404
    assert client.get(proj["video_url"], headers={"Range": "bytes=0-9"}).status_code == 206  # media still served
    client.delete(f"/api/projects/{proj['id']}")


def test_reanalysis_needs_confirmation_when_humans_worked(client):
    proj = _analysed_sample(client)
    pid = proj["id"]
    client.post(f"/api/descriptions/{proj['descriptions'][0]['id']}/validate", json={"validator": "Amira"})

    refused = client.post(f"/api/projects/{pid}/analyze")
    assert refused.status_code == 409 and "1 ligne(s)" in refused.json()["detail"]
    assert client.get(f"/api/projects/{pid}").json()["counts"]["validated"] == 1  # nothing erased

    job = client.post(f"/api/projects/{pid}/analyze", params={"force": "true"}).json()
    assert _wait(client, job["id"])["status"] == "done"
    assert client.get(f"/api/projects/{pid}").json()["counts"]["validated"] == 0
    client.delete(f"/api/projects/{pid}")


def test_longer_text_lengthens_the_line_into_free_silence(client):
    proj = _analysed_sample(client)
    last = proj["gaps"][-1]  # runs to the end of the clip: plenty of room
    _empty_gap(client, proj, last)
    line = client.post(f"/api/projects/{proj['id']}/descriptions",
                       json={"start": last["start"], "end": last["start"] + 1.0, "text": "Nuit.", "language": "fr"}).json()

    edited = client.patch(f"/api/descriptions/{line['id']}",
                          json={"text": "La nuit tombe sur la médina.", "editor": "Amira"}).json()

    assert edited["end"] > line["end"] and "too_long" not in edited["flags"]
    assert any("fin allongée" in h["detail"] for h in edited["history"])
    v = client.post(f"/api/descriptions/{line['id']}/validate", json={"validator": "Amira"})
    assert v.status_code == 200 and v.json()["status"] == "validated"
    client.delete(f"/api/projects/{proj['id']}")


def test_too_long_line_without_room_explains_the_word_limit(client):
    proj = _analysed_sample(client)
    first = proj["gaps"][0]  # followed by dialogue: the line cannot grow past it
    _empty_gap(client, proj, first)
    line = client.post(f"/api/projects/{proj['id']}/descriptions",
                       json={"start": first["end"] - 1.2, "end": first["end"], "text": "Une porte.", "language": "fr"}).json()
    client.patch(f"/api/descriptions/{line['id']}",
                 json={"text": " ".join(["mot"] * 15), "editor": "Amira"})

    r = client.post(f"/api/descriptions/{line['id']}/validate", json={"validator": "Amira"})

    assert r.status_code == 422 and "mots maximum" in r.json()["detail"]
    client.delete(f"/api/projects/{proj['id']}")


def test_trimmed_sentences_are_marked_for_review():
    d = Description(project_id="x", start=0, end=3, text="Une femme traverse…", flags_json='["trimmed_to_fit"]',
                    status=DescriptionStatus.AI_DRAFT, confidence=0.9)

    compute_flags(d, 0.6)

    assert d.needs_review
