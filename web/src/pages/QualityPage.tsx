/**
 * web/src/pages/QualityPage.tsx
 * Page 5 (`/quality`): Model Quality & Evaluation page (`FRONTEND.md` section 4.5).
 * Reads `GET /api/quality` (`cleaning_funnel`, `gmm_grid`, `bootstrap_ari_histogram`,
 * `segment_stability`, `tree_fidelity`, `nl_summary`, `test_set_status`):
 * - Cleaning funnel as stepped horizontal bars
 * - BIC chart by K and covariance type
 * - Bootstrap ARI histogram (B = 100)
 * - Per-segment Jaccard bars with the 0.75 Hennig stability reference line
 * - NL dev metrics + honest test-set status ("Test set: waiting for questions written by someone else")
 */

import React, { useEffect, useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  MetaResponse,
  QualityResponse,
  api,
  formatCurrency,
  formatNumber,
  segmentCssColor,
} from "../lib/api";

interface QualityPageProps {
  meta: MetaResponse | null;
}

export const QualityPage: React.FC<QualityPageProps> = ({ meta }) => {
  const [data, setData] = useState<QualityResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api
      .getQuality()
      .then((res) => {
        if (!cancelled) {
          setData(res);
          setLoading(false);
        }
      })
      .catch((err: Error) => {
        if (!cancelled) {
          setError(err.message || "Could not load quality metrics.");
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Pivot GMM BIC grid by K (2..8) across the 4 covariance types
  const bicChartData = useMemo(() => {
    if (!data) return [];
    const ks = [2, 3, 4, 5, 6, 7, 8];
    return ks.map((k) => {
      const rowsForK = data.gmm_grid.filter((r) => Number(r.k) === k);
      const findBic = (cov: string) => {
        const found = rowsForK.find((r) => r.covariance_type === cov);
        return found ? Math.round(Number(found.bic)) : null;
      };
      return {
        k: `K=${k}`,
        spherical: findBic("spherical"),
        tied: findBic("tied"),
        diag: findBic("diag"),
        full: findBic("full"),
      };
    });
  }, [data]);

  const ariHistData = useMemo(() => {
    if (!data) return [];
    return data.bootstrap_ari_histogram.map((b) => ({
      bin: `${b.bin_lower.toFixed(2)}–${b.bin_upper.toFixed(2)}`,
      Resamples: b.count,
    }));
  }, [data]);

  const jaccardData = useMemo(() => {
    if (!data) return [];
    return data.segment_stability.map((s) => ({
      segment: String(s.segment),
      jaccard: Number(s.jaccard_mean),
    }));
  }, [data]);

  const nlDev = data?.nl_summary.find((r) => r.split === "dev");

  return (
    <div className="flex flex-col gap-6">
      <div>
        <span className="label-caps">
          End-to-End Pipeline Audit · Data Cleaning, Clustering Stability &amp; NL Evaluation
        </span>
        <h1 className="text-h1 mt-1">Model Quality &amp; Verification</h1>
      </div>

      {error && <div className="card-surface text-small">{error}</div>}

      {loading || !data ? (
        <div className="flex flex-col gap-4">
          <div
            className="h-64 rounded-card animate-pulse"
            style={{ backgroundColor: "var(--surface)" }}
          />
          <div
            className="h-72 rounded-card animate-pulse"
            style={{ backgroundColor: "var(--surface)" }}
          />
        </div>
      ) : (
        <>
          {/* 1. Cleaning Funnel as Stepped Horizontal Bars */}
          <section className="card-surface flex flex-col gap-4">
            <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-2">
              <div>
                <span className="label-caps">Phase 1 · Six-Step SQL Cleaning Funnel</span>
                <h2 className="text-h2 mt-0.5">
                  Rows remaining after each rule, from {formatNumber(Number(data.raw_totals.n_rows))} raw rows to {formatNumber(Number(data.clean_sales_summary.n_lines_with_customer))} customer-identified sales
                </h2>
              </div>
              <div className="text-small tabular-nums" style={{ color: "var(--muted)" }}>
                Raw net: <strong className="text-code">{formatCurrency(Number(data.raw_totals.total_revenue))}</strong> · Clean sales:{" "}
                <strong className="text-code">{formatCurrency(Number(data.clean_sales_summary.total_revenue))}</strong> · With customer:{" "}
                <strong className="text-code">{formatCurrency(Number(data.clean_sales_summary.revenue_with_customer))}</strong>
              </div>
            </div>

            <div
              className="flex flex-col gap-2.5"
              role="img"
              aria-label="Stepped horizontal bar chart of the 6-step data cleaning funnel"
            >
              {[
                {
                  step: "0",
                  rule: "Raw transactions (both workbook sheets)",
                  rowsAfter: Number(data.raw_totals.n_rows),
                  removed: 0,
                  revAffected: 0,
                  shareRaw: 0,
                },
                ...data.cleaning_funnel.map((r) => ({
                  step: String(r.step_no),
                  rule: String(r.rule),
                  rowsAfter: Number(r.rows_after),
                  removed: Number(r.rows_removed),
                  revAffected: Number(r.revenue_affected),
                  shareRaw: Number(r.share_of_raw_revenue_pct),
                })),
              ].map((item) => {
                const pct =
                  (item.rowsAfter / Number(data.raw_totals.n_rows)) * 100;
                return (
                  <div key={item.step} className="flex flex-col gap-1">
                    <div className="flex items-center justify-between text-small">
                      <span className="font-medium">
                        {item.step === "0"
                          ? item.rule
                          : `Step ${item.step} · ${item.rule}`}
                      </span>
                      <span className="text-code text-xs tabular-nums">
                        <strong>{formatNumber(item.rowsAfter)}</strong> rows (
                        {pct.toFixed(1)}%)
                        {item.removed > 0 && (
                          <span style={{ color: "var(--muted)" }}>
                            {" "}
                            · −{formatNumber(item.removed)} rows (
                            {formatCurrency(item.revAffected)},{" "}
                            {item.shareRaw.toFixed(2)}% of raw)
                          </span>
                        )}
                      </span>
                    </div>
                    <div
                      className="h-3 w-full rounded-full overflow-hidden"
                      style={{ backgroundColor: "var(--surface-2)" }}
                    >
                      <div
                        className="h-full rounded-full transition-smooth"
                        style={{
                          width: `${pct.toFixed(2)}%`,
                          backgroundColor: "var(--ink)",
                        }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </section>

          {/* 2. BIC Chart by K and Covariance Type + 3. Bootstrap ARI Histogram */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <section className="card-surface flex flex-col gap-3">
              <div>
                <span className="label-caps">Phase 3 · GMM Model Selection Grid</span>
                <h2 className="text-h2 mt-0.5">
                  BIC across K = 2..8 by covariance structure (diag/full collapse on integer frequency)
                </h2>
              </div>
              <div
                className="h-64 w-full"
                role="img"
                aria-label="Line chart of GMM BIC scores across K=2 to K=8 for spherical, tied, diag, and full covariance types"
              >
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={bicChartData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--line)" />
                    <XAxis
                      dataKey="k"
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
                    <Line
                      type="monotone"
                      dataKey="spherical"
                      stroke="var(--ink)"
                      strokeWidth={2.5}
                    />
                    <Line
                      type="monotone"
                      dataKey="tied"
                      stroke="var(--ink-2)"
                      strokeWidth={2}
                    />
                    <Line
                      type="monotone"
                      dataKey="diag"
                      stroke="var(--muted)"
                      strokeDasharray="4 4"
                    />
                    <Line
                      type="monotone"
                      dataKey="full"
                      stroke="var(--muted)"
                      strokeDasharray="2 2"
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
              <p className="text-small" style={{ color: "var(--muted)" }}>
                <code>diag</code> and <code>full</code> produce negative BIC because components collapse onto the discrete planes <code>frequency = 1</code> (1,480 customers) and <code>frequency = 2</code> (781 customers).
              </p>
            </section>

            <section className="card-surface flex flex-col gap-3">
              <div>
                <span className="label-caps">
                  Phase 4 · Bootstrap Co-Assignment Stability (B = 100)
                </span>
                <h2 className="text-h2 mt-0.5">
                  Adjusted Rand Index vs reference GMM (median{" "}
                  {Number(data.bootstrap_stability.ari_median).toFixed(4)}, IQR{" "}
                  {Number(data.bootstrap_stability.ari_iqr).toFixed(4)})
                </h2>
              </div>
              <div
                className="h-64 w-full"
                role="img"
                aria-label="Histogram of bootstrap Adjusted Rand Index across 100 resamples"
              >
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={ariHistData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--line)" />
                    <XAxis
                      dataKey="bin"
                      tick={{ fill: "var(--muted)", fontSize: 11 }}
                    />
                    <YAxis
                      tick={{ fill: "var(--muted)", fontSize: 12 }}
                      label={{
                        value: "Resamples",
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
                    <Bar
                      dataKey="Resamples"
                      fill="var(--ink)"
                      radius={[4, 4, 0, 0]}
                    />
                  </BarChart>
                </ResponsiveContainer>
              </div>
              <p className="text-small" style={{ color: "var(--muted)" }}>
                Each resample draws 3,961 customers with replacement, refits spherical K=5 GMM, and aligns labels via Hungarian matching (<code>linear_sum_assignment</code>).
              </p>
            </section>
          </div>

          {/* 4. Per-Segment Jaccard Bars with 0.75 Reference Line + Surrogate Tree Fidelity */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            <section className="lg:col-span-7 card-surface flex flex-col gap-3">
              <div>
                <span className="label-caps">
                  Hennig (2007) Clusterwise Jaccard Stability
                </span>
                <h2 className="text-h2 mt-0.5">
                  All 5 segments exceed the 0.75 stability threshold across B = 100 resamples
                </h2>
              </div>
              <div
                className="h-60 w-full"
                role="img"
                aria-label="Bar chart of mean bootstrap Jaccard similarity per segment with 0.75 reference line"
              >
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={jaccardData} layout="vertical">
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--line)" />
                    <XAxis
                      type="number"
                      domain={[0, 1]}
                      tick={{ fill: "var(--muted)", fontSize: 12 }}
                    />
                    <YAxis
                      type="category"
                      dataKey="segment"
                      width={95}
                      tick={{ fill: "var(--ink)", fontSize: 12 }}
                    />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: "var(--surface)",
                        borderColor: "var(--line)",
                        color: "var(--ink)",
                      }}
                    />
                    <ReferenceLine
                      x={0.75}
                      stroke="var(--ink)"
                      strokeDasharray="4 4"
                      label={{
                        value: "Stable ≥ 0.75",
                        position: "top",
                        fill: "var(--ink)",
                        fontSize: 11,
                      }}
                    />
                    <Bar dataKey="jaccard" radius={[0, 4, 4, 0]}>
                      {jaccardData.map((entry) => (
                        <Cell
                          key={entry.segment}
                          fill={segmentCssColor(entry.segment, meta?.segments)}
                        />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </section>

            <section className="lg:col-span-5 card-surface flex flex-col justify-between gap-4">
              <div>
                <span className="label-caps">
                  Phase 4 · Decision-Tree Surrogate Fidelity (Dasgupta et al. 2020)
                </span>
                <h2 className="text-h2 mt-0.5">
                  Depth-{data.tree_fidelity.actual_depth} tree ({data.tree_fidelity.n_leaves} leaves) matches{" "}
                  {Number(data.tree_fidelity.test_fidelity_pct).toFixed(2)}% on held-out 30% test split
                </h2>
                <p className="text-small mt-1" style={{ color: "var(--muted)" }}>
                  Tree explanations in original R/F/M units are interpretable approximations of curved log-space GMM boundaries (train fidelity{" "}
                  {Number(data.tree_fidelity.train_fidelity_pct).toFixed(2)}%).
                </p>
              </div>

              <table className="w-full text-small border-collapse">
                <thead>
                  <tr style={{ borderBottom: "1px solid var(--line)" }}>
                    <th className="py-1.5 text-left">Segment</th>
                    <th className="py-1.5 text-right">Test Customers</th>
                    <th className="py-1.5 text-right">Matched</th>
                    <th className="py-1.5 text-right">Fidelity</th>
                  </tr>
                </thead>
                <tbody>
                  {data.tree_fidelity_by_segment.map((r) => (
                    <tr
                      key={String(r.segment)}
                      style={{ borderBottom: "1px solid var(--line)" }}
                    >
                      <td className="py-1.5 font-medium">{String(r.segment)}</td>
                      <td className="py-1.5 text-right text-code">
                        {formatNumber(Number(r.n_test_customers))}
                      </td>
                      <td className="py-1.5 text-right text-code">
                        {formatNumber(Number(r.n_matched))}
                      </td>
                      <td className="py-1.5 text-right text-code font-semibold">
                        {Number(r.test_fidelity_pct).toFixed(2)}%
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          </div>

          {/* 5. NL Dev Metrics & Honest Test-Set Status */}
          <section className="card-surface flex flex-col gap-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
              <div>
                <span className="label-caps">
                  Phase 7 · Natural-Language Engine Evaluation (Spider / BIRD Execution Accuracy)
                </span>
                <h2 className="text-h2 mt-0.5">
                  Development benchmark ({nlDev ? String(nlDev.n_total_questions) : 26} questions: {nlDev ? String(nlDev.n_in_scope) : 21} in-scope, {nlDev ? String(nlDev.n_out_of_scope) : 5} out-of-scope)
                </h2>
              </div>

              <span
                className="px-3 py-1.5 rounded-full text-small font-medium"
                style={{
                  backgroundColor: "var(--surface-2)",
                  border: "1px solid var(--line)",
                  color: "var(--ink)",
                }}
              >
                {data.test_set_status}
              </span>
            </div>

            {nlDev && (
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                <div
                  className="p-3.5 rounded-input"
                  style={{
                    backgroundColor: "var(--bg)",
                    border: "1px solid var(--line)",
                  }}
                >
                  <div className="label-caps">Execution Accuracy (Dev)</div>
                  <div className="text-h1 mt-1 tabular-nums">
                    {Number(nlDev.overall_execution_accuracy_pct).toFixed(1)}%
                  </div>
                </div>
                <div
                  className="p-3.5 rounded-input"
                  style={{
                    backgroundColor: "var(--bg)",
                    border: "1px solid var(--line)",
                  }}
                >
                  <div className="label-caps">Template Match Rate</div>
                  <div className="text-h1 mt-1 tabular-nums">
                    {Number(nlDev.template_match_rate_pct).toFixed(1)}%
                  </div>
                </div>
                <div
                  className="p-3.5 rounded-input"
                  style={{
                    backgroundColor: "var(--bg)",
                    border: "1px solid var(--line)",
                  }}
                >
                  <div className="label-caps">Out-of-Scope Rejection</div>
                  <div className="text-h1 mt-1 tabular-nums">
                    {Number(nlDev.out_of_scope_rejection_rate_pct).toFixed(1)}%
                  </div>
                </div>
                <div
                  className="p-3.5 rounded-input"
                  style={{
                    backgroundColor: "var(--bg)",
                    border: "1px solid var(--line)",
                  }}
                >
                  <div className="label-caps">Hedge Threshold Accuracy</div>
                  <div className="text-h1 mt-1 tabular-nums">
                    {Number(nlDev.hedge_threshold_accuracy_pct).toFixed(1)}%
                  </div>
                </div>
              </div>
            )}
          </section>
        </>
      )}
    </div>
  );
};
