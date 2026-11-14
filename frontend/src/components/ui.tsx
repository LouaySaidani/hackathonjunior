import { AlertTriangle, Bot, CheckCircle2, Loader2, PencilLine, XCircle, type LucideIcon } from "lucide-react";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { api, type Job, type Status } from "../lib/api";
import { useT, type Key } from "../lib/i18n";

const STATUS_STYLE: Record<Status, { icon: LucideIcon; cls: string }> = {
  ai_draft: { icon: Bot, cls: "border-[#4b3a73] bg-[#1d1630] text-ai" },
  edited: { icon: PencilLine, cls: "border-[#24496b] bg-[#0f2133] text-edited" },
  validated: { icon: CheckCircle2, cls: "border-[#1f5236] bg-[#0d2418] text-valid" },
  rejected: { icon: XCircle, cls: "border-[#5a2a2a] bg-[#2a1416] text-reject" },
};

/** Status is always conveyed by icon + text label, never by colour alone. */
export function StatusBadge({ status }: { status: Status }) {
  const { t } = useT();
  const { icon: Icon, cls } = STATUS_STYLE[status];
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[11px] font-bold tracking-wide ${cls}`}>
      <Icon size={14} aria-hidden="true" />
      {t(`st_${status}` as Key)}
    </span>
  );
}

export function FlagChip({ flag }: { flag: string }) {
  const { t } = useT();
  const key = `flag_${flag}` as Key;
  const danger = flag === "too_long" || flag === "low_confidence";
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-[11px] font-medium ${
        danger ? "bg-[#33260b] text-warn" : "bg-surface-3 text-muted"
      }`}
    >
      {danger && <AlertTriangle size={12} aria-hidden="true" />}
      {t(key)}
    </span>
  );
}

export function Spinner({ label }: { label?: string }) {
  return (
    <span className="inline-flex items-center gap-2 text-muted" role="status">
      <Loader2 className="animate-spin" size={16} aria-hidden="true" />
      {label && <span>{label}</span>}
    </span>
  );
}

export function ErrorBox({ message, onRetry }: { message: string; onRetry?: () => void }) {
  const { t } = useT();
  return (
    <div role="alert" className="flex items-start gap-3 rounded-xl border border-[#5a2a2a] bg-[#1f1012] p-3 text-sm text-reject">
      <AlertTriangle size={18} aria-hidden="true" className="mt-0.5 shrink-0" />
      <div className="flex-1">{message}</div>
      {onRetry && (
        <button className="btn-ghost !py-1" onClick={onRetry}>
          {t("retry")}
        </button>
      )}
    </div>
  );
}

export function Notice({ children, tone = "info" }: { children: ReactNode; tone?: "info" | "warn" | "success" }) {
  const cls = {
    info: "border-line bg-surface-2 text-muted",
    warn: "border-[#5b4413] bg-[#241a07] text-warn",
    success: "border-[#1f5236] bg-[#0d2418] text-valid",
  }[tone];
  return <div className={`rounded-xl border p-3 text-sm ${cls}`}>{children}</div>;
}

export function Stat({ label, value, icon: Icon }: { label: string; value: ReactNode; icon: LucideIcon }) {
  return (
    <div className="card flex items-center gap-4 p-4">
      <span className="grid h-11 w-11 place-items-center rounded-xl bg-surface-3 text-accent" aria-hidden="true">
        <Icon size={20} />
      </span>
      <div>
        <div className="text-2xl font-bold tabular-nums">{value}</div>
        <div className="text-sm text-muted">{label}</div>
      </div>
    </div>
  );
}

export function ProgressBar({ value, label }: { value: number; label: string }) {
  const pct = Math.round(value * 100);
  return (
    <div>
      <div
        role="progressbar"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={pct}
        className="h-2.5 w-full overflow-hidden rounded-full bg-surface-3"
      >
        <div className="h-full rounded-full bg-gradient-to-r from-accent to-teal transition-all" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

/** Polls a job until it ends. Status changes are announced via an aria-live region by the caller. */
export function useJob(jobId: string | null, onDone?: (job: Job) => void) {
  const [job, setJob] = useState<Job | null>(null);
  const doneRef = useRef(onDone);
  doneRef.current = onDone;
  useEffect(() => {
    if (!jobId) return;
    let stop = false;
    let timer: number;
    const tick = async () => {
      try {
        const j = await api.job(jobId);
        if (stop) return;
        setJob(j);
        if (j.status === "done" || j.status === "error") {
          doneRef.current?.(j);
          return;
        }
      } catch {
        /* transient: keep polling */
      }
      timer = window.setTimeout(tick, 900);
    };
    tick();
    return () => {
      stop = true;
      window.clearTimeout(timer);
    };
  }, [jobId]);
  return job;
}

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="font-display text-3xl font-semibold tracking-tight md:text-4xl">{title}</h1>
        {subtitle && <p className="mt-2 max-w-3xl text-muted">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  );
}
