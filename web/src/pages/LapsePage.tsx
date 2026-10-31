/**
 * web/src/pages/LapsePage.tsx
 * Page 4 (`/lapse`): 90-Day Lapse Risk page (`FRONTEND.md` section 4.4).
 * Reads `GET /api/lapse` (`s2_metrics`, `s1_cv_metrics`, `reliability_bins`,
 * `baseline_s1_rates`, `s3_by_segment`, `high_value_at_risk`):
 * - Metric tiles (Brier score, Brier skill score, ROC-AUC, 10-bin ECE).
 * - Reliability diagram (predicted vs observed with diagonal + customer count bar underneath).
 * - Model vs baselines comparison table (S1 5-fold CV and S2 held-out test).
 * - "High value, likely to lapse" table (top 20 top-quartile-spend S3 customers by `p_lapse_90d`).
 */

import React, { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  LapseResponse,
  MetaResponse,
  api,
  formatCurrency,
  formatNumber,
  segmentCssColor,
} from "../lib/api";
import { ProbabilityBar } from "../components/ProbabilityBar";

interface LapsePageProps {
  meta: MetaResponse | null;
  onSelectCustomer: (customerId: number) => void;
}

export const LapsePage: React.FC<LapsePageProps> = ({
  meta,
  onSelectCustomer,
}) => {
  const [data, setData] = useState<LapseResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api
      .getLapse()
      .then((res) => {
        if (!cancelled) {
          setData(res);
          setLoading(false);
        }
      })
      .catch((err: Error) => {
        if (!cancelled) {
          setError(err.message || "Could not load lapse evaluation.");
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const primaryS2 = data?.s2_metrics.find(
    (m) => m.model === "logistic_calibrated"
  );

  // Merge 10 reliability bins across the 3 models for the reliability chart
  const reliabilityChartData = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((binIdx) => {
    const binsForIdx = (data?.reliability_bins || []).filter(
      (b) => Number(b.bin_index) === binIdx
    );
    const logBin = binsForIdx.find((b) => b.model === "logistic_calibrated");
    const treeBin = binsForIdx.find(
      (b) => b.model === "tree_depth4_calibrated"
    );
    const ruleBin = binsForIdx.find((b) => b.model === "two_bin_recency_90d");
    const center = logBin
      ? 0.5 * (Number(logBin.bin_lower) + Number(logBin.bin_upper))
      : (binIdx - 0.5) / 10;

    return {
      binLabel: logBin
        ? `${Number(logBin.bin_lower).toFixed(1)}–${Number(
            logBin.bin_upper
          ).toFixed(1)}`
        : `Bin ${binIdx}`,
      binCenter: Number(center.toFixed(2)),
      Ideal: Number(center.toFixed(2)),
      "Calibrated Logistic (primary)":
        logBin?.observed_lapse_rate !== null &&
        logBin?.observed_lapse_rate !== undefined
          ? Number(logBin.observed_lapse_rate)
          : null,
      "Calibrated Depth-4 Tree":
        treeBin?.observed_lapse_rate !== null &&
        treeBin?.observed_lapse_rate !== undefined
          ? Number(treeBin.observed_lapse_rate)
          : null,
      "Two-Bin Rule (recency > 90d)":
        ruleBin?.observed_lapse_rate !== null &&
        ruleBin?.observed_lapse_rate !== undefined
          ? Number(ruleBin.observed_lapse_rate)
          : null,
      "Customer Count (S2)": Number(logBin?.n_customers || 0),
    };
  });

  return (
    <div className="flex flex-col gap-6">
      <div>
        <span className="label-caps">
          Topic 3 (Supervised Classification) × Topic 1 (Tuple-Independent Table `lapse_risk`)
        </span>
        <h1 className="text-h1 mt-1">
          90-Day Lapse Risk · Calibrated on S1, Verified Once on Held-Out S2
        </h1>
        <p className="text-small mt-1" style={{ color: "var(--muted)" }}>
          We model 90-day lapse (no purchase in the next 90 days), never permanent &ldquo;churn&rdquo;, because non-contractual retail customers can pause and return.
        </p>
      </div>

      {error && <div className="card-surface text-small">{error}</div>}

      {/* Four Metric Tiles */}
      {loading || !primaryS2 ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {[0, 1, 2, 3].map((i) => (
            <div
              key={i}
              className="h-28 rounded-card animate-pulse"
              style={{ backgroundColor: "var(--surface)" }}
            />
          ))}
        </div>
      ) : (
        <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="card-surface">
            <span className="label-caps">S2 Brier Score ↓</span>
            <div className="text-display mt-2 tabular-nums">
              {Number(primaryS2.brier_score).toFixed(4)}
            </div>
            <div className="text-small mt-1" style={{ color: "var(--muted)" }}>
              Proper scoring rule across {formatNumber(Number(primaryS2.n_customers))} S2 customers
            </div>
          </div>

          <div className="card-surface">
            <span className="label-caps">Brier Skill Score ↑</span>
            <div className="text-display mt-2 tabular-nums">
              +{(Number(primaryS2.brier_skill_score) * 100).toFixed(2)}%
            </div>
            <div className="text-small mt-1" style={{ color: "var(--muted)" }}>
              Skill gain over S2 base lapse rate ({(Number(primaryS2.base_lapse_rate) * 100).toFixed(2)}%)
            </div>
          </div>

          <div className="card-surface">
            <span className="label-caps">S2 ROC-AUC ↑</span>
            <div className="text-display mt-2 tabular-nums">
              {Number(primaryS2.roc_auc).toFixed(4)}
            </div>
            <div className="text-small mt-1" style={{ color: "var(--muted)" }}>
              Rank-order discrimination (+0.1019 over 2-bin recency rule)
            </div>
          </div>

          <div className="card-surface">
            <span className="label-caps">10-Bin ECE ↓</span>
            <div className="text-display mt-2 tabular-nums">
              {Number(primaryS2.ece_10_bins).toFixed(4)}
            </div>
            <div className="text-small mt-1" style={{ color: "var(--muted)" }}>
              Expected Calibration Error after 5-fold sigmoid Platt scaling
            </div>
          </div>
        </section>
      )}

      {/* Reliability Diagram + Count Bar Underneath */}
      {!loading && data && (
        <section className="card-surface flex flex-col gap-5">
          <div>
            <span className="label-caps">Calibration Verification (Held-Out S2 Cohort)</span>
            <h2 className="text-h2 mt-0.5">
              Predicted 90-day lapse probability vs observed S2 lapse rate across 10 bins
            </h2>
            <p className="text-small mt-0.5" style={{ color: "var(--muted)" }}>
              Points lying on the dashed diagonal indicate that a predicted probability of p corresponds to an empirical lapse frequency of p.
            </p>
          </div>

          <div
            className="h-72 w-full"
            role="img"
            aria-label="Reliability diagram comparing predicted lapse probability against observed lapse frequency on held-out S2"
          >
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={reliabilityChartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--line)" />
                <XAxis
                  dataKey="binLabel"
                  tick={{ fill: "var(--muted)", fontSize: 12 }}
                  label={{
                    value: "Predicted P(lapse in 90d) bin",
                    position: "insideBottom",
                    offset: -4,
                    fill: "var(--muted)",
                    fontSize: 12,
                  }}
                />
                <YAxis
                  domain={[0, 1]}
                  tick={{ fill: "var(--muted)", fontSize: 12 }}
                  label={{
                    value: "Observed 90d lapse rate",
                    angle: -90,
                    position: "insideLeft",
                    fill: "var(--muted)",
                    fontSize: 12,
                  }}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "var(--surface)",
                    borderColor: "var(--line)",
                    color: "var(--ink)",
                  }}
                />
                <Line
                  type="monotone"
                  dataKey="Ideal"
                  stroke="var(--muted)"
                  strokeDasharray="4 4"
                  dot={false}
                />
                <Line
                  type="monotone"
                  dataKey="Calibrated Logistic (primary)"
                  stroke="var(--lapse-3)"
                  strokeWidth={2.5}
                  connectNulls
                />
                <Line
                  type="monotone"
                  dataKey="Calibrated Depth-4 Tree"
                  stroke="var(--ink-2)"
                  strokeWidth={1.75}
                  connectNulls
                />
                <Line
                  type="monotone"
                  dataKey="Two-Bin Rule (recency > 90d)"
                  stroke="var(--muted)"
                  strokeWidth={1.5}
                  connectNulls
                />
              </LineChart>
            </ResponsiveContainer>
          </div>

          {/* Count Bar Underneath */}
          <div>
            <div className="text-small font-semibold mb-2">
              S2 customer count per predicted probability bin (primary calibrated logistic model)
            </div>
            <div
              className="h-40 w-full"
              role="img"
              aria-label="Histogram of S2 customer counts across the 10 predicted probability bins"
            >
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={reliabilityChartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--line)" />
                  <XAxis
                    dataKey="binLabel"
                    tick={{ fill: "var(--muted)", fontSize: 12 }}
                  />
                  <YAxis tick={{ fill: "var(--muted)", fontSize: 12 }} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "var(--surface)",
                      borderColor: "var(--line)",
                      color: "var(--ink)",
                    }}
                  />
                  <ReferenceLine x="0.6–0.7" stroke="var(--ink)" strokeDasharray="3 3" />
                  <Bar
                    dataKey="Customer Count (S2)"
                    fill="var(--lapse-3)"
                    radius={[4, 4, 0, 0]}
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </section>
      )}

      {/* Model vs Baselines Comparison Table */}
      {!loading && data && (
        <section className="card-surface flex flex-col gap-3">
          <div>
            <span className="label-caps">Model Selection (S1 CV) &amp; Final Held-Out Test (S2)</span>
            <h2 className="text-h2 mt-0.5">
              Calibrated logistic regression vs calibrated depth-4 tree and two-bin recency rule
            </h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-small">
              <thead>
                <tr style={{ borderBottom: "1px solid var(--line)" }}>
                  <th className="py-2.5 px-3">Split</th>
                  <th className="py-2.5 px-3">Model</th>
                  <th className="py-2.5 px-3 text-right">Customers</th>
                  <th className="py-2.5 px-3 text-right">Base Rate</th>
                  <th className="py-2.5 px-3 text-right">Mean Pred P</th>
                  <th className="py-2.5 px-3 text-right">Brier Score ↓</th>
                  <th className="py-2.5 px-3 text-right">Skill Score ↑</th>
                  <th className="py-2.5 px-3 text-right">ROC-AUC ↑</th>
                  <th className="py-2.5 px-3 text-right">Log Loss ↓</th>
                  <th className="py-2.5 px-3 text-right">10-Bin ECE ↓</th>
                </tr>
              </thead>
              <tbody>
                {[...data.s2_metrics, ...data.s1_cv_metrics].map((row, idx) => {
                  const isPrimaryS2 =
                    row.split === "S2_heldout_test" &&
                    row.model === "logistic_calibrated";
                  return (
                    <tr
                      key={idx}
                      style={{
                        borderBottom: "1px solid var(--line)",
                        backgroundColor: isPrimaryS2
                          ? "var(--surface-2)"
                          : "transparent",
                      }}
                    >
                      <td className="py-2.5 px-3 text-code text-xs">
                        {String(row.split)}
                      </td>
                      <td className="py-2.5 px-3 font-medium">
                        {String(row.model)}
                      </td>
                      <td className="py-2.5 px-3 text-right text-code">
                        {formatNumber(Number(row.n_customers))}
                      </td>
                      <td className="py-2.5 px-3 text-right text-code">
                        {Number(row.base_lapse_rate).toFixed(4)}
                      </td>
                      <td className="py-2.5 px-3 text-right text-code">
                        {Number(row.mean_predicted_p).toFixed(4)}
                      </td>
                      <td className="py-2.5 px-3 text-right text-code font-semibold">
                        {Number(row.brier_score).toFixed(4)}
                      </td>
                      <td className="py-2.5 px-3 text-right text-code">
                        +{(Number(row.brier_skill_score) * 100).toFixed(2)}%
                      </td>
                      <td className="py-2.5 px-3 text-right text-code">
                        {Number(row.roc_auc).toFixed(4)}
                      </td>
                      <td className="py-2.5 px-3 text-right text-code">
                        {Number(row.log_loss).toFixed(4)}
                      </td>
                      <td className="py-2.5 px-3 text-right text-code">
                        {Number(row.ece_10_bins).toFixed(4)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* High Value, Likely to Lapse Table (Top 20) */}
      {!loading && data && (
        <section className="card-surface flex flex-col gap-3">
          <div className="flex items-center justify-between">
            <div>
              <span className="label-caps">Actionable Priority Watchlist (Snapshot S3)</span>
              <h2 className="text-h2 mt-0.5">
                Top 20 high-monetary customers with the highest 90-day lapse risk
              </h2>
            </div>
            <span className="text-small" style={{ color: "var(--muted)" }}>
              Click any customer to inspect in drawer
            </span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-small">
              <thead>
                <tr style={{ borderBottom: "1px solid var(--line)" }}>
                  <th className="py-2.5 px-3">Customer</th>
                  <th className="py-2.5 px-3">Country</th>
                  <th className="py-2.5 px-3">Top Segment</th>
                  <th className="py-2.5 px-3">Segment Confidence</th>
                  <th className="py-2.5 px-3 text-right">Recency (d)</th>
                  <th className="py-2.5 px-3 text-right">Orders</th>
                  <th className="py-2.5 px-3 text-right">9m Spend</th>
                  <th className="py-2.5 px-3">P(Lapse in 90d)</th>
                </tr>
              </thead>
              <tbody>
                {data.high_value_at_risk.map((row) => {
                  const cid = Number(row.customer_id);
                  const seg = String(row.segment);
                  return (
                    <tr
                      key={cid}
                      onClick={() => onSelectCustomer(cid)}
                      className="cursor-pointer transition-smooth hover:opacity-90"
                      style={{ borderBottom: "1px solid var(--line)" }}
                    >
                      <td className="py-2.5 px-3 text-code font-semibold">
                        #{cid}
                      </td>
                      <td className="py-2.5 px-3">{String(row.country)}</td>
                      <td className="py-2.5 px-3">
                        <span className="inline-flex items-center gap-1.5 font-medium">
                          <span
                            className="w-2.5 h-2.5 rounded-full"
                            style={{
                              backgroundColor: segmentCssColor(
                                seg,
                                meta?.segments
                              ),
                            }}
                          />
                          <span>{seg}</span>
                        </span>
                      </td>
                      <td className="py-2.5 px-3">
                        <ProbabilityBar
                          value={Number(row.p_segment)}
                          segment={seg}
                          variant="segment"
                          segmentsMeta={meta?.segments}
                        />
                      </td>
                      <td className="py-2.5 px-3 text-right text-code">
                        {formatNumber(Number(row.recency_days))}
                      </td>
                      <td className="py-2.5 px-3 text-right text-code">
                        {formatNumber(Number(row.frequency))}
                      </td>
                      <td className="py-2.5 px-3 text-right text-code font-semibold">
                        {formatCurrency(Number(row.monetary))}
                      </td>
                      <td className="py-2.5 px-3">
                        <ProbabilityBar
                          value={Number(row.p_lapse_90d)}
                          variant="lapse"
                          threshold={0.66}
                        />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
};
