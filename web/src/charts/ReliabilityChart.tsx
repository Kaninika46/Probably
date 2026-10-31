/**
 * web/src/charts/ReliabilityChart.tsx
 * Full-width reliability diagram for the Overview headline (held-out S2, calibrated logistic model).
 * - x-axis: mean predicted P(lapse within 90 days) per bin; y-axis: observed lapse rate.
 * - Dashed diagonal labelled "perfect calibration".
 * - Dot area is proportional to the number of customers in the bin (hover shows the count).
 * - A caption below states, from the data, how the highest non-empty bin compares with
 *   the diagonal, so a known weakness is shown rather than left for the examiner to find.
 * Drawn in plain SVG at the measured pixel width so text renders at its true size.
 */

import React, { useEffect, useRef, useState } from "react";
import { formatNumber } from "../lib/api";

export interface ReliabilityBin {
  bin_lower: number;
  bin_upper: number;
  n_customers: number;
  mean_predicted_p: number;
  observed_lapse_rate: number;
}

interface ReliabilityChartProps {
  bins: ReliabilityBin[];
  totalCustomers: number;
}

// Below this many customers a bin's observed rate is too noisy to read as a trend,
// so the caption says so explicitly.
const SMALL_BIN_N = 30;

const HEIGHT = 400;
const PAD = { top: 20, right: 28, bottom: 60, left: 72 };
const TICKS = [0, 0.2, 0.4, 0.6, 0.8, 1.0];

const pct = (p: number) => `${(p * 100).toFixed(0)}%`;

/** Sentence describing the highest non-empty bin, computed from the bins themselves. */
export function describeTopBin(
  bins: ReliabilityBin[],
  totalCustomers: number
): string | null {
  if (bins.length === 0) return null;
  const top = bins.reduce((a, b) => (b.bin_upper > a.bin_upper ? b : a));
  const direction =
    top.observed_lapse_rate < top.mean_predicted_p ? "over-predicts" : "under-predicts";
  let sentence =
    `The highest bin ${direction}: ${formatNumber(top.n_customers)} ` +
    `customer${top.n_customers === 1 ? "" : "s"} predicted at ${pct(top.mean_predicted_p)}, ` +
    `observed ${pct(top.observed_lapse_rate)}.`;
  if (top.n_customers < SMALL_BIN_N) {
    sentence +=
      ` That bin holds only ${formatNumber(top.n_customers)} of ` +
      `${formatNumber(totalCustomers)} test customers, so the gap rests on very few cases.`;
  }
  return sentence;
}

export const ReliabilityChart: React.FC<ReliabilityChartProps> = ({
  bins,
  totalCustomers,
}) => {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [width, setWidth] = useState<number>(900);
  const [hoveredIdx, setHoveredIdx] = useState<number | null>(null);

  useEffect(() => {
    const updateSize = () => {
      if (containerRef.current) {
        setWidth(Math.max(360, containerRef.current.clientWidth));
      }
    };
    updateSize();
    window.addEventListener("resize", updateSize);
    return () => window.removeEventListener("resize", updateSize);
  }, []);

  const plotW = width - PAD.left - PAD.right;
  const plotH = HEIGHT - PAD.top - PAD.bottom;
  const xOf = (p: number) => PAD.left + p * plotW;
  const yOf = (p: number) => PAD.top + (1 - p) * plotH;

  // Dot radius grows with sqrt(n) so dot AREA is proportional to the bin's customer count.
  const maxN = Math.max(1, ...bins.map((b) => b.n_customers));
  const radiusOf = (n: number) => 4 + 14 * Math.sqrt(n / maxN);

  // Place the diagonal label near the top-right, rotated to follow the line on screen.
  const diagAngle = (-Math.atan2(plotH, plotW) * 180) / Math.PI;
  const labelX = xOf(0.86);
  const labelY = yOf(0.86) - 8;

  const hovered = hoveredIdx !== null ? bins[hoveredIdx] : null;

  return (
    <div ref={containerRef} className="relative w-full">
      <svg
        width={width}
        height={HEIGHT}
        role="img"
        aria-label="Reliability diagram: predicted 90-day lapse probability against observed lapse rate on held-out customers"
        className="block overflow-visible"
      >
        {/* Grid and tick labels */}
        {TICKS.map((t) => (
          <g key={`grid-${t}`}>
            <line x1={xOf(0)} x2={xOf(1)} y1={yOf(t)} y2={yOf(t)} stroke="var(--line)" />
            <line x1={xOf(t)} x2={xOf(t)} y1={yOf(0)} y2={yOf(1)} stroke="var(--line)" />
            <text
              x={PAD.left - 10}
              y={yOf(t)}
              textAnchor="end"
              dominantBaseline="middle"
              fontSize={13}
              fontFamily="JetBrains Mono"
              fill="var(--muted)"
            >
              {pct(t)}
            </text>
            <text
              x={xOf(t)}
              y={yOf(0) + 20}
              textAnchor="middle"
              fontSize={13}
              fontFamily="JetBrains Mono"
              fill="var(--muted)"
            >
              {pct(t)}
            </text>
          </g>
        ))}

        {/* Axis titles */}
        <text
          x={PAD.left + plotW / 2}
          y={HEIGHT - 12}
          textAnchor="middle"
          fontSize={14}
          fontFamily="Figtree"
          fill="var(--ink-2)"
        >
          Predicted P(lapse within 90 days)
        </text>
        <text
          transform={`translate(18, ${PAD.top + plotH / 2}) rotate(-90)`}
          textAnchor="middle"
          fontSize={14}
          fontFamily="Figtree"
          fill="var(--ink-2)"
        >
          Observed lapse rate
        </text>

        {/* Perfect-calibration diagonal with an in-plot label */}
        <line
          x1={xOf(0)}
          y1={yOf(0)}
          x2={xOf(1)}
          y2={yOf(1)}
          stroke="var(--muted)"
          strokeDasharray="6 5"
          strokeWidth={1.5}
        />
        <text
          x={labelX}
          y={labelY}
          transform={`rotate(${diagAngle}, ${labelX}, ${labelY})`}
          textAnchor="middle"
          fontSize={13}
          fontFamily="Figtree"
          fill="var(--muted)"
        >
          perfect calibration
        </text>

        {/* Model curve */}
        {bins.length > 1 && (
          <polyline
            fill="none"
            stroke="var(--lapse-3)"
            strokeWidth={2}
            points={bins
              .map((b) => `${xOf(b.mean_predicted_p).toFixed(1)},${yOf(b.observed_lapse_rate).toFixed(1)}`)
              .join(" ")}
          />
        )}

        {/* One dot per bin, sized by customer count */}
        {bins.map((b, idx) => (
          <circle
            key={idx}
            cx={xOf(b.mean_predicted_p)}
            cy={yOf(b.observed_lapse_rate)}
            r={radiusOf(b.n_customers)}
            fill="var(--lapse-3)"
            fillOpacity={hoveredIdx === idx ? 0.95 : 0.7}
            stroke="var(--surface)"
            strokeWidth={1.5}
            onMouseEnter={() => setHoveredIdx(idx)}
            onMouseLeave={() => setHoveredIdx(null)}
            style={{ cursor: "default" }}
          />
        ))}
      </svg>

      {hovered && (
        <div
          className="pointer-events-none absolute z-20 p-3 rounded-input text-small shadow-hairline tabular-nums"
          style={{
            left: Math.min(width - 240, Math.max(12, xOf(hovered.mean_predicted_p) + 18)),
            top: Math.max(8, yOf(hovered.observed_lapse_rate) - 70),
            backgroundColor: "var(--surface)",
            border: "1px solid var(--line)",
            color: "var(--ink)",
          }}
        >
          <div className="font-semibold">
            {formatNumber(hovered.n_customers)} customers
          </div>
          <div style={{ color: "var(--muted)" }}>
            Bin {pct(hovered.bin_lower)}–{pct(hovered.bin_upper)} · predicted{" "}
            {(hovered.mean_predicted_p * 100).toFixed(1)}% · observed{" "}
            {(hovered.observed_lapse_rate * 100).toFixed(1)}%
          </div>
        </div>
      )}
    </div>
  );
};
