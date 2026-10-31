/**
 * web/src/pages/SegmentsPage.tsx
 * Page 3 (`/segments`): Segments page (`FRONTEND.md` section 4.3).
 * - Full-width UncertaintyMap (`GET /api/segments/map`).
 * - Five segment cards (`GET /api/segments`): name, colour, hard vs expected count,
 *   median R/F/M, surrogate decision-tree rule, and max-p mini histogram.
 * - Bar chart of hard vs expected size per segment.
 */

import React, { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  MetaResponse,
  SegmentsMapResponse,
  SegmentsResponse,
  api,
  formatCurrency,
  formatNumber,
  segmentCssColor,
} from "../lib/api";
import { UncertaintyMap } from "../charts/UncertaintyMap";

interface SegmentsPageProps {
  meta: MetaResponse | null;
  theme: "light" | "dark";
  onSelectCustomer: (customerId: number) => void;
}

export const SegmentsPage: React.FC<SegmentsPageProps> = ({
  meta,
  theme,
  onSelectCustomer,
}) => {
  const [method, setMethod] = useState<"gmm" | "bootstrap">("gmm");
  const [segmentsData, setSegmentsData] = useState<SegmentsResponse | null>(
    null
  );
  const [mapData, setMapData] = useState<SegmentsMapResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    Promise.all([api.getSegments(method), api.getSegmentsMap(method)])
      .then(([segRes, mapRes]) => {
        if (!cancelled) {
          setSegmentsData(segRes);
          setMapData(mapRes);
          setLoading(false);
        }
      })
      .catch((err: Error) => {
        if (!cancelled) {
          setError(err.message || "Could not load segments.");
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [method]);

  const sizeComparisonData = (segmentsData?.segments || []).map((s) => ({
    name: s.name,
    "K-Means hard count": s.kmeans_hard_count,
    [`${method.toUpperCase()} hard count`]: s.hard_count,
    [`${method.toUpperCase()} expected size Σp`]: s.expected_size,
  }));

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-2">
        <div>
          <span className="label-caps">
            Topic 3 (KDD Segmentation) × Topic 1 (BID Probabilistic Table)
          </span>
          <h1 className="text-h1 mt-1">
            Customer Segments &amp; Boundary Uncertainty (PROVISIONAL K = 5)
          </h1>
        </div>
        {segmentsData && (
          <div className="text-small tabular-nums" style={{ color: "var(--muted)" }}>
            Boundary share (max p &lt; 0.60):{" "}
            <strong className="text-code" style={{ color: "var(--ink)" }}>
              {segmentsData.boundary_share_pct.toFixed(2)}%
            </strong>{" "}
            ({formatNumber(segmentsData.boundary_count)} customers) · Mean entropy:{" "}
            <strong className="text-code" style={{ color: "var(--ink)" }}>
              {segmentsData.mean_normalised_entropy.toFixed(4)}
            </strong>
          </div>
        )}
      </div>

      {error && <div className="card-surface text-small">{error}</div>}

      {/* Full-Width Uncertainty Map */}
      {loading || !mapData ? (
        <div
          className="h-[510px] rounded-card animate-pulse"
          style={{ backgroundColor: "var(--surface)" }}
        />
      ) : (
        <UncertaintyMap
          points={mapData.points}
          method={method}
          onMethodChange={setMethod}
          onSelectCustomer={onSelectCustomer}
          segmentsMeta={meta?.segments}
          theme={theme}
        />
      )}

      {/* Five Segment Cards */}
      <section className="flex flex-col gap-3">
        <span className="label-caps">
          Five S3 Segment Profiles in Original Units · Median R/F/M, Surrogate Tree Rule &amp; Max-p Histogram
        </span>

        {loading || !segmentsData ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {[0, 1, 2, 3, 4].map((i) => (
              <div
                key={i}
                className="h-64 rounded-card animate-pulse"
                style={{ backgroundColor: "var(--surface)" }}
              />
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {segmentsData.segments.map((seg) => {
              const maxHistCount = Math.max(
                ...seg.max_p_histogram.map((b) => b.count),
                1
              );
              const colorVar = segmentCssColor(seg.name, meta?.segments);

              return (
                <article
                  key={seg.name}
                  className="card-surface flex flex-col justify-between gap-4"
                >
                  <div>
                    <div className="flex items-center justify-between">
                      <div className="inline-flex items-center gap-2">
                        <span
                          className="w-3 h-3 rounded-full"
                          style={{ backgroundColor: colorVar }}
                        />
                        <h2 className="text-h2">{seg.name}</h2>
                      </div>
                      <span
                        className="text-code text-xs px-2 py-0.5 rounded-full"
                        style={{
                          backgroundColor: "var(--surface-2)",
                          color: "var(--ink-2)",
                        }}
                      >
                        Jaccard {seg.jaccard_mean.toFixed(2)} · AvePP{" "}
                        {seg.ave_pp.toFixed(2)}
                      </span>
                    </div>
                    <p
                      className="text-small mt-1"
                      style={{ color: "var(--muted)" }}
                    >
                      {seg.description}
                    </p>

                    {/* Hard vs Expected Size */}
                    <div
                      className="grid grid-cols-2 gap-2 mt-3 p-3 rounded-input"
                      style={{
                        backgroundColor: "var(--bg)",
                        border: "1px solid var(--line)",
                      }}
                    >
                      <div>
                        <div className="label-caps">Hard Count</div>
                        <div className="text-h2 mt-0.5 tabular-nums">
                          {formatNumber(seg.hard_count)}
                        </div>
                        <div
                          className="text-xs"
                          style={{ color: "var(--muted)" }}
                        >
                          {seg.share_of_customers_pct.toFixed(1)}% of S3
                        </div>
                      </div>
                      <div>
                        <div className="label-caps">Expected Size Σp</div>
                        <div className="text-h2 mt-0.5 tabular-nums">
                          {formatNumber(seg.expected_size, 2)}
                        </div>
                        <div
                          className="text-xs text-code"
                          style={{ color: "var(--muted)" }}
                        >
                          ±{seg.std_dev.toFixed(2)} SD
                        </div>
                      </div>
                    </div>

                    {/* Median R / F / M */}
                    <div className="grid grid-cols-3 gap-2 mt-3 text-center">
                      <div
                        className="p-2 rounded"
                        style={{ backgroundColor: "var(--surface-2)" }}
                      >
                        <div className="label-caps">Med Recency</div>
                        <div className="text-code font-semibold mt-0.5">
                          {seg.median_recency_days}d
                        </div>
                      </div>
                      <div
                        className="p-2 rounded"
                        style={{ backgroundColor: "var(--surface-2)" }}
                      >
                        <div className="label-caps">Med Orders</div>
                        <div className="text-code font-semibold mt-0.5">
                          {seg.median_frequency}
                        </div>
                      </div>
                      <div
                        className="p-2 rounded"
                        style={{ backgroundColor: "var(--surface-2)" }}
                      >
                        <div className="label-caps">Med Spend</div>
                        <div className="text-code font-semibold mt-0.5">
                          {formatCurrency(seg.median_monetary)}
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Mini Histogram of max-p */}
                  <div>
                    <div className="flex justify-between text-xs mb-1" style={{ color: "var(--muted)" }}>
                      <span>Confidence distribution (max p)</span>
                      <span className="text-code">0.20 → 1.00</span>
                    </div>
                    <div
                      className="h-12 flex items-end gap-1 pt-2 px-2 rounded"
                      style={{ backgroundColor: "var(--surface-2)" }}
                      role="img"
                      aria-label={`Histogram of maximum membership probability for ${seg.name}`}
                    >
                      {seg.max_p_histogram.map((b, idx) => {
                        const pct = Math.max(
                          4,
                          Math.round((b.count / maxHistCount) * 100)
                        );
                        return (
                          <div
                            key={idx}
                            className="flex-1 rounded-t transition-smooth"
                            title={`${b.bin_lower.toFixed(2)}–${b.bin_upper.toFixed(2)}: ${b.count} customers`}
                            style={{
                              height: `${pct}%`,
                              backgroundColor: colorVar,
                              opacity: b.bin_upper <= 0.6 ? 0.45 : 0.9,
                            }}
                          />
                        );
                      })}
                    </div>

                    {/* Decision-tree surrogate rule */}
                    <details className="mt-3 text-small">
                      <summary
                        className="cursor-pointer font-medium select-none"
                        style={{ color: "var(--ink-2)" }}
                      >
                        Surrogate decision-tree rule (approx.)
                      </summary>
                      <pre
                        className="mt-1.5 p-2.5 rounded text-code text-xs whitespace-pre-wrap"
                        style={{
                          backgroundColor: "var(--surface-2)",
                          color: "var(--ink-2)",
                        }}
                      >
                        {seg.tree_rule}
                      </pre>
                    </details>
                  </div>
                </article>
              );
            })}
          </div>
        )}
      </section>

      {/* Bar Chart of Hard vs Expected Size per Segment */}
      {segmentsData && (
        <section className="card-surface flex flex-col gap-3">
          <div>
            <span className="label-caps">Probabilistic vs Hard Counting</span>
            <h2 className="text-h2 mt-0.5">
              Hard K-Means and {method.toUpperCase()} counts compared with expected segment sizes Σp
            </h2>
          </div>
          <div
            className="h-72 w-full"
            role="img"
            aria-label="Bar chart comparing K-Means hard count, GMM hard count, and probabilistic expected size per segment"
          >
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={sizeComparisonData}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--line)" />
                <XAxis
                  dataKey="name"
                  tick={{ fill: "var(--muted)", fontSize: 12 }}
                />
                <YAxis
                  tick={{ fill: "var(--muted)", fontSize: 12 }}
                  label={{
                    value: "Customers",
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
                  dataKey="K-Means hard count"
                  fill="var(--muted)"
                  radius={[4, 4, 0, 0]}
                />
                <Bar
                  dataKey={`${method.toUpperCase()} hard count`}
                  fill="var(--ink-2)"
                  radius={[4, 4, 0, 0]}
                />
                <Bar
                  dataKey={`${method.toUpperCase()} expected size Σp`}
                  fill="var(--ink)"
                  radius={[4, 4, 0, 0]}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </section>
      )}
    </div>
  );
};
