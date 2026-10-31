/**
 * web/src/pages/OverviewPage.tsx
 * Page 1 (`/`): Overview page (`FRONTEND.md` section 4.1).
 * - Headline from `/api/meta` (`headline.title` & `headline.subtitle`) backed by a mini
 *   reliability chart from `/api/lapse` (`reliability_bins`) and the Brier skill score.
 * - Large Ask bar that navigates to `/ask` with the submitted question.
 * - Segment summary strip: 5 chips with hard count vs expected size (`GET /api/segments`).
 * - Three stat tiles: customers, segments, lapse calibration error (10-bin ECE).
 */

import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowRight, Search } from "lucide-react";
import {
  LapseResponse,
  MetaResponse,
  SegmentsResponse,
  api,
  formatNumber,
  segmentCssColor,
} from "../lib/api";

interface OverviewPageProps {
  meta: MetaResponse | null;
  onAskQuestion: (q: string) => void;
}

export const OverviewPage: React.FC<OverviewPageProps> = ({
  meta,
  onAskQuestion,
}) => {
  const navigate = useNavigate();
  const [askInput, setAskInput] = useState(
    "Which German customers are probably Champions but likely to lapse?"
  );
  const [segmentsData, setSegmentsData] = useState<SegmentsResponse | null>(
    null
  );
  const [lapseData, setLapseData] = useState<LapseResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    Promise.all([api.getSegments("gmm"), api.getLapse()])
      .then(([segRes, lapRes]) => {
        if (!cancelled) {
          setSegmentsData(segRes);
          setLapseData(lapRes);
          setLoading(false);
        }
      })
      .catch((err: Error) => {
        if (!cancelled) {
          setError(err.message || "Could not load overview metrics.");
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!askInput.trim()) return;
    onAskQuestion(askInput.trim());
    navigate("/ask");
  };

  const logisticBins = (lapseData?.reliability_bins || []).filter(
    (b) =>
      b.model === "logistic_calibrated" &&
      b.mean_predicted_p !== null &&
      b.observed_lapse_rate !== null &&
      Number(b.n_customers) > 0
  );

  return (
    <div className="flex flex-col gap-6">
      {/* Gate Headline + Mini Reliability Chart */}
      <section className="card-surface grid grid-cols-1 lg:grid-cols-12 gap-6 items-center">
        <div className="lg:col-span-7 flex flex-col gap-3">
          <span className="label-caps">
            Gate Decision Headline · Calibrated 90-Day Lapse Risk
          </span>
          <h1 className="text-display">
            {meta?.headline.title ||
              "When we say a customer is 70% likely to lapse, about that share really do."}
          </h1>
          <p className="text-body" style={{ color: "var(--ink-2)" }}>
            {meta?.headline.subtitle}
          </p>
          {meta && (
            <div className="flex flex-wrap items-center gap-3 pt-1">
              <span
                className="px-3 py-1 rounded-full text-small font-medium tabular-nums"
                style={{
                  backgroundColor: "var(--surface-2)",
                  border: "1px solid var(--line)",
                }}
              >
                Brier skill score:{" "}
                <strong className="text-code">
                  +{(meta.headline.brier_skill_score * 100).toFixed(2)}%
                </strong>{" "}
                vs base rate
              </span>
              <span
                className="px-3 py-1 rounded-full text-small font-medium tabular-nums"
                style={{
                  backgroundColor: "var(--surface-2)",
                  border: "1px solid var(--line)",
                }}
              >
                S2 Brier:{" "}
                <strong className="text-code">
                  {meta.headline.brier_score.toFixed(4)}
                </strong>
              </span>
              <span
                className="px-3 py-1 rounded-full text-small font-medium tabular-nums"
                style={{
                  backgroundColor: "var(--surface-2)",
                  border: "1px solid var(--line)",
                }}
              >
                S2 ROC-AUC:{" "}
                <strong className="text-code">
                  {meta.headline.roc_auc.toFixed(4)}
                </strong>
              </span>
            </div>
          )}
        </div>

        {/* Mini SVG Reliability Chart */}
        <div
          className="lg:col-span-5 p-4 rounded-card"
          style={{
            backgroundColor: "var(--bg)",
            border: "1px solid var(--line)",
          }}
        >
          <div className="text-small font-semibold mb-1">
            Predicted vs observed 90-day lapse rate on held-out S2
          </div>
          <div className="text-xs mb-2" style={{ color: "var(--muted)" }}>
            Diagonal = ideal calibration · dots = 10 probability bins (ECE ={" "}
            {meta ? meta.headline.ece_10_bins.toFixed(4) : "—"})
          </div>
          {loading ? (
            <div
              className="h-44 rounded animate-pulse"
              style={{ backgroundColor: "var(--surface-2)" }}
            />
          ) : (
            <svg
              viewBox="0 0 300 185"
              className="w-full h-44 overflow-visible"
              role="img"
              aria-label="Mini reliability diagram comparing predicted 90-day lapse probability to observed S2 lapse rate"
            >
              {/* Axes */}
              <line
                x1={38}
                y1={14}
                x2={38}
                y2={150}
                stroke="var(--line)"
                strokeWidth={1}
              />
              <line
                x1={38}
                y1={150}
                x2={280}
                y2={150}
                stroke="var(--line)"
                strokeWidth={1}
              />
              {/* Ideal diagonal */}
              <line
                x1={38}
                y1={150}
                x2={280}
                y2={14}
                stroke="var(--muted)"
                strokeDasharray="4 4"
                strokeWidth={1.25}
              />
              {/* Polyline and points */}
              {logisticBins.length > 1 && (
                <polyline
                  fill="none"
                  stroke="var(--lapse-3)"
                  strokeWidth={2}
                  points={logisticBins
                    .map((b) => {
                      const x = 38 + Number(b.mean_predicted_p) * 242;
                      const y = 150 - Number(b.observed_lapse_rate) * 136;
                      return `${x.toFixed(1)},${y.toFixed(1)}`;
                    })
                    .join(" ")}
                />
              )}
              {logisticBins.map((b, idx) => {
                const x = 38 + Number(b.mean_predicted_p) * 242;
                const y = 150 - Number(b.observed_lapse_rate) * 136;
                return (
                  <g key={idx}>
                    <circle
                      cx={x}
                      cy={y}
                      r={4}
                      fill="var(--lapse-3)"
                    >
                      <title>
                        Bin {String(b.bin_index)}: predicted{" "}
                        {Number(b.mean_predicted_p).toFixed(2)}, observed{" "}
                        {Number(b.observed_lapse_rate).toFixed(2)} (n=
                        {String(b.n_customers)})
                      </title>
                    </circle>
                  </g>
                );
              })}
              {/* Axis labels */}
              <text
                x={38}
                y={166}
                fontSize={10}
                fill="var(--muted)"
                fontFamily="JetBrains Mono"
              >
                0.0
              </text>
              <text
                x={159}
                y={166}
                fontSize={10}
                textAnchor="middle"
                fill="var(--muted)"
                fontFamily="Figtree"
              >
                Predicted P(lapse in 90d)
              </text>
              <text
                x={280}
                y={166}
                fontSize={10}
                textAnchor="end"
                fill="var(--muted)"
                fontFamily="JetBrains Mono"
              >
                1.0
              </text>
              <text
                x={32}
                y={150}
                fontSize={10}
                textAnchor="end"
                fill="var(--muted)"
                fontFamily="JetBrains Mono"
              >
                0.0
              </text>
              <text
                x={32}
                y={22}
                fontSize={10}
                textAnchor="end"
                fill="var(--muted)"
                fontFamily="JetBrains Mono"
              >
                1.0
              </text>
            </svg>
          )}
        </div>
      </section>

      {/* Large Ask Command Bar */}
      <section className="card-surface flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <span className="label-caps">
            Ask the Probabilistic Database in Plain English
          </span>
          <span className="text-small" style={{ color: "var(--muted)" }}>
            Maps IPCC &amp; Sherman Kent hedge words to parameterised SQL templates Q1–Q6
          </span>
        </div>
        <form onSubmit={handleSubmit} className="flex flex-col sm:flex-row gap-3">
          <div className="relative flex-1">
            <Search
              size={18}
              className="absolute left-3.5 top-1/2 -translate-y-1/2"
              style={{ color: "var(--muted)" }}
            />
            <input
              type="text"
              value={askInput}
              onChange={(e) => setAskInput(e.target.value)}
              aria-label="Ask a natural-language question"
              placeholder="e.g., Which German customers are probably Champions but likely to lapse?"
              className="w-full h-14 pl-11 pr-4 rounded-input text-body"
              style={{
                backgroundColor: "var(--bg)",
                border: "1px solid var(--line)",
                color: "var(--ink)",
              }}
            />
          </div>
          <button
            type="submit"
            className="btn-primary h-14 px-6 inline-flex items-center justify-center gap-2 shrink-0"
          >
            <span>Ask Probably</span>
            <ArrowRight size={16} />
          </button>
        </form>
        {meta && (
          <div className="flex flex-wrap items-center gap-2 pt-1">
            {meta.example_questions.map((ex) => (
              <button
                key={ex.id}
                type="button"
                onClick={() => {
                  onAskQuestion(ex.question);
                  navigate("/ask");
                }}
                className="px-3 py-1 rounded-full text-small transition-smooth"
                style={{
                  backgroundColor: "var(--surface-2)",
                  border: "1px solid var(--line)",
                  color: "var(--ink-2)",
                }}
              >
                {ex.question}
              </button>
            ))}
          </div>
        )}
      </section>

      {error && (
        <div className="card-surface text-small" style={{ color: "var(--ink)" }}>
          {error}
        </div>
      )}

      {/* Segment Summary Strip: 5 Chips with Hard Count vs Expected Size */}
      <section className="flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <span className="label-caps">
            S3 Segment Summary Strip · Hard Count vs Expected Size Σp (Method = GMM)
          </span>
          <button
            type="button"
            onClick={() => navigate("/segments")}
            className="text-small font-medium underline"
            style={{ color: "var(--ink-2)" }}
          >
            Open Uncertainty Map →
          </button>
        </div>

        {loading || !segmentsData ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
            {[0, 1, 2, 3, 4].map((i) => (
              <div
                key={i}
                className="h-28 rounded-card animate-pulse"
                style={{ backgroundColor: "var(--surface)" }}
              />
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
            {segmentsData.segments.map((seg) => (
              <button
                key={seg.name}
                type="button"
                onClick={() => navigate("/segments")}
                className="card-surface text-left flex flex-col justify-between gap-2 transition-smooth"
              >
                <div className="flex items-center justify-between">
                  <span className="inline-flex items-center gap-2 font-display font-semibold text-base">
                    <span
                      className="w-2.5 h-2.5 rounded-full"
                      style={{
                        backgroundColor: segmentCssColor(
                          seg.name,
                          meta?.segments
                        ),
                      }}
                    />
                    <span>{seg.name}</span>
                  </span>
                  <span
                    className="text-code text-xs"
                    style={{ color: "var(--muted)" }}
                  >
                    {seg.share_of_customers_pct.toFixed(1)}%
                  </span>
                </div>
                <div className="pt-1">
                  <div className="text-small" style={{ color: "var(--muted)" }}>
                    Hard count:{" "}
                    <strong
                      className="text-code"
                      style={{ color: "var(--ink)" }}
                    >
                      {formatNumber(seg.hard_count)}
                    </strong>
                  </div>
                  <div className="text-small" style={{ color: "var(--muted)" }}>
                    Expected Σp:{" "}
                    <strong
                      className="text-code"
                      style={{ color: "var(--ink)" }}
                    >
                      {formatNumber(seg.expected_size, 2)}
                    </strong>{" "}
                    <span className="text-xs">±{seg.std_dev.toFixed(1)}</span>
                  </div>
                </div>
              </button>
            ))}
          </div>
        )}
      </section>

      {/* Three Stat Tiles: Customers, Segments, Lapse Calibration Error */}
      <section className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="card-surface flex flex-col justify-between">
          <span className="label-caps">Active S3 Customers</span>
          <div className="text-display mt-2 tabular-nums">
            {meta ? formatNumber(meta.customer_count) : "—"}
          </div>
          <p className="text-small mt-1" style={{ color: "var(--muted)" }}>
            Customers with ≥1 clean product purchase in window{" "}
            {meta?.feature_window || "2011-03-10 to 2011-12-09"}.
          </p>
        </div>

        <div className="card-surface flex flex-col justify-between">
          <span className="label-caps">Probabilistic Segments (PROVISIONAL)</span>
          <div className="text-display mt-2 tabular-nums">
            {meta ? meta.segments.length : 5}
          </div>
          <p className="text-small mt-1" style={{ color: "var(--muted)" }}>
            Spherical GMM (K = 5) with{" "}
            {meta ? `${meta.headline.gmm_boundary_share_pct.toFixed(2)}%` : "—"}{" "}
            boundary customers (max p &lt; 0.60) and B=100 bootstrap stability check.
          </p>
        </div>

        <div className="card-surface flex flex-col justify-between">
          <span className="label-caps">Lapse Calibration Error (10-Bin ECE)</span>
          <div className="text-display mt-2 tabular-nums">
            {meta ? meta.headline.ece_10_bins.toFixed(4) : "—"}
          </div>
          <p className="text-small mt-1" style={{ color: "var(--muted)" }}>
            Evaluated once on held-out S2 (3,247 customers); Brier score{" "}
            {meta ? meta.headline.brier_score.toFixed(4) : "—"}, skill score +
            {meta ? (meta.headline.brier_skill_score * 100).toFixed(2) : "—"}%.
          </p>
        </div>
      </section>
    </div>
  );
};
