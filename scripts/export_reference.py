"""Turn a human-reviewed project into the reference files of the sample video, for DEMO MODE.

    python scripts/export_reference.py <project_id>            # validated lines only (default)
    python scripts/export_reference.py <project_id> --edited   # also lines edited but not yet validated

Writes, next to the sample video (SAMPLE_VIDEO, default samples/les_ephemeres.mp4):
  <name>.script.json      the descriptions, read by the `demo` VLM instead of Gemini
  <name>.transcript.json  the dialogue, read by the `demo` ASR instead of Whisper

Only lines a human validated are exported by default: DEMO MODE must show reviewed text, not raw AI output.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from sqlmodel import select  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.db import session_scope  # noqa: E402
from app.models import Description, DescriptionStatus, Project, TranscriptSegment  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project_id")
    ap.add_argument("--edited", action="store_true", help="inclure les lignes modifiées mais pas encore validées")
    args = ap.parse_args()

    settings = get_settings()
    statuses = [DescriptionStatus.VALIDATED] + ([DescriptionStatus.EDITED] if args.edited else [])
    with session_scope() as s:
        project = s.get(Project, args.project_id)
        if project is None:
            sys.exit(f"Projet introuvable : {args.project_id}")
        if project.filename != settings.resolved_sample_video.name:
            sys.exit(f"Ce projet porte sur « {project.filename} », pas sur la vidéo d'exemple "
                     f"« {settings.resolved_sample_video.name} » (SAMPLE_VIDEO).")
        lines = s.exec(select(Description).where(Description.project_id == project.id,
                                                 Description.status.in_(statuses))  # type: ignore[attr-defined]
                       .order_by(Description.start)).all()  # type: ignore[arg-type]
        segments = s.exec(select(TranscriptSegment).where(TranscriptSegment.project_id == project.id)
                          .order_by(TranscriptSegment.start)).all()  # type: ignore[arg-type]
        if not lines:
            sys.exit("Aucune ligne à exporter : validez les descriptions dans l'éditeur d'abord.")

        script = []
        for d in lines:
            item = {"anchor": round(d.start, 2), "confidence": round(d.confidence, 2), "text": {d.language: d.text}}
            if d.ai_original_text and d.ai_original_text != d.text:
                item["alt"] = {d.language: d.ai_original_text}  # offered when the describer clicks "Régénérer"
            script.append(item)
        transcript = {"language": project.asr_language or "und",
                      "segments": [{"start": round(t.start, 2), "end": round(t.end, 2), "text": t.text}
                                   for t in segments]}

    for path, data in ((settings.sample_script, script), (settings.sample_transcript, transcript)):
        path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"écrit : {path.relative_to(ROOT)}")
    print(f"{len(script)} description(s), {len(transcript['segments'])} réplique(s).")


if __name__ == "__main__":
    main()
