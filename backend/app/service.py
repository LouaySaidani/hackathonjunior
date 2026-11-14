"""Business logic: analysis pipeline, drafting, voice, export. Called by jobs and the API."""

from __future__ import annotations

import json
import logging
import shutil
import zipfile
from pathlib import Path

from sqlmodel import Session, delete, select

from .config import Settings, get_settings
from .db import session_scope
from .jobs import JobContext
from .models import (
    Description,
    DescriptionStatus,
    Gap,
    Keyframe,
    Project,
    SpeechRegion,
    TranscriptSegment,
    utcnow,
)
from .pipeline import export as exp
from .pipeline import media, mix
from .pipeline.fit import estimate_seconds, fit_to_gap, max_words
from .pipeline.gapscore import MediaSignals, compute_gap_features, get_gap_scorer
from .pipeline.gapscore import select as select_gaps
from .pipeline.vad import combine_speech, compute_gaps, detect_speech, overlaps, split_long_gaps
from .providers import asr as asr_mod
from .providers import tts as tts_mod
from .providers.vision import DraftRequest, get_vision

log = logging.getLogger("service")


# ------------------------------------------------------------------ paths ----------------------------

def project_dir(project_id: str, settings: Settings | None = None) -> Path:
    settings = settings or get_settings()
    d = settings.projects_dir / project_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def rel(path: Path, settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    return path.resolve().relative_to(settings.data_dir.resolve()).as_posix()


def absolute(relpath: str, settings: Settings | None = None) -> Path:
    settings = settings or get_settings()
    return settings.data_dir / relpath


def sidecar_for(project: Project, settings: Settings) -> Path | None:
    if project.is_sample:
        return settings.samples_dir / "sample.transcript.json"
    return None


def add_history(desc: Description, action: str, by: str = "", detail: str = "") -> None:
    hist = json.loads(desc.history_json or "[]")
    hist.append({"at": utcnow().isoformat(), "action": action, "by": by, "detail": detail[:300]})
    desc.history_json = json.dumps(hist, ensure_ascii=False)


def speech_regions(s: Session, project_id: str) -> list[tuple[float, float]]:
    rows = s.exec(select(SpeechRegion).where(SpeechRegion.project_id == project_id)).all()
    return [(r.start, r.end) for r in rows]


def available_until(s: Session, project: Project, t: float) -> float:
    """Time at which the next speech starts after t (or end of film)."""
    nxt = [a for a, _ in speech_regions(s, project.id) if a > t + 0.01]
    return min(nxt) if nxt else project.duration


def compute_flags(desc: Description, conf_threshold: float) -> None:
    flags = set(json.loads(desc.flags_json or "[]"))
    flags.discard("too_long")
    if estimate_seconds(desc.text, desc.language) > (desc.end - desc.start) + 0.05:
        flags.add("too_long")
    desc.flags_json = json.dumps(sorted(flags))
    desc.needs_review = bool(flags & {"too_long", "low_confidence", "uncertain"}) and desc.status != DescriptionStatus.VALIDATED


# ------------------------------------------------------------------ analysis --------------------------

def analyze(project_id: str, ctx: JobContext) -> dict:
    settings = get_settings()
    with session_scope() as s:
        p = s.get(Project, project_id)
        if not p:
            raise ValueError("Projet introuvable")
        p.status, p.error = "analyzing", ""
        s.add(p)
        s.commit()
        video = absolute(p.video_path)
        duration = p.duration
        lang_hint = p.dialogue_language
        sidecar = sidecar_for(p, settings)
        has_audio = bool(p.audio_codec)
    pdir = project_dir(project_id)
    try:
        # 1. audio
        ctx.update(0.05, "audio", "Extraction de la piste audio (FFmpeg)…")
        wav = pdir / "audio.wav"
        if has_audio:
            media.extract_audio(video, wav)
        else:
            media.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-t", f"{duration:.3f}", "-i",
                       "anullsrc=r=16000:cl=mono", "-c:a", "pcm_s16le", str(wav)])

        # 2. VAD
        ctx.update(0.15, "vad", "Détection de la parole et des silences (VAD)…")
        vad_speech, vad_engine = detect_speech(wav, settings.vad_engine)

        # 3. ASR
        ctx.update(0.25, "asr", f"Transcription des dialogues ({settings.asr_provider}/{settings.whisper_model})…")
        result = asr_mod.transcribe(settings, wav, lang_hint, sidecar)

        # 4. gaps (VAD timing, ASR only fills VAD misses - see combine_speech)
        ctx.update(0.55, "gaps", "Calcul des intervalles disponibles pour l'audiodescription…")
        speech = combine_speech(vad_speech, [(seg.start, seg.end) for seg in result.segments])
        gaps = compute_gaps(speech, duration, settings.min_gap_seconds, settings.gap_padding_seconds)

        # 5. keyframes (only inside gaps + at scene cuts)
        ctx.update(0.62, "scenes", "Détection des changements de plan…")
        cuts = media.detect_scene_changes(video, settings.scene_threshold)
        # long silent sequences need several descriptions: split them into slots at shot changes
        gaps = split_long_gaps(gaps, cuts, settings.max_slot_seconds, settings.min_gap_seconds)

        # 5b. ML: which silences would a human audio describer use?
        ctx.update(0.66, "ml", "Score de pertinence des silences (modèle ML)…")
        scores, recommended, selection = score_gaps(settings, video, wav, duration, speech, cuts, gaps)

        ctx.update(0.7, "keyframes", f"Extraction de quelques images clés pour {len(gaps)} silences…")
        frames_dir = pdir / "frames"
        shutil.rmtree(frames_dir, ignore_errors=True)
        frames_dir.mkdir()

        with session_scope() as s:
            for model in (TranscriptSegment, SpeechRegion, Gap, Keyframe, Description):
                s.exec(delete(model).where(model.project_id == project_id))  # type: ignore[arg-type]
            for seg in result.segments:
                s.add(TranscriptSegment(project_id=project_id, start=seg.start, end=seg.end, text=seg.text))
            for a, b in speech:
                s.add(SpeechRegion(project_id=project_id, start=a, end=b))
            gap_rows = []
            for (a, b), sc, rec in zip(gaps, scores, recommended, strict=True):
                g = Gap(project_id=project_id, start=a, end=b, score=sc, recommended=rec)
                s.add(g)
                gap_rows.append(g)
            s.commit()
            for g in gap_rows:
                s.refresh(g)
            gap_data = [(g.id, g.start, g.end) for g in gap_rows]

            for gid, a, b in gap_data:
                for t, reason in select_keyframe_times(a, b, cuts, settings.max_keyframes_per_gap):
                    out = frames_dir / f"g{gid}_{t:07.2f}.jpg"
                    try:
                        media.extract_frame(video, t, out)
                    except media.MediaError:
                        continue
                    s.add(Keyframe(project_id=project_id, gap_id=gid, time=t, path=rel(out), reason=reason))
            p = s.get(Project, project_id)
            p.asr_provider, p.asr_model, p.asr_language = result.provider, result.model, result.language
            p.vad_engine = vad_engine
            p.audio_path = rel(wav)
            p.status = "analyzed"
            p.updated_at = utcnow()
            s.add(p)
            s.commit()

        # 6. drafts
        ctx.update(0.8, "drafts", "Rédaction des brouillons d'audiodescription (IA)…")
        n = draft_all(project_id, ctx)
        with session_scope() as s:
            p = s.get(Project, project_id)
            p.status = "ready"
            p.updated_at = utcnow()
            s.add(p)
            s.commit()
        return {"gaps": len(gaps), "segments": len(result.segments), "drafts": n, "notes": result.notes,
                "scene_changes": len(cuts), "vad": vad_engine, "gap_selection": selection,
                "gaps_recommended": sum(recommended)}
    except Exception as exc:
        with session_scope() as s:
            p = s.get(Project, project_id)
            if p:
                p.status, p.error = "error", str(exc)[:500]
                s.add(p)
                s.commit()
        raise


def score_gaps(settings: Settings, video: Path, wav: Path, duration: float, speech: list[tuple[float, float]],
               cuts: list[float], gaps: list[tuple[float, float]]) -> tuple[list[float | None], list[bool], str]:
    """Score each gap with the trained model. Without a model (or GAP_SELECTION=all), every gap is kept."""
    mode = settings.gap_selection.lower()
    scorer = get_gap_scorer(settings.gap_model_path) if mode in ("auto", "model") else None
    if mode == "model" and scorer is None:
        raise ValueError(f"GAP_SELECTION=model mais aucun modèle entraîné dans {settings.gap_model_path} "
                         "(voir ml/README.md)")
    if scorer is None or not gaps:
        return [None] * len(gaps), [True] * len(gaps), "all"
    sig = MediaSignals.from_files(video, wav, duration, speech, cuts)
    scores = scorer.score(compute_gap_features(gaps, sig))
    threshold = settings.gap_score_threshold or scorer.threshold
    return list(scores), select_gaps(scores, threshold), "model"


def select_keyframe_times(start: float, end: float, cuts: list[float], cap: int = 3) -> list[tuple[float, str]]:
    """1-3 frames per gap: just after any scene cut inside it, the middle, and the edges for long gaps."""
    cands: list[tuple[float, str]] = [(min(end - 0.05, c + 0.2), "scene_change") for c in cuts if start <= c <= end]
    mid = (start + end) / 2
    cands.append((mid, "gap"))
    if end - start > 4:
        cands += [(start + 0.5, "gap"), (end - 0.5, "gap")]
    chosen: list[tuple[float, str]] = []
    for t, reason in cands:  # scene cuts first: they carry the most new visual information
        if all(abs(t - c) > 0.8 for c, _ in chosen):
            chosen.append((round(t, 2), reason))
        if len(chosen) >= cap:
            break
    return sorted(chosen)


def _context(s: Session, project: Project, start: float, end: float, exclude_id: str | None = None) -> dict:
    segs = s.exec(select(TranscriptSegment).where(TranscriptSegment.project_id == project.id)
                  .order_by(TranscriptSegment.start)).all()  # type: ignore[arg-type]
    before = [x.text for x in segs if x.end <= start + 0.05][-2:]
    after = [x.text for x in segs if x.start >= end - 0.05][:1]
    prev = s.exec(select(Description).where(Description.project_id == project.id, Description.end <= start + 0.05,
                                            Description.status != DescriptionStatus.REJECTED)
                  .order_by(Description.end.desc())).first()  # type: ignore[attr-defined]
    if prev and prev.id == exclude_id:
        prev = None
    return {"before": " ".join(before), "after": " ".join(after), "prev": prev.text if prev else ""}


def make_draft(s: Session, project: Project, gap_start: float, gap_end: float, gap_id: int | None,
               language: str, hint: str = "", exclude_id: str | None = None) -> dict:
    settings = get_settings()
    provider = get_vision(settings)
    frames = s.exec(select(Keyframe).where(Keyframe.project_id == project.id, Keyframe.time >= gap_start - 0.01,
                                           Keyframe.time <= gap_end + 0.01).order_by(Keyframe.time)).all()  # type: ignore[arg-type]
    ctxd = _context(s, project, gap_start, gap_end, exclude_id)
    duration = gap_end - gap_start
    req = DraftRequest(
        start=gap_start, end=gap_end, language=language, max_words=max_words(duration, language),
        frames=[absolute(f.path) for f in frames], frame_times=[f.time for f in frames],
        dialogue_before=ctxd["before"], dialogue_after=ctxd["after"], previous_description=ctxd["prev"],
        cast=json.loads(project.cast_json or "[]"), scene_change=any(f.reason == "scene_change" for f in frames),
        film_title=project.title, is_sample=project.is_sample, hint=hint,
    )
    draft = provider.draft(req)
    text, flags = fit_to_gap(draft.text or "", duration, language)
    if draft.confidence < settings.confidence_threshold:
        flags.append("low_confidence")
    if draft.uncertain:
        flags.append("uncertain")
    if provider.name == "demo":
        flags.append("demo")
    est = estimate_seconds(text, language)
    end = round(min(gap_end, gap_start + max(est + 0.4, 1.2)), 3)
    return {"text": text, "flags": sorted(set(flags)), "confidence": round(draft.confidence, 2),
            "provider": draft.provider, "model": draft.model, "start": gap_start, "end": end,
            "uncertain": draft.uncertain}


def draft_all(project_id: str, ctx: JobContext | None = None) -> int:
    settings = get_settings()
    with session_scope() as s:
        p = s.get(Project, project_id)
        gaps = s.exec(select(Gap).where(Gap.project_id == project_id, Gap.recommended == True)  # noqa: E712
                      .order_by(Gap.start)).all()  # type: ignore[arg-type]
        p.vlm_provider = get_vision(settings).name
        p.vlm_model = get_vision(settings).model
        p.demo_mode = p.vlm_provider == "demo"
        n = 0
        for i, g in enumerate(gaps):
            if ctx:
                ctx.update(0.8 + 0.2 * i / max(1, len(gaps)), "drafts", f"Brouillon {i + 1}/{len(gaps)}…")
            _new_ai_description(s, p, g, settings)
            s.commit()  # commit each draft so the UI can stream them
            n += 1
        s.add(p)
        s.commit()
    return n


def _new_ai_description(s: Session, p: Project, g: Gap, settings: Settings) -> Description:
    d = make_draft(s, p, g.start, g.end, g.id, p.language)
    desc = Description(project_id=p.id, gap_id=g.id, start=d["start"], end=d["end"], text=d["text"],
                       language=p.language, origin="ai", status=DescriptionStatus.AI_DRAFT,
                       confidence=d["confidence"], flags_json=json.dumps(d["flags"]),
                       provider=d["provider"], model=d["model"], ai_original_text=d["text"])
    compute_flags(desc, settings.confidence_threshold)
    detail = "; ".join(d["uncertain"])
    if g.score is not None:
        detail = f"pertinence ML {g.score:.2f}" + (f"; {detail}" if detail else "")
    add_history(desc, "ai_draft", d["provider"], detail)
    s.add(desc)
    return desc


def draft_gap(gap_id: int) -> Description:
    """Human override of the model: draft a description in a gap the model did not prioritise."""
    settings = get_settings()
    with session_scope() as s:
        g = s.get(Gap, gap_id)
        if not g:
            raise LookupError("Silence introuvable")
        existing = s.exec(select(Description).where(Description.gap_id == gap_id,
                                                    Description.status != DescriptionStatus.REJECTED)).first()
        if existing:
            raise FileExistsError("Ce silence a déjà une description")
        p = s.get(Project, g.project_id)
        desc = _new_ai_description(s, p, g, settings)
        s.commit()
        s.refresh(desc)
        return Description.model_validate(desc)


def regenerate(desc_id: str, hint: str = "", language: str | None = None) -> Description:
    settings = get_settings()
    with session_scope() as s:
        desc = s.get(Description, desc_id)
        p = s.get(Project, desc.project_id)
        gap = s.get(Gap, desc.gap_id) if desc.gap_id else None
        g_start, g_end = (gap.start, gap.end) if gap else (desc.start, available_until(s, p, desc.start))
        lang = language or desc.language
        d = make_draft(s, p, g_start, g_end, desc.gap_id, lang, hint=hint or "nouvelle proposition", exclude_id=desc.id)
        desc.text, desc.ai_original_text = d["text"], d["text"]
        desc.start, desc.end, desc.language = d["start"], d["end"], lang
        desc.confidence = d["confidence"]
        desc.flags_json = json.dumps(d["flags"])
        desc.provider, desc.model, desc.origin = d["provider"], d["model"], "ai"
        desc.status = DescriptionStatus.AI_DRAFT
        desc.validated_by, desc.validated_at = "", None
        clear_audio(desc)
        compute_flags(desc, settings.confidence_threshold)
        add_history(desc, "regenerated", d["provider"], hint)
        desc.updated_at = utcnow()
        s.add(desc)
        s.commit()
        s.refresh(desc)
        return Description.model_validate(desc)


def clear_audio(desc: Description) -> None:
    if desc.audio_path:
        try:
            absolute(desc.audio_path).unlink(missing_ok=True)
        except OSError:
            pass
    desc.audio_path, desc.audio_source, desc.audio_duration, desc.audio_voice = "", "", 0.0, ""


# ------------------------------------------------------------------ voice ------------------------------

def place_audio(s: Session, p: Project, desc: Description, src: Path, source: str, voice: str) -> list[str]:
    """Normalize a clip, speed it up slightly if needed, never let it run into the next dialogue."""
    warnings: list[str] = []
    out_dir = project_dir(p.id) / "voice"
    out_dir.mkdir(exist_ok=True)
    out = out_dir / f"{desc.id}.wav"
    raw = media.audio_duration(src)
    slot = max(0.3, available_until(s, p, desc.start) - desc.start - 0.05)
    tempo = 1.0
    if raw > slot:
        tempo = min(1.3, raw / slot)
        if raw / tempo > slot:
            warnings.append(f"Audio trop long ({raw:.1f}s pour {slot:.1f}s) : coupé avant la reprise du dialogue.")
        else:
            warnings.append(f"Audio accéléré ×{tempo:.2f} pour tenir dans le silence.")
    tmp = out_dir / f"{desc.id}.tmp.wav"
    media.normalize_clip(src, tmp, max_duration=slot, tempo=tempo)
    tmp.replace(out)
    if src != out and src.parent == out_dir:
        src.unlink(missing_ok=True)
    desc.audio_path = rel(out)
    desc.audio_source = source
    desc.audio_voice = voice
    desc.audio_duration = media.audio_duration(out)
    return warnings


def synthesize_validated(project_id: str, ctx: JobContext | None = None, only_id: str | None = None,
                         force: bool = False) -> dict:
    settings = get_settings()
    results = []
    with session_scope() as s:
        p = s.get(Project, project_id)
        q = select(Description).where(Description.project_id == project_id,
                                      Description.status == DescriptionStatus.VALIDATED)
        if only_id:
            q = q.where(Description.id == only_id)
        descs = s.exec(q.order_by(Description.start)).all()  # type: ignore[arg-type]
        if not descs:
            raise ValueError("Aucune ligne validée : la voix n'est générée que pour les lignes validées par un humain.")
        for i, d in enumerate(descs):
            if d.audio_source == "human" and not force:
                results.append({"id": d.id, "skipped": "voix humaine conservée"})
                continue
            if d.audio_path and d.audio_source in ("tts", "demo_tone") and not force:
                results.append({"id": d.id, "skipped": "déjà synthétisé"})
                continue
            if ctx:
                ctx.update(i / len(descs), "tts", f"Synthèse vocale {i + 1}/{len(descs)}…")
            out_dir = project_dir(project_id) / "voice"
            out_dir.mkdir(exist_ok=True)
            r = tts_mod.synthesize(settings, d.text, d.language, out_dir / f"{d.id}.raw")
            warnings = place_audio(s, p, d, r.path, "demo_tone" if r.provider == "demo" else "tts", r.voice)
            if r.warning:
                warnings.insert(0, r.warning)
            add_history(d, "tts", r.voice, " ".join(warnings))
            s.add(d)
            s.commit()
            results.append({"id": d.id, "provider": r.provider, "voice": r.voice, "warnings": warnings})
    return {"results": results}


# ------------------------------------------------------------------ export -----------------------------

def export_project(project_id: str, ctx: JobContext | None = None) -> dict:
    settings = get_settings()
    with session_scope() as s:
        p = s.get(Project, project_id)
        all_descs = s.exec(select(Description).where(Description.project_id == project_id)
                           .order_by(Description.start)).all()  # type: ignore[arg-type]
        descs = [d for d in all_descs if d.status == DescriptionStatus.VALIDATED]
        if not descs:
            raise ValueError("Aucune ligne validée par un humain : rien à exporter.")
        speech = speech_regions(s, project_id)
        out = project_dir(project_id) / "export"
        shutil.rmtree(out, ignore_errors=True)
        out.mkdir()
        cues = [exp.Cue(d.start, d.end, d.text, d.language, d.origin, d.validated_by, d.validated_at) for d in descs]
        demo = any("demo" in json.loads(d.flags_json) for d in descs) or p.demo_mode
        if ctx:
            ctx.update(0.1, "subtitles", "Génération WebVTT / TTML…")
        (out / "description.vtt").write_text(exp.to_vtt(cues, p.title, demo), encoding="utf-8")
        (out / "description.ttml").write_text(exp.to_ttml(cues, p.title, p.language, demo), encoding="utf-8")
        tts_voices = sorted({d.audio_voice for d in descs if d.audio_voice}) or ["aucune"]
        credits = exp.credits_text(
            p.title, [d.validated_by for d in descs], len(descs), sum(d.origin == "ai" for d in descs),
            sum(d.origin == "human" for d in descs), f"{p.asr_provider} ({p.asr_model})",
            f"{p.vlm_provider} ({p.vlm_model})", ", ".join(tts_voices), demo)
        (out / "credits.txt").write_text(credits, encoding="utf-8")
        script = [{"start": d.start, "end": d.end, "text": d.text, "language": d.language, "origin": d.origin,
                   "ai_original_text": d.ai_original_text, "validated_by": d.validated_by,
                   "validated_at": d.validated_at.isoformat() if d.validated_at else None,
                   "history": json.loads(d.history_json)} for d in descs]
        (out / "script_ayant_droit.json").write_text(json.dumps(
            {"title": p.title, "demo_mode": demo, "rights_holder_delivery": True,
             "training_opt_in": p.training_opt_in, "lines": script}, ensure_ascii=False, indent=2), encoding="utf-8")

        files = ["description.vtt", "description.ttml", "credits.txt", "script_ayant_droit.json"]
        warnings: list[str] = []
        for d in descs:
            if overlaps((d.start, d.end), speech):
                warnings.append(f"La ligne {d.start:.1f}s chevauche un dialogue.")

        # audio
        if ctx:
            ctx.update(0.35, "ad_track", "Assemblage de la piste d'audiodescription…")
        ad_wav = out / "ad_track.wav"
        if p.voice_track_path:
            media.normalize_clip(absolute(p.voice_track_path), ad_wav, max_duration=p.duration)
            warnings.append("Piste voix humaine complète utilisée.")
        else:
            clips = [(d.start, absolute(d.audio_path)) for d in descs if d.audio_path and absolute(d.audio_path).exists()]
            missing = [d for d in descs if not d.audio_path]
            if missing:
                warnings.append(f"{len(missing)} ligne(s) validée(s) sans voix : générez la voix ou enregistrez-la.")
            mix.build_ad_track(clips, p.duration, ad_wav)
        mix.encode_mp3(ad_wav, out / "ad_track.mp3")
        files += ["ad_track.wav", "ad_track.mp3"]

        if ctx:
            ctx.update(0.6, "mix", "Mixage avec ducking de la bande originale…")
        intervals = [(d.start, min(d.end + 0.5, available_until(s, p, d.start)) if d.audio_duration == 0
                      else d.start + d.audio_duration) for d in descs]
        meta = {"title": f"{p.title} (audiodécrit)",
                "comment": credits.splitlines()[2] + (" | DEMO MODE" if demo else ""),
                "description": "Audiodescription assistée par IA, validée par un humain."}
        mix.mix_final(absolute(p.video_path), ad_wav, intervals, out / "film_audiodecrit.mp4",
                      bool(p.audio_codec), settings.duck_volume, meta)
        files.append("film_audiodecrit.mp4")

        if ctx:
            ctx.update(0.9, "zip", "Archive…")
        with zipfile.ZipFile(out / "export_complet.zip", "w", zipfile.ZIP_DEFLATED) as z:
            for f in files:
                z.write(out / f, f)
        files.append("export_complet.zip")
        return {"files": files, "validated": len(descs), "total": len([d for d in all_descs
                                                                       if d.status != DescriptionStatus.REJECTED]),
                "warnings": warnings, "demo_mode": demo}
