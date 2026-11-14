"""Database models (SQLite via SQLModel)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlmodel import Field, SQLModel


def _uuid() -> str:
    return uuid.uuid4().hex[:12]


def utcnow() -> datetime:
    return datetime.now(UTC)


class DescriptionStatus:
    AI_DRAFT = "ai_draft"
    EDITED = "edited"
    VALIDATED = "validated"
    REJECTED = "rejected"
    ALL = (AI_DRAFT, EDITED, VALIDATED, REJECTED)


class Project(SQLModel, table=True):
    id: str = Field(default_factory=_uuid, primary_key=True)
    title: str
    language: str = "fr"  # target AD language: fr | ar | aeb (Tunisian darija) | en
    dialogue_language: str = "auto"  # hint for ASR: auto | fr | ar | en
    status: str = "uploaded"  # uploaded | analyzing | analyzed | drafting | ready | error
    filename: str = ""
    video_path: str = ""
    audio_path: str = ""
    size_bytes: int = 0
    duration: float = 0.0
    width: int = 0
    height: int = 0
    fps: float = 0.0
    video_codec: str = ""
    audio_codec: str = ""
    consent: bool = False
    training_opt_in: bool = False  # off by default; we never train on uploads anyway
    cast_json: str = "[]"  # [{"name": "...", "description": "..."}]
    validator_name: str = ""
    is_sample: bool = False
    asr_provider: str = ""
    asr_model: str = ""
    asr_language: str = ""
    vlm_provider: str = ""
    vlm_model: str = ""
    vad_engine: str = ""
    demo_mode: bool = False
    voice_track_path: str = ""  # optional full human-recorded AD track
    error: str = ""
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class TranscriptSegment(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    project_id: str = Field(index=True)
    start: float
    end: float
    text: str
    speaker: str = ""


class SpeechRegion(SQLModel, table=True):
    """Speech detected by VAD (union with ASR segments) - descriptions may never overlap these."""

    id: int | None = Field(default=None, primary_key=True)
    project_id: str = Field(index=True)
    start: float
    end: float


class Gap(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    project_id: str = Field(index=True)
    start: float
    end: float


class Keyframe(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    project_id: str = Field(index=True)
    gap_id: int | None = None
    time: float
    path: str
    reason: str = "gap"  # gap | scene_change


class Description(SQLModel, table=True):
    id: str = Field(default_factory=_uuid, primary_key=True)
    project_id: str = Field(index=True)
    gap_id: int | None = None
    start: float
    end: float
    text: str
    language: str = "fr"
    origin: str = "ai"  # ai | human
    status: str = DescriptionStatus.AI_DRAFT
    confidence: float = 0.0
    needs_review: bool = False
    flags_json: str = "[]"  # e.g. ["low_confidence", "trimmed_to_fit", "too_long", "demo"]
    provider: str = ""
    model: str = ""
    ai_original_text: str = ""
    validated_by: str = ""
    validated_at: datetime | None = None
    history_json: str = "[]"  # traceability log
    audio_path: str = ""
    audio_source: str = ""  # tts | human | demo_tone
    audio_duration: float = 0.0
    audio_voice: str = ""
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class Job(SQLModel, table=True):
    id: str = Field(default_factory=_uuid, primary_key=True)
    project_id: str = Field(index=True)
    kind: str  # analyze | draft | regenerate | tts | export
    status: str = "queued"  # queued | running | done | error
    progress: float = 0.0
    step: str = ""
    message: str = ""
    error: str = ""
    result_json: str = "{}"
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class Feedback(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    project_id: str = ""
    tester_alias: str = ""
    comprehension: int  # 1..5
    preferred_language: str  # msa | darija | fr | no_preference
    comment: str = ""
    consent: bool = False
    paid_tester: bool = False
    created_at: datetime = Field(default_factory=utcnow)
