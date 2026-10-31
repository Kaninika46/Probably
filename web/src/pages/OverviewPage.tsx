/**
 * web/src/pages/OverviewPage.tsx
 * Page 1 (`/`): Overview page (`FRONTEND.md` section 4.1).
 * - Headline from `/api/meta` (`headline.title` & `headline.subtitle`) with metric pills,
 *   and a full-width reliability diagram from `/api/lapse` (`reliability_bins`) below it.
 * - Large Ask bar that navigates to `/ask` with the submitted question.
 * - Segment summary strip: 5 chips with hard count vs expected size (`GET /api/segments`).
 * - Three stat tiles: customers, segments, lapse calibration error (10-bin ECE).
 */

import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowRight, Search } from "lucide-react";
import {
  ReliabilityBin,
  ReliabilityChart,
  describeTopBin,
} from "../charts/ReliabilityChart";
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

  // Shared scale for the strip's mini bars: the largest hard or expected size across segments.
  const stripScaleMax = Math.max(
    1,
    ...(segmentsData?.segments || []).flatMap((seg) => [seg.hard_count, seg.expected_size])
  );
  // Σp over all segments must equal the customer count (linearity of expectation).
  const expectedTotal = (segmentsData?.segments || []).reduce(
    (sum, seg) => sum + seg.expected_size,
    0
  );
  const expectedSumMatches =
    segmentsData !== null &&
    Math.abs(expectedTotal - segmentsData.customer_count) < 0.01;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!askInput.trim()) return;
    onAskQuestion(askInput.trim());
    navigate("/ask");
  };

  // Non-empty bins of the primary (calibrated logistic) model on held-out S2.
  const logisticBins: ReliabilityBin[] = (lapseData?.reliability_bins || [])
    .filter(
      (b) =>
        b.model === "logistic_calibrated" &&
        b.mean_predicted_p !== null &&
        b.observed_lapse_rate !== null &&
        Number(b.n_customers) > 0
    )
    .map((b) => ({
      bin_lower: Number(b.bin_lower),
      bin_upper: Number(b.bin_upper),
      n_customers: Number(b.n_customers),
      mean_predicted_p: Number(b.mean_predicted_p),
      observed_lapse_rate: Number(b.observed_lapse_rate),
    }));
  const s2CustomerCount = meta?.headline.s2_customer_count ?? 0;
  const topBinSentence = meta ? describeTopBin(logisticBins, s2CustomerCount) : null;

  return (
    <div className="flex flex-col gap-6">
      {/* Headline finding, with the full-width reliability diagram stacked below it */}
      <section className="card-surface flex flex-col gap-5">
        <div className="flex flex-col gap-3">
          <span className="label-caps">Headline finding</span>
          <h1 className="text-display">
            {meta?.headline.title ||
              "When we say a customer is 70% likely to lapse, about that share really do."}
          </h1>
          <p className="text-body" style={{ color: "var(--ink-2)" }}>
            {meta?.headline.subtitle}
          </p>
          {meta && (
            <div className="flex flex-wrap items-center gap-3 pt-1">
              {[
                {
                  label: "Brier skill score",
                  value: `+${(meta.headline.brier_skill_score * 100).toFixed(2)}%`,
                  note: "vs base rate",
                },
                { label: "Brier score", value: meta.headline.brier_score.toFixed(4) },
                { label: "ROC-AUC", value: meta.headline.roc_auc.toFixed(4) },
                { label: "ECE (10 bins)", value: meta.headline.ece_10_bins.toFixed(4) },
              ].map((pill) => (
                <span
                  key={pill.label}
                  className="px-3 py-1 rounded-full text-small font-medium tabular-nums"
                  style={{
                    backgroundColor: "var(--surface-2)",
                    border: "1px solid var(--line)",
                  }}
                >
                  {pill.label}: <strong className="text-code">{pill.value}</strong>
                  {pill.note ? ` ${pill.note}` : ""}
                </span>
              ))}
            </div>
          )}
        </div>

        <div className="pt-4" style={{ borderTop: "1px solid var(--line)" }}>
          <h2 className="text-h2">Predicted vs observed 90-day lapse on held-out customers</h2>
          <p className="text-small mt-1 mb-3" style={{ color: "var(--muted)" }}>
            Predictions are grouped into 10 equal-width probability bins; each dot is a non-empty bin, sized by how many customers fall in it. Hover a dot for its count.
          </p>
          {loading ? (
            <div
              className="h-[400px] rounded animate-pulse"
              style={{ backgroundColor: "var(--surface-2)" }}
            />
          ) : (
            <>
              <ReliabilityChart bins={logisticBins} totalCustomers={s2CustomerCount} />
              {topBinSentence && (
                <p className="text-small mt-3" style={{ color: "var(--ink-2)" }}>
                  {topBinSentence}
                </p>
              )}
            </>
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
            Segments today · hard count vs expected size Σp (GMM)
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
          <>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
              {segmentsData.segments.map((seg) => {
                const colorVar = segmentCssColor(seg.name, meta?.segments);
                return (
                  <button
                    key={seg.name}
                    type="button"
                    onClick={() => navigate("/segments")}
                    className="card-surface text-left flex flex-col justify-between gap-2 transition-smooth"
                  >
                    <div className="flex items-center gap-2 font-display font-semibold text-base">
                      <span
                        className="w-2.5 h-2.5 rounded-full"
                        style={{ backgroundColor: colorVar }}
                      />
                      <span>{seg.name}</span>
                    </div>
                    <div className="text-small" style={{ color: "var(--muted)" }}>
                      {seg.share_of_customers_pct.toFixed(1)}% of customers
                    </div>
                    <div className="pt-1">
                      <div className="text-small" style={{ color: "var(--muted)" }}>
                        Hard count:{" "}
                        <strong className="text-code" style={{ color: "var(--ink)" }}>
                          {formatNumber(seg.hard_count)}
                        </strong>
                      </div>
                      <div className="text-small" style={{ color: "var(--muted)" }}>
                        Expected Σp:{" "}
                        <strong className="text-code" style={{ color: "var(--ink)" }}>
                          {formatNumber(seg.expected_size, 2)}
                        </strong>{" "}
                        <span className="text-xs">±{seg.std_dev.toFixed(1)}</span>
                      </div>
                    </div>
                    {/* Hard vs expected bars on one scale shared by all five cards */}
                    <div
                      className="flex flex-col gap-1 pt-1"
                      role="img"
                      aria-label={`${seg.name}: hard count ${seg.hard_count}, expected size ${seg.expected_size.toFixed(2)}`}
                    >
                      {[
                        { label: "Hard", value: seg.hard_count, opacity: 0.45 },
                        { label: "Σp", value: seg.expected_size, opacity: 1 },
                      ].map((bar) => (
                        <div key={bar.label} className="flex items-center gap-2">
                          <span
                            className="text-xs w-9 shrink-0"
                            style={{ color: "var(--muted)" }}
                          >
                            {bar.label}
                          </span>
                          <div
                            className="flex-1 h-2 rounded-full"
                            style={{ backgroundColor: "var(--surface-2)" }}
                          >
                            <div
                              className="h-2 rounded-full"
                              style={{
                                width: `${(bar.value / stripScaleMax) * 100}%`,
                                backgroundColor: colorVar,
                                opacity: bar.opacity,
                              }}
                            />
                          </div>
                        </div>
                      ))}
                    </div>
                  </button>
                );
              })}
            </div>
            <p className="text-small" style={{ color: "var(--ink-2)" }}>
              Expected sizes sum to {formatNumber(expectedTotal)}
              {expectedSumMatches ? ", exactly the number of customers" : ""}. Hard
              counts round each customer to one segment; expected sizes keep the uncertainty.
            </p>
          </>
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
            Evaluated once on held-out S2 (
            {meta ? formatNumber(meta.headline.s2_customer_count) : "—"} customers); Brier score{" "}
            {meta ? meta.headline.brier_score.toFixed(4) : "—"}, skill score +
            {meta ? (meta.headline.brier_skill_score * 100).toFixed(2) : "—"}%.
          </p>
        </div>
      </section>
    </div>
  );
};
