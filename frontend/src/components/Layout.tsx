import { FlaskConical, Languages, LayoutDashboard, MessageSquareHeart, Plus } from "lucide-react";
import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { api, type SystemInfo } from "../lib/api";
import { useT } from "../lib/i18n";

const SystemCtx = createContext<SystemInfo | null>(null);
export const useSystem = () => useContext(SystemCtx);

function Logo() {
  return (
    <svg width="34" height="34" viewBox="0 0 64 64" aria-hidden="true">
      <rect width="64" height="64" rx="14" fill="#1a1e29" />
      <path d="M8 32c6-11 14-17 24-17s18 6 24 17c-6 11-14 17-24 17S14 43 8 32z" fill="none" stroke="#f5b544" strokeWidth="4" />
      <circle cx="32" cy="32" r="7" fill="#f5b544" />
      <path d="M44 22c3 3 4 6 4 10s-1 7-4 10" fill="none" stroke="#5eead4" strokeWidth="3" strokeLinecap="round" />
    </svg>
  );
}

function NavItem({ to, icon, children, end }: { to: string; icon: ReactNode; children: ReactNode; end?: boolean }) {
  return (
    <NavLink
      to={to}
      end={end}
      className={({ isActive }) =>
        `inline-flex items-center gap-2 rounded-xl px-3 py-2 text-sm font-medium transition-colors ${
          isActive ? "bg-surface-3 text-ink" : "text-muted hover:bg-surface-2 hover:text-ink"
        }`
      }
    >
      {icon}
      {children}
    </NavLink>
  );
}

export default function Layout() {
  const { t, lang, setLang } = useT();
  const [system, setSystem] = useState<SystemInfo | null>(null);
  useEffect(() => {
    api.system().then(setSystem).catch(() => setSystem(null));
  }, []);

  return (
    <SystemCtx.Provider value={system}>
      <a href="#main" className="skip-link">
        {t("skip")}
      </a>
      {system?.demo_mode && (
        <div role="note" aria-label={t("demoBanner")} className="border-b border-[#5b4413] bg-[#241a07] text-warn">
          <div className="mx-auto flex max-w-[1400px] items-start gap-3 px-4 py-2 text-sm md:px-6">
            <FlaskConical size={18} aria-hidden="true" className="mt-0.5 shrink-0" />
            <p>
              <strong className="mr-2 rounded bg-warn px-1.5 py-0.5 text-xs font-extrabold tracking-wider text-[#241a07]">
                {t("demoBanner")}
              </strong>
              {t("demoBannerText")}
            </p>
          </div>
        </div>
      )}
      <header className="sticky top-0 z-30 border-b border-line bg-bg/85 backdrop-blur">
        <div className="mx-auto flex max-w-[1400px] flex-wrap items-center gap-3 px-4 py-3 md:px-6">
          <NavLink to="/" className="mr-4 flex items-center gap-3 rounded-xl">
            <Logo />
            <span className="leading-tight">
              <span className="block font-display text-lg font-semibold">
                Basira <span lang="ar" className="text-accent">بصيرة</span>
              </span>
              <span className="block text-xs text-muted">{t("appTagline")}</span>
            </span>
          </NavLink>
          <nav aria-label="Navigation principale" className="flex flex-1 flex-wrap items-center gap-1">
            <NavItem to="/" end icon={<LayoutDashboard size={16} aria-hidden="true" />}>
              {t("navDashboard")}
            </NavItem>
            <NavItem to="/new" icon={<Plus size={16} aria-hidden="true" />}>
              {t("navNew")}
            </NavItem>
            <NavItem to="/feedback" icon={<MessageSquareHeart size={16} aria-hidden="true" />}>
              {t("navFeedback")}
            </NavItem>
          </nav>
          <button
            type="button"
            className="btn-secondary"
            onClick={() => setLang(lang === "fr" ? "en" : "fr")}
            title={t("switchLangLabel")}
          >
            <Languages size={16} aria-hidden="true" />
            <span lang={lang === "fr" ? "en" : "fr"}>{t("switchLang")}</span>
          </button>
        </div>
      </header>
      <main id="main" tabIndex={-1} className="mx-auto max-w-[1400px] px-4 py-8 outline-none md:px-6">
        <Outlet />
      </main>
      <footer className="border-t border-line">
        <div className="mx-auto flex max-w-[1400px] flex-wrap justify-between gap-2 px-4 py-6 text-sm text-muted md:px-6">
          <p>{t("ethicsNote")}</p>
          <p>
            OIF × JEI — IA Éthique 360 · Apache-2.0 ·{" "}
            <a className="underline hover:text-ink" href="/docs" target="_blank" rel="noreferrer">
              API
            </a>
          </p>
        </div>
      </footer>
    </SystemCtx.Provider>
  );
}
