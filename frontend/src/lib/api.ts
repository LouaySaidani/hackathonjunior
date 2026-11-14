export type Status = "ai_draft" | "edited" | "validated" | "rejected";
export type Lang = "fr" | "ar" | "aeb" | "en";

export interface Job {
  id: string;
  project_id: string;
  kind: string;
  status: "queued" | "running" | "done" | "error";
  progress: number;
  step: string;
  message: string;
  error: string;
  result?: Record<string, unknown>;
}

export interface Description {
  id: string;
  project_id: string;
  gap_id: number | null;
  start: number;
  end: number;
  text: string;
  language: Lang;
  origin: "ai" | "human";
  status: Status;
  confidence: number;
  needs_review: boolean;
  flags: string[];
  provider: string;
  model: string;
  ai_original_text: string;
  validated_by: string;
  validated_at: string | null;
  history: { at: string; action: string; by: string; detail: string }[];
  audio_url: string;
  audio_source: string;
  audio_duration: number;
  audio_voice: string;
  estimated_seconds: number;
  warnings?: string[];
}

export interface CastMember {
  name: string;
  description: string;
}

export interface ProjectSummary {
  id: string;
  title: string;
  language: Lang;
  dialogue_language: string;
  status: string;
  filename: string;
  size_bytes: number;
  duration: number;
  width: number;
  height: number;
  fps: number;
  video_codec: string;
  audio_codec: string;
  consent: boolean;
  training_opt_in: boolean;
  validator_name: string;
  is_sample: boolean;
  asr_provider: string;
  asr_model: string;
  asr_language: string;
  vlm_provider: string;
  vlm_model: string;
  vad_engine: string;
  demo_mode: boolean;
  error: string;
  created_at: string;
  video_url: string;
  cast: CastMember[];
  counts: Record<Status, number>;
  needs_review: number;
  active_job: Job | null;
}

export interface Interval {
  id: number;
  start: number;
  end: number;
}

/** A silence. `score` is the ML relevance (null when no trained model was used). */
export interface Gap extends Interval {
  score: number | null;
  recommended: boolean;
}

export interface GapModelInfo {
  active: boolean;
  selection: string;
  threshold?: number;
  model?: string;
  trained_at?: string;
  train_videos?: number;
  test_metrics?: { videos: number; gaps: number; precision: number; recall: number; f1: number; selected_share: number };
}

export interface Project extends ProjectSummary {
  transcript: (Interval & { text: string })[];
  speech: Interval[];
  gaps: Gap[];
  keyframes: { id: number; gap_id: number; time: number; url: string; reason: string }[];
  descriptions: Description[];
}

export interface SystemInfo {
  demo_mode: boolean;
  providers: Record<string, string>;
  min_gap_seconds: number;
  max_upload_mb: number;
  confidence_threshold: number;
  gap_model: GapModelInfo;
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  if (!res.ok) {
    let msg = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if (body?.detail) msg = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* ignore */
    }
    throw new ApiError(res.status, msg);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

const json = (method: string, body?: unknown): RequestInit => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: body === undefined ? undefined : JSON.stringify(body),
});

export const api = {
  system: () => request<SystemInfo>("/api/system"),
  stats: () => request<Record<string, number>>("/api/stats"),
  projects: () => request<ProjectSummary[]>("/api/projects"),
  project: (id: string) => request<Project>(`/api/projects/${id}`),
  createSample: () => request<ProjectSummary>("/api/projects/sample", { method: "POST" }),
  patchProject: (id: string, body: Partial<{ title: string; language: Lang; validator_name: string; cast: CastMember[] }>) =>
    request<ProjectSummary>(`/api/projects/${id}`, json("PATCH", body)),
  deleteProject: (id: string) => request<void>(`/api/projects/${id}`, { method: "DELETE" }),
  analyze: (id: string) => request<Job>(`/api/projects/${id}/analyze`, { method: "POST" }),
  job: (id: string) => request<Job>(`/api/jobs/${id}`),
  addDescription: (pid: string, body: { start: number; end: number; text: string; language: Lang; author: string }) =>
    request<Description>(`/api/projects/${pid}/descriptions`, json("POST", body)),
  patchDescription: (id: string, body: Partial<{ text: string; start: number; end: number; language: Lang; editor: string }>) =>
    request<Description>(`/api/descriptions/${id}`, json("PATCH", body)),
  deleteDescription: (id: string) => request<void>(`/api/descriptions/${id}`, { method: "DELETE" }),
  validate: (id: string, validator: string) => request<Description>(`/api/descriptions/${id}/validate`, json("POST", { validator })),
  validateAll: (pid: string, validator: string) =>
    request<{ validated: number; blocked: string[] }>(`/api/projects/${pid}/validate-all`, json("POST", { validator })),
  reject: (id: string, by: string, reason = "") => request<Description>(`/api/descriptions/${id}/reject`, json("POST", { by, reason })),
  reopen: (id: string, by: string) => request<Description>(`/api/descriptions/${id}/reopen`, json("POST", { by })),
  regenerate: (id: string, hint: string, language?: Lang) =>
    request<Description>(`/api/descriptions/${id}/regenerate`, json("POST", { hint, language })),
  draftGap: (gid: number) => request<Description>(`/api/gaps/${gid}/draft`, { method: "POST" }),
  tts: (id: string) => request<Description>(`/api/descriptions/${id}/tts`, { method: "POST" }),
  ttsAll: (pid: string) => request<Job>(`/api/projects/${pid}/tts`, { method: "POST" }),
  deleteVoice: (id: string) => request<Description>(`/api/descriptions/${id}/voice`, { method: "DELETE" }),
  export: (pid: string) => request<Job>(`/api/projects/${pid}/export`, { method: "POST" }),
  exports: (pid: string) =>
    request<{ files: { name: string; size: number; url: string }[]; generated_at: string | null }>(`/api/projects/${pid}/export`),
  postFeedback: (body: Record<string, unknown>) => request(`/api/feedback`, json("POST", body)),
  feedbackSummary: (pid?: string) =>
    request<{
      count: number;
      mean_comprehension: number | null;
      language_preference: Record<string, number>;
      comprehension_histogram: Record<string, number>;
      paid_testers: number;
    }>(`/api/feedback/summary${pid ? `?project_id=${pid}` : ""}`),
  feedbackList: (pid?: string) =>
    request<{ id: number; comprehension: number; preferred_language: string; comment: string; tester_alias: string; created_at: string }[]>(
      `/api/feedback${pid ? `?project_id=${pid}` : ""}`,
    ),
};

/** Upload with progress (fetch has no upload progress). */
export function uploadProject(form: FormData, onProgress: (p: number) => void): Promise<ProjectSummary> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/projects");
    xhr.upload.onprogress = (e) => e.lengthComputable && onProgress(e.loaded / e.total);
    xhr.onload = () => {
      let body: { detail?: string } | ProjectSummary = {};
      try {
        body = JSON.parse(xhr.responseText);
      } catch {
        /* ignore */
      }
      if (xhr.status >= 200 && xhr.status < 300) resolve(body as ProjectSummary);
      else reject(new ApiError(xhr.status, (body as { detail?: string }).detail || xhr.statusText));
    };
    xhr.onerror = () => reject(new ApiError(0, "Réseau indisponible"));
    xhr.send(form);
  });
}

export const isRtl = (lang: string) => lang === "ar" || lang === "aeb";

export function fmtTime(s: number, withMs = false): string {
  if (!Number.isFinite(s)) return "--:--";
  const m = Math.floor(s / 60);
  const sec = s - m * 60;
  return withMs ? `${m}:${sec.toFixed(1).padStart(4, "0")}` : `${m}:${Math.floor(sec).toString().padStart(2, "0")}`;
}

export function fmtBytes(b: number): string {
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(0)} Ko`;
  return `${(b / 1024 / 1024).toFixed(1)} Mo`;
}
