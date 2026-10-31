/**
 * web/src/components/CustomerDrawer.tsx
 * Signature component #5: Right-side drawer displaying a single customer's profile
 * from `GET /api/customers/{id}`:
 * - customer_id and country
 * - R/F/M and basket facts
 * - 100% stacked bar of segment membership for `gmm` and `bootstrap`
 * - 90-day lapse risk gauge (`ProbabilityBar` in red)
 * - decision-tree rule path in plain English (`tree_rule_path`, `tree_leaf_rule`)
 */

import React, { useEffect, useState } from "react";
import { X } from "lucide-react";
import {
  CustomerDetailResponse,
  SegmentColorInfo,
  api,
  formatCurrency,
  formatNumber,
  segmentCssColor,
} from "../lib/api";
import { ProbabilityBar } from "./ProbabilityBar";

interface CustomerDrawerProps {
  customerId: number | null;
  onClose: () => void;
  segmentsMeta?: SegmentColorInfo[];
}

export const CustomerDrawer: React.FC<CustomerDrawerProps> = ({
  customerId,
  onClose,
  segmentsMeta,
}) => {
  const [data, setData] = useState<CustomerDetailResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (customerId === null) {
      setData(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    api
      .getCustomer(customerId)
      .then((res) => {
        if (!cancelled) {
          setData(res);
          setLoading(false);
        }
      })
      .catch((err: Error) => {
        if (!cancelled) {
          setError(err.message || "Could not load customer details.");
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [customerId]);

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && customerId !== null) {
        onClose();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [customerId, onClose]);

  if (customerId === null) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex justify-end"
      role="dialog"
      aria-modal="true"
      aria-label={`Customer ${customerId} details`}
    >
      {/* Backdrop */}
      <div
        className="fixed inset-0 transition-smooth"
        style={{ backgroundColor: "rgba(18, 22, 28, 0.42)" }}
        onClick={onClose}
      />

      {/* Drawer sheet */}
      <aside
        className="relative z-10 w-full max-w-lg h-full overflow-y-auto p-6 flex flex-col gap-6"
        style={{
          backgroundColor: "var(--surface)",
          borderLeft: "1px solid var(--line)",
        }}
      >
        <div className="flex items-start justify-between pb-4" style={{ borderBottom: "1px solid var(--line)" }}>
          <div>
            <span className="label-caps">Customer Record · Snapshot S3</span>
            <h2 className="text-h1 mt-1 tabular-nums">
              #{customerId}
              {data ? (
                <span className="text-body font-normal ml-2.5" style={{ color: "var(--muted)" }}>
                  · {data.country}
                </span>
              ) : null}
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close customer drawer"
            className="p-2 rounded-input transition-smooth"
            style={{
              backgroundColor: "var(--surface-2)",
              color: "var(--ink)",
            }}
          >
            <X size={18} />
          </button>
        </div>

        {loading && (
          <div className="flex flex-col gap-4" aria-live="polite">
            <div className="h-24 rounded-card animate-pulse" style={{ backgroundColor: "var(--surface-2)" }} />
            <div className="h-36 rounded-card animate-pulse" style={{ backgroundColor: "var(--surface-2)" }} />
            <div className="h-40 rounded-card animate-pulse" style={{ backgroundColor: "var(--surface-2)" }} />
          </div>
        )}

        {error && (
          <div
            className="p-4 rounded-card text-small"
            style={{
              backgroundColor: "var(--surface-2)",
              border: "1px solid var(--line)",
              color: "var(--ink)",
            }}
          >
            {error}
          </div>
        )}

        {!loading && data && (
          <>
            {/* R/F/M Facts Grid */}
            <section>
              <span className="label-caps">9-Month S3 Window Facts</span>
              <div className="grid grid-cols-3 gap-3 mt-2">
                <div
                  className="p-3 rounded-input"
                  style={{
                    backgroundColor: "var(--surface-2)",
                    border: "1px solid var(--line)",
                  }}
                >
                  <div className="label-caps">Recency</div>
                  <div className="text-h2 mt-1 tabular-nums">
                    {formatNumber(data.recency_days)}d
                  </div>
                  <div className="text-small mt-0.5" style={{ color: "var(--muted)" }}>
                    since last order
                  </div>
                </div>
                <div
                  className="p-3 rounded-input"
                  style={{
                    backgroundColor: "var(--surface-2)",
                    border: "1px solid var(--line)",
                  }}
                >
                  <div className="label-caps">Frequency</div>
                  <div className="text-h2 mt-1 tabular-nums">
                    {formatNumber(data.frequency)}
                  </div>
                  <div className="text-small mt-0.5" style={{ color: "var(--muted)" }}>
                    clean invoices
                  </div>
                </div>
                <div
                  className="p-3 rounded-input"
                  style={{
                    backgroundColor: "var(--surface-2)",
                    border: "1px solid var(--line)",
                  }}
                >
                  <div className="label-caps">Monetary</div>
                  <div className="text-h2 mt-1 tabular-nums">
                    {formatCurrency(data.monetary)}
                  </div>
                  <div className="text-small mt-0.5" style={{ color: "var(--muted)" }}>
                    avg {formatCurrency(data.avg_basket)}
                  </div>
                </div>
              </div>
              <div className="flex justify-between text-small mt-2" style={{ color: "var(--muted)" }}>
                <span>First seen: {data.first_purchase.slice(0, 10)}</span>
                <span>Tenure: {formatNumber(data.tenure_days)} days</span>
              </div>
            </section>

            {/* 100% Stacked Bar of Segment Membership (GMM vs Bootstrap) */}
            <section
              className="p-4 rounded-card"
              style={{
                backgroundColor: "var(--bg)",
                border: "1px solid var(--line)",
              }}
            >
              <span className="label-caps">
                BID Segment Membership Distribution (Σp = 1.00)
              </span>

              {(
                [
                  {
                    label: "GMM Posterior",
                    top: data.top_segment_gmm,
                    maxP: data.max_p_gmm,
                    items: data.membership_gmm,
                  },
                  {
                    label: "Bootstrap (B=100)",
                    top: data.top_segment_bootstrap,
                    maxP: data.max_p_bootstrap,
                    items: data.membership_bootstrap,
                  },
                ] as const
              ).map((row) => (
                <div key={row.label} className="mt-3">
                  <div className="flex justify-between text-small mb-1">
                    <span className="font-medium">{row.label}</span>
                    <span className="text-code">
                      Top: <strong>{row.top}</strong> ({row.maxP.toFixed(2)})
                    </span>
                  </div>
                  <div
                    className="h-4 w-full rounded-full overflow-hidden flex"
                    style={{
                      backgroundColor: "var(--surface-2)",
                      border: "1px solid var(--line)",
                    }}
                  >
                    {row.items.map((item) =>
                      item.p > 0.002 ? (
                        <div
                          key={item.segment}
                          title={`${item.segment}: ${(item.p * 100).toFixed(1)}%`}
                          style={{
                            width: `${(item.p * 100).toFixed(2)}%`,
                            backgroundColor: segmentCssColor(
                              item.segment,
                              segmentsMeta
                            ),
                          }}
                        />
                      ) : null
                    )}
                  </div>
                </div>
              ))}

              {/* Segment breakdown table */}
              <div className="grid grid-cols-5 gap-1.5 mt-4 pt-3" style={{ borderTop: "1px solid var(--line)" }}>
                {data.membership_gmm.map((gItem, i) => {
                  const bItem = data.membership_bootstrap[i];
                  return (
                    <div key={gItem.segment} className="text-center">
                      <div className="flex items-center justify-center gap-1 text-xs font-medium">
                        <span
                          className="w-2 h-2 rounded-full inline-block"
                          style={{
                            backgroundColor: segmentCssColor(
                              gItem.segment,
                              segmentsMeta
                            ),
                          }}
                        />
                        <span className="truncate">{gItem.segment}</span>
                      </div>
                      <div className="text-code text-xs mt-0.5">
                        {gItem.p.toFixed(2)}
                      </div>
                      <div className="text-code text-[11px]" style={{ color: "var(--muted)" }}>
                        boot {bItem?.p.toFixed(2)}
                      </div>
                    </div>
                  );
                })}
              </div>
            </section>

            {/* 90-day Lapse Gauge */}
            <section
              className="p-4 rounded-card"
              style={{
                backgroundColor: "var(--bg)",
                border: "1px solid var(--line)",
              }}
            >
              <div className="flex items-center justify-between mb-2">
                <span className="label-caps">90-Day Lapse Risk (Tuple-Independent)</span>
                <span className="text-small" style={{ color: "var(--muted)" }}>
                  model {data.model_version}
                </span>
              </div>
              <div className="flex items-center justify-between mt-2">
                <span className="text-body font-medium">
                  P(no purchase in next 90 days)
                </span>
                <ProbabilityBar
                  value={data.p_lapse_90d}
                  variant="lapse"
                  threshold={0.66}
                  widthClass="w-36"
                />
              </div>
              <p className="text-small mt-2" style={{ color: "var(--muted)" }}>
                Vertical tick marks the 0.66 IPCC &ldquo;probably&rdquo; threshold.
              </p>
            </section>

            {/* Decision-Tree Surrogate Rule Path */}
            <section
              className="p-4 rounded-card"
              style={{
                backgroundColor: "var(--bg)",
                border: "1px solid var(--line)",
              }}
            >
              <div className="flex items-center justify-between">
                <span className="label-caps">Surrogate Decision-Tree Path (Depth 4)</span>
                <span className="text-small font-medium">
                  Predicts:{" "}
                  <strong
                    style={{
                      color: segmentCssColor(
                        data.tree_predicted_segment,
                        segmentsMeta
                      ),
                    }}
                  >
                    {data.tree_predicted_segment}
                  </strong>
                </span>
              </div>
              <ol className="mt-3 space-y-1.5 text-small list-decimal list-inside">
                {data.tree_rule_path.map((step, idx) => (
                  <li key={idx} style={{ color: "var(--ink-2)" }}>
                    {step}
                  </li>
                ))}
              </ol>
              <div
                className="mt-3 p-2.5 rounded text-code text-xs"
                style={{
                  backgroundColor: "var(--surface-2)",
                  color: "var(--ink-2)",
                }}
              >
                Leaf rule: {data.tree_leaf_rule}
              </div>
            </section>
          </>
        )}
      </aside>
    </div>
  );
};
