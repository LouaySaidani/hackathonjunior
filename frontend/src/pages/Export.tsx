import { AudioLines, Download, FileAudio, FileText, FileVideo, MessageSquareHeart, Package, PencilRuler } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ErrorBox, Notice, PageHeader, ProgressBar, Spinner, useJob } from "../components/ui";
import { api, fmtBytes, isRtl } from "../lib/api";
import { useT, type Key } from "../lib/i18n";
import { useProject } from "../lib/useProject";
import { useTitle } from "../lib/useTitle";

type Files = { name: string; size: number; url: string }[];

const ICONS: Record<string, typeof FileText> = { mp4: FileVideo, mp3: FileAudio, wav: FileAudio, zip: Package };

export default function ExportPage() {
  const { id } = useParams();
  const { t } = useT();
  const { project, error, reload } = useProject(id);
  useTitle(`${t("exportTitle")} — ${project?.title ?? ""}`);
  const [files, setFiles] = useState<Files>([]);
  const [generatedAt, setGeneratedAt] = useState<string | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [actionError, setActionError] = useState("");
  const [lastResult, setLastResult] = useState<{ warnings?: string[] } | null>(null);

  const loadFiles = useCallback(() => {
    if (!id) return;
    api.exports(id).then((r) => {
      setFiles(r.files);
      setGeneratedAt(r.generated_at);
    });
  }, [id]);
  useEffect(loadFiles, [loadFiles]);

  const job = useJob(jobId, (j) => {
    reload();
    loadFiles();
    if (j.status === "done") setLastResult(j.result as { warnings?: string[] });
  });
  const running = job && (job.status === "running" || job.status === "queued");

  const startJob = async (fn: () => Promise<{ id: string }>) => {
    setActionError("");
    setLastResult(null);
    try {
      const j = await fn();
      setJobId(j.id);
    } catch (e) {
      setActionError((e as Error).message);
    }
  };

  if (error) return <ErrorBox message={error} onRetry={reload} />;
  if (!project) return <Spinner label={t("loading")} />;

  const active = project.descriptions.filter((d) => d.status !== "rejected");
  const validated = project.descriptions.filter((d) => d.status === "validated");
  const voiced = validated.filter((d) => d.audio_url).length;
  const review = active.filter((d) => d.needs_review).length;
  const vtt = files.find((f) => f.name === "description.vtt");
  const mp4 = files.find((f) => f.name === "film_audiodecrit.mp4");
  const v = `?v=${encodeURIComponent(generatedAt ?? "")}`;

  return (
    <>
      <PageHeader
        title={t("exportTitle")}
        subtitle={project.title}
        actions={
          <>
            <Link to={`/projects/${project.id}/editor`} className="btn-secondary">
              <PencilRuler size={16} aria-hidden="true" /> {t("editor")}
            </Link>
            <Link to={`/feedback?project=${project.id}`} className="btn-secondary">
              <MessageSquareHeart size={16} aria-hidden="true" /> {t("feedbackLink")}
            </Link>
          </>
        }
      />

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[1.3fr_1fr]">
        <div className="space-y-6">
          <section className="card p-5" aria-labelledby="prev-h">
            <h2 id="prev-h" className="mb-3 text-lg font-semibold">
              {t("finalPreview")}
            </h2>
            <video
              key={mp4 ? mp4.url + v : project.video_url}
              src={mp4 ? mp4.url + v : project.video_url}
              controls
              preload="metadata"
              className="aspect-video w-full rounded-xl bg-black"
            >
              {vtt && <track kind="descriptions" src={vtt.url + v} srcLang={project.language} label="Audiodescription" default />}
            </video>
            {!mp4 && <p className="hint mt-2">{t("exportOnlyValidated")}</p>}
            {validated.length > 0 && (
              <ol className="mt-4 space-y-1 text-sm">
                {validated.map((d) => (
                  <li key={d.id} className="flex gap-3 rounded-lg bg-surface-2 px-3 py-2">
                    <span className="shrink-0 font-mono text-xs text-teal">{d.start.toFixed(1)} s</span>
                    <span dir={isRtl(d.language) ? "rtl" : "ltr"} lang={d.language} className="flex-1">
                      {d.text}
                    </span>
                  </li>
                ))}
              </ol>
            )}
          </section>

          <section className="card p-5" aria-labelledby="files-h">
            <h2 id="files-h" className="mb-3 text-lg font-semibold">
              {t("files")}
            </h2>
            <div className="mb-4 flex flex-wrap items-center gap-3">
              <button
                type="button"
                className="btn-primary"
                onClick={() => startJob(() => api.export(project.id))}
                disabled={!!running || validated.length === 0}
              >
                <Package size={16} aria-hidden="true" /> {t("runExport")}
              </button>
              <span className="hint">{t("exportOnlyValidated")}</span>
            </div>
            {validated.length === 0 && <Notice tone="warn">{t("nothingValidated")}</Notice>}
            {files.length > 0 && (
              <ul className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                {files.map((f) => {
                  const Icon = ICONS[f.name.split(".").pop() ?? ""] ?? FileText;
                  return (
                    <li key={f.name}>
                      <a
                        href={f.url + v}
                        download
                        className="flex items-center gap-3 rounded-xl border border-line bg-surface-2 px-3 py-2.5 hover:bg-surface-3"
                      >
                        <Icon size={18} aria-hidden="true" className="text-accent" />
                        <span className="flex-1 truncate font-mono text-sm">{f.name}</span>
                        <span className="text-xs text-muted">{fmtBytes(f.size)}</span>
                        <Download size={16} aria-hidden="true" />
                        <span className="sr-only">{t("download")}</span>
                      </a>
                    </li>
                  );
                })}
              </ul>
            )}
          </section>
        </div>

        <div className="space-y-6">
          <section className="card p-5" aria-labelledby="val-h">
            <h2 id="val-h" className="mb-3 text-lg font-semibold">
              {t("humanValidation")}
            </h2>
            <p className="mb-2 text-3xl font-bold tabular-nums">
              {validated.length}/{active.length}
            </p>
            <ProgressBar value={active.length ? validated.length / active.length : 0} label={t("humanValidation")} />
            <p className="mt-2 text-sm text-muted">{t("progressValidated", { a: validated.length, b: active.length })}</p>
          </section>

          <section className="card p-5" aria-labelledby="acc-h">
            <h2 id="acc-h" className="mb-3 text-lg font-semibold">
              {t("accessSummary")}
            </h2>
            <ul className="space-y-2 text-sm">
              <li>✓ {t("voiceCoverage", { a: voiced, b: validated.length })}</li>
              <li className={review ? "text-warn" : ""}>{review ? "⚠" : "✓"} {t("reviewLeft", { n: review })}</li>
              <li>✓ WebVTT kind=descriptions + TTML</li>
              <li>
                ✓ {t("language")} : {t(`lang_${project.language}` as Key)}
                {isRtl(project.language) && " (RTL)"}
              </li>
              <li>✓ « audiodescription assistée par IA, validée par {project.validator_name || "…"} »</li>
              {project.demo_mode && <li className="font-semibold text-warn">⚠ DEMO MODE — brouillons IA simulés (indiqué dans les exports)</li>}
            </ul>
          </section>

          <section className="card space-y-4 p-5" aria-labelledby="voice-h">
            <h2 id="voice-h" className="text-lg font-semibold">
              {t("voice")}
            </h2>
            <button
              type="button"
              className="btn-secondary w-full"
              onClick={() => startJob(() => api.ttsAll(project.id))}
              disabled={!!running || validated.length === 0}
            >
              <AudioLines size={16} aria-hidden="true" /> {t("genAllVoices")}
            </button>
          </section>

          <div aria-live="polite" aria-atomic="true" className="space-y-3">
            {running && (
              <div className="card p-4">
                <p className="mb-2 text-sm">{job.message || t("loading")}</p>
                <ProgressBar value={job.progress} label={job.kind} />
              </div>
            )}
            {job?.status === "error" && <ErrorBox message={job.error} />}
            {job?.status === "done" && (
              <Notice tone="success">
                {job.kind === "export" ? t("exportDone") : "✓"}
                {lastResult?.warnings?.map((w) => (
                  <span key={w} className="mt-1 block text-xs text-warn">
                    {w}
                  </span>
                ))}
              </Notice>
            )}
            {actionError && <ErrorBox message={actionError} />}
          </div>
        </div>
      </div>
    </>
  );
}
