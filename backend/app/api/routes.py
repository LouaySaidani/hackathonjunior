"""REST API. All endpoints are documented in docs/api.md and at /docs (OpenAPI)."""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlmodel import Session, delete, select

from .. import jobs, service
from ..config import get_settings
from ..db import get_session
from ..models import (
    Description,
    DescriptionStatus,
    Feedback,
    Gap,
    Job,
    Keyframe,
    Project,
    SpeechRegion,
    TranscriptSegment,
    utcnow,
)
from ..pipeline import gapscore, media
from ..pipeline.fit import estimate_seconds
from ..pipeline.vad import overlaps
from ..providers.vision import get_vision

router = APIRouter(prefix="/api")
LANGS = {"fr", "ar", "aeb", "en"}
AUDIO_EXT = {".wav", ".mp3", ".m4a", ".ogg", ".webm", ".flac", ".aac", ".opus"}


# ------------------------------------------------------------------ helpers ---------------------------

def _project(s: Session, pid: str) -> Project:
    p = s.get(Project, pid)
    if not p:
        raise HTTPException(404, "Projet introuvable")
    return p


def _desc(s: Session, did: str) -> Description:
    d = s.get(Description, did)
    if not d:
        raise HTTPException(404, "Description introuvable")
    return d


def desc_out(d: Description) -> dict:
    data = d.model_dump(exclude={"flags_json", "history_json"})
    data["flags"] = json.loads(d.flags_json or "[]")
    data["history"] = json.loads(d.history_json or "[]")
    data["estimated_seconds"] = estimate_seconds(d.text, d.language)
    data["audio_url"] = f"/api/files/{d.audio_path}" if d.audio_path else ""
    return data


def project_summary(s: Session, p: Project) -> dict:
    descs = s.exec(select(Description).where(Description.project_id == p.id)).all()
    counts = {k: 0 for k in DescriptionStatus.ALL}
    for d in descs:
        counts[d.status] = counts.get(d.status, 0) + 1
    data = p.model_dump(exclude={"cast_json"})
    data["cast"] = json.loads(p.cast_json or "[]")
    data["video_url"] = f"/api/files/{p.video_path}" if p.video_path else ""
    data["voice_track_url"] = f"/api/files/{p.voice_track_path}" if p.voice_track_path else ""
    data["counts"] = counts
    data["needs_review"] = sum(1 for d in descs if d.needs_review and d.status != DescriptionStatus.REJECTED)
    data["active_job"] = jobs.active_job(p.id)
    return data


async def _save_upload(upload: UploadFile, dest: Path, max_bytes: int) -> int:
    size = 0
    with dest.open("wb") as f:
        while chunk := await upload.read(1024 * 1024):
            size += len(chunk)
            if size > max_bytes:
                f.close()
                dest.unlink(missing_ok=True)
                raise HTTPException(413, f"Fichier trop volumineux (max {max_bytes // (1024 * 1024)} Mo)")
            f.write(chunk)
    return size


def _check_interval(s: Session, p: Project, start: float, end: float) -> None:
    if start < 0 or end > p.duration + 0.01:
        raise HTTPException(422, "L'intervalle sort de la durée de la vidéo.")
    if end - start < 0.5:
        raise HTTPException(422, "Une description doit durer au moins 0,5 s.")
    if overlaps((start, end), service.speech_regions(s, p.id)):
        raise HTTPException(422, "Cet intervalle chevauche un dialogue : une audiodescription ne doit jamais "
                                 "couvrir la parole.")


# ------------------------------------------------------------------ system ----------------------------

@router.get("/system")
def system_info():
    st = get_settings()
    vision = get_vision(st)
    return {
        "demo_mode": st.demo_mode,
        "providers": {
            "asr": st.asr_provider, "whisper_model": st.whisper_model,
            "vlm": vision.name, "vlm_model": vision.model, "tts": st.tts_provider,
            "vad": st.vad_engine,
        },
        "min_gap_seconds": st.min_gap_seconds,
        "max_upload_mb": st.max_upload_mb,
        "languages": sorted(LANGS),
        "confidence_threshold": st.confidence_threshold,
        "gap_model": _gap_model_info(st),
    }


def _gap_model_info(st) -> dict:  # noqa: ANN001
    info = gapscore.model_info(st.gap_model_path)
    active = st.gap_selection.lower() != "all" and info is not None and gapscore.get_gap_scorer(st.gap_model_path)
    if not info:
        return {"active": False, "selection": st.gap_selection}
    return {
        "active": bool(active),
        "selection": st.gap_selection,
        "threshold": st.gap_score_threshold or info.get("threshold"),
        "model": info.get("model"),
        "trained_at": info.get("trained_at"),
        "train_videos": info.get("train_videos"),
        "test_metrics": info.get("test_metrics"),
    }


@router.get("/stats")
def stats(s: Session = Depends(get_session)):
    projects = s.exec(select(Project)).all()
    descs = s.exec(select(Description)).all()
    return {
        "projects": len(projects),
        "descriptions": len(descs),
        "validated": sum(d.status == DescriptionStatus.VALIDATED for d in descs),
        "pending": sum(d.status in (DescriptionStatus.AI_DRAFT, DescriptionStatus.EDITED) for d in descs),
        "minutes_processed": round(sum(p.duration for p in projects if p.status == "ready") / 60, 1),
        "feedback": len(s.exec(select(Feedback)).all()),
    }


# ------------------------------------------------------------------ projects --------------------------

@router.get("/projects")
def list_projects(s: Session = Depends(get_session)):
    rows = s.exec(select(Project).order_by(Project.created_at.desc())).all()  # type: ignore[attr-defined]
    return [project_summary(s, p) for p in rows]


@router.post("/projects", status_code=201)
async def create_project(
    file: UploadFile = File(...),
    title: str = Form(...),
    language: str = Form("fr"),
    dialogue_language: str = Form("auto"),
    cast: str = Form("[]"),
    consent: bool = Form(False),
    training_opt_in: bool = Form(False),
    s: Session = Depends(get_session),
):
    st = get_settings()
    if not consent:
        raise HTTPException(400, "Vous devez confirmer posséder les droits ou l'autorisation de traiter cette vidéo.")
    ext = Path(file.filename or "").suffix.lower()
    if ext not in media.ALLOWED_EXTENSIONS:
        raise HTTPException(415, "Format non pris en charge. Formats acceptés : MP4, MOV, MKV.")
    if language not in LANGS:
        raise HTTPException(422, "Langue inconnue")
    try:
        cast_list = [{"name": str(c.get("name", ""))[:80], "description": str(c.get("description", ""))[:300]}
                     for c in json.loads(cast or "[]") if c.get("name")]
    except (json.JSONDecodeError, AttributeError) as exc:
        raise HTTPException(422, "Liste de personnages invalide") from exc
    p = Project(title=title.strip()[:200] or "Sans titre", language=language, dialogue_language=dialogue_language,
                cast_json=json.dumps(cast_list, ensure_ascii=False), consent=True, training_opt_in=training_opt_in,
                filename=(file.filename or "")[:200])
    pdir = service.project_dir(p.id)
    dest = pdir / f"source{ext}"
    p.size_bytes = await _save_upload(file, dest, st.max_upload_mb * 1024 * 1024)
    try:
        meta = media.probe(dest)
    except media.MediaError as exc:
        shutil.rmtree(pdir, ignore_errors=True)
        raise HTTPException(415, f"Vidéo illisible : {exc}") from exc
    for k in ("duration", "width", "height", "fps", "video_codec", "audio_codec"):
        setattr(p, k, meta[k])
    p.video_path = service.rel(dest)
    s.add(p)
    s.commit()
    s.refresh(p)
    return project_summary(s, p)


def create_sample_project(s: Session) -> Project:
    st = get_settings()
    src = st.samples_dir / "sample_medina.mp4"
    if not src.exists():
        raise HTTPException(404, "Clip d'exemple absent")
    p = Project(title="Exemple — Une journée à Sidi Bou Saïd (clip synthétique)", language="fr",
                dialogue_language="fr", consent=True, is_sample=True, filename=src.name,
                cast_json=json.dumps([{"name": "La voyageuse", "description": "silhouette claire qui marche"}],
                                     ensure_ascii=False))
    dest = service.project_dir(p.id) / "source.mp4"
    shutil.copyfile(src, dest)
    meta = media.probe(dest)
    for k in ("duration", "width", "height", "fps", "video_codec", "audio_codec"):
        setattr(p, k, meta[k])
    p.size_bytes = dest.stat().st_size
    p.video_path = service.rel(dest)
    s.add(p)
    s.commit()
    s.refresh(p)
    return p


@router.post("/projects/sample", status_code=201)
def create_sample(s: Session = Depends(get_session)):
    return project_summary(s, create_sample_project(s))


@router.get("/projects/{pid}")
def get_project(pid: str, s: Session = Depends(get_session)):
    p = _project(s, pid)
    data = project_summary(s, p)
    data["transcript"] = s.exec(select(TranscriptSegment).where(TranscriptSegment.project_id == pid)
                                .order_by(TranscriptSegment.start)).all()  # type: ignore[arg-type]
    data["speech"] = s.exec(select(SpeechRegion).where(SpeechRegion.project_id == pid)
                            .order_by(SpeechRegion.start)).all()  # type: ignore[arg-type]
    data["gaps"] = s.exec(select(Gap).where(Gap.project_id == pid).order_by(Gap.start)).all()  # type: ignore[arg-type]
    kfs = s.exec(select(Keyframe).where(Keyframe.project_id == pid).order_by(Keyframe.time)).all()  # type: ignore[arg-type]
    data["keyframes"] = [{**k.model_dump(), "url": f"/api/files/{k.path}"} for k in kfs]
    descs = s.exec(select(Description).where(Description.project_id == pid)
                   .order_by(Description.start)).all()  # type: ignore[arg-type]
    data["descriptions"] = [desc_out(d) for d in descs]
    return data


class ProjectPatch(BaseModel):
    title: str | None = None
    language: str | None = None
    validator_name: str | None = None
    cast: list[dict] | None = None
    training_opt_in: bool | None = None


@router.patch("/projects/{pid}")
def patch_project(pid: str, body: ProjectPatch, s: Session = Depends(get_session)):
    p = _project(s, pid)
    if body.title is not None:
        p.title = body.title.strip()[:200] or p.title
    if body.language is not None:
        if body.language not in LANGS:
            raise HTTPException(422, "Langue inconnue")
        p.language = body.language
    if body.validator_name is not None:
        p.validator_name = body.validator_name.strip()[:120]
    if body.cast is not None:
        p.cast_json = json.dumps(body.cast, ensure_ascii=False)
    if body.training_opt_in is not None:
        p.training_opt_in = body.training_opt_in
    p.updated_at = utcnow()
    s.add(p)
    s.commit()
    s.refresh(p)
    return project_summary(s, p)


@router.delete("/projects/{pid}", status_code=204)
def delete_project(pid: str, s: Session = Depends(get_session)):
    p = _project(s, pid)
    for model in (TranscriptSegment, SpeechRegion, Gap, Keyframe, Description, Job):
        s.exec(delete(model).where(model.project_id == pid))  # type: ignore[arg-type]
    s.delete(p)
    s.commit()
    shutil.rmtree(get_settings().projects_dir / pid, ignore_errors=True)


@router.post("/projects/{pid}/analyze", status_code=202)
def analyze(pid: str, s: Session = Depends(get_session)):
    p = _project(s, pid)
    if jobs.active_job(pid):
        raise HTTPException(409, "Une tâche est déjà en cours pour ce projet.")
    if not p.consent:
        raise HTTPException(403, "Consentement manquant")
    return jobs.submit(pid, "analyze", lambda ctx: service.analyze(pid, ctx))


@router.get("/jobs/{jid}")
def get_job(jid: str, s: Session = Depends(get_session)):
    j = s.get(Job, jid)
    if not j:
        raise HTTPException(404, "Tâche introuvable")
    data = j.model_dump()
    data["result"] = json.loads(j.result_json or "{}")
    return data


# ------------------------------------------------------------------ descriptions ----------------------

class DescCreate(BaseModel):
    start: float
    end: float
    text: str = Field(min_length=1, max_length=1000)
    language: str = "fr"
    author: str = ""


class DescPatch(BaseModel):
    text: str | None = Field(default=None, max_length=1000)
    start: float | None = None
    end: float | None = None
    language: str | None = None
    editor: str = ""


class ValidateBody(BaseModel):
    validator: str = Field(min_length=1, max_length=120)


class RejectBody(BaseModel):
    by: str = ""
    reason: str = ""


class RegenBody(BaseModel):
    hint: str = ""
    language: str | None = None


@router.post("/projects/{pid}/descriptions", status_code=201)
def add_description(pid: str, body: DescCreate, s: Session = Depends(get_session)):
    p = _project(s, pid)
    if body.language not in LANGS:
        raise HTTPException(422, "Langue inconnue")
    _check_interval(s, p, body.start, body.end)
    d = Description(project_id=pid, start=round(body.start, 3), end=round(body.end, 3), text=body.text.strip(),
                    language=body.language, origin="human", status=DescriptionStatus.EDITED, confidence=1.0,
                    provider="human", model="")
    service.compute_flags(d, get_settings().confidence_threshold)
    service.add_history(d, "manual_create", body.author)
    s.add(d)
    s.commit()
    s.refresh(d)
    return desc_out(d)


@router.patch("/descriptions/{did}")
def patch_description(did: str, body: DescPatch, s: Session = Depends(get_session)):
    d = _desc(s, did)
    p = _project(s, d.project_id)
    start = body.start if body.start is not None else d.start
    end = body.end if body.end is not None else d.end
    if (start, end) != (d.start, d.end):
        _check_interval(s, p, start, end)
    changed = []
    if body.text is not None and body.text.strip() != d.text:
        d.text = body.text.strip()
        changed.append("texte")
        if d.audio_source != "human":
            service.clear_audio(d)
    if (start, end) != (d.start, d.end):
        d.start, d.end = round(start, 3), round(end, 3)
        changed.append("minutage")
    if body.language is not None and body.language != d.language:
        if body.language not in LANGS:
            raise HTTPException(422, "Langue inconnue")
        d.language = body.language
        changed.append("langue")
    if changed:
        # Any human change moves the line to EDITED BY HUMAN and removes a previous validation.
        d.status = DescriptionStatus.EDITED
        d.validated_by, d.validated_at = "", None
        flags = set(json.loads(d.flags_json))
        flags -= {"trimmed_to_fit"}
        d.flags_json = json.dumps(sorted(flags))
        service.add_history(d, "edited", body.editor, ", ".join(changed))
        service.compute_flags(d, get_settings().confidence_threshold)
        d.updated_at = utcnow()
        s.add(d)
        s.commit()
        s.refresh(d)
    return desc_out(d)


@router.delete("/descriptions/{did}", status_code=204)
def delete_description(did: str, s: Session = Depends(get_session)):
    d = _desc(s, did)
    service.clear_audio(d)
    s.delete(d)
    s.commit()


@router.post("/descriptions/{did}/validate")
def validate_description(did: str, body: ValidateBody, s: Session = Depends(get_session)):
    """The ONLY way a line becomes HUMAN VALIDATED: an explicit human action with a name."""
    d = _desc(s, did)
    if not body.validator.strip():
        raise HTTPException(422, "Nom du validateur requis")
    if "too_long" in json.loads(d.flags_json):
        raise HTTPException(422, "Texte trop long pour l'intervalle : raccourcissez-le ou élargissez l'intervalle.")
    d.status = DescriptionStatus.VALIDATED
    d.validated_by = body.validator.strip()
    d.validated_at = utcnow()
    d.needs_review = False
    service.add_history(d, "validated", d.validated_by)
    s.add(d)
    p = _project(s, d.project_id)
    if not p.validator_name:
        p.validator_name = d.validated_by
        s.add(p)
    s.commit()
    s.refresh(d)
    return desc_out(d)


@router.post("/descriptions/{did}/reject")
def reject_description(did: str, body: RejectBody, s: Session = Depends(get_session)):
    d = _desc(s, did)
    d.status = DescriptionStatus.REJECTED
    d.validated_by, d.validated_at = "", None
    service.add_history(d, "rejected", body.by, body.reason)
    s.add(d)
    s.commit()
    s.refresh(d)
    return desc_out(d)


@router.post("/descriptions/{did}/reopen")
def reopen_description(did: str, body: RejectBody, s: Session = Depends(get_session)):
    d = _desc(s, did)
    d.status = DescriptionStatus.EDITED if d.origin == "human" or d.text != d.ai_original_text \
        else DescriptionStatus.AI_DRAFT
    d.validated_by, d.validated_at = "", None
    service.compute_flags(d, get_settings().confidence_threshold)
    service.add_history(d, "reopened", body.by)
    s.add(d)
    s.commit()
    s.refresh(d)
    return desc_out(d)


@router.post("/descriptions/{did}/regenerate")
def regenerate_description(did: str, body: RegenBody, s: Session = Depends(get_session)):
    _desc(s, did)
    if body.language and body.language not in LANGS:
        raise HTTPException(422, "Langue inconnue")
    try:
        d = service.regenerate(did, body.hint, body.language)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, f"Échec de la régénération : {exc}") from exc
    return desc_out(d)


@router.post("/gaps/{gid}/draft", status_code=201)
def draft_gap(gid: int, s: Session = Depends(get_session)):
    """Draft a description in any gap, including those the ML model did not prioritise."""
    g = s.get(Gap, gid)
    if not g:
        raise HTTPException(404, "Silence introuvable")
    if jobs.active_job(g.project_id):
        raise HTTPException(409, "Une tâche est déjà en cours pour ce projet.")
    try:
        d = service.draft_gap(gid)
    except FileExistsError as exc:
        raise HTTPException(409, str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, f"Échec de la rédaction : {exc}") from exc
    return desc_out(d)


@router.post("/descriptions/{did}/tts")
def tts_description(did: str, s: Session = Depends(get_session)):
    d = _desc(s, did)
    if d.status != DescriptionStatus.VALIDATED:
        raise HTTPException(409, "La voix n'est générée que pour une ligne validée par un humain.")
    try:
        res = service.synthesize_validated(d.project_id, only_id=did, force=True)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, str(exc)) from exc
    s.expire_all()
    out = desc_out(_desc(s, did))
    out["warnings"] = res["results"][0].get("warnings", []) if res["results"] else []
    return out


@router.post("/descriptions/{did}/voice")
async def upload_voice(did: str, file: UploadFile = File(...), s: Session = Depends(get_session)):
    """Human-recorded voice for one line (fallback when TTS is poor, e.g. darija)."""
    d = _desc(s, did)
    p = _project(s, d.project_id)
    ext = Path(file.filename or "").suffix.lower() or ".webm"
    if ext not in AUDIO_EXT:
        raise HTTPException(415, "Format audio non pris en charge")
    vdir = service.project_dir(p.id) / "voice"
    vdir.mkdir(exist_ok=True)
    raw = vdir / f"{did}.upload{ext}"
    await _save_upload(file, raw, 50 * 1024 * 1024)
    try:
        warnings = service.place_audio(s, p, d, raw, "human", "voix humaine")
    except media.MediaError as exc:
        raise HTTPException(415, f"Audio illisible : {exc}") from exc
    finally:
        raw.unlink(missing_ok=True)
    service.add_history(d, "human_voice", "", " ".join(warnings))
    s.add(d)
    s.commit()
    s.refresh(d)
    out = desc_out(d)
    out["warnings"] = warnings
    return out


@router.delete("/descriptions/{did}/voice")
def delete_voice(did: str, s: Session = Depends(get_session)):
    d = _desc(s, did)
    service.clear_audio(d)
    s.add(d)
    s.commit()
    s.refresh(d)
    return desc_out(d)


@router.post("/projects/{pid}/tts", status_code=202)
def tts_all(pid: str, s: Session = Depends(get_session)):
    _project(s, pid)
    if jobs.active_job(pid):
        raise HTTPException(409, "Une tâche est déjà en cours pour ce projet.")
    return jobs.submit(pid, "tts", lambda ctx: service.synthesize_validated(pid, ctx))


@router.post("/projects/{pid}/voice-track")
async def upload_voice_track(pid: str, file: UploadFile = File(...), s: Session = Depends(get_session)):
    """A complete human-recorded AD track, aligned on the film timeline."""
    p = _project(s, pid)
    ext = Path(file.filename or "").suffix.lower()
    if ext not in AUDIO_EXT:
        raise HTTPException(415, "Format audio non pris en charge")
    dest = service.project_dir(pid) / f"voice_track{ext}"
    await _save_upload(file, dest, 300 * 1024 * 1024)
    try:
        media.audio_duration(dest)
    except media.MediaError as exc:
        dest.unlink(missing_ok=True)
        raise HTTPException(415, f"Audio illisible : {exc}") from exc
    p.voice_track_path = service.rel(dest)
    s.add(p)
    s.commit()
    s.refresh(p)
    return project_summary(s, p)


@router.delete("/projects/{pid}/voice-track")
def delete_voice_track(pid: str, s: Session = Depends(get_session)):
    p = _project(s, pid)
    if p.voice_track_path:
        service.absolute(p.voice_track_path).unlink(missing_ok=True)
    p.voice_track_path = ""
    s.add(p)
    s.commit()
    s.refresh(p)
    return project_summary(s, p)


# ------------------------------------------------------------------ export ----------------------------

@router.post("/projects/{pid}/export", status_code=202)
def export(pid: str, s: Session = Depends(get_session)):
    _project(s, pid)
    if jobs.active_job(pid):
        raise HTTPException(409, "Une tâche est déjà en cours pour ce projet.")
    if not s.exec(select(Description).where(Description.project_id == pid,
                                            Description.status == DescriptionStatus.VALIDATED)).first():
        raise HTTPException(409, "Aucune ligne validée par un humain : validez au moins une description.")
    return jobs.submit(pid, "export", lambda ctx: service.export_project(pid, ctx))


@router.get("/projects/{pid}/export")
def list_exports(pid: str, s: Session = Depends(get_session)):
    _project(s, pid)
    out = get_settings().projects_dir / pid / "export"
    if not out.exists():
        return {"files": [], "generated_at": None}
    files = [{"name": f.name, "size": f.stat().st_size, "url": f"/api/projects/{pid}/export/{f.name}"}
             for f in sorted(out.iterdir()) if f.is_file()]
    ts = max((f.stat().st_mtime for f in out.iterdir()), default=None)
    return {"files": files, "generated_at": datetime.fromtimestamp(ts).isoformat() if ts else None}


@router.get("/projects/{pid}/export/{name}")
def download_export(pid: str, name: str):
    out = (get_settings().projects_dir / pid / "export").resolve()
    f = (out / name).resolve()
    if f.parent != out or not f.is_file():
        raise HTTPException(404, "Fichier introuvable")
    media_type = "text/vtt" if f.suffix == ".vtt" else None
    return FileResponse(f, filename=f.name, media_type=media_type)


@router.get("/files/{path:path}")
def serve_file(path: str):
    """Serve project media (video with Range support, keyframes, voice clips) from the data dir only."""
    root = get_settings().data_dir.resolve()
    f = (root / path).resolve()
    if root not in f.parents or not f.is_file():
        raise HTTPException(404, "Fichier introuvable")
    return FileResponse(f)


# ------------------------------------------------------------------ feedback --------------------------

class FeedbackIn(BaseModel):
    project_id: str = ""
    tester_alias: str = Field(default="", max_length=80)
    comprehension: int = Field(ge=1, le=5)
    preferred_language: str
    comment: str = Field(default="", max_length=3000)
    consent: bool
    paid_tester: bool = False


@router.post("/feedback", status_code=201)
def post_feedback(body: FeedbackIn, s: Session = Depends(get_session)):
    if not body.consent:
        raise HTTPException(400, "Le consentement est requis pour enregistrer un retour.")
    if body.preferred_language not in {"msa", "darija", "fr", "no_preference"}:
        raise HTTPException(422, "Préférence de langue inconnue")
    fb = Feedback(**body.model_dump())
    s.add(fb)
    s.commit()
    s.refresh(fb)
    return fb


@router.get("/feedback")
def list_feedback(project_id: str | None = None, s: Session = Depends(get_session)):
    q = select(Feedback).order_by(Feedback.created_at.desc())  # type: ignore[attr-defined]
    if project_id:
        q = q.where(Feedback.project_id == project_id)
    return s.exec(q).all()


@router.get("/feedback/summary")
def feedback_summary(project_id: str | None = None, s: Session = Depends(get_session)):
    q = select(Feedback)
    if project_id:
        q = q.where(Feedback.project_id == project_id)
    rows = s.exec(q).all()
    prefs = {k: 0 for k in ("msa", "darija", "fr", "no_preference")}
    hist = {str(i): 0 for i in range(1, 6)}
    for r in rows:
        prefs[r.preferred_language] = prefs.get(r.preferred_language, 0) + 1
        hist[str(r.comprehension)] += 1
    return {
        "count": len(rows),
        "mean_comprehension": round(sum(r.comprehension for r in rows) / len(rows), 2) if rows else None,
        "language_preference": prefs,
        "comprehension_histogram": hist,
        "paid_testers": sum(r.paid_tester for r in rows),
    }
