import { Send } from "lucide-react";
import { useCallback, useEffect, useId, useState, type FormEvent } from "react";
import { useSearchParams } from "react-router-dom";
import { ErrorBox, Notice, PageHeader } from "../components/ui";
import { api, type ProjectSummary } from "../lib/api";
import { useT, type Key } from "../lib/i18n";
import { useTitle } from "../lib/useTitle";

const PREFS = ["msa", "darija", "fr", "no_preference"] as const;
type Summary = Awaited<ReturnType<typeof api.feedbackSummary>>;

export default function FeedbackPage() {
  const { t } = useT();
  useTitle(t("navFeedback"));
  const [params] = useSearchParams();
  const ids = { project: useId(), alias: useId(), comment: useId(), consent: useId(), paid: useId() };
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [projectId, setProjectId] = useState(params.get("project") ?? "");
  const [alias, setAlias] = useState("");
  const [score, setScore] = useState<number | null>(null);
  const [pref, setPref] = useState<string>("");
  const [comment, setComment] = useState("");
  const [consent, setConsent] = useState(false);
  const [paid, setPaid] = useState(false);
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [list, setList] = useState<Awaited<ReturnType<typeof api.feedbackList>>>([]);

  const load = useCallback(() => {
    api.feedbackSummary(projectId || undefined).then(setSummary);
    api.feedbackList(projectId || undefined).then(setList);
  }, [projectId]);
  useEffect(() => {
    api.projects().then(setProjects);
  }, []);
  useEffect(load, [load]);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setDone(false);
    if (!score || !pref) return setError(`${t("fbComprehension")} · ${t("fbPref")}`);
    if (!consent) return setError(t("consentRequired"));
    try {
      await api.postFeedback({
        project_id: projectId,
        tester_alias: alias,
        comprehension: score,
        preferred_language: pref,
        comment,
        consent,
        paid_tester: paid,
      });
      setDone(true);
      setScore(null);
      setPref("");
      setComment("");
      setConsent(false);
      load();
    } catch (err) {
      setError((err as Error).message);
    }
  };

  const maxPref = Math.max(1, ...Object.values(summary?.language_preference ?? { a: 1 }));

  return (
    <>
      <PageHeader title={t("fbTitle")} subtitle={t("fbSub")} />
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1.2fr_1fr]">
        <form onSubmit={submit} className="card space-y-5 p-6" noValidate aria-label={t("fbTitle")}>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <label className="label" htmlFor={ids.project}>
                {t("fbProject")}
              </label>
              <select id={ids.project} className="input" value={projectId} onChange={(e) => setProjectId(e.target.value)}>
                <option value="">{t("fbNone")}</option>
                {projects.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.title}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="label" htmlFor={ids.alias}>
                {t("fbAlias")}
              </label>
              <input id={ids.alias} className="input" dir="auto" value={alias} onChange={(e) => setAlias(e.target.value)} maxLength={80} />
            </div>
          </div>

          <fieldset>
            <legend className="label">{t("fbComprehension")}</legend>
            <div className="flex flex-wrap gap-2">
              {[1, 2, 3, 4, 5].map((n) => (
                <label
                  key={n}
                  className={`grid h-12 w-12 cursor-pointer place-items-center rounded-xl border text-lg font-bold has-[:focus-visible]:outline has-[:focus-visible]:outline-3 has-[:focus-visible]:outline-accent ${
                    score === n ? "border-accent bg-accent text-accent-ink" : "border-line bg-surface-2"
                  }`}
                >
                  <input type="radio" name="score" value={n} checked={score === n} onChange={() => setScore(n)} className="sr-only" />
                  {n}
                </label>
              ))}
            </div>
          </fieldset>

          <fieldset>
            <legend className="label">{t("fbPref")}</legend>
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
              {PREFS.map((p) => (
                <label
                  key={p}
                  className={`flex cursor-pointer items-center gap-3 rounded-xl border px-3 py-2.5 text-sm has-[:focus-visible]:outline has-[:focus-visible]:outline-3 has-[:focus-visible]:outline-accent ${
                    pref === p ? "border-accent bg-surface-3" : "border-line bg-surface-2"
                  }`}
                >
                  <input type="radio" name="pref" value={p} checked={pref === p} onChange={() => setPref(p)} className="h-4 w-4 accent-[#f4f4f4]" />
                  {t(`pref_${p}` as Key)}
                </label>
              ))}
            </div>
          </fieldset>

          <div>
            <label className="label" htmlFor={ids.comment}>
              {t("fbComment")}
            </label>
            <textarea id={ids.comment} className="input" rows={4} dir="auto" value={comment} onChange={(e) => setComment(e.target.value)} maxLength={3000} />
          </div>

          <div className="space-y-3 rounded-xl border border-line bg-surface-2 p-4">
            <div className="flex items-start gap-3">
              <input id={ids.paid} type="checkbox" checked={paid} onChange={(e) => setPaid(e.target.checked)} className="mt-1 h-5 w-5 accent-[#f4f4f4]" />
              <label htmlFor={ids.paid} className="text-sm">
                {t("fbPaid")}
              </label>
            </div>
            <div className="flex items-start gap-3">
              <input
                id={ids.consent}
                type="checkbox"
                aria-required="true"
                checked={consent}
                onChange={(e) => setConsent(e.target.checked)}
                className="mt-1 h-5 w-5 accent-[#f4f4f4]"
              />
              <label htmlFor={ids.consent} className="text-sm font-medium">
                {t("fbConsent")} <span aria-hidden="true" className="text-accent">*</span>
              </label>
            </div>
          </div>

          <div aria-live="polite">
            {error && <ErrorBox message={error} />}
            {done && <Notice tone="success">{t("fbThanks")}</Notice>}
          </div>
          <button type="submit" className="btn-primary w-full !py-3 text-base">
            <Send size={18} aria-hidden="true" /> {t("fbSubmit")}
          </button>
        </form>

        <section className="card space-y-5 p-6" aria-labelledby="sum-h">
          <h2 id="sum-h" className="text-lg font-semibold">
            {t("fbSummary")} <span className="text-sm font-normal text-muted">· {t("fbCount", { n: summary?.count ?? 0 })}</span>
          </h2>
          <div>
            <p className="text-sm text-muted">{t("fbMean")}</p>
            <p className="text-4xl font-bold tabular-nums">
              {summary?.mean_comprehension ?? "–"}
              <span className="text-lg text-muted"> / 5</span>
            </p>
          </div>
          <div>
            <p className="mb-2 text-sm text-muted">{t("fbPrefs")}</p>
            <ul className="space-y-2">
              {PREFS.map((p) => {
                const n = summary?.language_preference[p] ?? 0;
                return (
                  <li key={p}>
                    <div className="mb-1 flex justify-between text-sm">
                      <span>{t(`pref_${p}` as Key)}</span>
                      <span className="tabular-nums">{n}</span>
                    </div>
                    <div className="h-2 rounded-full bg-surface-3" aria-hidden="true">
                      <div className="h-2 rounded-full bg-teal" style={{ width: `${(n / maxPref) * 100}%` }} />
                    </div>
                  </li>
                );
              })}
            </ul>
          </div>
          {list.length > 0 && (
            <ul className="max-h-72 space-y-2 overflow-y-auto text-sm">
              {list.map((f) => (
                <li key={f.id} className="rounded-xl bg-surface-2 p-3">
                  <p className="font-semibold">
                    {f.comprehension}/5 · {t(`pref_${f.preferred_language}` as Key)} {f.tester_alias && `· ${f.tester_alias}`}
                  </p>
                  {f.comment && (
                    <p className="mt-1 text-muted" dir="auto">
                      {f.comment}
                    </p>
                  )}
                </li>
              ))}
            </ul>
          )}
          {summary?.count === 0 && <p className="text-sm text-muted">{t("fbCount", { n: 0 })}</p>}
        </section>
      </div>
    </>
  );
}
