import { ArrowRight, CheckCheck, Keyboard, Plus, Volume2 } from "lucide-react";
import { useCallback, useEffect, useId, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import DescriptionCard, { type CardActions } from "../components/DescriptionCard";
import Timeline from "../components/Timeline";
import { ErrorBox, Notice, PageHeader, ProgressBar, Spinner } from "../components/ui";
import { api, fmtTime, type Description } from "../lib/api";
import { useT } from "../lib/i18n";
import { useProject, useVideoTime } from "../lib/useProject";
import { useTitle } from "../lib/useTitle";

type Filter = "all" | "review" | "pending";

function readValidator(): string {
  try {
    return localStorage.getItem("wasf.validator") || localStorage.getItem("basira.validator") || "";
  } catch {
    return "";
  }
}

export default function Editor() {
  const { id } = useParams();
  const { t } = useT();
  const { project, setProject, error, reload } = useProject(id);
  useTitle(`${t("editorTitle")} — ${project?.title ?? ""}`);
  const { ref: videoRef, time, seek } = useVideoTime();
  const [activeId, setActiveId] = useState<string | null>(null);
  const [validator, setValidator] = useState(readValidator);
  const [filter, setFilter] = useState<Filter>("all");
  const [showHelp, setShowHelp] = useState(false);
  const [previewAd, setPreviewAd] = useState(false);
  const [announce, setAnnounce] = useState("");
  const [addError, setAddError] = useState("");
  const [confirmAll, setConfirmAll] = useState(false);
  const [bulkBusy, setBulkBusy] = useState(false);
  const [bulkResult, setBulkResult] = useState<{ tone: "ok" | "warn" | "error"; text: string } | null>(null);
  const cardRefs = useRef<Record<string, HTMLElement | null>>({});
  const actionsRef = useRef<CardActions | null>(null);
  const stopAt = useRef<number | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const lastTime = useRef(0);
  const validatorId = useId();
  const helpId = useId();

  useEffect(() => {
    if (project && !validator && project.validator_name) setValidator(project.validator_name);
  }, [project, validator]);

  const descs = useMemo(() => project?.descriptions ?? [], [project]);
  const visible = useMemo(
    () =>
      descs.filter((d) =>
        filter === "all" ? true : filter === "review" ? d.needs_review : d.status !== "validated" && d.status !== "rejected",
      ),
    [descs, filter],
  );
  const total = descs.filter((d) => d.status !== "rejected").length;
  const validated = descs.filter((d) => d.status === "validated").length;
  const pending = descs.filter((d) => d.status === "ai_draft" || d.status === "edited");
  const pendingReview = pending.filter((d) => d.needs_review).length;

  const validateAll = async () => {
    if (!project) return;
    setBulkBusy(true);
    try {
      const res = await api.validateAll(project.id, validator.trim());
      await reload();
      const parts = [t("validateAllDone", { n: res.validated })];
      if (res.blocked.length) parts.push(t("validateAllBlocked", { n: res.blocked.length }));
      setBulkResult({ tone: res.blocked.length ? "warn" : "ok", text: parts.join(" ") });
      setAnnounce(parts.join(" "));
      setConfirmAll(false);
    } catch (e) {
      setBulkResult({ tone: "error", text: (e as Error).message });
    } finally {
      setBulkBusy(false);
    }
  };

  const updateDesc = (d: Description) =>
    setProject((p) => (p ? { ...p, descriptions: p.descriptions.map((x) => (x.id === d.id ? d : x)) } : p));
  const removeDesc = (did: string) =>
    setProject((p) => (p ? { ...p, descriptions: p.descriptions.filter((x) => x.id !== did) } : p));

  const slotFor = useCallback(
    (d: Description) => {
      const next = project?.speech.map((s) => s.start).filter((s) => s > d.start + 0.01) ?? [];
      return (next.length ? Math.min(...next) : (project?.duration ?? d.end)) - d.start;
    },
    [project],
  );

  const playSegment = useCallback(
    (start: number, end: number) => {
      const v = videoRef.current;
      if (!v) return;
      v.currentTime = start;
      stopAt.current = end;
      v.play().catch(() => undefined);
    },
    [videoRef],
  );

  // stop at end of segment + optional AD preview (plays validated clips over the ducked film)
  useEffect(() => {
    const v = videoRef.current;
    if (!v) return;
    if (stopAt.current !== null && time >= stopAt.current) {
      v.pause();
      stopAt.current = null;
    }
    if (previewAd && !v.paused) {
      const prev = lastTime.current;
      const hit = descs.find((d) => d.status === "validated" && d.audio_url && d.start > prev - 0.01 && d.start <= time && time - prev < 1);
      if (hit) {
        audioRef.current?.pause();
        const a = new Audio(hit.audio_url);
        audioRef.current = a;
        v.volume = 0.3;
        a.onended = () => {
          v.volume = 1;
        };
        a.play().catch(() => (v.volume = 1));
      }
    }
    lastTime.current = time;
  }, [time, previewAd, descs, videoRef]);

  useEffect(() => () => audioRef.current?.pause(), []);

  const activate = useCallback(
    (idx: number) => {
      const d = visible[idx];
      if (!d) return;
      setActiveId(d.id);
      seek(d.start);
      const el = cardRefs.current[d.id];
      el?.scrollIntoView({ block: "nearest", behavior: "smooth" });
      el?.focus({ preventScroll: true });
      setAnnounce(`${t("activeLine")} ${idx + 1}/${visible.length} — ${fmtTime(d.start, true)}`);
    },
    [visible, seek, t],
  );

  // keyboard shortcuts
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      const typing = ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName) || target.isContentEditable;
      if (typing && !e.altKey) return;
      if (e.ctrlKey || e.metaKey) return;
      const idx = visible.findIndex((d) => d.id === activeId);
      const key = e.key.toLowerCase();
      if (key === "j" || (e.altKey && e.key === "ArrowDown")) {
        e.preventDefault();
        activate(Math.min(visible.length - 1, idx + 1));
      } else if (key === "k" || (e.altKey && e.key === "ArrowUp")) {
        e.preventDefault();
        activate(Math.max(0, idx - 1));
      } else if (key === "v") {
        e.preventDefault();
        actionsRef.current?.validate();
      } else if (key === "x") {
        e.preventDefault();
        actionsRef.current?.reject();
      } else if (key === "p") {
        e.preventDefault();
        actionsRef.current?.play();
      } else if (key === "s" && e.altKey) {
        e.preventDefault();
        actionsRef.current?.save();
      } else if (e.key === "?") {
        e.preventDefault();
        setShowHelp((s) => !s);
      } else if (e.key === "Escape") {
        setShowHelp(false);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [visible, activeId, activate]);

  const saveValidator = (v: string) => {
    setValidator(v);
    try {
      localStorage.setItem("wasf.validator", v);
    } catch {
      /* ignore */
    }
  };

  const addManual = async () => {
    if (!project) return;
    setAddError("");
    // place it in the silence containing the playhead, or the next one
    const gap = project.gaps.find((g) => time >= g.start && time < g.end) ?? project.gaps.find((g) => g.start >= time);
    const start = gap ? Math.max(gap.start, Math.min(time, gap.end - 1)) : time;
    const end = gap ? Math.min(gap.end, start + 2.5) : start + 2;
    try {
      const d = await api.addDescription(project.id, {
        start: Number(start.toFixed(2)),
        end: Number(end.toFixed(2)),
        text: "…",
        language: project.language,
        author: validator,
      });
      setProject((p) => (p ? { ...p, descriptions: [...p.descriptions, d].sort((a, b) => a.start - b.start) } : p));
      setFilter("all");
      setActiveId(d.id);
      setTimeout(() => cardRefs.current[d.id]?.querySelector("textarea")?.focus(), 50);
    } catch (e) {
      setAddError((e as Error).message);
    }
  };

  if (error) return <ErrorBox message={error} onRetry={reload} />;
  if (!project) return <Spinner label={t("loading")} />;

  const activeDesc = descs.find((d) => d.id === activeId);

  return (
    <>
      <PageHeader
        title={t("editorTitle")}
        subtitle={project.title}
        actions={
          <>
            <button type="button" className="btn-secondary" onClick={() => setShowHelp((s) => !s)} aria-expanded={showHelp} aria-controls={helpId}>
              <Keyboard size={16} aria-hidden="true" /> {t("shortcuts")}
            </button>
            <Link to={`/projects/${project.id}/export`} className="btn-primary">
              {t("exportQa")} <ArrowRight size={16} aria-hidden="true" />
            </Link>
          </>
        }
      />
      <p className="sr-only" aria-live="polite">
        {announce}
      </p>

      {showHelp && (
        <section id={helpId} className="card mb-6 p-5" aria-labelledby={`${helpId}-h`}>
          <h2 id={`${helpId}-h`} className="mb-3 font-semibold">
            {t("shortcuts")}
          </h2>
          <dl className="grid grid-cols-1 gap-2 text-sm sm:grid-cols-2 lg:grid-cols-3">
            {[
              ["J / K", t("sc_next")],
              ["V", t("sc_validate")],
              ["X", t("sc_reject")],
              ["P", t("sc_play")],
              ["Alt + S · Ctrl + Entrée", t("sc_save")],
              ["?", t("sc_help")],
            ].map(([k, v]) => (
              <div key={k} className="flex items-center gap-3">
                <dt>
                  <kbd className="kbd">{k}</kbd>
                </dt>
                <dd className="text-muted">{v}</dd>
              </div>
            ))}
          </dl>
          <p className="hint mt-3">{t("sc_note")}</p>
        </section>
      )}

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)]">
        {/* left: player + timeline + transcript */}
        <div className="space-y-4 xl:sticky xl:top-24 xl:self-start">
          <section className="card p-4" aria-label="Lecteur vidéo">
            <video ref={videoRef} src={project.video_url} controls preload="metadata" className="aspect-video w-full rounded-xl bg-black" />
            <div className="mt-3 flex flex-wrap items-center gap-3">
              <label className="inline-flex items-center gap-2 text-sm">
                <input type="checkbox" checked={previewAd} onChange={(e) => setPreviewAd(e.target.checked)} className="h-4 w-4 accent-[#f4f4f4]" />
                <Volume2 size={15} aria-hidden="true" /> {t("previewAd")}
              </label>
              <span className="ml-auto font-mono text-sm tabular-nums text-muted" aria-hidden="true">
                {fmtTime(time, true)} / {fmtTime(project.duration, true)}
              </span>
            </div>
          </section>
          <section className="card p-4">
            <Timeline
              duration={project.duration}
              speech={project.speech}
              gaps={project.gaps}
              descriptions={descs}
              current={time}
              activeId={activeId}
              onSeek={seek}
              onSelect={(did) => {
                const idx = visible.findIndex((d) => d.id === did);
                if (idx >= 0) activate(idx);
              }}
            />
          </section>
          <section className="card p-4" aria-labelledby="tr-h">
            <h2 id="tr-h" className="mb-2 text-sm font-semibold">
              {t("transcript")}
            </h2>
            {project.transcript.length === 0 ? (
              <p className="text-sm text-muted">{t("noTranscript")}</p>
            ) : (
              <ol className="max-h-52 space-y-0.5 overflow-y-auto pr-1 text-sm">
                {project.transcript.map((s) => (
                  <li key={s.id}>
                    <button
                      type="button"
                      onClick={() => seek(s.start)}
                      className={`flex w-full gap-3 rounded-lg px-2 py-1 text-left hover:bg-surface-2 ${
                        time >= s.start && time < s.end ? "bg-surface-3" : ""
                      }`}
                    >
                      <span className="shrink-0 font-mono text-xs text-teal">{fmtTime(s.start, true)}</span>
                      <span dir="auto">{s.text}</span>
                    </button>
                  </li>
                ))}
              </ol>
            )}
          </section>
        </div>

        {/* right: validation controls + cards */}
        <div className="space-y-4">
          <section className="card space-y-4 p-4" aria-label="Validation">
            <div>
              <label htmlFor={validatorId} className="label">
                {t("validator")}
              </label>
              <input
                id={validatorId}
                className="input"
                value={validator}
                onChange={(e) => saveValidator(e.target.value)}
                onBlur={() => validator && api.patchProject(project.id, { validator_name: validator }).catch(() => undefined)}
                placeholder="ex. Amira B."
                aria-describedby={`${validatorId}-hint`}
                autoComplete="name"
              />
              <p id={`${validatorId}-hint`} className="hint mt-1">
                {t("validatorHint")}
              </p>
            </div>
            <div>
              <p className="mb-1 text-sm font-medium">{t("progressValidated", { a: validated, b: total })}</p>
              <ProgressBar value={total ? validated / total : 0} label={t("humanValidation")} />
            </div>
            {pending.length > 0 && !confirmAll && (
              <button
                type="button"
                className="btn-success w-full"
                onClick={() => {
                  setBulkResult(null);
                  if (!validator.trim()) setBulkResult({ tone: "error", text: t("needValidator") });
                  else setConfirmAll(true);
                }}
              >
                <CheckCheck size={16} aria-hidden="true" /> {t("validateAll", { n: pending.length })}
              </button>
            )}
            {confirmAll && (
              <div role="group" aria-labelledby="bulk-confirm" className="space-y-3 rounded-xl border border-line p-3">
                <p id="bulk-confirm" className="font-semibold">
                  {t("validateAllConfirm", { n: pending.length, name: validator.trim() })}
                </p>
                {pendingReview > 0 && <Notice tone="warn">{t("validateAllReview", { n: pendingReview })}</Notice>}
                <p className="hint">{t("validateAllHint")}</p>
                <div className="flex flex-wrap justify-end gap-2">
                  <button type="button" className="btn-ghost" onClick={() => setConfirmAll(false)} disabled={bulkBusy} autoFocus>
                    {t("validateAllCancel")}
                  </button>
                  <button type="button" className="btn-success" onClick={validateAll} disabled={bulkBusy} aria-busy={bulkBusy}>
                    <CheckCheck size={16} aria-hidden="true" /> {bulkBusy ? t("loading") : t("validateAllGo")}
                  </button>
                </div>
              </div>
            )}
            {bulkResult &&
              (bulkResult.tone === "error" ? (
                <ErrorBox message={bulkResult.text} />
              ) : (
                <Notice tone={bulkResult.tone === "warn" ? "warn" : "success"}>{bulkResult.text}</Notice>
              ))}
            <div className="flex flex-wrap items-center gap-2">
              <div role="group" aria-label="Filtre" className="inline-flex rounded-xl border border-line p-0.5">
                {(["all", "review", "pending"] as const).map((f) => (
                  <button
                    key={f}
                    type="button"
                    aria-pressed={filter === f}
                    onClick={() => setFilter(f)}
                    className={`rounded-lg px-3 py-1.5 text-sm font-medium ${filter === f ? "bg-surface-3 text-ink" : "text-muted hover:text-ink"}`}
                  >
                    {t(f === "all" ? "filterAll" : f === "review" ? "filterReview" : "filterPending")}
                  </button>
                ))}
              </div>
              <button type="button" className="btn-secondary ml-auto" onClick={addManual}>
                <Plus size={16} aria-hidden="true" /> {t("addManual", { t: fmtTime(time, true) })}
              </button>
            </div>
            {addError && <ErrorBox message={addError} />}
            {project.demo_mode && <Notice tone="warn">{t("demoBannerText")}</Notice>}
          </section>

          {visible.length === 0 && <p className="text-muted">{t("noDescriptions")}</p>}
          <ol className="space-y-4" aria-label="Descriptions">
            {visible.map((d, i) => (
              <li key={d.id}>
                <DescriptionCard
                  ref={(el) => {
                    cardRefs.current[d.id] = el;
                  }}
                  d={d}
                  index={i}
                  active={d.id === activeId}
                  validator={validator}
                  slot={slotFor(d)}
                  onActivate={() => setActiveId(d.id)}
                  onChange={updateDesc}
                  onDelete={removeDesc}
                  onPlay={playSegment}
                  registerActions={(a) => {
                    if (a || activeDesc?.id === d.id) actionsRef.current = a;
                  }}
                />
              </li>
            ))}
          </ol>
        </div>
      </div>
    </>
  );
}
