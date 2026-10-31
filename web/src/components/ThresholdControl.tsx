/**
 * web/src/components/ThresholdControl.tsx
 * Signature component #4: Compact probability slider (0.05 to 0.99) for each hedge
 * threshold in `/api/ask` (`threshold_controls`), with clickable labelled ticks at
 * 0.33, 0.66, 0.90, and 0.95 (IPCC AR5 and Sherman Kent anchors), plus the
 * membership method toggle (`gmm` vs `bootstrap`).
 */

import React, { useEffect, useState } from "react";
import { ThresholdControlItem } from "../lib/api";

interface ThresholdControlProps {
  controls: ThresholdControlItem[];
  method: "gmm" | "bootstrap";
  onChange: (updates: {
    tau?: number;
    tau2?: number;
    method?: "gmm" | "bootstrap";
  }) => void;
}

const ANCHOR_TICKS = [
  { value: 0.33, label: "0.33 · Possibly" },
  { value: 0.66, label: "0.66 · Probably" },
  { value: 0.9, label: "0.90 · Very likely" },
  { value: 0.95, label: "0.95 · Almost certain" },
];

export const ThresholdControl: React.FC<ThresholdControlProps> = ({
  controls,
  method,
  onChange,
}) => {
  const [localValues, setLocalValues] = useState<Record<string, number>>({});

  useEffect(() => {
    const next: Record<string, number> = {};
    controls.forEach((c) => {
      next[c.param_key] = c.value;
    });
    setLocalValues(next);
  }, [controls]);

  const handleSliderChange = (paramKey: "tau" | "tau2", nextVal: number) => {
    const rounded = Math.round(nextVal * 100) / 100;
    setLocalValues((prev) => ({ ...prev, [paramKey]: rounded }));
  };

  // Debounce slider updates to 300ms as specified in FRONTEND.md section 3.4
  useEffect(() => {
    if (controls.length === 0) return;
    const changed = controls.some(
      (c) =>
        localValues[c.param_key] !== undefined &&
        Math.abs(localValues[c.param_key] - c.value) > 0.004
    );
    if (!changed) return;

    const timer = window.setTimeout(() => {
      onChange({
        tau: localValues.tau,
        tau2: localValues.tau2,
        method,
      });
    }, 300);

    return () => window.clearTimeout(timer);
  }, [localValues, controls, method, onChange]);

  return (
    <div
      className="flex flex-col md:flex-row md:items-center justify-between gap-4 px-4 py-3 rounded-input"
      style={{
        backgroundColor: "var(--surface)",
        border: "1px solid var(--line)",
      }}
    >
      <div className="flex flex-wrap items-center gap-6 flex-1">
        {controls.length === 0 ? (
          <span className="text-small" style={{ color: "var(--muted)" }}>
            Deterministic aggregation across all S3 customers (no threshold cutoff required).
          </span>
        ) : (
          controls.map((ctrl) => {
            const currentVal = localValues[ctrl.param_key] ?? ctrl.value;
            return (
              <div
                key={ctrl.param_key}
                className="flex flex-col gap-1.5 min-w-[260px] flex-1 max-w-md"
              >
                <div className="flex items-center justify-between text-small">
                  <span className="font-medium" style={{ color: "var(--ink)" }}>
                    {ctrl.predicate} {ctrl.operator === "<=" ? "≤" : ctrl.operator === "<" ? "<" : "≥"}{" "}
                    <span className="text-code font-semibold">
                      {currentVal.toFixed(2)}
                    </span>
                  </span>
                  <span className="text-small" style={{ color: "var(--muted)" }}>
                    Hedge: <strong style={{ color: "var(--ink-2)" }}>{ctrl.hedge_word}</strong>
                  </span>
                </div>
                <input
                  type="range"
                  min={0.05}
                  max={0.99}
                  step={0.01}
                  value={currentVal}
                  aria-label={`Threshold slider for ${ctrl.predicate}`}
                  onChange={(e) =>
                    handleSliderChange(
                      ctrl.param_key,
                      parseFloat(e.target.value)
                    )
                  }
                  className="w-full cursor-pointer accent-current"
                  style={{ color: "var(--ink)" }}
                />
                <div className="flex items-center justify-between gap-1 pt-0.5">
                  {ANCHOR_TICKS.map((tick) => {
                    const active = Math.abs(currentVal - tick.value) < 0.015;
                    return (
                      <button
                        key={tick.value}
                        type="button"
                        onClick={() => {
                          setLocalValues((prev) => ({
                            ...prev,
                            [ctrl.param_key]: tick.value,
                          }));
                          onChange({
                            tau:
                              ctrl.param_key === "tau"
                                ? tick.value
                                : localValues.tau,
                            tau2:
                              ctrl.param_key === "tau2"
                                ? tick.value
                                : localValues.tau2,
                            method,
                          });
                        }}
                        className="px-2 py-0.5 rounded-full text-xs transition-smooth"
                        style={{
                          backgroundColor: active
                            ? "var(--ink)"
                            : "var(--surface-2)",
                          color: active ? "var(--bg)" : "var(--ink-2)",
                        }}
                      >
                        {tick.label}
                      </button>
                    );
                  })}
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Membership method toggle */}
      <div className="flex items-center gap-2 shrink-0">
        <span className="label-caps">Method</span>
        <div
          className="inline-flex p-0.5 rounded-input"
          style={{
            backgroundColor: "var(--surface-2)",
            border: "1px solid var(--line)",
          }}
          role="group"
          aria-label="Membership probability method"
        >
          {(["gmm", "bootstrap"] as const).map((m) => {
            const isSelected = method === m;
            return (
              <button
                key={m}
                type="button"
                onClick={() =>
                  onChange({
                    tau: localValues.tau,
                    tau2: localValues.tau2,
                    method: m,
                  })
                }
                className="px-3 py-1 rounded text-small font-medium transition-smooth"
                style={{
                  backgroundColor: isSelected ? "var(--surface)" : "transparent",
                  color: isSelected ? "var(--ink)" : "var(--muted)",
                  boxShadow: isSelected ? "var(--card-shadow)" : "none",
                }}
              >
                {m === "gmm" ? "GMM posterior" : "Bootstrap (B=100)"}
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
};
