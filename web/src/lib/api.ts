/**
 * web/src/lib/api.ts
 * Typed client for the read-only FastAPI backend (`/api/*`) and formatting helpers.
 * Uses CSS variables from `tokens.css` so components never hardcode hex colours or numbers.
 */

export interface SegmentColorInfo {
  name: string;
  description: string;
  color_light: string;
  color_dark: string;
  css_var: string;
}

export interface HedgeEntry {
  words: string[];
  operator: string;
  threshold: number;
  anchor: string;
}

export interface HeadlineInfo {
  focus: string;
  title: string;
  subtitle: string;
  brier_score: number;
  brier_skill_score: number;
  roc_auc: number;
  ece_10_bins: number;
  s2_customer_count: number;
  gmm_boundary_share_pct: number;
  bootstrap_boundary_share_pct: number;
}

export interface ExampleQuestion {
  id: string;
  template_id: string;
  label: string;
  question: string;
}

export interface MetaResponse {
  dataset_name: string;
  dataset_id: number;
  doi: string;
  licence: string;
  snapshot: string;
  snapshot_date: string;
  snapshot_date_display: string;
  feature_window: string;
  customer_count: number;
  default_method: "gmm" | "bootstrap";
  methods: ("gmm" | "bootstrap")[];
  segments: SegmentColorInfo[];
  hedge_lexicon: HedgeEntry[];
  headline: HeadlineInfo;
  example_questions: ExampleQuestion[];
}

export interface RecognizedToken {
  text: string;
  label: string;
  start: number;
  end: number;
  canonical?: string | null;
  detail?: string | null;
}

export interface ThresholdControlItem {
  param_key: "tau" | "tau2";
  hedge_word: string;
  predicate: string;
  operator: string;
  value: number;
}

export interface AskSummary {
  matched: number;
  hard_count?: number | null;
  expected_count?: number | null;
  expected_revenue?: number | null;
}

export interface AskResponse {
  status: "ok" | "refused";
  question: string;
  interpretation: string;
  refusal_reason?: string | null;
  suggestions: string[];
  tokens: RecognizedToken[];
  thresholds: Record<string, number>;
  threshold_controls: ThresholdControlItem[];
  template_id?: string | null;
  sql: string;
  params: Record<string, unknown>;
  columns: string[];
  rows: Record<string, unknown>[];
  row_count: number;
  summary: AskSummary;
}

export interface HistogramBin {
  bin_lower: number;
  bin_upper: number;
  count: number;
}

export interface SegmentDetail {
  name: string;
  description: string;
  tree_rule: string;
  hard_count: number;
  expected_size: number;
  std_dev: number;
  kmeans_hard_count: number;
  share_of_customers_pct: number;
  mean_recency_days: number;
  median_recency_days: number;
  mean_frequency: number;
  median_frequency: number;
  mean_monetary: number;
  median_monetary: number;
  hard_revenue: number;
  expected_revenue: number;
  ave_pp: number;
  jaccard_mean: number;
  max_p_histogram: HistogramBin[];
}

export interface SegmentsResponse {
  method: "gmm" | "bootstrap";
  customer_count: number;
  boundary_count: number;
  boundary_share_pct: number;
  mean_normalised_entropy: number;
  segments: SegmentDetail[];
}

export interface CustomerMapPoint {
  id: number;
  country: string;
  recency_days: number;
  monetary: number;
  frequency: number;
  segment: string;
  max_p: number;
  p_lapse_90d: number;
}

export interface SegmentsMapResponse {
  method: "gmm" | "bootstrap";
  customer_count: number;
  points: CustomerMapPoint[];
}

export interface SegmentProbabilityItem {
  segment: string;
  p: number;
}

export interface CustomerDetailResponse {
  customer_id: number;
  country: string;
  first_purchase: string;
  last_purchase: string;
  recency_days: number;
  frequency: number;
  monetary: number;
  tenure_days: number;
  avg_basket: number;
  top_segment_gmm: string;
  max_p_gmm: number;
  top_segment_bootstrap: string;
  max_p_bootstrap: number;
  membership_gmm: SegmentProbabilityItem[];
  membership_bootstrap: SegmentProbabilityItem[];
  p_lapse_90d: number;
  model_version: string;
  tree_predicted_segment: string;
  tree_rule_path: string[];
  tree_leaf_rule: string;
}

export interface LapseResponse {
  s2_metrics: Record<string, number | string>[];
  s1_cv_metrics: Record<string, number | string>[];
  reliability_bins: Record<string, number | string | null>[];
  baseline_s1_rates: Record<string, number>;
  s3_by_segment: Record<string, number | string>[];
  high_value_at_risk: Record<string, number | string>[];
}

export interface QualityResponse {
  cleaning_funnel: Record<string, number | string>[];
  raw_totals: Record<string, number>;
  clean_sales_summary: Record<string, number | string>;
  gmm_grid: Record<string, number | string>[];
  kmeans_grid: Record<string, number>[];
  bootstrap_stability: Record<string, number | string>;
  bootstrap_ari_histogram: HistogramBin[];
  segment_stability: Record<string, number | string>[];
  gate: Record<string, number | string>[];
  tree_fidelity: Record<string, number>;
  tree_fidelity_by_segment: Record<string, number | string>[];
  nl_summary: Record<string, number | string>[];
  nl_dev_results: Record<string, number | string | boolean>[];
  nl_error_analysis: Record<string, number | string>[];
  test_set_status: string;
  test_set_question_count: number;
}

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  if (!res.ok) {
    let message = `Request failed (${res.status})`;
    try {
      const err = await res.json();
      if (err?.detail) message = String(err.detail);
    } catch {
      // ignore json parse error
    }
    throw new Error(message);
  }
  return res.json() as Promise<T>;
}

export const api = {
  getMeta: () => fetchJson<MetaResponse>("/api/meta"),
  ask: (
    question: string,
    overrides?: { tau?: number; tau2?: number; method?: "gmm" | "bootstrap" }
  ) =>
    fetchJson<AskResponse>("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, overrides }),
    }),
  getSegments: (method: "gmm" | "bootstrap" = "gmm") =>
    fetchJson<SegmentsResponse>(`/api/segments?method=${method}`),
  getSegmentsMap: (method: "gmm" | "bootstrap" = "gmm") =>
    fetchJson<SegmentsMapResponse>(`/api/segments/map?method=${method}`),
  getCustomer: (id: number) =>
    fetchJson<CustomerDetailResponse>(`/api/customers/${id}`),
  getLapse: () => fetchJson<LapseResponse>("/api/lapse"),
  getQuality: () => fetchJson<QualityResponse>("/api/quality"),
};

/**
 * Resolve a segment name to its CSS variable expression (e.g. `var(--seg-champions)`),
 * using the `/api/meta` segment list when provided.
 */
export function segmentCssColor(
  segmentName: string | undefined | null,
  segmentsMeta?: SegmentColorInfo[]
): string {
  if (!segmentName) return "var(--ink)";
  const found = segmentsMeta?.find(
    (s) => s.name.toLowerCase() === segmentName.toLowerCase()
  );
  if (found) {
    return `var(${found.css_var})`;
  }
  const map: Record<string, string> = {
    champions: "var(--seg-champions)",
    loyal: "var(--seg-loyal)",
    new: "var(--seg-new)",
    "at-risk": "var(--seg-at-risk)",
    hibernating: "var(--seg-hibernating)",
  };
  return map[segmentName.toLowerCase()] || "var(--ink)";
}

/**
 * Map a 90-day lapse probability p in [0, 1] to the sequential red ramp CSS variable.
 */
export function lapseCssColor(p: number): string {
  if (p < 0.2) return "var(--lapse-2)";
  if (p < 0.45) return "var(--lapse-3)";
  if (p < 0.7) return "var(--lapse-4)";
  return "var(--lapse-5)";
}

export function formatCurrency(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "—";
  }
  return new Intl.NumberFormat("en-GB", {
    style: "currency",
    currency: "GBP",
    maximumFractionDigits: Number(value) >= 1000 ? 0 : 2,
  }).format(Number(value));
}

export function formatNumber(
  value: number | null | undefined,
  decimals = 0
): string {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "—";
  }
  return new Intl.NumberFormat("en-GB", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(Number(value));
}
