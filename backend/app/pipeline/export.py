"""WebVTT (kind=descriptions), TTML and credits generation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from xml.sax.saxutils import escape

RTL_LANGS = {"ar", "aeb"}
RLM = "‏"

LANG_TAGS = {"fr": "fr", "ar": "ar", "aeb": "aeb", "en": "en"}


@dataclass
class Cue:
    start: float
    end: float
    text: str
    language: str = "fr"
    origin: str = "ai"
    validated_by: str = ""
    validated_at: datetime | None = None


def ts_vtt(seconds: float) -> str:
    ms = int(round(max(0.0, seconds) * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


def _clean(text: str) -> str:
    # "-->" and blank lines are illegal inside a VTT cue payload
    return " ".join(text.replace("-->", "→").split())


def to_vtt(cues: list[Cue], title: str, demo_mode: bool = False) -> str:
    lines = ["WEBVTT - Audiodescription", ""]
    lines.append("NOTE")
    lines.append(f"Titre : {_clean(title)}")
    lines.append("Piste de type kind=descriptions. Audiodescription assistée par IA, validée par un·e humain·e.")
    if demo_mode:
        lines.append("DEMO MODE : les brouillons IA proviennent d'un fournisseur simulé (aucun modèle réel).")
    lines.append("")
    for i, cue in enumerate(sorted(cues, key=lambda c: c.start), start=1):
        text = _clean(cue.text)
        if cue.language in RTL_LANGS:
            text = f"<lang {LANG_TAGS[cue.language]}>{RLM}{text}</lang>"
        origin = "IA puis validée" if cue.origin == "ai" else "rédigée par un humain"
        lines.append(f"NOTE origine={origin}; validée par {cue.validated_by or '-'}")
        lines.append("")
        lines.append(f"ad-{i}")
        lines.append(f"{ts_vtt(cue.start)} --> {ts_vtt(cue.end)}")
        lines.append(text)
        lines.append("")
    return "\n".join(lines)


def ts_ttml(seconds: float) -> str:
    return ts_vtt(seconds)


def to_ttml(cues: list[Cue], title: str, language: str, demo_mode: bool = False) -> str:
    lang = LANG_TAGS.get(language, "fr")
    out = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<tt xmlns="http://www.w3.org/ns/ttml" xmlns:tts="http://www.w3.org/ns/ttml#styling" '
        f'xmlns:ttm="http://www.w3.org/ns/ttml#metadata" xml:lang="{lang}">',
        "  <head>",
        "    <metadata>",
        f"      <ttm:title>{escape(title)}</ttm:title>",
        "      <ttm:desc>Audiodescription assistée par IA, validée par un·e humain·e."
        + (" DEMO MODE : brouillons IA simulés." if demo_mode else "")
        + "</ttm:desc>",
        "    </metadata>",
        "  </head>",
        "  <body>",
        "    <div>",
    ]
    for i, cue in enumerate(sorted(cues, key=lambda c: c.start), start=1):
        clang = LANG_TAGS.get(cue.language, lang)
        direction = ' tts:direction="rtl"' if cue.language in RTL_LANGS else ""
        agent = "ai-assisted" if cue.origin == "ai" else "human"
        out.append(
            f'      <p xml:id="ad-{i}" begin="{ts_ttml(cue.start)}" end="{ts_ttml(cue.end)}" '
            f'xml:lang="{clang}"{direction} ttm:role="description" ttm:agent="{agent}">{escape(_clean(cue.text))}</p>'
        )
    out += ["    </div>", "  </body>", "</tt>", ""]
    return "\n".join(out)


def credits_text(
    title: str,
    validators: list[str],
    n_validated: int,
    n_ai_origin: int,
    n_human_origin: int,
    asr: str,
    vlm: str,
    tts: str,
    demo_mode: bool,
) -> str:
    names = ", ".join(sorted(set(v for v in validators if v))) or "—"
    lines = [
        f"Titre : {title}",
        "",
        f"audiodescription assistée par IA, validée par {names}",
        "",
        f"Lignes d'audiodescription validées par un humain : {n_validated}",
        f"  - dont brouillons IA relus et validés : {n_ai_origin}",
        f"  - dont lignes rédigées par un humain : {n_human_origin}",
        "",
        "Outils :",
        f"  - Transcription (ASR) : {asr}",
        f"  - Compréhension visuelle / rédaction : {vlm}",
        f"  - Voix : {tts}",
        "",
        "L'IA assiste les audiodescripteurs, elle ne les remplace pas.",
        "Aucune reconnaissance faciale n'a été utilisée ; les personnages sont nommés",
        "uniquement à partir de la distribution fournie par l'utilisateur.",
        "Le script d'audiodescription est remis à l'ayant droit de l'œuvre.",
    ]
    if demo_mode:
        lines += ["", "DEMO MODE : les brouillons IA de ce projet proviennent d'un fournisseur simulé."]
    lines.append("")
    return "\n".join(lines)
