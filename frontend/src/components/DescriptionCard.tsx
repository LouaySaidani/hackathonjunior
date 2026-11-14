import {
  Check,
  CircleStop,
  Mic,
  Play,
  RotateCcw,
  Save,
  Sparkles,
  Trash2,
  Upload,
  Volume2,
  Wand2,
  X,
} from "lucide-react";
import { forwardRef, useEffect, useId, useRef, useState } from "react";
import { api, fmtTime, isRtl, type Description, type Lang } from "../lib/api";
import { useT, type Key } from "../lib/i18n";
import { ErrorBox, FlagChip, Notice, StatusBadge } from "./ui";

interface Props {
  d: Description;
  index: number;
  active: boolean;
  validator: string;
  slot: number; // seconds available until next dialogue
  onActivate: () => void;
  onChange: (d: Description) => void;
  onDelete: (id: string) => void;
  onPlay: (start: number, end: number) => void;
  registerActions?: (a: CardActions | null) => void;
}

export interface CardActions {
  validate: () => void;
  reject: () => void;
  save: () => void;
  play: () => void;
}

const DescriptionCard = forwardRef<HTMLElement, Props>(function DescriptionCard(
  { d, index, active, validator, slot, onActivate, onChange, onDelete, onPlay, registerActions },
  ref,
) {
  const { t, lang: uiLang } = useT();
  const uid = useId();
  const [text, setText] = useState(d.text);
  const [start, setStart] = useState(d.start.toFixed(2));
  const [end, setEnd] = useState(d.end.toFixed(2));
  const [hint, setHint] = useState("");
  const [showRegen, setShowRegen] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");
  const [recording, setRecording] = useState(false);
  const recRef = useRef<MediaRecorder | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    setText(d.text);
    setStart(d.start.toFixed(2));
    setEnd(d.end.toFixed(2));
  }, [d.text, d.start, d.end]);

  const dirty = text.trim() !== d.text || Number(start) !== Number(d.start.toFixed(2)) || Number(end) !== Number(d.end.toFixed(2));
  const rtl = isRtl(d.language);
  const words = (text.match(/[\p{L}\p{N}]+/gu) || []).length;
  const wps = { fr: 2.6, en: 2.7, ar: 2.0, aeb: 2.1 }[d.language] ?? 2.5;
  const est = words / wps + 0.3;
  const dur = Number(end) - Number(start);
  const tooLong = est > dur + 0.05;

  const run = async (name: string, fn: () => Promise<Description | void>, ok?: string) => {
    setBusy(name);
    setError("");
    setInfo("");
    try {
      const res = await fn();
      if (res) {
        onChange(res);
        if (res.warnings?.length) setInfo(res.warnings.join(" "));
        else if (ok) setInfo(ok);
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  };

  const save = () =>
    run(
      "save",
      () => api.patchDescription(d.id, { text: text.trim(), start: Number(start), end: Number(end), editor: validator }),
      t("saved"),
    );

  const validate = async () => {
    if (!validator.trim()) {
      setError(t("needValidator"));
      return;
    }
    if (dirty) {
      try {
        const saved = await api.patchDescription(d.id, { text: text.trim(), start: Number(start), end: Number(end), editor: validator });
        onChange(saved);
      } catch (e) {
        setError((e as Error).message);
        return;
      }
    }
    run("validate", () => api.validate(d.id, validator));
  };
  const reject = () => run("reject", () => api.reject(d.id, validator));
  const reopen = () => run("reopen", () => api.reopen(d.id, validator));
  const regen = () =>
    run("regen", async () => {
      const r = await api.regenerate(d.id, hint);
      setShowRegen(false);
      setHint("");
      return r;
    });
  const play = () => onPlay(Number(start), Number(end));

  useEffect(() => {
    if (!active || !registerActions) return;
    registerActions({ validate, reject, save, play });
    return () => registerActions(null);
  });

  const startRecording = async () => {
    setError("");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const rec = new MediaRecorder(stream);
      const chunks: Blob[] = [];
      rec.ondataavailable = (e) => chunks.push(e.data);
      rec.onstop = () => {
        stream.getTracks().forEach((tr) => tr.stop());
        const blob = new Blob(chunks, { type: rec.mimeType || "audio/webm" });
        run("voice", () => api.uploadVoice(d.id, blob, "recording.webm"));
      };
      rec.start();
      recRef.current = rec;
      setRecording(true);
    } catch (e) {
      setError(`Micro indisponible : ${(e as Error).message}`);
    }
  };
  const stopRecording = () => {
    recRef.current?.stop();
    setRecording(false);
  };

  const date = d.validated_at ? new Date(d.validated_at).toLocaleString(uiLang === "fr" ? "fr-FR" : "en-GB") : "";
  const headingId = `${uid}-h`;
  const border = {
    ai_draft: "border-l-ai",
    edited: "border-l-edited",
    validated: "border-l-valid",
    rejected: "border-l-reject",
  }[d.status];

  return (
    <article
      ref={ref}
      aria-labelledby={headingId}
      tabIndex={-1}
      onFocus={onActivate}
      onClick={onActivate}
      className={`card border-l-4 ${border} p-4 transition ${active ? "ring-2 ring-accent/70" : ""} ${
        d.status === "rejected" ? "opacity-75" : ""
      }`}
    >
      <header className="mb-3 flex flex-wrap items-center gap-2">
        <h3 id={headingId} className="mr-1 font-mono text-sm font-semibold tabular-nums">
          #{index + 1} · {fmtTime(d.start, true)} → {fmtTime(d.end, true)}
        </h3>
        <StatusBadge status={d.status} />
        <span className="text-xs text-muted">{t(d.origin === "ai" ? "origin_ai" : "origin_human")}</span>
        {d.origin === "ai" && (
          <span className="text-xs text-muted">
            · {t("confidence")} {Math.round(d.confidence * 100)} %
          </span>
        )}
        {d.needs_review && (
          <span className="ml-auto rounded-md bg-warn px-2 py-0.5 text-[11px] font-extrabold uppercase text-[#241a07]">
            {t("needsReview")}
          </span>
        )}
      </header>

      {d.flags.length > 0 && (
        <ul className="mb-3 flex flex-wrap gap-1.5" aria-label="Signalements">
          {d.flags.map((f) => (
            <li key={f}>
              <FlagChip flag={f} />
            </li>
          ))}
        </ul>
      )}

      <label htmlFor={`${uid}-text`} className="sr-only">
        {t("text")}
      </label>
      <textarea
        id={`${uid}-text`}
        value={text}
        dir={rtl ? "rtl" : "ltr"}
        lang={d.language}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
            e.preventDefault();
            save();
          }
        }}
        rows={3}
        className={`input resize-y text-base leading-relaxed ${rtl ? "text-right" : ""}`}
      />
      <p className={`mt-1 text-xs ${tooLong ? "font-semibold text-warn" : "text-muted"}`} aria-live="polite">
        {t("estimate", { est: est.toFixed(1), slot: dur.toFixed(1) })}
        {tooLong && ` — ${t("flag_too_long")}`} · max {slot.toFixed(1)} s
      </p>

      <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-3">
        <label className="text-xs text-muted">
          {t("start")}
          <input type="number" step="0.05" min={0} className="input mt-1 font-mono" value={start} onChange={(e) => setStart(e.target.value)} />
        </label>
        <label className="text-xs text-muted">
          {t("end")}
          <input type="number" step="0.05" min={0} className="input mt-1 font-mono" value={end} onChange={(e) => setEnd(e.target.value)} />
        </label>
        <label className="col-span-2 text-xs text-muted sm:col-span-1">
          {t("language")}
          <select
            className="input mt-1"
            value={d.language}
            onChange={(e) => run("lang", () => api.patchDescription(d.id, { language: e.target.value as Lang, editor: validator }))}
          >
            {(["fr", "ar", "aeb", "en"] as const).map((l) => (
              <option key={l} value={l}>
                {t(`lang_${l}` as Key)}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        <button type="button" className="btn-secondary" onClick={play}>
          <Play size={15} aria-hidden="true" /> {t("playSegment")}
        </button>
        <button type="button" className="btn-secondary" onClick={save} disabled={!dirty || !!busy}>
          <Save size={15} aria-hidden="true" /> {t("save")}
        </button>
        {d.status !== "rejected" ? (
          <>
            <button type="button" className="btn-success" onClick={validate} disabled={!!busy || d.status === "validated"}>
              <Check size={15} aria-hidden="true" /> {t("validate")}
            </button>
            <button type="button" className="btn-danger" onClick={reject} disabled={!!busy}>
              <X size={15} aria-hidden="true" /> {t("reject")}
            </button>
          </>
        ) : (
          <button type="button" className="btn-secondary" onClick={reopen} disabled={!!busy}>
            <RotateCcw size={15} aria-hidden="true" /> {t("reopen")}
          </button>
        )}
        <button
          type="button"
          className="btn-secondary"
          onClick={() => setShowRegen((v) => !v)}
          aria-expanded={showRegen}
          aria-controls={`${uid}-regen`}
        >
          <Wand2 size={15} aria-hidden="true" /> {t("regenerate")}
        </button>
        <button
          type="button"
          className="btn-ghost ml-auto"
          onClick={() => window.confirm(t("confirmDeleteLine")) && api.deleteDescription(d.id).then(() => onDelete(d.id), (e) => setError(e.message))}
          aria-label={`${t("deleteLine")} #${index + 1}`}
        >
          <Trash2 size={15} aria-hidden="true" />
        </button>
      </div>

      {showRegen && (
        <div id={`${uid}-regen`} className="mt-3 flex flex-wrap items-end gap-2 rounded-xl bg-surface-2 p-3">
          <label className="min-w-[220px] flex-1 text-xs text-muted">
            {t("regenHint")}
            <input className="input mt-1" dir="auto" value={hint} onChange={(e) => setHint(e.target.value)} placeholder="ex. insister sur le geste de la main" />
          </label>
          <button type="button" className="btn-primary" onClick={regen} disabled={!!busy}>
            <Sparkles size={15} aria-hidden="true" /> {busy === "regen" ? t("loading") : t("regenerate")}
          </button>
        </div>
      )}

      <section className="mt-3 rounded-xl border border-line p-3" aria-label={`${t("voice")} #${index + 1}`}>
        <div className="flex flex-wrap items-center gap-2">
          <span className="mr-1 inline-flex items-center gap-1.5 text-sm font-semibold">
            <Volume2 size={15} aria-hidden="true" /> {t("voice")}
          </span>
          <button
            type="button"
            className="btn-secondary !py-1.5"
            disabled={d.status !== "validated" || !!busy}
            onClick={() => run("tts", () => api.tts(d.id))}
            title={d.status !== "validated" ? t("voiceOnlyValidated") : undefined}
          >
            {busy === "tts" ? t("loading") : t("genVoice")}
          </button>
          {!recording ? (
            <button type="button" className="btn-secondary !py-1.5" onClick={startRecording} disabled={!!busy}>
              <Mic size={15} aria-hidden="true" /> {t("record")}
            </button>
          ) : (
            <button type="button" className="btn-danger !py-1.5" onClick={stopRecording}>
              <CircleStop size={15} aria-hidden="true" /> {t("stopRecord")}
            </button>
          )}
          <button type="button" className="btn-secondary !py-1.5" onClick={() => fileRef.current?.click()} disabled={!!busy}>
            <Upload size={15} aria-hidden="true" /> {t("uploadAudio")}
          </button>
          <input
            ref={fileRef}
            type="file"
            accept="audio/*"
            className="sr-only"
            tabIndex={-1}
            aria-label={t("uploadAudio")}
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) run("voice", () => api.uploadVoice(d.id, f, f.name));
              e.target.value = "";
            }}
          />
          {d.audio_url && (
            <button type="button" className="btn-ghost !py-1.5" onClick={() => run("rmvoice", () => api.deleteVoice(d.id))}>
              {t("removeAudio")}
            </button>
          )}
        </div>
        {d.status !== "validated" && !d.audio_url && <p className="hint mt-2">{t("voiceOnlyValidated")}</p>}
        {d.audio_url && (
          <div className="mt-2 flex flex-wrap items-center gap-3">
            <audio controls src={`${d.audio_url}?v=${encodeURIComponent(d.audio_voice + d.audio_duration)}`} className="h-9 max-w-full" />
            <span className="text-xs text-muted">
              {t(`audioSource_${d.audio_source}` as Key)} · {d.audio_voice} · {d.audio_duration.toFixed(1)} s
            </span>
          </div>
        )}
      </section>

      {d.status === "validated" && (
        <p className="mt-3 text-sm text-valid">{t("validatedBy", { name: d.validated_by, date })}</p>
      )}
      <div aria-live="polite">
        {info && (
          <div className="mt-3">
            <Notice tone="warn">{info}</Notice>
          </div>
        )}
        {error && (
          <div className="mt-3">
            <ErrorBox message={error} />
          </div>
        )}
      </div>

      {d.history.length > 0 && (
        <details className="mt-3 text-xs text-muted">
          <summary className="cursor-pointer select-none rounded">{t("history")} ({d.history.length})</summary>
          <ol className="mt-2 space-y-1">
            {d.history.map((h, i) => (
              <li key={i}>
                <span className="font-mono">{new Date(h.at).toLocaleString(uiLang === "fr" ? "fr-FR" : "en-GB")}</span> — {h.action}
                {h.by && ` · ${h.by}`}
                {h.detail && ` · ${h.detail}`}
              </li>
            ))}
          </ol>
          {d.origin === "ai" && d.ai_original_text && d.ai_original_text !== d.text && (
            <p className="mt-2" dir="auto">
              IA (original) : « {d.ai_original_text} »
            </p>
          )}
        </details>
      )}
    </article>
  );
});

export default DescriptionCard;
