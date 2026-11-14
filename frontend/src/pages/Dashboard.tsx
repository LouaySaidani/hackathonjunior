import { CheckCircle2, Clapperboard, Eye, FolderOpen, MessageSquareHeart, Plus, Sparkles, Trash2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ErrorBox, ProgressBar, Spinner, Stat } from "../components/ui";
import { api, fmtTime, type ProjectSummary } from "../lib/api";
import { useT, type Key } from "../lib/i18n";
import { useTitle } from "../lib/useTitle";

export default function Dashboard() {
  const { t, lang } = useT();
  useTitle(t("navDashboard"));
  const nav = useNavigate();
  const [projects, setProjects] = useState<ProjectSummary[] | null>(null);
  const [stats, setStats] = useState<Record<string, number> | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    setError("");
    Promise.all([api.projects(), api.stats()])
      .then(([p, s]) => {
        setProjects(p);
        setStats(s);
      })
      .catch((e) => setError(e.message));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  // keep processing statuses fresh
  useEffect(() => {
    if (!projects?.some((p) => p.active_job)) return;
    const id = window.setTimeout(load, 2000);
    return () => window.clearTimeout(id);
  }, [projects, load]);

  const sample = async () => {
    setBusy(true);
    try {
      const existing = projects?.find((p) => p.is_sample);
      const p = existing ?? (await api.createSample());
      nav(`/projects/${p.id}`);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const remove = async (p: ProjectSummary) => {
    if (!window.confirm(`${t("confirmDelete")}\n\n${p.title}`)) return;
    try {
      await api.deleteProject(p.id);
      load();
    } catch (e) {
      setError((e as Error).message);
    }
  };

  return (
    <>
      <section className="card relative mb-8 overflow-hidden p-8 md:p-10">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute -right-24 -top-24 h-72 w-72 rounded-full bg-[radial-gradient(circle,rgba(245,181,68,0.18),transparent_65%)]"
        />
        <p className="mb-3 inline-flex items-center gap-2 rounded-full border border-line bg-surface-2 px-3 py-1 text-xs font-semibold text-teal">
          <Sparkles size={14} aria-hidden="true" /> {t("ethicsNote")}
        </p>
        <h1 className="max-w-3xl font-display text-3xl font-semibold leading-tight tracking-tight md:text-5xl">{t("welcome")}</h1>
        <p className="mt-4 max-w-2xl text-lg text-muted">{t("welcomeSub")}</p>
        <div className="mt-6 flex flex-wrap gap-3">
          <Link to="/new" className="btn-primary !px-5 !py-2.5 text-base">
            <Plus size={18} aria-hidden="true" /> {t("createProject")}
          </Link>
          <button type="button" className="btn-secondary !px-5 !py-2.5 text-base" onClick={sample} disabled={busy}>
            <Clapperboard size={18} aria-hidden="true" /> {t("trySample")}
          </button>
        </div>
      </section>

      <section aria-labelledby="stats-h" className="mb-8">
        <h2 id="stats-h" className="sr-only">
          Statistiques
        </h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Stat icon={FolderOpen} label={t("statProjects")} value={stats?.projects ?? "–"} />
          <Stat icon={CheckCircle2} label={t("statValidated")} value={stats?.validated ?? "–"} />
          <Stat icon={Eye} label={t("statPending")} value={stats?.pending ?? "–"} />
          <Stat icon={MessageSquareHeart} label={t("statFeedback")} value={stats?.feedback ?? "–"} />
        </div>
      </section>

      <section aria-labelledby="recent-h">
        <h2 id="recent-h" className="mb-4 font-display text-2xl font-semibold">
          {t("recentProjects")}
        </h2>
        {error && <ErrorBox message={error} onRetry={load} />}
        {!projects && !error && <Spinner label={t("loading")} />}
        {projects?.length === 0 && <p className="text-muted">{t("noProjects")}</p>}
        <ul className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {projects?.map((p) => {
            const total = p.counts.ai_draft + p.counts.edited + p.counts.validated;
            return (
              <li key={p.id} className="card flex flex-col gap-4 p-5">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <h3 className="truncate text-lg font-semibold">
                      <Link to={`/projects/${p.id}${p.status === "ready" ? "/editor" : ""}`} className="hover:underline">
                        {p.title}
                      </Link>
                    </h3>
                    <p className="mt-1 text-sm text-muted">
                      {fmtTime(p.duration)} · {t(`lang_${p.language}` as Key)} ·{" "}
                      {new Date(p.created_at).toLocaleDateString(lang === "fr" ? "fr-FR" : "en-GB")}
                    </p>
                  </div>
                  <div className="flex shrink-0 flex-col items-end gap-1">
                    <span className="rounded-full border border-line bg-surface-2 px-2.5 py-0.5 text-xs font-semibold">
                      {t(`status_${p.status}` as Key)}
                    </span>
                    {p.is_sample && <span className="text-xs text-teal">{t("sample")}</span>}
                    {p.demo_mode && <span className="text-xs font-bold text-warn">DEMO MODE</span>}
                  </div>
                </div>
                {p.active_job ? (
                  <div aria-live="polite">
                    <p className="mb-1 text-sm text-muted">{p.active_job.message}</p>
                    <ProgressBar value={p.active_job.progress} label={t("jobStatus")} />
                  </div>
                ) : (
                  total > 0 && (
                    <div>
                      <p className="mb-1 text-sm text-muted">{t("validatedOf", { a: p.counts.validated, b: total })}</p>
                      <ProgressBar value={p.counts.validated / total} label={t("humanValidation")} />
                    </div>
                  )
                )}
                <div className="mt-auto flex flex-wrap gap-2">
                  <Link className="btn-secondary" to={`/projects/${p.id}`}>
                    {t("analysis")}
                  </Link>
                  <Link className="btn-secondary" to={`/projects/${p.id}/editor`}>
                    {t("editor")}
                  </Link>
                  <Link className="btn-secondary" to={`/projects/${p.id}/export`}>
                    {t("exportQa")}
                  </Link>
                  <button type="button" className="btn-ghost ml-auto" onClick={() => remove(p)} aria-label={`${t("delete")} — ${p.title}`}>
                    <Trash2 size={16} aria-hidden="true" /> {t("delete")}
                  </button>
                </div>
              </li>
            );
          })}
        </ul>
      </section>
    </>
  );
}
