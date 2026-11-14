"""FastAPI entrypoint: REST API under /api, the built React app at /, health at /health."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session, select

from . import __version__
from .api.routes import create_sample_project, router
from .config import get_settings
from .db import get_engine
from .models import Job, Project

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("app")


def _startup() -> None:
    settings = get_settings()
    engine = get_engine()
    with Session(engine) as s:
        # jobs interrupted by a restart can never finish: mark them failed
        for j in s.exec(select(Job).where(Job.status.in_(["queued", "running"]))).all():  # type: ignore[attr-defined]
            j.status, j.error = "error", "Interrompu par un redémarrage du serveur"
            s.add(j)
        for p in s.exec(select(Project).where(Project.status == "analyzing")).all():
            p.status, p.error = "error", "Analyse interrompue par un redémarrage"
            s.add(p)
        # A sample made from a previous SAMPLE_VIDEO stays as an ordinary project (nothing is deleted),
        # so the current sample video can be seeded.
        sample_name = settings.resolved_sample_video.name
        for p in s.exec(select(Project).where(Project.is_sample == True)).all():  # noqa: E712
            if p.filename != sample_name:
                p.is_sample = False
                s.add(p)
        s.commit()
        if settings.seed_sample and not s.exec(select(Project).where(Project.is_sample == True)).first():  # noqa: E712
            try:
                create_sample_project(s)
                log.info("Sample project created")
            except Exception as exc:  # noqa: BLE001
                log.warning("Could not seed sample: %s", exc)
    log.info("DEMO MODE: %s (VLM provider: %s)", settings.demo_mode, settings.resolved_vlm_provider())


@asynccontextmanager
async def lifespan(_: FastAPI):
    _startup()
    yield


app = FastAPI(title="Wasf — AI Audio Description Co-Pilot", version=__version__, lifespan=lifespan)
app.include_router(router)


@app.get("/health")
def health():
    settings = get_settings()
    return {"status": "ok", "version": __version__, "demo_mode": settings.demo_mode}


_dist = get_settings().frontend_dist
if (_dist / "assets").exists():
    app.mount("/assets", StaticFiles(directory=_dist / "assets"), name="assets")


@app.get("/{full_path:path}", include_in_schema=False)
def spa(full_path: str):
    if full_path.startswith("api/"):
        return JSONResponse({"detail": "Not found"}, status_code=404)
    candidate = (_dist / full_path).resolve()
    if full_path and candidate.is_file() and _dist.resolve() in candidate.parents:
        return FileResponse(candidate)
    index = _dist / "index.html"
    if index.exists():
        return FileResponse(index)
    return JSONResponse({"detail": "Frontend non construit. Lancez `npm run build` dans frontend/."}, status_code=404)
