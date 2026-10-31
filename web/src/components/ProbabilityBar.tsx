/**
 * web/src/components/ProbabilityBar.tsx
 * Signature component #1: Renders a thin horizontal probability track with fill up to `p`
 * in the segment colour (or sequential lapse red), an optional vertical threshold tick,
 * and the numeric probability in JetBrains Mono (`p`, `p_segment`, `p_lapse_90d`, `max_p`).
 */

import React from "react";
import {
  SegmentColorInfo,
  lapseCssColor,
  segmentCssColor,
} from "../lib/api";

interface ProbabilityBarProps {
  value: number;
  segment?: string | null;
  variant?: "segment" | "lapse";
  threshold?: number | null;
  segmentsMeta?: SegmentColorInfo[];
  widthClass?: string;
}

export const ProbabilityBar: React.FC<ProbabilityBarProps> = ({
  value,
  segment,
  variant = "segment",
  threshold,
  segmentsMeta,
  widthClass = "w-28",
}) => {
  const clamped = Math.max(0, Math.min(1, Number(value) || 0));
  const fillColor =
    variant === "lapse"
      ? lapseCssColor(clamped)
      : segmentCssColor(segment, segmentsMeta);

  return (
    <div
      className="inline-flex items-center gap-2.5 align-middle"
      aria-label={`Probability ${clamped.toFixed(2)}${
        threshold !== undefined && threshold !== null
          ? `, threshold ${threshold.toFixed(2)}`
          : ""
      }`}
    >
      <div
        className={`relative h-2 ${widthClass} rounded-full overflow-visible`}
        style={{ backgroundColor: "var(--surface-2)" }}
      >
        <div
          className="h-full rounded-full transition-smooth"
          style={{
            width: `${(clamped * 100).toFixed(1)}%`,
            backgroundColor: fillColor,
          }}
        />
        {threshold !== undefined &&
          threshold !== null &&
          threshold > 0 &&
          threshold < 1 && (
            <span
              title={`Active threshold: ${threshold.toFixed(2)}`}
              className="absolute -top-1 -bottom-1 w-0.5 pointer-events-none"
              style={{
                left: `${(threshold * 100).toFixed(1)}%`,
                backgroundColor: "var(--ink)",
              }}
            />
          )}
      </div>
      <span className="text-code tabular-nums" style={{ color: "var(--ink)" }}>
        {clamped.toFixed(2)}
      </span>
    </div>
  );
};
