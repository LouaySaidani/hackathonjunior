/* Line-art decorations in the spirit of the Wasf presentation: film reel, vintage camera, film strip.
   Drawn for Wasf (no third-party artwork), monochrome, and always hidden from assistive technologies. */

const HOLES = [0, 72, 144, 216, 288].map((deg) => {
  const a = ((deg - 90) * Math.PI) / 180;
  return [60 + 31 * Math.cos(a), 60 + 31 * Math.sin(a)] as const;
});

export function FilmReel({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 120 120" className={className} aria-hidden="true" focusable="false">
      <g fill="none" stroke="currentColor" strokeWidth="3">
        <circle cx="60" cy="60" r="56" />
        <circle cx="60" cy="60" r="49" strokeWidth="1.5" />
        <circle cx="60" cy="60" r="9" />
        <circle cx="60" cy="60" r="3" fill="currentColor" />
        {HOLES.map(([x, y]) => (
          <circle key={`${x}`} cx={x} cy={y} r="13" />
        ))}
        {HOLES.map(([x, y]) => (
          <line key={`s${x}`} x1="60" y1="60" x2={60 + (x - 60) * 0.55} y2={60 + (y - 60) * 0.55} strokeWidth="1.5" />
        ))}
      </g>
    </svg>
  );
}

export function VintageCamera({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 170 150" className={className} aria-hidden="true" focusable="false">
      <g fill="none" stroke="currentColor" strokeWidth="3" strokeLinejoin="round" strokeLinecap="round">
        {/* two magazine reels on top */}
        <circle cx="55" cy="38" r="26" />
        <circle cx="55" cy="38" r="6" />
        <circle cx="108" cy="42" r="21" />
        <circle cx="108" cy="42" r="5" />
        <path d="M55 64v6M108 63v7" />
        {/* body */}
        <rect x="30" y="70" width="96" height="46" rx="7" />
        <path d="M44 84h28M44 94h18" strokeWidth="2" />
        <circle cx="104" cy="93" r="7" strokeWidth="2" />
        {/* lens */}
        <path d="M126 80l26-9v44l-26-9z" />
        <ellipse cx="152" cy="93" rx="5" ry="22" />
        {/* tripod */}
        <path d="M78 116l-22 30M78 116l22 30M78 116v30" />
      </g>
    </svg>
  );
}

/** A horizontal strip of film, drawn in CSS: a thin perforated band, or a pale strip with frames. */
export function FilmStrip({ className = "", variant = "band" }: { className?: string; variant?: "band" | "photo" }) {
  return <div className={`${variant === "photo" ? "film-strip-photo" : "film-strip"} ${className}`} aria-hidden="true" />;
}
