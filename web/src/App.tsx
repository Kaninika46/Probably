/**
 * web/src/App.tsx
 * Root React component managing global metadata (`/api/meta`), light/dark theme toggle
 * (defaulting to light mode for projector readability), last-5 recent questions history,
 * and the right-side CustomerDrawer.
 */

import React, { useEffect, useState } from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { MetaResponse, api } from "./lib/api";
import { CustomerDrawer } from "./components/CustomerDrawer";
import { Layout } from "./components/Layout";
import { AboutPage } from "./pages/AboutPage";
import { AskPage } from "./pages/AskPage";
import { LapsePage } from "./pages/LapsePage";
import { OverviewPage } from "./pages/OverviewPage";
import { QualityPage } from "./pages/QualityPage";
import { SegmentsPage } from "./pages/SegmentsPage";

const INITIAL_QUESTION =
  "Which customers are almost certainly Champions?";

export const App: React.FC = () => {
  const [meta, setMeta] = useState<MetaResponse | null>(null);
  const [theme, setTheme] = useState<"light" | "dark">(() => {
    const params = new URLSearchParams(window.location.search);
    const qTheme = params.get("theme");
    if (qTheme === "dark" || qTheme === "light") return qTheme;
    try {
      const saved = window.localStorage.getItem("probably-theme");
      if (saved === "dark" || saved === "light") return saved;
    } catch {
      // Storage unavailable: fall through to the light default
    }
    return "light"; // Light theme is default per FRONTEND.md section 3
  });
  const [activeQuestion, setActiveQuestion] = useState<string>(() => {
    const params = new URLSearchParams(window.location.search);
    return params.get("q") || INITIAL_QUESTION;
  });
  const [recentQuestions, setRecentQuestions] = useState<string[]>([
    INITIAL_QUESTION,
    "Which German customers are probably Champions but likely to lapse?",
  ]);
  const [selectedCustomerId, setSelectedCustomerId] = useState<number | null>(
    () => {
      const params = new URLSearchParams(window.location.search);
      const cid = params.get("customer");
      return cid && !Number.isNaN(Number(cid)) ? Number(cid) : null;
    }
  );

  // Apply the theme, but only persist it once the user has explicitly toggled.
  // A first-time visitor therefore always lands on light (projector-friendly),
  // whatever their OS colour-scheme preference is.
  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
  }, [theme]);

  const toggleTheme = () => {
    setTheme((prev) => {
      const next = prev === "light" ? "dark" : "light";
      try {
        window.localStorage.setItem("probably-theme", next);
      } catch {
        // Storage can be blocked (private window); the toggle still works for this visit
      }
      return next;
    });
  };

  useEffect(() => {
    api
      .getMeta()
      .then((res) => setMeta(res))
      .catch(() => {
        // Fallback handled gracefully by components
      });
  }, []);

  const handleAskQuestion = (q: string) => {
    const trimmed = q.trim();
    if (!trimmed) return;
    setActiveQuestion(trimmed);
    setRecentQuestions((prev) => {
      const filtered = prev.filter(
        (item) => item.toLowerCase() !== trimmed.toLowerCase()
      );
      return [trimmed, ...filtered].slice(0, 5);
    });
  };

  return (
    <BrowserRouter>
      <Layout
        meta={meta}
        theme={theme}
        onToggleTheme={toggleTheme}
        recentQuestions={recentQuestions}
        onSelectRecentQuestion={handleAskQuestion}
      >
        <Routes>
          <Route
            path="/"
            element={
              <OverviewPage meta={meta} onAskQuestion={handleAskQuestion} />
            }
          />
          <Route
            path="/ask"
            element={
              <AskPage
                meta={meta}
                activeQuestion={activeQuestion}
                onAskQuestion={handleAskQuestion}
                onSelectCustomer={setSelectedCustomerId}
              />
            }
          />
          <Route
            path="/segments"
            element={
              <SegmentsPage
                meta={meta}
                theme={theme}
                onSelectCustomer={setSelectedCustomerId}
              />
            }
          />
          <Route
            path="/lapse"
            element={
              <LapsePage
                meta={meta}
                onSelectCustomer={setSelectedCustomerId}
              />
            }
          />
          <Route path="/quality" element={<QualityPage meta={meta} />} />
          <Route path="/about" element={<AboutPage meta={meta} />} />
        </Routes>
      </Layout>

      <CustomerDrawer
        customerId={selectedCustomerId}
        onClose={() => setSelectedCustomerId(null)}
        segmentsMeta={meta?.segments}
      />
    </BrowserRouter>
  );
};

export default App;
