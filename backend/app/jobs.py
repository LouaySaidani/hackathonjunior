"""Tiny in-process background job runner (no Redis needed for the MVP)."""

from __future__ import annotations

import json
import logging
import traceback
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor

from sqlmodel import select

from .db import session_scope
from .models import Job, utcnow

log = logging.getLogger("jobs")
_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="job")


class JobContext:
    def __init__(self, job_id: str):
        self.job_id = job_id

    def update(self, progress: float | None = None, step: str | None = None, message: str | None = None):
        with session_scope() as s:
            job = s.get(Job, self.job_id)
            if not job:
                return
            if progress is not None:
                job.progress = max(0.0, min(1.0, progress))
            if step is not None:
                job.step = step
            if message is not None:
                job.message = message
            job.updated_at = utcnow()
            s.add(job)
            s.commit()


def submit(project_id: str, kind: str, fn: Callable[[JobContext], dict | None]) -> Job:
    with session_scope() as s:
        job = Job(project_id=project_id, kind=kind)
        s.add(job)
        s.commit()
        s.refresh(job)
        job_id = job.id
        job_copy = Job.model_validate(job)

    def _run():
        ctx = JobContext(job_id)
        _set(job_id, status="running")
        try:
            result = fn(ctx) or {}
            _set(job_id, status="done", progress=1.0, result_json=json.dumps(result))
        except Exception as exc:  # noqa: BLE001
            log.error("job %s failed: %s", job_id, traceback.format_exc())
            _set(job_id, status="error", error=str(exc) or exc.__class__.__name__)

    _executor.submit(_run)
    return job_copy


def run_sync(project_id: str, kind: str, fn: Callable[[JobContext], dict | None]) -> Job:
    """Run a job synchronously (tests / notebook)."""
    with session_scope() as s:
        job = Job(project_id=project_id, kind=kind, status="running")
        s.add(job)
        s.commit()
        s.refresh(job)
        job_id = job.id
    try:
        result = fn(JobContext(job_id)) or {}
        _set(job_id, status="done", progress=1.0, result_json=json.dumps(result))
    except Exception as exc:
        _set(job_id, status="error", error=str(exc))
        raise
    with session_scope() as s:
        return Job.model_validate(s.get(Job, job_id))


def _set(job_id: str, **fields):
    with session_scope() as s:
        job = s.get(Job, job_id)
        if not job:
            return
        for k, v in fields.items():
            setattr(job, k, v)
        job.updated_at = utcnow()
        s.add(job)
        s.commit()


def active_job(project_id: str) -> Job | None:
    with session_scope() as s:
        job = s.exec(
            select(Job)
            .where(Job.project_id == project_id, Job.status.in_(["queued", "running"]))  # type: ignore[attr-defined]
            .order_by(Job.created_at.desc())  # type: ignore[attr-defined]
        ).first()
        return Job.model_validate(job) if job else None
