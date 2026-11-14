"""Vision-language drafting providers: gemini | openai (any OpenAI-compatible endpoint) | demo.

All providers receive the same `DraftRequest` (keyframes + surrounding dialogue + user cast list)
and must return a `Draft`. No facial recognition: characters may only be named from the cast list.
"""

from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from ..config import Settings

LANG_NAMES = {
    "fr": "French",
    "ar": "Modern Standard Arabic (فصحى)",
    "aeb": "Tunisian Arabic (Darija / تونسي), written in Arabic script",
    "en": "English",
}


@dataclass
class DraftRequest:
    start: float
    end: float
    language: str
    max_words: int
    frames: list[Path]
    frame_times: list[float]
    dialogue_before: str = ""
    dialogue_after: str = ""
    previous_description: str = ""
    cast: list[dict] = field(default_factory=list)
    scene_change: bool = False
    film_title: str = ""
    is_sample: bool = False
    hint: str = ""  # optional instruction from the human describer on regenerate


@dataclass
class Draft:
    text: str
    confidence: float
    provider: str
    model: str
    uncertain: list[str] = field(default_factory=list)


SYSTEM_PROMPT = """You are an assistant to a professional audio describer (audiodescripteur) working on \
Tunisian and Francophone films for blind and visually impaired audiences. You write a DRAFT that a \
human will edit and validate.

Strict rules:
1. Describe ONLY what is visible in the frames: actions, gestures, expressions, movements, objects, places, \
scene transitions. Never invent details. Never interpret intentions you cannot see.
2. NO facial recognition. Never identify real people. Name a character ONLY if the user-provided cast list \
contains a matching visual description; otherwise use a neutral description ("une femme en foulard rouge").
3. Do not repeat or paraphrase the dialogue; add only visual information the dialogue does not give.
4. Present tense, concise, natural, culturally sensitive and respectful (Tunisian/Arab context: use correct \
local terms, e.g. chéchia, sefsari, médina, when clearly visible).
5. Maximum {max_words} words - it must fit in a {duration:.1f}-second silence.
6. Write in {language}.
7. If you are unsure about something, lower the confidence and list it in "uncertain".

Answer ONLY with JSON: {{"text": "...", "confidence": 0.0-1.0, "uncertain": ["..."]}}"""


def build_user_prompt(req: DraftRequest) -> str:
    cast = "\n".join(f"- {c.get('name', '?')}: {c.get('description', '')}" for c in req.cast) or "(none provided)"
    parts = [
        f"Film: {req.film_title or 'untitled'}",
        f"Silence window: {req.start:.2f}s -> {req.end:.2f}s ({req.end - req.start:.1f}s).",
        f"Frames attached at times: {', '.join(f'{t:.2f}s' for t in req.frame_times)}.",
        f"Scene change inside the window: {'yes' if req.scene_change else 'no'}.",
        f"Dialogue just before: “{req.dialogue_before or '-'}”",
        f"Dialogue just after: “{req.dialogue_after or '-'}”",
        f"Previous description (avoid repeating it): “{req.previous_description or '-'}”",
        f"Cast list supplied by the user (the ONLY allowed names):\n{cast}",
    ]
    if req.hint:
        parts.append(f"Instruction from the human describer for this new draft: {req.hint}")
    return "\n".join(parts)


def parse_json_answer(raw: str) -> tuple[str, float, list[str]]:
    match = re.search(r"\{.*\}", raw, flags=re.S)
    if not match:
        return raw.strip(), 0.3, ["réponse non structurée"]
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return raw.strip(), 0.3, ["réponse non structurée"]
    conf = data.get("confidence", 0.5)
    try:
        conf = float(conf)
    except (TypeError, ValueError):
        conf = 0.5
    return str(data.get("text", "")).strip(), max(0.0, min(1.0, conf)), [str(u) for u in data.get("uncertain", [])]


def _b64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode()


class VisionProvider:
    name = "base"
    model = ""

    def draft(self, req: DraftRequest) -> Draft:
        raise NotImplementedError


class GeminiVision(VisionProvider):
    name = "gemini"

    def __init__(self, settings: Settings, client: httpx.Client | None = None):
        self.key = settings.gemini_api_key
        self.model = settings.gemini_model
        self.client = client or httpx.Client(timeout=60)

    def draft(self, req: DraftRequest) -> Draft:
        system = SYSTEM_PROMPT.format(max_words=req.max_words, duration=req.end - req.start,
                                      language=LANG_NAMES.get(req.language, req.language))
        parts: list[dict] = [{"text": build_user_prompt(req)}]
        parts += [{"inline_data": {"mime_type": "image/jpeg", "data": _b64(f)}} for f in req.frames]
        body = {
            "system_instruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": {"temperature": 0.3, "responseMimeType": "application/json"},
        }
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        resp = self.client.post(url, json=body, headers={"x-goog-api-key": self.key})
        resp.raise_for_status()
        data = resp.json()
        raw = "".join(p.get("text", "") for p in data["candidates"][0]["content"]["parts"])
        text, conf, unc = parse_json_answer(raw)
        return Draft(text, conf, self.name, self.model, unc)


class OpenAICompatibleVision(VisionProvider):
    """Works with OpenAI, Azure-compatible gateways, vLLM, Ollama (/v1), LM Studio, OpenRouter..."""

    name = "openai"

    def __init__(self, settings: Settings, client: httpx.Client | None = None):
        self.key = settings.openai_api_key
        self.base_url = settings.openai_base_url.rstrip("/")
        self.model = settings.openai_model
        self.client = client or httpx.Client(timeout=90)

    def draft(self, req: DraftRequest) -> Draft:
        system = SYSTEM_PROMPT.format(max_words=req.max_words, duration=req.end - req.start,
                                      language=LANG_NAMES.get(req.language, req.language))
        content: list[dict] = [{"type": "text", "text": build_user_prompt(req)}]
        content += [{"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{_b64(f)}"}} for f in req.frames]
        body = {
            "model": self.model,
            "temperature": 0.3,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": content}],
        }
        headers = {"Authorization": f"Bearer {self.key}"} if self.key else {}
        resp = self.client.post(f"{self.base_url}/chat/completions", json=body, headers=headers)
        resp.raise_for_status()
        raw = resp.json()["choices"][0]["message"]["content"]
        text, conf, unc = parse_json_answer(raw)
        return Draft(text, conf, self.name, self.model, unc)


# ---------------------------------------------------------------- DEMO -----------------------------

COLOR_NAMES = {
    "fr": ["rouge", "orangée", "jaune", "verte", "cyan", "bleue", "violette", "rose"],
    "en": ["red", "orange", "yellow", "green", "cyan", "blue", "purple", "pink"],
    "ar": ["حمراء", "برتقالية", "صفراء", "خضراء", "سماوية", "زرقاء", "بنفسجية", "وردية"],
    "aeb": ["حمراء", "برتقالية", "صفراء", "خضراء", "سماوية", "زرقاء", "بنفسجية", "وردية"],
}


def _frame_stats(frame: Path) -> tuple[int, float, float]:
    """(hue bucket 0-7, brightness 0-1, saturation 0-1) computed from real pixels."""
    import cv2
    import numpy as np

    img = cv2.imread(str(frame))
    if img is None:
        return 0, 0.5, 0.0
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    sat_mask = hsv[..., 1] > 60
    hue = hsv[..., 0][sat_mask] if sat_mask.any() else hsv[..., 0].ravel()
    # OpenCV hue is 0-179. Upper bounds for: red, orange, yellow, green, cyan, blue, purple, pink, (red again)
    bounds = np.array([8, 20, 33, 78, 95, 130, 150, 165, 180])
    buckets = np.searchsorted(bounds, hue.astype(int), side="right") % 8
    hist = np.bincount(buckets, minlength=8)
    return int(hist.argmax()), float(hsv[..., 2].mean() / 255), float(hsv[..., 1].mean() / 255)


class DemoVision(VisionProvider):
    """DEMO MODE. For the bundled sample clip it returns a curated reference script; for any other
    video it returns a deliberately generic, low-confidence line built from real pixel statistics.
    Output is always flagged `demo` - it is never presented as real AI analysis."""

    name = "demo"
    model = "demo-mock"

    def __init__(self, settings: Settings):
        path = settings.samples_dir / "sample_script.json"
        self.script = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []

    def draft(self, req: DraftRequest) -> Draft:
        if req.is_sample:
            for item in self.script:
                if req.start - 0.5 <= item["anchor"] <= req.end + 0.5:
                    text = item["text"].get(req.language) or item["text"]["fr"]
                    if req.hint:
                        text = item.get("alt", {}).get(req.language) or text
                    return Draft(text, item.get("confidence", 0.7), self.name, "demo-sample-script",
                                 item.get("uncertain", []))
        return self._generic(req)

    def _generic(self, req: DraftRequest) -> Draft:
        lang = req.language if req.language in COLOR_NAMES else "fr"
        if not req.frames:
            hue, bright = 0, 0.5
        else:
            hue, bright, _ = _frame_stats(req.frames[len(req.frames) // 2])
        color = COLOR_NAMES[lang][hue]
        light = {"fr": ("sombre", "lumineux"), "en": ("dark", "bright"),
                 "ar": ("مظلمة", "مضيئة"), "aeb": ("مظلمة", "مضوية")}[lang][1 if bright > 0.45 else 0]
        templates = {
            "fr": ("Changement de plan. " if req.scene_change else "") + f"Plan {light}, à dominante {color}.",
            "en": ("Cut. " if req.scene_change else "") + f"A {light} shot, mostly {color}.",
            "ar": ("تغيّر اللقطة. " if req.scene_change else "") + f"لقطة {light} بألوان {color}.",
            "aeb": ("تتبدّل اللقطة. " if req.scene_change else "") + f"لقطة {light} لونها {color}.",
        }
        return Draft(templates[lang], 0.3, self.name, self.model,
                     ["DEMO : description générique calculée à partir des couleurs, à réécrire"])


def get_vision(settings: Settings) -> VisionProvider:
    p = settings.resolved_vlm_provider()
    if p == "gemini":
        return GeminiVision(settings)
    if p == "openai":
        return OpenAICompatibleVision(settings)
    return DemoVision(settings)
