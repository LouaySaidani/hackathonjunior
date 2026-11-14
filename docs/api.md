# API REST

Base URL: `http://localhost:8000`. Interactive OpenAPI docs: **`/docs`**. All bodies are JSON unless noted.
Errors return `{"detail": "<message en français>"}`.

## System

| Method | Path | Description |
|---|---|---|
| GET | `/health` | `{"status":"ok","version","demo_mode"}`, used by the Docker HEALTHCHECK |
| GET | `/api/system` | Active providers, DEMO MODE, thresholds (never secrets) |
| GET | `/api/stats` | Dashboard counters |

## Projects

| Method | Path | Description |
|---|---|---|
| GET | `/api/projects` | List with status counts, `needs_review`, `active_job` |
| POST | `/api/projects` | **multipart**: `file` (mp4/mov/mkv), `title`, `language` (`fr`/`ar`/`aeb`/`en`), `dialogue_language` (`auto`/…), `cast` (JSON `[{name, description}]`), `consent` (**must be true**, else 400), `training_opt_in` (default false). 415 on bad type/unreadable video, 413 if too large |
| POST | `/api/projects/sample` | Creates a project from the CC0 sample clip |
| GET | `/api/projects/{id}` | Full project: transcript, speech regions, gaps, keyframes, descriptions |
| PATCH | `/api/projects/{id}` | `title`, `language`, `validator_name`, `cast`, `training_opt_in` |
| DELETE | `/api/projects/{id}` | Deletes the project and its files |
| POST | `/api/projects/{id}/analyze` | Starts the analysis job (audio → VAD → ASR → gaps → scenes → keyframes → drafts). 202 + Job. 409 if a job is running |
| GET | `/api/jobs/{job_id}` | `status` (`queued`/`running`/`done`/`error`), `progress` 0–1, `step`, `message`, `result` |

## Descriptions (human-in-the-loop)

| Method | Path | Description |
|---|---|---|
| POST | `/api/projects/{id}/descriptions` | Manual line `{start, end, text, language, author}` → `origin=human`, `status=edited`. 422 if it overlaps dialogue |
| PATCH | `/api/descriptions/{id}` | `{text?, start?, end?, language?, editor}`. Any change → `status=edited`, removes validation, recomputes flags. 422 on dialogue overlap |
| DELETE | `/api/descriptions/{id}` | Delete |
| POST | `/api/descriptions/{id}/validate` | `{validator}` **required**. Sets `validated`, `validated_by`, `validated_at`. 422 if text is `too_long` |
| POST | `/api/projects/{id}/validate-all` | `{validator}` **required**. Validates every `ai_draft` / `edited` line at once (history: « validation groupée »). Rejected lines are untouched; `too_long` lines stay blocked and are returned in `blocked`. → `{validated, blocked[]}` |
| POST | `/api/descriptions/{id}/reject` | `{by, reason}` |
| POST | `/api/descriptions/{id}/reopen` | Back from `rejected` |
| POST | `/api/descriptions/{id}/regenerate` | `{hint?, language?}`: new AI draft for the same gap, status back to `ai_draft` |
| POST | `/api/descriptions/{id}/tts` | Synthesize voice (**validated lines only**, else 409). Returns `warnings` (speed-up, Arabic quality…) |
| DELETE | `/api/descriptions/{id}/voice` | Remove the synthesized voice (it can be generated again) |

Description object: `id, start, end, text, language, origin (ai|human), status (ai_draft|edited|validated|rejected),
confidence, needs_review, flags[] (low_confidence, uncertain, trimmed_to_fit, too_long, demo), provider, model,
ai_original_text, validated_by, validated_at, history[], audio_url, audio_source (tts|demo_tone),
audio_duration, audio_voice, estimated_seconds`.

## Voice & export

| Method | Path | Description |
|---|---|---|
| POST | `/api/projects/{id}/tts` | Job: TTS for all validated lines without audio |
| POST | `/api/projects/{id}/export` | Job: builds `film_audiodecrit.mp4` (AD mix + original track), `ad_track.wav/.mp3`, `description.vtt`, `description.ttml`, `credits.txt`, `script_ayant_droit.json`, `export_complet.zip`. **Validated lines only**; 409 if none |
| GET | `/api/projects/{id}/export` | List generated files |
| GET | `/api/projects/{id}/export/{name}` | Download one file |
| GET | `/api/files/{path}` | Project media (video with HTTP Range, keyframes, voice clips), confined to `DATA_DIR` |

## Feedback (blind / visually impaired testers)

| Method | Path | Description |
|---|---|---|
| POST | `/api/feedback` | `{project_id?, tester_alias?, comprehension 1–5, preferred_language (msa|darija|fr|no_preference), comment?, consent (must be true), paid_tester}` |
| GET | `/api/feedback?project_id=` | List |
| GET | `/api/feedback/summary?project_id=` | Count, mean comprehension, language preference counts, histogram |
