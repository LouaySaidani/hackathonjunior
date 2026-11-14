import xml.etree.ElementTree as ET

from app.pipeline.export import Cue, credits_text, to_ttml, to_vtt, ts_vtt
from app.pipeline.fit import estimate_seconds, fit_to_gap


def test_estimate_and_fit():
    assert estimate_seconds("un deux trois quatre cinq", "fr") < 2.5
    long = ("Une femme en sefsari blanc traverse lentement la place de la médina "
            "pendant que des enfants jouent au ballon.")
    text, flags = fit_to_gap(long, 2.0, "fr")
    assert "trimmed_to_fit" in flags
    assert estimate_seconds(text, "fr") <= 2.0 or "too_long" in flags
    ok, flags = fit_to_gap("Porte bleue.", 3.0, "fr")
    assert ok == "Porte bleue." and flags == []


def test_vtt_format_and_rtl():
    cues = [
        Cue(1.0, 2.5, "Une porte bleue.", "fr", "ai", "Amira"),
        Cue(10.0, 12.0, "باب أزرق.", "ar", "human", "Amira"),
        Cue(5.0, 6.0, "a --> b", "fr"),
    ]
    vtt = to_vtt(cues, "Test", demo_mode=True)
    assert vtt.startswith("WEBVTT")
    assert "00:00:01.000 --> 00:00:02.500" in vtt
    assert "DEMO MODE" in vtt
    assert "<lang ar>‏باب أزرق.</lang>" in vtt
    assert "a → b" in vtt  # arrow escaped inside payload
    assert vtt.index("00:00:05.000") < vtt.index("00:00:10.000")  # cues sorted
    assert ts_vtt(3723.456) == "01:02:03.456"


def test_ttml_is_valid_xml_with_rtl():
    cues = [Cue(1.0, 2.0, "A & B <c>", "fr"), Cue(3.0, 4.0, "ليل", "aeb")]
    root = ET.fromstring(to_ttml(cues, "Titre", "fr"))
    ps = root.findall(".//{http://www.w3.org/ns/ttml}p")
    assert len(ps) == 2
    assert ps[0].text == "A & B <c>"
    assert ps[1].get("{http://www.w3.org/ns/ttml#styling}direction") == "rtl"


def test_credits_mention_human_validation():
    txt = credits_text("Film", ["Amira", "Amira", "Sami"], 3, 2, 1, "whisper", "demo", "edge", True)
    assert "audiodescription assistée par IA, validée par Amira, Sami" in txt
    assert "DEMO MODE" in txt
