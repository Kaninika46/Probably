/**
 * web/src/charts/UncertaintyMap.tsx
 * Signature component #3: 3,961-point customer uncertainty scatter map (`GET /api/segments/map`).
 * - x-axis: days since last purchase on a square-root scale (reversed, so recent buyers are on
 *   the right). Recency is right-skewed (most customers bought recently), so a linear axis
 *   piles them against the right edge; sqrt spreads the recent region out.
 * - x jitter: +/-0.4 days per customer, fixed by customer id, to break up whole-day stripes
 * - y-axis: 9-month monetary spend on a log10 scale
 * - colour: segment (Okabe-Ito tokens)
 * - opacity: membership confidence `max_p` mapped to alpha in [0.35, 0.95]
 * - caption: "Faded dots are customers between segments."
 * - includes method toggle (`gmm` vs `bootstrap`), hover tooltip, and click-to-open CustomerDrawer.
 */

import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  CustomerMapPoint,
  SegmentColorInfo,
  formatCurrency,
  formatNumber,
} from "../lib/api";

interface UncertaintyMapProps {
  points: CustomerMapPoint[];
  method: "gmm" | "bootstrap";
  onMethodChange: (method: "gmm" | "bootstrap") => void;
  onSelectCustomer: (customerId: number) => void;
  segmentsMeta?: SegmentColorInfo[];
  theme: "light" | "dark";
}

// Half-width of the horizontal jitter, in days. Recency is a whole number of days, which
// draws vertical stripes; a small, fixed offset per customer breaks them up.
const JITTER_DAYS = 0.4;

/** Stable pseudo-random number in [0, 1) derived from the customer id (same on every render). */
function seededUnit(id: number): number {
  // Knuth multiplicative hash; Math.imul keeps the product in 32-bit integer arithmetic.
  return (Math.imul(id, 2654435761) >>> 0) / 4294967296;
}

/** Map recency (days) to [0, 1] across the plot, square-root scaled and reversed. */
function recencyToXNorm(days: number, maxDays: number): number {
  return 1 - Math.sqrt(Math.max(0, days) / maxDays);
}

interface ProjectedPoint {
  px: number;
  py: number;
  raw: CustomerMapPoint;
}

export const UncertaintyMap: React.FC<UncertaintyMapProps> = ({
  points,
  method,
  onMethodChange,
  onSelectCustomer,
  segmentsMeta,
  theme,
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [width, setWidth] = useState<number>(880);
  const [hovered, setHovered] = useState<ProjectedPoint | null>(null);
  const [filterSegment, setFilterSegment] = useState<string | null>(null);
  const [onlyBoundary, setOnlyBoundary] = useState<boolean>(false);

  const height = 430;
  const pad = { top: 24, right: 28, bottom: 46, left: 68 };

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

  const colorMap = useMemo(() => {
    const styles = getComputedStyle(document.documentElement);
    const readVar = (v: string) => styles.getPropertyValue(v).trim();

    const map: Record<string, string> = {
      Champions: readVar("--seg-champions"),
      Loyal: readVar("--seg-loyal"),
      New: readVar("--seg-new"),
      "At-Risk": readVar("--seg-at-risk"),
      Hibernating: readVar("--seg-hibernating"),
      line: readVar("--line"),
      muted: readVar("--muted"),
      ink: readVar("--ink"),
    };
    return map;
  }, [theme, segmentsMeta]);

  const { projected, maxRecency, minLogM, maxLogM } = useMemo(() => {
    if (points.length === 0) {
      return { projected: [], maxRecency: 275, minLogM: 1, maxLogM: 5.4 };
    }
    const maxR = Math.max(...points.map((p) => p.recency_days), 275);
    const minL = 1.0; // £10
    const maxL = Math.log10(
      Math.max(...points.map((p) => Math.max(10, p.monetary)), 100000)
    );

    const plotW = width - pad.left - pad.right;
    const plotH = height - pad.top - pad.bottom;

    const proj: ProjectedPoint[] = [];
    for (const pt of points) {
      if (filterSegment && pt.segment !== filterSegment) continue;
      if (onlyBoundary && pt.max_p >= 0.6) continue;

      // Reversed sqrt X: oldest on the left, 0 days on the right; jitter is display-only
      const jitteredDays = pt.recency_days + (seededUnit(pt.id) * 2 - 1) * JITTER_DAYS;
      const xNorm = recencyToXNorm(jitteredDays, maxR);
      const logM = Math.log10(Math.max(10, pt.monetary));
      const yNorm = (logM - minL) / (maxL - minL);

      const px = pad.left + Math.max(0, Math.min(1, xNorm)) * plotW;
      const py = pad.top + (1 - Math.max(0, Math.min(1, yNorm))) * plotH;
      proj.push({ px, py, raw: pt });
    }
    return {
      projected: proj,
      maxRecency: maxR,
      minLogM: minL,
      maxLogM: maxL,
    };
  }, [points, width, filterSegment, onlyBoundary]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const dpr = window.devicePixelRatio || 1;
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    ctx.save();
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, width, height);

    const plotW = width - pad.left - pad.right;
    const plotH = height - pad.top - pad.bottom;

    // Grid lines and axis labels
    ctx.strokeStyle = colorMap.line;
    ctx.fillStyle = colorMap.muted;
    ctx.lineWidth = 1;
    ctx.font = "12px 'JetBrains Mono', monospace";

    // Y-axis ticks (£10, £100, £1k, £10k, £100k)
    const yTicks = [10, 100, 1000, 10000, 100000];
    for (const val of yTicks) {
      const logV = Math.log10(val);
      if (logV < minLogM || logV > maxLogM) continue;
      const yNorm = (logV - minLogM) / (maxLogM - minLogM);
      const y = pad.top + (1 - yNorm) * plotH;
      ctx.beginPath();
      ctx.moveTo(pad.left, y);
      ctx.lineTo(width - pad.right, y);
      ctx.stroke();

      ctx.textAlign = "right";
      ctx.textBaseline = "middle";
      const label = val >= 1000 ? `£${val / 1000}k` : `£${val}`;
      ctx.fillText(label, pad.left - 8, y);
    }

    // X-axis ticks chosen to sit evenly on the square-root scale
    const xTicks = [270, 120, 60, 30, 14, 7, 1];
    for (const days of xTicks) {
      const xNorm = recencyToXNorm(days, maxRecency);
      const x = pad.left + xNorm * plotW;
      ctx.beginPath();
      ctx.moveTo(x, pad.top);
      ctx.lineTo(x, height - pad.bottom);
      ctx.stroke();

      ctx.textAlign = "center";
      ctx.textBaseline = "top";
      ctx.fillText(`${days}d`, x, height - pad.bottom + 8);
    }

    // Axis titles
    ctx.font = "13px 'Figtree', sans-serif";
    ctx.fillStyle = colorMap.muted;
    ctx.textAlign = "center";
    ctx.fillText(
      "Days since last purchase (reversed: most recent on right →)",
      pad.left + plotW / 2,
      height - 14
    );

    ctx.save();
    ctx.translate(16, pad.top + plotH / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.fillText("9-month spend (£, log scale)", 0, 0);
    ctx.restore();

    // Draw customer points: opacity maps max_p from [0.2, 1.0] -> [0.35, 0.95].
    // The 0.35 floor keeps the least certain customers visible on a projector.
    for (const item of projected) {
      const { px, py, raw } = item;
      const alpha = Math.max(0.35, Math.min(0.95, 0.35 + ((raw.max_p - 0.2) / 0.8) * 0.6));
      ctx.beginPath();
      ctx.arc(px, py, raw.max_p < 0.6 ? 3.2 : 2.8, 0, Math.PI * 2);
      ctx.fillStyle = colorMap[raw.segment] || colorMap.ink;
      ctx.globalAlpha = alpha;
      ctx.fill();
    }

    // Highlight hovered point
    if (hovered) {
      ctx.globalAlpha = 1;
      ctx.beginPath();
      ctx.arc(hovered.px, hovered.py, 6, 0, Math.PI * 2);
      ctx.strokeStyle = colorMap.ink;
      ctx.lineWidth = 2;
      ctx.stroke();
    }

    ctx.restore();
  }, [projected, width, height, colorMap, hovered, maxRecency, minLogM, maxLogM]);

  const findNearest = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    let best: ProjectedPoint | null = null;
    let bestDistSq = 144; // 12px radius
    for (const p of projected) {
      const d2 = (p.px - mx) ** 2 + (p.py - my) ** 2;
      if (d2 < bestDistSq) {
        bestDistSq = d2;
        best = p;
      }
    }
    return best;
  };

  return (
    <div className="card-surface flex flex-col gap-4">
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3">
        <div>
          <span className="label-caps">Signature View · Uncertainty Map</span>
          <h2 className="text-h2 mt-0.5">
            All {formatNumber(points.length)} S3 customers by recency and spend, shaded by segment certainty
          </h2>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <label className="inline-flex items-center gap-2 text-small cursor-pointer select-none">
            <input
              type="checkbox"
              checked={onlyBoundary}
              onChange={(e) => setOnlyBoundary(e.target.checked)}
              className="rounded accent-current"
            />
            <span>Boundary only (max p &lt; 0.60)</span>
          </label>

          <div
            className="inline-flex p-0.5 rounded-input"
            style={{
              backgroundColor: "var(--surface-2)",
              border: "1px solid var(--line)",
            }}
            role="group"
            aria-label="Map probability method toggle"
          >
            {(["gmm", "bootstrap"] as const).map((m) => {
              const active = method === m;
              return (
                <button
                  key={m}
                  type="button"
                  onClick={() => onMethodChange(m)}
                  className="px-3 py-1 rounded text-small font-medium transition-smooth"
                  style={{
                    backgroundColor: active ? "var(--surface)" : "transparent",
                    color: active ? "var(--ink)" : "var(--muted)",
                  }}
                >
                  {m === "gmm" ? "GMM (default)" : "Bootstrap (stability)"}
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* Segment legend + interactive filter pills */}
      <div className="flex flex-wrap items-center justify-between gap-3 text-small">
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => setFilterSegment(null)}
            className="px-2.5 py-1 rounded-full text-xs font-medium transition-smooth"
            style={{
              backgroundColor:
                filterSegment === null ? "var(--ink)" : "var(--surface-2)",
              color: filterSegment === null ? "var(--bg)" : "var(--ink-2)",
            }}
          >
            All segments ({formatNumber(points.length)})
          </button>
          {["Champions", "Loyal", "At-Risk", "New", "Hibernating"].map((seg) => {
            const active = filterSegment === seg;
            return (
              <button
                key={seg}
                type="button"
                onClick={() => setFilterSegment(active ? null : seg)}
                className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium transition-smooth"
                style={{
                  backgroundColor: active ? "var(--ink)" : "var(--surface-2)",
                  color: active ? "var(--bg)" : "var(--ink)",
                }}
              >
                <span
                  className="w-2.5 h-2.5 rounded-full"
                  style={{ backgroundColor: `var(--seg-${seg.toLowerCase()})` }}
                />
                <span>{seg}</span>
              </button>
            );
          })}
        </div>
        <span className="text-small italic" style={{ color: "var(--muted)" }}>
          Faded dots are customers between segments. Recency on a square-root scale, jittered ±0.4 days. Click any dot to inspect.
        </span>
      </div>

      {/* Canvas container */}
      <div ref={containerRef} className="relative w-full">
        <canvas
          ref={canvasRef}
          style={{ width: `${width}px`, height: `${height}px` }}
          className="block cursor-crosshair rounded-input"
          aria-label="Customer uncertainty scatter map of recency vs monetary spend"
          onMouseMove={(e) => setHovered(findNearest(e))}
          onMouseLeave={() => setHovered(null)}
          onClick={(e) => {
            const found = findNearest(e);
            if (found) {
              onSelectCustomer(found.raw.id);
            }
          }}
        />

        {hovered && (
          <div
            className="pointer-events-none absolute z-20 p-3 rounded-input text-small shadow-hairline"
            style={{
              left: Math.min(width - 230, Math.max(12, hovered.px + 14)),
              top: Math.max(12, hovered.py - 76),
              backgroundColor: "var(--surface)",
              border: "1px solid var(--line)",
              color: "var(--ink)",
            }}
          >
            <div className="flex items-center justify-between gap-4 font-semibold">
              <span className="text-code">#{hovered.raw.id}</span>
              <span>{hovered.raw.country}</span>
            </div>
            <div className="mt-1 flex items-center gap-1.5">
              <span
                className="w-2 h-2 rounded-full"
                style={{
                  backgroundColor: `var(--seg-${hovered.raw.segment.toLowerCase()})`,
                }}
              />
              <span className="font-medium">{hovered.raw.segment}</span>
              <span className="text-code ml-auto">
                max p = {hovered.raw.max_p.toFixed(2)}
              </span>
            </div>
            <div
              className="mt-1 pt-1 text-xs flex justify-between gap-3 tabular-nums"
              style={{
                borderTop: "1px solid var(--line)",
                color: "var(--muted)",
              }}
            >
              <span>Recency: {hovered.raw.recency_days}d</span>
              <span>Orders: {hovered.raw.frequency}</span>
              <span>Spend: {formatCurrency(hovered.raw.monetary)}</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
