/**
 * web/src/pages/AskPage.tsx
 * Page 2 (`/ask`): Natural-language query interface (`FRONTEND.md` section 4.2).
 * - Command-bar input (56px tall; Enter submits; `/` focuses).
 * - Six example chips (one per template Q1-Q6, from `/api/meta`).
 * - Answer rendered in strict order:
 *   1. Interpretation sentence (large)
 *   2. ParseStrip (`tokens`)
 *   3. ThresholdControl (`threshold_controls` + method toggle)
 *   4. Summary tiles (`summary`: matched, expected_count vs hard_count, expected_revenue)
 *   5. Results table with inline `ProbabilityBar`s (sortable; row click opens CustomerDrawer)
 *   6. Distribution/comparison chart of probabilities or expected sizes in the result
 *   7. Collapsible SQL panel with syntax-styled code, parameters table, and copy button
 * - Out-of-scope questions show a friendly refusal card with 3 clickable suggestions.
 */

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  AlertCircle,
  ArrowUpDown,
  Check,
  ChevronDown,
  ChevronRight,
  Copy,
  CornerDownLeft,
  Sparkles,
} from "lucide-react";
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
  AskResponse,
  MetaResponse,
  api,
  formatCurrency,
  formatNumber,
} from "../lib/api";
import { useChartTooltip } from "../lib/useChartTooltip";
import { ParseStrip } from "../components/ParseStrip";
import { ProbabilityBar } from "../components/ProbabilityBar";
import { ThresholdControl } from "../components/ThresholdControl";

interface AskPageProps {
  meta: MetaResponse | null;
  activeQuestion: string;
  onAskQuestion: (q: string) => void;
  onSelectCustomer: (customerId: number) => void;
}

export const AskPage: React.FC<AskPageProps> = ({
  meta,
  activeQuestion,
  onAskQuestion,
  onSelectCustomer,
}) => {
  const tooltip = useChartTooltip();
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [inputText, setInputText] = useState<string>(activeQuestion);
  const [response, setResponse] = useState<AskResponse | null>(null);
  const [method, setMethod] = useState<"gmm" | "bootstrap">("gmm");
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [sortCol, setSortCol] = useState<string | null>(null);
  const [sortAsc, setSortAsc] = useState<boolean>(false);
  const [sqlOpen, setSqlOpen] = useState<boolean>(false);
  const [copied, setCopied] = useState<boolean>(false);

  const runQuery = useCallback(
    (
      q: string,
      overrides?: { tau?: number; tau2?: number; method?: "gmm" | "bootstrap" }
    ) => {
      if (!q.trim()) return;
      setLoading(true);
      setError(null);
      api
        .ask(q.trim(), overrides)
        .then((res) => {
          setResponse(res);
          setSortCol(null);
          setLoading(false);
        })
        .catch((err: Error) => {
          setError(err.message || "Query failed.");
          setLoading(false);
        });
    },
    []
  );

  useEffect(() => {
    setInputText(activeQuestion);
    runQuery(activeQuestion, { method });
  }, [activeQuestion]);

  // Press `/` anywhere outside an input to focus the 56px command bar
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName;
      if (e.key === "/" && tag !== "INPUT" && tag !== "TEXTAREA") {
        e.preventDefault();
        inputRef.current?.focus();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  const handleFormSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputText.trim()) return;
    onAskQuestion(inputText.trim());
    runQuery(inputText.trim(), { method });
  };

  const handleOverrideChange = useCallback(
    (updates: { tau?: number; tau2?: number; method?: "gmm" | "bootstrap" }) => {
      const nextMethod = updates.method || method;
      if (updates.method && updates.method !== method) {
        setMethod(updates.method);
      }
      runQuery(inputText, {
        tau: updates.tau,
        tau2: updates.tau2,
        method: nextMethod,
      });
    },
    [inputText, method, runQuery]
  );

  const sortedRows = useMemo(() => {
    if (!response?.rows) return [];
    if (!sortCol) return response.rows;
    return [...response.rows].sort((a, b) => {
      const va = a[sortCol];
      const vb = b[sortCol];
      if (va === vb) return 0;
      if (va === null || va === undefined) return 1;
      if (vb === null || vb === undefined) return -1;
      if (typeof va === "number" && typeof vb === "number") {
        return sortAsc ? va - vb : vb - va;
      }
      return sortAsc
        ? String(va).localeCompare(String(vb))
        : String(vb).localeCompare(String(va));
    });
  }, [response, sortCol, sortAsc]);

  // Build data for the small companion chart
  const chartData = useMemo(() => {
    if (!response || response.status !== "ok" || response.rows.length === 0) {
      return [];
    }
    const tpl = response.template_id;
    if (tpl === "Q3") {
      return response.rows.map((r) => ({
        name: String(r.segment),
        Hard: Number(r.hard_count),
        Expected: Number(r.expected_size),
      }));
    }
    if (tpl === "Q4") {
      return response.rows.map((r) => ({
        name: String(r.segment),
        HardRevenue: Math.round(Number(r.hard_revenue)),
        ExpectedRevenue: Math.round(Number(r.expected_revenue)),
      }));
    }
    // For customer-level results (Q1, Q2, Q5, Q6), build a 5-bin histogram of the primary probability column
    const probCol =
      tpl === "Q2"
        ? "max_p"
        : tpl === "Q6"
        ? "p_lapse_90d"
        : "p";
    const edges = [0.0, 0.2, 0.4, 0.6, 0.8, 1.01];
    return [0, 1, 2, 3, 4].map((i) => {
      const lo = edges[i];
      const hi = edges[i + 1];
      const count = response.rows.filter((r) => {
        const v = Number(r[probCol] ?? 0);
        return v >= lo && v < hi;
      }).length;
      return {
        name: `${lo.toFixed(1)}–${Math.min(1.0, hi).toFixed(1)}`,
        Customers: count,
      };
    });
  }, [response]);

  const activeSegThreshold = response?.threshold_controls.find(
    (c) => c.param_key === "tau"
  )?.value;
  const activeLapseThreshold =
    response?.threshold_controls.find((c) => c.param_key === "tau2")?.value ??
    (response?.template_id === "Q6" ? 0.66 : undefined);

  return (
    <div className="flex flex-col gap-6">
      {/* Command Bar Input (56px tall) + 6 Example Chips */}
      <section className="card-surface flex flex-col gap-4">
        <div className="flex items-center justify-between">
          <span className="label-caps">
            Natural-Language Query Interface · Press &ldquo;/&rdquo; to Focus
          </span>
          <span className="text-code text-xs" style={{ color: "var(--muted)" }}>
            Templates Q1–Q6 · Zero Raw Text Interpolation
          </span>
        </div>

        <form onSubmit={handleFormSubmit} className="relative">
          <input
            ref={inputRef}
            type="text"
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            aria-label="Ask a question in plain English"
            placeholder="Ask a question about segments, boundary uncertainty, or 90-day lapse risk..."
            className="w-full h-[56px] pl-4 pr-32 rounded-input text-body font-medium"
            style={{
              backgroundColor: "var(--bg)",
              border: "1px solid var(--line)",
              color: "var(--ink)",
            }}
          />
          <button
            type="submit"
            className="btn-primary absolute right-2 top-2 bottom-2 px-4 inline-flex items-center gap-1.5"
          >
            <span>Ask</span>
            <CornerDownLeft size={14} />
          </button>
        </form>

        {/* Six Example Chips */}
        {meta && (
          <div className="flex flex-wrap items-center gap-2">
            {meta.example_questions.map((chip) => {
              const isCurrent = inputText.trim() === chip.question.trim();
              return (
                <button
                  key={chip.id}
                  type="button"
                  onClick={() => {
                    setInputText(chip.question);
                    onAskQuestion(chip.question);
                    runQuery(chip.question, { method });
                  }}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-small transition-smooth"
                  style={{
                    backgroundColor: isCurrent
                      ? "var(--ink)"
                      : "var(--surface-2)",
                    color: isCurrent ? "var(--bg)" : "var(--ink-2)",
                    border: "1px solid var(--line)",
                  }}
                >
                  <Sparkles size={12} />
                  <span>{chip.question}</span>
                </button>
              );
            })}
          </div>
        )}
      </section>

      {loading && (
        <div className="flex flex-col gap-4" aria-live="polite">
          <div
            className="h-20 rounded-card animate-pulse"
            style={{ backgroundColor: "var(--surface)" }}
          />
          <div
            className="h-28 rounded-card animate-pulse"
            style={{ backgroundColor: "var(--surface)" }}
          />
          <div
            className="h-72 rounded-card animate-pulse"
            style={{ backgroundColor: "var(--surface)" }}
          />
        </div>
      )}

      {error && (
        <div className="card-surface text-small" role="alert">
          <strong>Could not run query:</strong> {error}
        </div>
      )}

      {!loading && response && response.status === "refused" && (
        <section
          className="card-surface flex flex-col gap-4"
          role="region"
          aria-live="polite"
          aria-label="Out-of-scope query refusal"
        >
          <div className="flex items-start gap-3">
            <AlertCircle size={22} className="mt-0.5 shrink-0" />
            <div>
              <span className="label-caps">Polite Refusal · Out of Scope or Unsafe</span>
              <h2 className="text-h2 mt-1">{response.interpretation}</h2>
              {response.refusal_reason && (
                <p className="text-small mt-1" style={{ color: "var(--muted)" }}>
                  Reason: {response.refusal_reason}. User text never becomes SQL; only typed parameters for templates Q1–Q6 are permitted.
                </p>
              )}
            </div>
          </div>

          <ParseStrip
            question={response.question}
            tokens={response.tokens}
            segmentsMeta={meta?.segments}
          />

          <div>
            <span className="label-caps">Try One of These Supported Questions</span>
            <div className="flex flex-wrap gap-2 mt-2">
              {response.suggestions.map((sug, idx) => (
                <button
                  key={idx}
                  type="button"
                  onClick={() => {
                    setInputText(sug);
                    onAskQuestion(sug);
                    runQuery(sug, { method });
                  }}
                  className="px-3.5 py-2 rounded-input text-small font-medium transition-smooth"
                  style={{
                    backgroundColor: "var(--surface-2)",
                    border: "1px solid var(--line)",
                    color: "var(--ink)",
                  }}
                >
                  {sug}
                </button>
              ))}
            </div>
          </div>
        </section>
      )}

      {!loading && response && response.status === "ok" && (
        <div
          className="flex flex-col gap-5"
          aria-live="polite"
          role="region"
          aria-label="Query answer"
        >
          {/* 1. Interpretation Sentence (Large) */}
          <div className="card-surface flex flex-col gap-3">
            <div className="flex items-center justify-between">
              <span className="label-caps">
                1 · Interpretation · Template {response.template_id}
              </span>
              <span className="text-code text-xs" style={{ color: "var(--muted)" }}>
                {response.row_count} {response.row_count === 1 ? "row" : "rows"} returned
              </span>
            </div>
            <h1 className="text-h1">{response.interpretation}</h1>

            {/* 2. ParseStrip */}
            <ParseStrip
              question={response.question}
              tokens={response.tokens}
              segmentsMeta={meta?.segments}
            />

            {/* 3. Threshold Controls */}
            <ThresholdControl
              controls={response.threshold_controls}
              method={method}
              onChange={handleOverrideChange}
            />
          </div>

          {/* 4. Summary Tiles */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="card-surface">
              <span className="label-caps">Matched Rows</span>
              <div className="text-h1 mt-1 tabular-nums">
                {formatNumber(response.summary.matched)}
              </div>
              <div className="text-small mt-0.5" style={{ color: "var(--muted)" }}>
                Satisfying active probability constraints
              </div>
            </div>

            <div className="card-surface">
              <span className="label-caps">Expected Count vs Hard Count</span>
              <div className="text-h1 mt-1 tabular-nums">
                {response.summary.expected_count !== null &&
                response.summary.expected_count !== undefined
                  ? formatNumber(response.summary.expected_count, 2)
                  : "—"}
                {response.summary.hard_count !== null &&
                  response.summary.hard_count !== undefined && (
                    <span
                      className="text-body font-normal ml-2"
                      style={{ color: "var(--muted)" }}
                    >
                      vs {formatNumber(response.summary.hard_count)} hard
                    </span>
                  )}
              </div>
              <div className="text-small mt-0.5" style={{ color: "var(--muted)" }}>
                Linearity of expectation Σp across customers
              </div>
            </div>

            <div className="card-surface">
              <span className="label-caps">Expected Revenue in Result</span>
              <div className="text-h1 mt-1 tabular-nums">
                {response.summary.expected_revenue !== null &&
                response.summary.expected_revenue !== undefined
                  ? formatCurrency(response.summary.expected_revenue)
                  : "—"}
              </div>
              <div className="text-small mt-0.5" style={{ color: "var(--muted)" }}>
                Probability-weighted 9-month S3 spend
              </div>
            </div>
          </div>

          {/* 5. Results Table with Inline ProbabilityBars */}
          <section className="card-surface flex flex-col gap-3 overflow-hidden">
            <div className="flex items-center justify-between">
              <span className="label-caps">
                Results Table · Click Any Customer Row to Open Drawer
              </span>
              <span className="text-small" style={{ color: "var(--muted)" }}>
                Showing {formatNumber(sortedRows.length)} rows
              </span>
            </div>

            {sortedRows.length === 0 ? (
              <div
                className="p-8 text-center rounded-input"
                style={{
                  backgroundColor: "var(--bg)",
                  border: "1px solid var(--line)",
                }}
              >
                <p className="text-body font-medium">
                  No customers matched this probability threshold.
                </p>
                <p className="text-small mt-1" style={{ color: "var(--muted)" }}>
                  Try lowering the probability threshold slider above (for example to 0.33 &ldquo;possibly&rdquo;) or switching between GMM and Bootstrap.
                </p>
              </div>
            ) : (
              <div className="overflow-x-auto max-h-[460px] overflow-y-auto">
                <table className="w-full text-left border-collapse text-small">
                  <thead>
                    <tr style={{ borderBottom: "1px solid var(--line)" }}>
                      {response.columns.map((col) => (
                        <th
                          key={col}
                          className="py-2.5 px-3 font-semibold whitespace-nowrap sticky top-0"
                          style={{
                            backgroundColor: "var(--surface)",
                            color: "var(--ink-2)",
                          }}
                        >
                          <button
                            type="button"
                            onClick={() => {
                              if (sortCol === col) {
                                setSortAsc(!sortAsc);
                              } else {
                                setSortCol(col);
                                setSortAsc(false);
                              }
                            }}
                            className="inline-flex items-center gap-1 hover:underline"
                          >
                            <span>{col}</span>
                            <ArrowUpDown size={12} />
                          </button>
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {sortedRows.slice(0, 200).map((row, rIdx) => {
                      const hasCustomerId =
                        row.customer_id !== undefined &&
                        row.customer_id !== null;
                      const rowSeg = String(
                        row.segment ||
                          row.top_segment ||
                          response.params.seg ||
                          "Champions"
                      );

                      return (
                        <tr
                          key={rIdx}
                          onClick={() => {
                            if (hasCustomerId) {
                              onSelectCustomer(Number(row.customer_id));
                            }
                          }}
                          className={
                            hasCustomerId
                              ? "cursor-pointer transition-smooth hover:opacity-90"
                              : ""
                          }
                          style={{ borderBottom: "1px solid var(--line)" }}
                        >
                          {response.columns.map((col) => {
                            const val = row[col];
                            if (
                              col === "p" ||
                              col === "p_segment" ||
                              col === "max_p" ||
                              col === "second_p"
                            ) {
                              return (
                                <td key={col} className="py-2.5 px-3 whitespace-nowrap">
                                  <ProbabilityBar
                                    value={Number(val)}
                                    segment={rowSeg}
                                    variant="segment"
                                    threshold={
                                      col === "second_p"
                                        ? null
                                        : activeSegThreshold
                                    }
                                    segmentsMeta={meta?.segments}
                                  />
                                </td>
                              );
                            }
                            if (col === "p_lapse_90d") {
                              return (
                                <td key={col} className="py-2.5 px-3 whitespace-nowrap">
                                  <ProbabilityBar
                                    value={Number(val)}
                                    variant="lapse"
                                    threshold={activeLapseThreshold}
                                  />
                                </td>
                              );
                            }
                            if (
                              col === "monetary" ||
                              col === "avg_basket" ||
                              col === "hard_revenue" ||
                              col === "expected_revenue"
                            ) {
                              return (
                                <td
                                  key={col}
                                  className="py-2.5 px-3 text-code tabular-nums whitespace-nowrap"
                                >
                                  {formatCurrency(Number(val))}
                                </td>
                              );
                            }
                            if (typeof val === "number") {
                              return (
                                <td
                                  key={col}
                                  className="py-2.5 px-3 text-code tabular-nums whitespace-nowrap"
                                >
                                  {Number.isInteger(val)
                                    ? col === "customer_id"
                                      ? `#${val}`
                                      : formatNumber(val)
                                    : val.toFixed(2)}
                                </td>
                              );
                            }
                            return (
                              <td key={col} className="py-2.5 px-3 whitespace-nowrap">
                                {String(val ?? "—")}
                              </td>
                            );
                          })}
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          {/* 6. Companion Chart */}
          {chartData.length > 0 && (
            <section className="card-surface flex flex-col gap-3">
              <div>
                <span className="label-caps">Result Distribution</span>
                <h2 className="text-h2 mt-0.5">
                  {response.template_id === "Q3"
                    ? "Hard cluster count vs probabilistic expected size Σp per segment"
                    : response.template_id === "Q4"
                    ? "Hard segment revenue vs probabilistic expected revenue Σ(p × monetary)"
                    : "Distribution of probabilities among matched customers"}
                </h2>
              </div>
              <div
                className="h-56 w-full"
                role="img"
                aria-label="Bar chart summarizing the query result distribution"
              >
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={chartData} {...tooltip.bind("result")}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--line)" />
                    <XAxis
                      dataKey="name"
                      tick={{ fill: "var(--muted)", fontSize: 12 }}
                    />
                    <YAxis tick={{ fill: "var(--muted)", fontSize: 12 }} />
                    <Tooltip active={tooltip.activeFor("result")}
                      contentStyle={{
                        backgroundColor: "var(--surface)",
                        borderColor: "var(--line)",
                        color: "var(--ink)",
                      }}
                    />
                    {response.template_id === "Q3" ? (
                      <>
                        <Bar dataKey="Hard" fill="var(--muted)" radius={[4, 4, 0, 0]} />
                        <Bar dataKey="Expected" fill="var(--ink)" radius={[4, 4, 0, 0]} />
                      </>
                    ) : response.template_id === "Q4" ? (
                      <>
                        <Bar
                          dataKey="HardRevenue"
                          fill="var(--muted)"
                          radius={[4, 4, 0, 0]}
                        />
                        <Bar
                          dataKey="ExpectedRevenue"
                          fill="var(--ink)"
                          radius={[4, 4, 0, 0]}
                        />
                      </>
                    ) : (
                      <Bar
                        dataKey="Customers"
                        fill="var(--ink)"
                        radius={[4, 4, 0, 0]}
                      />
                    )}
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </section>
          )}

          {/* 7. Collapsible SQL Panel with Parameters Table and Copy Button */}
          <section className="card-surface flex flex-col gap-3">
            <div className="flex items-center justify-between">
              <button
                type="button"
                onClick={() => setSqlOpen(!sqlOpen)}
                className="inline-flex items-center gap-2 text-small font-semibold"
              >
                {sqlOpen ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                <span>
                  Parameterised SQL Template ({response.template_id}) &amp; Bound Parameters
                </span>
              </button>

              <button
                type="button"
                onClick={() => {
                  navigator.clipboard.writeText(response.sql);
                  setCopied(true);
                  window.setTimeout(() => setCopied(false), 1800);
                }}
                className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-medium"
                style={{
                  backgroundColor: "var(--surface-2)",
                  border: "1px solid var(--line)",
                  color: "var(--ink)",
                }}
              >
                {copied ? <Check size={13} /> : <Copy size={13} />}
                <span>{copied ? "Copied SQL" : "Copy SQL"}</span>
              </button>
            </div>

            {sqlOpen && (
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 pt-2">
                <pre
                  className="lg:col-span-8 p-4 rounded-input overflow-x-auto text-code"
                  style={{
                    backgroundColor: "var(--surface-2)",
                    border: "1px solid var(--line)",
                    color: "var(--ink)",
                  }}
                >
                  <code>{response.sql}</code>
                </pre>

                <div
                  className="lg:col-span-4 p-4 rounded-input flex flex-col gap-2"
                  style={{
                    backgroundColor: "var(--bg)",
                    border: "1px solid var(--line)",
                  }}
                >
                  <span className="label-caps">Allow-Listed Bound Parameters</span>
                  <table className="w-full text-small border-collapse">
                    <tbody>
                      {Object.entries(response.params).map(([k, v]) => (
                        <tr
                          key={k}
                          style={{ borderBottom: "1px solid var(--line)" }}
                        >
                          <td className="py-1.5 text-code" style={{ color: "var(--muted)" }}>
                            ${k}
                          </td>
                          <td className="py-1.5 text-right text-code font-medium">
                            {v === null ? "NULL" : String(v)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </section>
        </div>
      )}
    </div>
  );
};
