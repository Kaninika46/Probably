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
  "Which German customers are probably Champions but likely to lapse?";

export const App: React.FC = () => {
  const [meta, setMeta] = useState<MetaResponse | null>(null);
  const [theme, setTheme] = useState<"light" | "dark">(() => {
    const saved = window.localStorage.getItem("probably-theme");
    if (saved === "dark" || saved === "light") return saved;
    return "light"; // Light theme is default per FRONTEND.md section 3
  });
  const [activeQuestion, setActiveQuestion] =
    useState<string>(INITIAL_QUESTION);
  const [recentQuestions, setRecentQuestions] = useState<string[]>([
    INITIAL_QUESTION,
  ]);
  const [selectedCustomerId, setSelectedCustomerId] = useState<number | null>(
    null
  );

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    window.localStorage.setItem("probably-theme", theme);
  }, [theme]);

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
        onToggleTheme={() =>
          setTheme((prev) => (prev === "light" ? "dark" : "light"))
        }
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
