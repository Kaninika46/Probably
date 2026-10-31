/**
 * web/src/components/Layout.tsx
 * App shell implementing `FRONTEND.md` section 4:
 * - Top bar: product name "Probably", subtitle "Customer intelligence with honest confidence",
 *   dataset badge ("UCI Online Retail II · snapshot 10 Dec 2011 · N customers" from `/api/meta`),
 *   and light/dark theme toggle.
 * - Left sidebar navigation (240px) with the 6 pages + last 5 asked questions history list.
 * - Main content area (max-width 1200px).
 * - Footer status: "Read-only · app.duckdb".
 */

import React from "react";
import { NavLink, useNavigate } from "react-router-dom";
import {
  Activity,
  BarChart3,
  Compass,
  Info,
  Layers,
  MessageSquare,
  Moon,
  ShieldCheck,
  Sun,
} from "lucide-react";
import { MetaResponse, formatNumber } from "../lib/api";

interface LayoutProps {
  meta: MetaResponse | null;
  metaError: string | null;
  theme: "light" | "dark";
  onToggleTheme: () => void;
  recentQuestions: string[];
  onSelectRecentQuestion: (q: string) => void;
  children: React.ReactNode;
}

const NAV_ITEMS = [
  { to: "/", label: "Overview", icon: Compass },
  { to: "/ask", label: "Ask", icon: MessageSquare },
  { to: "/segments", label: "Segments", icon: Layers },
  { to: "/lapse", label: "Lapse risk", icon: Activity },
  { to: "/quality", label: "Model quality", icon: BarChart3 },
  { to: "/about", label: "About", icon: Info },
];

export const Layout: React.FC<LayoutProps> = ({
  meta,
  metaError,
  theme,
  onToggleTheme,
  recentQuestions,
  onSelectRecentQuestion,
  children,
}) => {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen flex flex-col" style={{ backgroundColor: "var(--bg)", color: "var(--ink)" }}>
      {/* Top Bar */}
      <header
        className="sticky top-0 z-30 h-16 px-6 flex items-center justify-between"
        style={{
          backgroundColor: "var(--surface)",
          borderBottom: "1px solid var(--line)",
        }}
      >
        <div className="flex items-baseline gap-3">
          <span className="font-display font-semibold text-xl tracking-tight">
            Probably
          </span>
          <span
            className="hidden sm:inline text-small"
            style={{ color: "var(--muted)" }}
          >
            Customer intelligence with honest confidence
          </span>
        </div>

        <div className="flex items-center gap-3">
          <div
            className="hidden md:inline-flex items-center gap-2 px-3 py-1 rounded-full text-small tabular-nums"
            style={{
              backgroundColor: "var(--surface-2)",
              border: "1px solid var(--line)",
              color: "var(--ink-2)",
            }}
          >
            <span>
              {meta ? meta.dataset_name : "UCI Online Retail II"} · snapshot{" "}
              {meta ? meta.snapshot_date_display : "10 Dec 2011"} ·{" "}
              <strong style={{ color: "var(--ink)" }}>
                {meta ? formatNumber(meta.customer_count) : "—"}
              </strong>{" "}
              customers
            </span>
          </div>

          <button
            type="button"
            onClick={onToggleTheme}
            aria-label={`Switch to ${theme === "light" ? "dark" : "light"} mode`}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-input text-small font-medium transition-smooth"
            style={{
              backgroundColor: "var(--surface-2)",
              border: "1px solid var(--line)",
              color: "var(--ink)",
            }}
          >
            {theme === "light" ? <Moon size={15} /> : <Sun size={15} />}
            <span className="hidden sm:inline">
              {theme === "light" ? "Dark" : "Light"}
            </span>
          </button>
        </div>
      </header>

      <div className="flex-1 flex flex-col md:flex-row">
        {/* Left Sidebar Navigation (240px on desktop) */}
        <aside
          className="w-full md:w-[240px] shrink-0 p-4 flex flex-col justify-between gap-6"
          style={{
            backgroundColor: "var(--surface)",
            borderRight: "1px solid var(--line)",
          }}
        >
          <div className="flex flex-col gap-6">
            <nav aria-label="Main navigation" className="flex md:flex-col gap-1 overflow-x-auto">
              {NAV_ITEMS.map((item) => {
                const Icon = item.icon;
                return (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    end={item.to === "/"}
                    className={({ isActive }) =>
                      `flex items-center gap-2.5 px-3 py-2 rounded-input text-small font-medium transition-smooth whitespace-nowrap ${
                        isActive ? "font-semibold" : ""
                      }`
                    }
                    style={({ isActive }) => ({
                      backgroundColor: isActive
                        ? "var(--ink)"
                        : "transparent",
                      color: isActive ? "var(--bg)" : "var(--ink-2)",
                    })}
                  >
                    <Icon size={16} />
                    <span>{item.label}</span>
                  </NavLink>
                );
              })}
            </nav>

            {/* Recent Questions History (Last 5) */}
            {recentQuestions.length > 0 && (
              <div className="hidden md:flex flex-col gap-2 pt-4" style={{ borderTop: "1px solid var(--line)" }}>
                <span className="label-caps px-2">Recent Questions</span>
                <ul className="flex flex-col gap-1">
                  {recentQuestions.map((q, idx) => (
                    <li key={`${idx}-${q}`}>
                      <button
                        type="button"
                        onClick={() => {
                          onSelectRecentQuestion(q);
                          navigate("/ask");
                        }}
                        className="w-full text-left px-2.5 py-1.5 rounded text-small transition-smooth"
                        style={{ color: "var(--ink-2)" }}
                        title={q}
                      >
                        {q}
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          {/* Footer status inside sidebar */}
          <div
            className="hidden md:flex items-center gap-2 px-2.5 py-2 rounded-input text-small"
            style={{
              backgroundColor: "var(--surface-2)",
              color: "var(--muted)",
            }}
          >
            <ShieldCheck size={15} style={{ color: "var(--ink)" }} />
            <span className="text-code text-xs">Read-only · app.duckdb</span>
          </div>
        </aside>

        {/* Main Content Container (max-width 1200px) */}
        <main className="flex-1 p-6 md:p-8 overflow-x-hidden">
          <div className="max-w-[1200px] mx-auto flex flex-col gap-6">
            {metaError && (
              <div
                role="alert"
                className="card-surface text-small"
                style={{ borderColor: "var(--lapse-3)", color: "var(--ink)" }}
              >
                Could not load dataset metadata from <code>/api/meta</code> ({metaError}).
                Figures that depend on it show "—". Restart the app with <code>run_app.bat</code>.
              </div>
            )}
            {children}
          </div>
        </main>
      </div>

      {/* Footer */}
      <footer
        className="px-6 py-3 flex items-center justify-between text-small"
        style={{
          backgroundColor: "var(--surface)",
          borderTop: "1px solid var(--line)",
          color: "var(--muted)",
        }}
      >
        <span>
          ABAI2009L · Data Management and AI Integration · Topics 3 (KDD), 1 (Probabilistic DB), 2 (NLP → SQL)
        </span>
        <span className="text-code text-xs">Read-only · app.duckdb</span>
      </footer>
    </div>
  );
};
