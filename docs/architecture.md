# Architecture

Wasf is a single container: a FastAPI backend that serves a React single-page app, runs AI/media jobs in an
in-process thread pool, and stores everything in SQLite + local files under `./data`.

```mermaid
flowchart LR
  subgraph Browser["Navigateur (React + TS + Tailwind)"]
    UI1[Tableau de bord] --> UI2[Nouveau projet]
    UI2 --> UI3[Espace d'analyse]
    UI3 --> UI4[Éditeur AD<br/>human-in-the-loop]
    UI4 --> UI5[Export & QA]
    UI5 --> UI6[Retours testeurs aveugles]
  end

  subgraph API["FastAPI /api"]
    R[routes.py] --> J[jobs.py<br/>ThreadPool]
    J --> S[service.py]
  end

  subgraph Pipeline["Pipeline (CPU par défaut)"]
    FF[FFmpeg<br/>audio 16 kHz · scènes · images clés]
    VAD[Silero VAD<br/>repli webrtcvad]
    ASR[ASR provider<br/>faster-whisper · demo]
    GAP[compute_gaps<br/>≥ 1,5 s, marge 0,25 s]
    VLM[VLM provider<br/>gemini · openai-compatible · demo]
    FIT[fit_to_gap<br/>mots/s → coupe ou signale]
    TTS[TTS provider<br/>edge-tts · espeak-ng · demo]
    MIX[FFmpeg mix<br/>ducking · MP4 2 pistes]
    EXP[WebVTT · TTML · credits · script ayant droit]
  end

  Browser -- REST/JSON --> R
  S --> FF --> VAD --> GAP
  FF --> ASR --> GAP
  GAP --> FF
  GAP --> VLM --> FIT
  S --> TTS --> MIX --> EXP
  S <--> DB[(SQLite<br/>data/app.db)]
  S <--> FS[(data/projects/&lt;id&gt;/<br/>source · audio · frames · voice · export)]
  ASR -. lazy download .-> M[(/models volume)]
```

## Key design decisions

| Decision | Why |
|---|---|
| **VAD is authoritative for timing**, ASR segments only fill VAD misses | Whisper segment boundaries often span silences; trusting them erased all gaps on the sample. VAD timing + a 0.25 s safety margin guarantees descriptions never overlap speech. |
| **Only gaps + 1–3 keyframes per gap** reach the VLM | A 90-min film has ~130 000 frames; we send a few hundred. Lower cost, lower energy, less data sent to third parties. |
| **Providers behind tiny interfaces** (`providers/asr.py`, `vision.py`, `tts.py`) | Swap Whisper for a Tunisian fine-tune, Gemini for a local VLM via an OpenAI-compatible server, edge-tts for Piper, by env var only. |
| **Validation is a separate, explicit API call with a name** (`POST /descriptions/{id}/validate`) | No code path sets `validated` automatically. Any edit after validation resets the line to `edited`. |
| **Export only includes human-validated lines** | Nothing reaches the audience without human sign-off. |
| **In-process job queue** | No Redis needed for an MVP; jobs interrupted by a restart are marked failed at boot. |
| **Server-side interval check** | `PATCH`/`POST` descriptions refuse intervals overlapping detected speech (HTTP 422). |
| **DEMO MODE flags propagate** | `demo` flag on each line, banner in UI, `NOTE` in VTT, `ttm:desc` in TTML, MP4 `comment` metadata, `credits.txt`. |

## Data model (SQLite)

`Project` · `TranscriptSegment` · `SpeechRegion` · `Gap` · `Keyframe` · `Description` (status, origin, flags,
confidence, provider/model, original AI text, validator + timestamp, JSON history, audio) · `Job` · `Feedback`.

Files live in `data/projects/<id>/`: `source.*`, `audio.wav`, `frames/*.jpg`, `voice/*.wav`, `export/*`.
Paths are stored relative to `DATA_DIR`, so moving to object storage only requires changing `service.absolute/rel`.

## Description lifecycle

```mermaid
stateDiagram-v2
  [*] --> ai_draft: VLM draft
  [*] --> edited: manual line
  ai_draft --> edited: human edits text/time/lang
  ai_draft --> ai_draft: regenerate
  edited --> ai_draft: regenerate
  ai_draft --> validated: human validates (name required)
  edited --> validated: human validates (name required)
  validated --> edited: any further edit
  ai_draft --> rejected
  edited --> rejected
  validated --> rejected
  rejected --> edited: reopen
  rejected --> ai_draft: reopen (unchanged AI text)
```
