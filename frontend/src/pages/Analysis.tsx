import { CheckCircle2, Circle, Loader2, PencilRuler, RefreshCw, Play, Scissors } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import Timeline from "../components/Timeline";
import { ErrorBox, Notice, PageHeader, ProgressBar, Spinner, useJob } from "../components/ui";
import { api, fmtTime } from "../lib/api";
import { useT, type Key } from "../lib/i18n";
import { useProject, useVideoTime } from "../lib/useProject";
import { useTitle } from "../lib/useTitle";

const STEPS = ["audio", "vad", "asr", "gaps", "scenes", "keyframes", "drafts"] as const;

export default function Analysis() {
  const { id } = useParams();
  const { t } = useT();
  const { project, error, reload } = useProject(id);
  useTitle(`${t("analysisTitle")} — ${project?.title ?? ""}`);
  const { ref, time, seek } = useVideoTime();
  const [jobId, setJobId] = useState<string | null>(null);
  const [startError, setStartError] = useState("");
  const job = useJob(jobId, () => reload());

  useEffect(() => {
    if (project?.active_job && !jobId) setJobId(project.active_job.id);
  }, [project, jobId]);

  // refresh partial results while running (drafts stream in)
  useEffect(() => {
    if (!job || job.status !== "running") return;
    const i = window.setInterval(reload, 3000);
    return () => window.clearInterval(i);
  }, [job, reload]);

  const start = async () => {
    setStartError("");
    try {
      const j = await api.analyze(project!.id);
      setJobId(j.id);
      reload();
    } catch (e) {
      setStartError((e as Error).message);
    }
  };

  if (error) return <ErrorBox message={error} onRetry={reload} />;
  if (!project) return <Spinner label={t("loading")} />;

  const running = job && (job.status === "running" || job.status === "queued");
  const stepIdx = running ? STEPS.indexOf(job.step as (typeof STEPS)[number]) : -1;
  const analyzed = project.status === "ready" || project.status === "analyzed";

  return (
    <>
      <PageHeader
        title={project.title}
        subtitle={t("analysisTitle")}
        actions={
          <>
            <button type="button" className="btn-secondary" onClick={start} disabled={!!running}>
              <RefreshCw size={16} aria-hidden="true" /> {analyzed || project.status === "error" ? t("rerun") : t("launch")}
            </button>
            <Link to={`/projects/${project.id}/editor`} className="btn-primary">
              <PencilRuler size={16} aria-hidden="true" /> {t("openEditor")}
            </Link>
          </>
        }
      />

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[1.4fr_1fr]">
        <div className="space-y-6">
          <section className="card p-4" aria-label="Lecteur vidéo">
            <video ref={ref} src={project.video_url} controls preload="metadata" className="aspect-video w-full rounded-xl bg-black">
              Votre navigateur ne lit pas cette vidéo.
            </video>
            <dl className="mt-3 flex flex-wrap gap-x-6 gap-y-1 text-sm text-muted">
              <div>
                <dt className="inline">{t("duration")} : </dt>
                <dd className="inline font-semibold text-ink">{fmtTime(project.duration)}</dd>
              </div>
              <div>
                <dt className="inline">{t("resolution")} : </dt>
                <dd className="inline font-semibold text-ink">
                  {project.width}×{project.height} · {project.fps} i/s
                </dd>
              </div>
              <div>
                <dt className="inline">Codecs : </dt>
                <dd className="inline font-semibold text-ink">
                  {project.video_codec} / {project.audio_codec || "—"}
                </dd>
              </div>
            </dl>
          </section>

          {analyzed && (
            <section className="card p-4">
              <Timeline
                duration={project.duration}
                speech={project.speech}
                gaps={project.gaps}
                descriptions={project.descriptions}
                current={time}
                onSeek={seek}
              />
            </section>
          )}

          <section className="card p-5" aria-labelledby="kf-h">
            <h2 id="kf-h" className="text-lg font-semibold">
              {t("keyframes")} <span className="text-sm font-normal text-muted">({project.keyframes.length})</span>
            </h2>
            <p className="hint mb-4">{t("keyframesHint")}</p>
            <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
              {project.keyframes.map((k) => (
                <li key={k.id}>
                  <button
                    type="button"
                    onClick={() => seek(k.time)}
                    className="group block w-full overflow-hidden rounded-xl border border-line bg-surface-2 text-left"
                    title={t("seekTo", { t: fmtTime(k.time, true) })}
                  >
                    <img src={k.url} alt="" loading="lazy" className="aspect-video w-full object-cover transition group-hover:opacity-80" />
                    <span className="flex items-center justify-between px-2 py-1 text-xs">
                      <span className="tabular-nums">{fmtTime(k.time, true)}</span>
                      {k.reason === "scene_change" && (
                        <span className="inline-flex items-center gap-1 text-teal">
                          <Scissors size={12} aria-hidden="true" />
                          {t("sceneChange")}
                        </span>
                      )}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </section>
        </div>

        <div className="space-y-6">
          <section className="card p-5" aria-labelledby="job-h">
            <h2 id="job-h" className="mb-3 text-lg font-semibold">
              {t("jobStatus")}
            </h2>
            <div aria-live="polite" aria-atomic="true" className="space-y-3">
              {running && (
                <>
                  <p className="text-sm">{job.message}</p>
                  <ProgressBar value={job.progress} label={t("jobStatus")} />
                </>
              )}
              {job?.status === "error" && <ErrorBox message={job.error} />}
              {!running && project.status === "error" && !job && <ErrorBox message={project.error} />}
              {!running && project.status === "uploaded" && (
                <Notice>
                  <button type="button" className="btn-primary" onClick={start}>
                    <Play size={16} aria-hidden="true" /> {t("launch")}
                  </button>
                </Notice>
              )}
              {job?.status === "done" && (
                <Notice tone="success">
                  ✓ {String(job.result?.drafts ?? "")} brouillons · {String(job.result?.gaps ?? "")} silences ·{" "}
                  {String(job.result?.segments ?? "")} segments de dialogue
                  {Array.isArray(job.result?.notes) &&
                    (job.result!.notes as string[]).map((n) => (
                      <span key={n} className="mt-1 block text-xs text-muted">
                        {n}
                      </span>
                    ))}
                </Notice>
              )}
              {startError && <ErrorBox message={startError} />}
            </div>
            <ol className="mt-4 space-y-2" aria-label="Étapes">
              {STEPS.map((s, i) => {
                const done = analyzed || (running && i < stepIdx);
                const current = running && i === stepIdx;
                return (
                  <li key={s} className={`flex items-center gap-2 text-sm ${current ? "text-ink" : done ? "text-muted" : "text-subtle"}`}>
                    {current ? (
                      <Loader2 size={16} className="animate-spin text-accent" aria-hidden="true" />
                    ) : done ? (
                      <CheckCircle2 size={16} className="text-valid" aria-hidden="true" />
                    ) : (
                      <Circle size={16} aria-hidden="true" />
                    )}
                    {t(`step_${s}` as Key)}
                    <span className="sr-only">{current ? " — en cours" : done ? " — terminé" : " — à venir"}</span>
                  </li>
                );
              })}
            </ol>
            {project.asr_provider && (
              <div className="mt-4 rounded-xl bg-surface-2 p-3 text-xs text-muted">
                <p className="mb-1 font-semibold text-ink">{t("providers")}</p>
                <p>
                  ASR : {project.asr_provider} ({project.asr_model}, langue détectée : {project.asr_language}) · VAD : {project.vad_engine}
                </p>
                <p>
                  VLM : {project.vlm_provider} ({project.vlm_model}) {project.demo_mode && <strong className="text-warn">· DEMO MODE</strong>}
                </p>
              </div>
            )}
          </section>

          <section className="card p-5" aria-labelledby="tr-h">
            <h2 id="tr-h" className="mb-3 text-lg font-semibold">
              {t("transcript")}
            </h2>
            {project.transcript.length === 0 ? (
              <p className="text-sm text-muted">{t("noTranscript")}</p>
            ) : (
              <ol className="max-h-80 space-y-1 overflow-y-auto pr-1">
                {project.transcript.map((s) => (
                  <li key={s.id}>
                    <button
                      type="button"
                      onClick={() => seek(s.start)}
                      className={`flex w-full gap-3 rounded-lg px-2 py-1.5 text-left text-sm hover:bg-surface-2 ${
                        time >= s.start && time < s.end ? "bg-surface-3" : ""
                      }`}
                    >
                      <span className="shrink-0 font-mono text-xs tabular-nums text-teal">
                        {fmtTime(s.start, true)}–{fmtTime(s.end, true)}
                      </span>
                      <span dir="auto">{s.text}</span>
                    </button>
                  </li>
                ))}
              </ol>
            )}
          </section>

          <section className="card p-5" aria-labelledby="gap-h">
            <h2 id="gap-h" className="text-lg font-semibold">
              {t("silences")}
            </h2>
            <p className="hint mb-3">{t("gapsCount", { n: project.gaps.length, min: 1.5 })}</p>
            <ol className="flex flex-wrap gap-2">
              {project.gaps.map((g) => (
                <li key={g.id}>
                  <button type="button" onClick={() => seek(g.start)} className="btn-secondary !px-2.5 !py-1 font-mono text-xs">
                    {fmtTime(g.start, true)} → {fmtTime(g.end, true)} ({(g.end - g.start).toFixed(1)} s)
                  </button>
                </li>
              ))}
            </ol>
          </section>
        </div>
      </div>
    </>
  );
}
