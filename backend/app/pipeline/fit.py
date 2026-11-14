"""Estimate spoken duration of a description and fit it to its gap."""

from __future__ import annotations

import re

# Conservative AD speaking rates (words per second). Arabic words are longer on average.
WORDS_PER_SECOND = {"fr": 2.6, "ar": 2.0, "aeb": 2.1}


def word_count(text: str) -> int:
    return len(re.findall(r"\w+", text, flags=re.UNICODE))


def estimate_seconds(text: str, language: str = "fr") -> float:
    wps = WORDS_PER_SECOND.get(language, 2.5)
    return round(word_count(text) / wps + 0.3, 2)  # +0.3 s breathing room


def max_words(duration: float, language: str = "fr") -> int:
    wps = WORDS_PER_SECOND.get(language, 2.5)
    return max(2, int((duration - 0.3) * wps))


def fit_to_gap(text: str, duration: float, language: str = "fr") -> tuple[str, list[str]]:
    """Trim to the time available. Returns (text, flags). Never silently drops everything."""
    text = re.sub(r"\s+", " ", text).strip()
    flags: list[str] = []
    if estimate_seconds(text, language) <= duration:
        return text, flags
    limit = max_words(duration, language)
    # prefer cutting at a sentence / clause boundary
    sentences = re.split(r"(?<=[.!?؟;،,])\s+", text)
    kept = ""
    for sentence in sentences:
        candidate = (kept + " " + sentence).strip()
        if word_count(candidate) <= limit:
            kept = candidate
        else:
            break
    if not kept:
        words = text.split(" ")
        kept = " ".join(words[:limit]).rstrip(",;،") + "…"
    flags.append("trimmed_to_fit")
    if estimate_seconds(kept, language) > duration:
        flags.append("too_long")
    return kept, flags
