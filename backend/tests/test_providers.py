import json

import httpx

from app.config import Settings
from app.providers.vision import (
    DemoVision,
    DraftRequest,
    GeminiVision,
    OpenAICompatibleVision,
    parse_json_answer,
)


def _req(**kw):
    base = dict(start=0.0, end=2.75, language="fr", max_words=6, frames=[], frame_times=[])
    base.update(kw)
    return DraftRequest(**base)


def test_demo_uses_sample_script_only_for_sample():
    v = DemoVision(Settings())
    d = v.draft(_req(is_sample=True))
    assert "porte bleue" in d.text.lower() and d.provider == "demo"
    d_ar = v.draft(_req(is_sample=True, language="ar"))
    assert "باب" in d_ar.text
    generic = v.draft(_req(is_sample=False))
    assert generic.confidence < 0.5  # generic demo lines are always low confidence
    assert generic.uncertain


def test_demo_generic_reads_real_pixels(sample_video, tmp_path):
    from app.pipeline.media import extract_frame

    frame = extract_frame(sample_video, 13.0, tmp_path / "f.jpg")  # ochre alley
    d = DemoVision(Settings()).draft(_req(frames=[frame], frame_times=[13.0], scene_change=True))
    assert "orangée" in d.text and d.text.startswith("Changement de plan")


def test_parse_json_answer():
    assert parse_json_answer('```json\n{"text": "Hi", "confidence": 0.9}\n```')[:2] == ("Hi", 0.9)
    text, conf, unc = parse_json_answer("plain text")
    assert text == "plain text" and conf < 0.5 and unc


def test_gemini_request_shape(tmp_path):
    img = tmp_path / "x.jpg"
    img.write_bytes(b"\xff\xd8fake")
    seen = {}

    def handler(request: httpx.Request):
        seen["url"] = str(request.url)
        seen["key"] = request.headers.get("x-goog-api-key")
        seen["body"] = json.loads(request.content)
        answer = {"text": "Une femme sourit.", "confidence": 0.8, "uncertain": []}
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": json.dumps(answer)}]}}]})

    s = Settings(gemini_api_key="k", gemini_model="gemini-test")
    v = GeminiVision(s, client=httpx.Client(transport=httpx.MockTransport(handler)))
    d = v.draft(_req(frames=[img], frame_times=[1.0], cast=[{"name": "Amel", "description": "foulard rouge"}]))
    assert d.text == "Une femme sourit." and d.provider == "gemini"
    assert "gemini-test:generateContent" in seen["url"] and seen["key"] == "k"
    parts = seen["body"]["contents"][0]["parts"]
    assert "Amel" in parts[0]["text"] and parts[1]["inline_data"]["mime_type"] == "image/jpeg"
    assert "NO facial recognition" in seen["body"]["system_instruction"]["parts"][0]["text"]


def test_openai_compatible_request_shape(tmp_path):
    img = tmp_path / "x.jpg"
    img.write_bytes(b"\xff\xd8fake")

    def handler(request: httpx.Request):
        assert request.url.path == "/v1/chat/completions"
        body = json.loads(request.content)
        assert body["messages"][1]["content"][1]["type"] == "image_url"
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"text": "Nuit.", "confidence": 0.4}'}}]})

    s = Settings(openai_api_key="k", openai_base_url="http://local/v1", openai_model="m")
    v = OpenAICompatibleVision(s, client=httpx.Client(transport=httpx.MockTransport(handler)))
    d = v.draft(_req(frames=[img], frame_times=[1.0]))
    assert d.text == "Nuit." and d.confidence == 0.4
