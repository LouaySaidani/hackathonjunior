import { fmtTime, type Description, type Gap, type Interval } from "../lib/api";
import { useT, type Key } from "../lib/i18n";

interface Props {
  duration: number;
  speech: Interval[];
  gaps: (Interval & Partial<Pick<Gap, "score" | "recommended">>)[];
  descriptions?: Description[];
  current: number;
  activeId?: string | null;
  onSeek: (t: number) => void;
  onSelect?: (id: string) => void;
}

const DESC_COLOR: Record<string, string> = {
  ai_draft: "bg-ai",
  edited: "bg-edited",
  validated: "bg-valid",
  rejected: "bg-reject/40",
};
const STATE_ORDER = ["ai_draft", "edited", "validated", "rejected"] as const;

/** Visual timeline. All information is also available as text lists elsewhere on the page. */
export default function Timeline({ duration, speech, gaps, descriptions = [], current, activeId, onSeek, onSelect }: Props) {
  const { t } = useT();
  const pct = (x: number) => `${(Math.max(0, Math.min(duration, x)) / Math.max(duration, 0.001)) * 100}%`;
  const ticks = Array.from({ length: Math.floor(duration / 5) + 1 }, (_, i) => i * 5);

  return (
    <figure className="select-none">
      <figcaption className="mb-2 flex flex-wrap items-center gap-4 text-xs text-muted">
        <span className="font-semibold text-ink">{t("timeline")}</span>
        <span className="inline-flex items-center gap-1.5">
          <span className="h-2.5 w-4 rounded-sm bg-speech" aria-hidden="true" /> {t("speechLegend")}
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="h-2.5 w-4 rounded-sm border border-teal/60 bg-gap" aria-hidden="true" /> {t("gapLegend")}
        </span>
        {gaps.some((g) => g.recommended === false) && (
          <span className="inline-flex items-center gap-1.5">
            <span className="h-2.5 w-4 rounded-sm border border-dashed border-subtle bg-gap/25" aria-hidden="true" />{" "}
            {t("gapSkippedLegend")}
          </span>
        )}
        {descriptions.length > 0 && (
          // audio description lines are coloured by state: list exactly the states shown on this timeline
          <span className="inline-flex flex-wrap items-center gap-3">
            <span>{t("adLegend")} :</span>
            {STATE_ORDER.filter((st) => descriptions.some((d) => d.status === st)).map((st) => (
              <span key={st} className="inline-flex items-center gap-1.5">
                <span className={`h-2.5 w-4 rounded-sm ${DESC_COLOR[st]}`} aria-hidden="true" /> {t(`legend_${st}` as Key)}
              </span>
            ))}
          </span>
        )}
      </figcaption>
      <div
        className="relative h-20 cursor-pointer overflow-hidden rounded-xl border border-line bg-surface-2"
        onClick={(e) => {
          const r = e.currentTarget.getBoundingClientRect();
          onSeek(((e.clientX - r.left) / r.width) * duration);
        }}
        aria-hidden="true"
      >
        {ticks.map((x) => (
          <div key={x} className="absolute top-0 h-full border-l border-line/60" style={{ left: pct(x) }}>
            <span className="absolute left-1 top-0.5 text-[10px] text-subtle">{fmtTime(x)}</span>
          </div>
        ))}
        {gaps.map((g) => (
          <div
            key={`g${g.id}`}
            className={`absolute top-5 h-5 rounded-sm border ${
              g.recommended === false ? "border-dashed border-subtle bg-gap/25" : "border-teal/50 bg-gap"
            }`}
            style={{ left: pct(g.start), width: `calc(${pct(g.end)} - ${pct(g.start)})` }}
          />
        ))}
        {speech.map((s, i) => (
          <div
            key={`s${i}`}
            className="absolute top-5 h-5 rounded-sm bg-speech"
            style={{ left: pct(s.start), width: `calc(${pct(s.end)} - ${pct(s.start)})` }}
          />
        ))}
        {descriptions.map((d) => (
          <div
            key={d.id}
            onClick={(e) => {
              e.stopPropagation();
              onSelect?.(d.id);
              onSeek(d.start);
            }}
            className={`absolute top-12 h-5 rounded-sm ${DESC_COLOR[d.status]} ${
              d.id === activeId ? "ring-2 ring-ink ring-offset-1 ring-offset-surface-2" : ""
            }`}
            style={{ left: pct(d.start), width: `calc(${pct(d.end)} - ${pct(d.start)})` }}
          />
        ))}
        <div className="absolute top-0 h-full w-0.5 bg-accent" style={{ left: pct(current) }} />
      </div>
      <label className="mt-2 block">
        <span className="sr-only">Position de lecture</span>
        <input
          type="range"
          min={0}
          max={duration || 0}
          step={0.1}
          value={current}
          onChange={(e) => onSeek(Number(e.target.value))}
          className="w-full accent-[#f4f4f4]"
          aria-valuetext={fmtTime(current)}
        />
      </label>
    </figure>
  );
}
