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


# ------------------------------------------------------------------ quota / batching -----------------

import pytest  # noqa: E402

from app.providers import vision  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_quota_memory(monkeypatch):
    vision._EXHAUSTED.clear()
    monkeypatch.setattr(vision.time, "sleep", lambda s: None)
    yield
    vision._EXHAUSTED.clear()


def _ok(payload):
    return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": json.dumps(payload)}]}}]})


def _quota(delay="47917s"):
    return httpx.Response(429, json={"error": {"code": 429, "message": "quota", "details": [
        {"@type": "type.googleapis.com/google.rpc.QuotaFailure",
         "violations": [{"quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier", "quotaValue": "20"}]},
        {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": delay}]}})


def _gemini(handler, models="gemini-a", fallbacks="gemini-b", batch=8):
    s = Settings(gemini_api_key="k", gemini_model=models, gemini_fallback_models=fallbacks, vlm_batch_size=batch)
    return GeminiVision(s, client=httpx.Client(transport=httpx.MockTransport(handler)))


def test_gemini_batches_several_slots_in_one_request(tmp_path):
    img = tmp_path / "x.jpg"
    img.write_bytes(b"\xff\xd8fake")
    calls = []

    def handler(request):
        body = json.loads(request.content)
        calls.append(body)
        texts = [p["text"] for p in body["contents"][0]["parts"] if "text" in p]
        assert any("Slot 3" in t for t in texts)
        assert "NO facial recognition" in body["system_instruction"]["parts"][0]["text"]
        return _ok({"items": [{"slot": 2, "text": "Deux.", "confidence": 0.7},
                              {"slot": 1, "text": "Un.", "confidence": 0.9, "uncertain": ["x"]},
                              {"slot": 3, "text": "Trois.", "confidence": 0.5}]})

    reqs = [_req(start=float(i), end=i + 2.5, frames=[img], frame_times=[i + 1.0]) for i in range(3)]
    out = _gemini(handler).draft_many(reqs)
    assert len(calls) == 1  # 3 slots, 1 request
    assert [d.text for d in out] == ["Un.", "Deux.", "Trois."]
    assert out[0].uncertain == ["x"] and out[0].model == "gemini-a"


def test_gemini_switches_model_when_daily_quota_is_exhausted():
    hits = []

    def handler(request):
        model = request.url.path.split("/")[-1].split(":")[0]
        hits.append(model)
        return _quota() if model == "gemini-a" else _ok({"text": "Nuit.", "confidence": 0.6})

    v = _gemini(handler)
    assert v.draft(_req()).model == "gemini-b"
    assert v.draft(_req()).model == "gemini-b"
    assert hits == ["gemini-a", "gemini-b", "gemini-b"]  # the exhausted model is not retried


def test_gemini_short_rate_limit_is_retried_on_the_same_model():
    hits = []

    def handler(request):
        hits.append(1)
        return _quota("2s") if len(hits) == 1 else _ok({"text": "Jour.", "confidence": 0.6})

    d = _gemini(handler, fallbacks="").draft(_req())
    assert d.text == "Jour." and d.model == "gemini-a" and len(hits) == 2


def test_all_quotas_exhausted_returns_errors_instead_of_crashing():
    v = _gemini(lambda request: _quota(), batch=2)
    out = v.draft_many([_req(start=float(i), end=i + 2.0) for i in range(5)])
    assert len(out) == 5 and all(isinstance(e, vision.QuotaExceeded) for e in out)
    assert "Quota Gemini épuisé" in str(out[0]) and "20 requêtes" in str(out[0])
    with pytest.raises(vision.QuotaExceeded):
        v.draft(_req())


def test_parse_batch_answer_tolerates_missing_and_unordered_items():
    raw = '{"items": [{"slot": 3, "text": "C"}, {"slot": 1, "text": "A", "confidence": 2}, {"slot": 9, "text": "?"}]}'
    out = vision.parse_batch_answer(raw, 3)
    assert out[0] == ("A", 1.0, []) and out[1] is None and out[2][0] == "C"
    assert vision.parse_batch_answer("not json", 2) == [None, None]
