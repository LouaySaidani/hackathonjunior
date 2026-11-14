import { Film, Plus, Trash2, Upload } from "lucide-react";
import { useEffect, useId, useRef, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useSystem } from "../components/Layout";
import { ErrorBox, PageHeader, ProgressBar } from "../components/ui";
import { api, fmtBytes, fmtTime, uploadProject, type CastMember, type Lang } from "../lib/api";
import { useT, type Key } from "../lib/i18n";
import { useTitle } from "../lib/useTitle";

const EXT = [".mp4", ".mov", ".mkv", ".m4v"];

export default function NewProject() {
  const { t } = useT();
  useTitle(t("newTitle"));
  const system = useSystem();
  const nav = useNavigate();
  const maxMb = system?.max_upload_mb ?? 500;
  const ids = { file: useId(), title: useId(), lang: useId(), dlang: useId(), consent: useId(), optin: useId() };

  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState("");
  const [meta, setMeta] = useState<{ duration: number; w: number; h: number } | null>(null);
  const [title, setTitle] = useState("");
  const [language, setLanguage] = useState<Lang>("fr");
  const [dialogueLang, setDialogueLang] = useState("auto");
  const [cast, setCast] = useState<CastMember[]>([]);
  const [consent, setConsent] = useState(false);
  const [optIn, setOptIn] = useState(false);
  const [error, setError] = useState("");
  const [progress, setProgress] = useState<number | null>(null);
  const [drag, setDrag] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => () => void (preview && URL.revokeObjectURL(preview)), [preview]);

  const pick = (f: File | undefined | null) => {
    setError("");
    if (!f) return;
    const ext = f.name.slice(f.name.lastIndexOf(".")).toLowerCase();
    if (!EXT.includes(ext)) return setError(t("badType"));
    if (f.size > maxMb * 1024 * 1024) return setError(t("tooBig"));
    setFile(f);
    setMeta(null);
    setPreview(URL.createObjectURL(f));
    if (!title) setTitle(f.name.replace(/\.[^.]+$/, ""));
  };

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    if (!file) return setError(t("chooseFile"));
    if (!consent) return setError(t("consentRequired"));
    const fd = new FormData();
    fd.append("file", file);
    fd.append("title", title || file.name);
    fd.append("language", language);
    fd.append("dialogue_language", dialogueLang);
    fd.append("cast", JSON.stringify(cast.filter((c) => c.name.trim())));
    fd.append("consent", "true");
    fd.append("training_opt_in", String(optIn));
    try {
      setProgress(0);
      const p = await uploadProject(fd, setProgress);
      await api.analyze(p.id);
      nav(`/projects/${p.id}`);
    } catch (err) {
      setProgress(null);
      setError((err as Error).message);
    }
  };

  return (
    <>
      <PageHeader title={t("newTitle")} subtitle={t("newSub")} />
      <form onSubmit={submit} className="grid grid-cols-1 gap-6 lg:grid-cols-[1.1fr_1fr]" noValidate>
        <section className="card p-6" aria-labelledby="file-h">
          <h2 id="file-h" className="mb-4 text-lg font-semibold">
            {t("fileLabel")}
          </h2>
          <div
            onDragOver={(e) => {
              e.preventDefault();
              setDrag(true);
            }}
            onDragLeave={() => setDrag(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDrag(false);
              pick(e.dataTransfer.files?.[0]);
            }}
            className={`flex flex-col items-center justify-center gap-3 rounded-2xl border-2 border-dashed p-8 text-center transition-colors ${
              drag ? "border-accent bg-surface-3" : "border-line bg-surface-2"
            }`}
          >
            <Upload size={28} className="text-accent" aria-hidden="true" />
            <p className="text-sm text-muted" id={`${ids.file}-hint`}>
              {t("fileHint", { mb: maxMb })}
            </p>
            <label htmlFor={ids.file} className="btn-primary cursor-pointer">
              <Film size={16} aria-hidden="true" /> {t("chooseFile")}
            </label>
            <input
              ref={inputRef}
              id={ids.file}
              type="file"
              accept=".mp4,.mov,.mkv,.m4v,video/mp4,video/quicktime,video/x-matroska"
              className="sr-only"
              aria-describedby={`${ids.file}-hint`}
              onChange={(e) => pick(e.target.files?.[0])}
            />
          </div>
          {file && (
            <div className="mt-5 space-y-4">
              <video
                src={preview}
                controls
                className="aspect-video w-full rounded-xl bg-black"
                onLoadedMetadata={(e) =>
                  setMeta({ duration: e.currentTarget.duration, w: e.currentTarget.videoWidth, h: e.currentTarget.videoHeight })
                }
                aria-label={file.name}
              />
              <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4" aria-label={t("metadata")}>
                {[
                  [t("duration"), meta ? fmtTime(meta.duration) : "…"],
                  [t("resolution"), meta ? `${meta.w}×${meta.h}` : "…"],
                  [t("size"), fmtBytes(file.size)],
                  [t("type"), file.type || file.name.split(".").pop()],
                ].map(([k, v]) => (
                  <div key={k} className="rounded-xl bg-surface-2 p-3">
                    <dt className="text-xs text-muted">{k}</dt>
                    <dd className="font-semibold">{v}</dd>
                  </div>
                ))}
              </dl>
            </div>
          )}
        </section>

        <section className="card space-y-5 p-6" aria-label="Paramètres">
          <div>
            <label className="label" htmlFor={ids.title}>
              {t("titleLabel")}
            </label>
            <input id={ids.title} className="input" value={title} onChange={(e) => setTitle(e.target.value)} maxLength={200} />
          </div>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <label className="label" htmlFor={ids.lang}>
                {t("adLanguage")}
              </label>
              <select id={ids.lang} className="input" value={language} onChange={(e) => setLanguage(e.target.value as Lang)}>
                {(["fr", "ar", "aeb", "en"] as const).map((l) => (
                  <option key={l} value={l}>
                    {t(`lang_${l}` as Key)}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="label" htmlFor={ids.dlang}>
                {t("dialogueLanguage")}
              </label>
              <select id={ids.dlang} className="input" value={dialogueLang} onChange={(e) => setDialogueLang(e.target.value)}>
                <option value="auto">{t("auto")}</option>
                <option value="ar">{t("lang_ar")}</option>
                <option value="fr">{t("lang_fr")}</option>
                <option value="en">{t("lang_en")}</option>
              </select>
            </div>
          </div>

          <fieldset className="rounded-xl border border-line p-4">
            <legend className="px-1 font-semibold">{t("castTitle")}</legend>
            <p className="hint mb-3">{t("castHint")}</p>
            <ul className="space-y-3">
              {cast.map((c, i) => (
                <li key={i} className="grid grid-cols-[1fr_1.4fr_auto] items-end gap-2">
                  <label className="text-xs text-muted">
                    {t("castName")}
                    <input
                      className="input mt-1"
                      dir="auto"
                      value={c.name}
                      onChange={(e) => setCast(cast.map((x, j) => (j === i ? { ...x, name: e.target.value } : x)))}
                    />
                  </label>
                  <label className="text-xs text-muted">
                    {t("castDesc")}
                    <input
                      className="input mt-1"
                      dir="auto"
                      value={c.description}
                      placeholder="ex. femme âgée, sefsari blanc"
                      onChange={(e) => setCast(cast.map((x, j) => (j === i ? { ...x, description: e.target.value } : x)))}
                    />
                  </label>
                  <button
                    type="button"
                    className="btn-ghost"
                    onClick={() => setCast(cast.filter((_, j) => j !== i))}
                    aria-label={t("removeCast", { name: c.name || `#${i + 1}` })}
                  >
                    <Trash2 size={16} aria-hidden="true" />
                  </button>
                </li>
              ))}
            </ul>
            <button type="button" className="btn-secondary mt-3" onClick={() => setCast([...cast, { name: "", description: "" }])}>
              <Plus size={16} aria-hidden="true" /> {t("addCast")}
            </button>
          </fieldset>

          <div className="space-y-3 rounded-xl border border-line bg-surface-2 p-4">
            <div className="flex items-start gap-3">
              <input
                id={ids.consent}
                type="checkbox"
                required
                aria-required="true"
                checked={consent}
                onChange={(e) => setConsent(e.target.checked)}
                className="mt-1 h-5 w-5 accent-[#f4f4f4]"
              />
              <label htmlFor={ids.consent} className="text-sm font-medium">
                {t("consent")} <span aria-hidden="true" className="text-accent">*</span>
              </label>
            </div>
            <div className="flex items-start gap-3">
              <input
                id={ids.optin}
                type="checkbox"
                checked={optIn}
                onChange={(e) => setOptIn(e.target.checked)}
                className="mt-1 h-5 w-5 accent-[#f4f4f4]"
              />
              <label htmlFor={ids.optin} className="text-sm text-muted">
                {t("optIn")}
              </label>
            </div>
          </div>

          {error && <ErrorBox message={error} />}
          {progress !== null && (
            <div aria-live="polite">
              <p className="mb-1 text-sm text-muted">{t("uploading", { p: Math.round(progress * 100) })}</p>
              <ProgressBar value={progress} label={t("uploading", { p: Math.round(progress * 100) })} />
            </div>
          )}
          <button type="submit" className="btn-primary w-full !py-3 text-base" disabled={progress !== null}>
            <Upload size={18} aria-hidden="true" /> {t("startAnalysis")}
          </button>
        </section>
      </form>
    </>
  );
}
