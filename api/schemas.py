"""Pydantic schemas for the FastAPI endpoints defined in FRONTEND.md section 2."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = "ok"


class SegmentColorInfo(BaseModel):
    name: str
    description: str
    color_light: str
    color_dark: str
    css_var: str


class HedgeEntry(BaseModel):
    words: list[str]
    operator: str
    threshold: float
    anchor: str


class HeadlineInfo(BaseModel):
    focus: str
    title: str
    subtitle: str
    brier_score: float
    brier_skill_score: float
    roc_auc: float
    ece_10_bins: float
    s2_customer_count: int
    gmm_boundary_share_pct: float
    bootstrap_boundary_share_pct: float


class ExampleQuestion(BaseModel):
    id: str
    template_id: str
    label: str
    question: str


class MetaResponse(BaseModel):
    dataset_name: str
    dataset_id: int
    doi: str
    licence: str
    snapshot: str
    snapshot_date: str
    snapshot_date_display: str
    feature_window: str
    customer_count: int
    default_method: str
    methods: list[str]
    segments: list[SegmentColorInfo]
    hedge_lexicon: list[HedgeEntry]
    headline: HeadlineInfo
    example_questions: list[ExampleQuestion]


class AskOverrides(BaseModel):
    tau: float | None = Field(default=None, ge=0.0, le=1.0)
    tau2: float | None = Field(default=None, ge=0.0, le=1.0)
    method: str | None = None


class AskRequest(BaseModel):
    question: str
    overrides: AskOverrides | None = None


class RecognizedToken(BaseModel):
    text: str
    label: str
    start: int
    end: int
    canonical: str | None = None
    detail: str | None = None


class ThresholdControlItem(BaseModel):
    param_key: str  # "tau" or "tau2"
    hedge_word: str
    predicate: str
    operator: str
    value: float


class AskSummary(BaseModel):
    matched: int
    hard_count: int | None = None
    expected_count: float | None = None
    expected_revenue: float | None = None


class AskResponse(BaseModel):
    status: str  # "ok" or "refused"
    question: str
    interpretation: str
    refusal_reason: str | None = None
    suggestions: list[str] = Field(default_factory=list)
    tokens: list[RecognizedToken] = Field(default_factory=list)
    thresholds: dict[str, float] = Field(default_factory=dict)
    threshold_controls: list[ThresholdControlItem] = Field(default_factory=list)
    template_id: str | None = None
    sql: str = ""
    params: dict[str, Any] = Field(default_factory=dict)
    columns: list[str] = Field(default_factory=list)
    rows: list[dict[str, Any]] = Field(default_factory=list)
    row_count: int = 0
    summary: AskSummary


class HistogramBin(BaseModel):
    bin_lower: float
    bin_upper: float
    count: int


class SegmentDetail(BaseModel):
    name: str
    description: str
    tree_rule: str
    hard_count: int
    expected_size: float
    std_dev: float
    kmeans_hard_count: int
    share_of_customers_pct: float
    mean_recency_days: float
    median_recency_days: float
    mean_frequency: float
    median_frequency: float
    mean_monetary: float
    median_monetary: float
    hard_revenue: float
    expected_revenue: float
    ave_pp: float
    jaccard_mean: float
    max_p_histogram: list[HistogramBin]


class SegmentsResponse(BaseModel):
    method: str
    customer_count: int
    boundary_count: int
    boundary_share_pct: float
    mean_normalised_entropy: float
    segments: list[SegmentDetail]


class CustomerMapPoint(BaseModel):
    id: int
    country: str
    recency_days: int
    monetary: float
    frequency: int
    segment: str
    max_p: float
    p_lapse_90d: float


class SegmentsMapResponse(BaseModel):
    method: str
    customer_count: int
    points: list[CustomerMapPoint]


class SegmentProbabilityItem(BaseModel):
    segment: str
    p: float


class CustomerDetailResponse(BaseModel):
    customer_id: int
    country: str
    first_purchase: str
    last_purchase: str
    recency_days: int
    frequency: int
    monetary: float
    tenure_days: int
    avg_basket: float
    top_segment_gmm: str
    max_p_gmm: float
    top_segment_bootstrap: str
    max_p_bootstrap: float
    membership_gmm: list[SegmentProbabilityItem]
    membership_bootstrap: list[SegmentProbabilityItem]
    p_lapse_90d: float
    model_version: str
    tree_predicted_segment: str
    tree_rule_path: list[str]
    tree_leaf_rule: str


class LapseResponse(BaseModel):
    s2_metrics: list[dict[str, Any]]
    s1_cv_metrics: list[dict[str, Any]]
    reliability_bins: list[dict[str, Any]]
    baseline_s1_rates: dict[str, Any]
    s3_by_segment: list[dict[str, Any]]
    high_value_at_risk: list[dict[str, Any]]


class QualityResponse(BaseModel):
    cleaning_funnel: list[dict[str, Any]]
    raw_totals: dict[str, Any]
    clean_sales_summary: dict[str, Any]
    gmm_grid: list[dict[str, Any]]
    kmeans_grid: list[dict[str, Any]]
    bootstrap_stability: dict[str, Any]
    bootstrap_ari_histogram: list[HistogramBin]
    segment_stability: list[dict[str, Any]]
    gate: list[dict[str, Any]]
    tree_fidelity: dict[str, Any]
    tree_fidelity_by_segment: list[dict[str, Any]]
    nl_summary: list[dict[str, Any]]
    nl_dev_results: list[dict[str, Any]]
    nl_error_analysis: list[dict[str, Any]]
    test_set_status: str
    test_set_question_count: int
