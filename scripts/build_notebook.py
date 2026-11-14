"""Builds notebooks/pipeline_demo.ipynb (kept as a script so the notebook stays reviewable in git)."""

from pathlib import Path

import nbformat as nbf

nb = nbf.v4.new_notebook()
md, code = nbf.v4.new_markdown_cell, nbf.v4.new_code_cell
nb.cells = [
    md("""# Basira — démonstration du pipeline (DEMO MODE)

Ce notebook exécute, sur le clip d'exemple **synthétique et libre de droits** (`samples/sample_medina.mp4`, CC0),
les étapes clés du pipeline : extraction audio → détection de la parole (VAD) → transcription →
calcul des silences → images clés → brouillons d'audiodescription → WebVTT.

Par défaut il tourne **sans réseau ni clé d'API** (`ASR_PROVIDER=demo`, `VLM_PROVIDER=demo`) :
les brouillons proviennent d'un script de référence et sont étiquetés `demo`.
Passez `ASR_PROVIDER=whisper` pour une vraie transcription faster-whisper (téléchargement du modèle)."""),
    code("""import os, sys, tempfile
from pathlib import Path

ROOT = Path.cwd().parent if Path.cwd().name == "notebooks" else Path.cwd()
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("ASR_PROVIDER", "demo")
os.environ.setdefault("VLM_PROVIDER", "demo")
os.environ.setdefault("DATA_DIR", tempfile.mkdtemp())

from app.config import get_settings
from app.pipeline import media
from app.pipeline.vad import detect_speech, compute_gaps, merge_intervals, overlaps
from app.pipeline.fit import fit_to_gap, max_words, estimate_seconds
from app.pipeline.export import Cue, to_vtt
from app.providers import asr
from app.providers.vision import get_vision, DraftRequest

settings = get_settings()
VIDEO = ROOT / "samples" / "sample_medina.mp4"
WORK = Path(tempfile.mkdtemp())
meta = media.probe(VIDEO)
meta"""),
    md("## 1. Audio + détection de la parole (Silero VAD, repli webrtcvad)"),
    code("""wav = media.extract_audio(VIDEO, WORK / "audio.wav")
speech, engine = detect_speech(wav, settings.vad_engine)
print(engine, [(round(a, 2), round(b, 2)) for a, b in speech])"""),
    md("## 2. Transcription"),
    code("""res = asr.transcribe(settings, wav, "fr", ROOT / "samples" / "sample.transcript.json")
print(res.provider, res.model, res.notes)
for s in res.segments:
    print(f"{s.start:6.2f}–{s.end:6.2f}  {s.text}")"""),
    md("## 3. Silences exploitables (≥ 1,5 s, marge de 0,25 s autour de la parole)"),
    code("""asr_only = [(s.start, s.end) for s in res.segments if not overlaps((s.start, s.end), speech, 0.0)]
speech_all = merge_intervals(speech + asr_only, join_within=0.1)
gaps = compute_gaps(speech_all, meta["duration"], settings.min_gap_seconds, settings.gap_padding_seconds)

def bar(t0, t1, ch, width=72, dur=meta["duration"]):
    return int(t0 / dur * width), max(1, int((t1 - t0) / dur * width)), ch
line = [" "] * 72
for a, b in speech_all:
    s, n, _ = bar(a, b, "#"); line[s:s + n] = "#" * n
for a, b in gaps:
    s, n, _ = bar(a, b, "."); line[s:s + n] = "." * n
print("|" + "".join(line) + "|   # parole   . silence exploitable")
gaps"""),
    md("## 4. Images clés (seulement dans les silences + changements de plan)"),
    code("""from app.service import select_keyframe_times
cuts = media.detect_scene_changes(VIDEO, settings.scene_threshold)
plan = {g: select_keyframe_times(g[0], g[1], cuts, settings.max_keyframes_per_gap) for g in gaps}
print("changements de plan :", cuts)
for g, frames in plan.items():
    print(g, frames)"""),
    md("## 5. Brouillons d'audiodescription (VLM) ajustés à la durée disponible"),
    code("""vision = get_vision(settings)
cues = []
for (a, b), frames in plan.items():
    paths = [media.extract_frame(VIDEO, t, WORK / f"f_{t:.2f}.jpg") for t, _ in frames]
    req = DraftRequest(start=a, end=b, language="fr", max_words=max_words(b - a, "fr"),
                       frames=paths, frame_times=[t for t, _ in frames], is_sample=True,
                       scene_change=any(r == "scene_change" for _, r in frames))
    d = vision.draft(req)
    text, flags = fit_to_gap(d.text, b - a, "fr")
    review = d.confidence < settings.confidence_threshold
    print(f"[{a:5.2f}-{b:5.2f}] conf={d.confidence:.2f} {'⚠ À RELIRE ' if review else ''}{flags} ({d.provider}) {text}")
    assert estimate_seconds(text, "fr") <= b - a or "too_long" in flags
    cues.append(Cue(a, min(b, a + estimate_seconds(text, "fr") + 0.4), text, "fr", "ai", "(non validé)"))"""),
    md("""## 6. WebVTT (`kind=descriptions`)

Dans l'application, **seules les lignes validées par un humain** sont exportées.
Ici on affiche les brouillons pour illustration."""),
    code("""print(to_vtt(cues, "Démo notebook", demo_mode=vision.name == "demo"))"""),
]
nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
out = Path(__file__).resolve().parents[1] / "notebooks" / "pipeline_demo.ipynb"
nbf.write(nb, out)
print("written", out)
