"""Audio description is written in French, Arabic or darija; a film may still speak another language."""


def _create(client, video, **form):
    with video.open("rb") as f:
        return client.post("/api/projects", files={"file": ("film.mp4", f, "video/mp4")},
                           data={"title": "Langues", "consent": "true", **form})


def test_english_is_not_an_audio_description_language(client, sample_video):
    r = _create(client, sample_video, language="en")

    assert r.status_code == 422


def test_an_english_speaking_film_can_be_described_in_french(client, sample_video):
    r = _create(client, sample_video, language="fr", dialogue_language="en")

    assert r.status_code == 201
    p = r.json()
    assert p["language"] == "fr" and p["dialogue_language"] == "en"
    client.delete(f"/api/projects/{p['id']}")
