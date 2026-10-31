"""FastAPI read-only backend (`FRONTEND.md` section 2).

All analytical logic lives in Python (`src/` and `sql/templates/`) and queries
`app/app.duckdb` with `read_only=True`. In production, if `web/dist` exists,
this server also serves the compiled React SPA on port 8000.
"""

from __future__ import annotations

import re
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import numpy as np
import pandas as pd

from api import schemas
from src import config, db, prob_queries
from src.nl import lexicon, parser

app = FastAPI(
    title="Probably API",
    description="Read-only probabilistic customer intelligence API",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

SEGMENT_ORDER = ["Champions", "Loyal", "At-Risk", "New", "Hibernating"]

SEGMENT_COLORS: dict[str, dict[str, str]] = {
    "Champions": {
        "light": "#009E73",
        "dark": "#2BC48F",
        "css_var": "--seg-champions",
    },
    "Loyal": {
        "light": "#0072B2",
        "dark": "#4FA3E0",
        "css_var": "--seg-loyal",
    },
    "New": {
        "light": "#CC79A7",
        "dark": "#E59AC4",
        "css_var": "--seg-new",
    },
    "At-Risk": {
        "light": "#E69F00",
        "dark": "#F2B33D",
        "css_var": "--seg-at-risk",
    },
    "Hibernating": {
        "light": "#7A7F87",
        "dark": "#A3A9B1",
        "css_var": "--seg-hibernating",
    },
}

EXAMPLE_QUESTIONS: list[schemas.ExampleQuestion] = [
    schemas.ExampleQuestion(
        id="q6_de",
        template_id="Q6",
        label="Q6 · Segment + Lapse",
        question="Which German customers are probably Champions but likely to lapse?",
    ),
    schemas.ExampleQuestion(
        id="q1_champions",
        template_id="Q1",
        label="Q1 · Confident Members",
        question="Which customers are almost certainly Champions?",
    ),
    schemas.ExampleQuestion(
        id="q2_boundary",
        template_id="Q2",
        label="Q2 · Boundary Customers",
        question="Show boundary customers who sit between segments.",
    ),
    schemas.ExampleQuestion(
        id="q3_sizes",
        template_id="Q3",
        label="Q3 · Expected Sizes",
        question="What is the expected customer count per segment?",
    ),
    schemas.ExampleQuestion(
        id="q4_revenue",
        template_id="Q4",
        label="Q4 · Expected Revenue",
        question="What is the expected revenue per segment?",
    ),
    schemas.ExampleQuestion(
        id="q5_topk",
        template_id="Q5",
        label="Q5 · Top-K Members",
        question="Show the top 10 most confident Loyal customers in the United Kingdom.",
    ),
]

REFUSAL_SUGGESTIONS = [
    "Which German customers are probably Champions but likely to lapse?",
    "Which customers are almost certainly Champions?",
    "Show boundary customers who sit between segments.",
]


def get_readonly_con():
    """Open a fresh read-only connection to `app/app.duckdb`."""
    return db.connect_app(config.APP_DB_PATH)


def _clean_records(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Convert a DataFrame to JSON-safe dicts (replacing NaN with None)."""
    if df.empty:
        return []
    clean_df = df.astype(object).where(pd.notna(df), None)
    records = clean_df.to_dict(orient="records")
    for row in records:
        for k, v in row.items():
            if isinstance(v, (np.integer,)):
                row[k] = int(v)
            elif isinstance(v, (np.floating, float)):
                row[k] = None if v is None or np.isnan(v) else round(float(v), 4)
            elif isinstance(v, (pd.Timestamp,)):
                row[k] = str(v)
    return records


def extract_recognized_tokens(
    question: str,
    active_thresholds: dict[str, float] | None = None,
) -> list[schemas.RecognizedToken]:
    """Extract recognised spans for the ParseStrip component."""
    clean_q = (question or "").strip()
    if not clean_q:
        return []

    nlp = parser.get_nlp()
    doc = nlp(clean_q)
    spans: list[schemas.RecognizedToken] = []
    occupied: list[tuple[int, int]] = []

    for ent in doc.ents:
        start, end = ent.start_char, ent.end_char
        label = ent.label_
        canonical = ent.ent_id_ or ent.text
        detail = label

        if label == "HEDGE":
            op, thr = lexicon.lookup_hedge(canonical)
            op_sym = "≥" if op == ">=" else "≤"
            # Show the active threshold if overridden
            shown_thr = thr
            if active_thresholds and canonical in active_thresholds:
                shown_thr = active_thresholds[canonical]
            detail = f"{ent.text} → P {op_sym} {shown_thr:.2f}"
        elif label == "SEGMENT":
            detail = f"Segment: {canonical}"
        elif label == "COUNTRY":
            detail = f"Country: {canonical}"
        elif label == "LAPSE":
            detail = "Predicate: 90-day lapse risk"
        elif label == "BOUNDARY":
            detail = "Intent: Boundary uncertainty (max p < τ)"
        elif label == "EXP_SIZE":
            detail = "Intent: Expected segment size SUM(p)"
        elif label == "EXP_REV":
            detail = "Intent: Expected segment revenue SUM(p × monetary)"

        spans.append(
            schemas.RecognizedToken(
                text=clean_q[start:end],
                label=label,
                start=start,
                end=end,
                canonical=canonical,
                detail=detail,
            )
        )
        occupied.append((start, end))

    # Also detect number / comparison spans ("top 10", ">= 0.80", "at least 0.75")
    for m in re.finditer(
        r"\b(?:top|first)\s+\d+\b|(?:(?:>=|<=|>|<|at\s+least|more\s+than|over|above|under|below|less\s+than)\s*)?\b(?:0\.\d+|[1-9]\d?\s*%)",
        clean_q,
        flags=re.IGNORECASE,
    ):
        s, e = m.span()
        if any(not (e <= os or s >= oe) for os, oe in occupied):
            continue
        spans.append(
            schemas.RecognizedToken(
                text=clean_q[s:e],
                label="NUMBER",
                start=s,
                end=e,
                canonical=m.group(0),
                detail=f"Numeric constraint: {m.group(0)}",
            )
        )

    spans.sort(key=lambda t: t.start)
    return spans


def evaluate_tree_rule_path(
    recency_days: float,
    frequency: float,
    monetary: float,
) -> tuple[str, list[str], str]:
    """Trace the exact depth-4 surrogate decision tree path in plain English.

    Matches the fitted DecisionTreeClassifier(max_depth=4, random_state=42)
    documented in `reports/tables/tree_rules.md`.
    """
    steps: list[str] = []
    if monetary <= 512.32:
        steps.append(f"9-month spend (£{monetary:,.2f}) is at or below £512.32")
        if recency_days <= 47.50:
            steps.append(f"Last purchase ({int(recency_days)} days ago) is within 47.5 days")
            if frequency <= 2.50:
                steps.append(f"Order frequency ({int(frequency)} orders) is at or below 2.5")
                if recency_days <= 46.50:
                    steps.append(f"Last purchase ({int(recency_days)} days ago) is within 46.5 days")
                    return (
                        "New",
                        steps,
                        "recency_days <= 46.50 AND frequency <= 2.50 AND monetary <= £512.32 (98.6% leaf purity)",
                    )
                steps.append(f"Last purchase ({int(recency_days)} days ago) is between 46.5 and 47.5 days")
                return (
                    "New",
                    steps,
                    "46.50 < recency_days <= 47.50 AND frequency <= 2.50 AND monetary <= £512.32 (44.4% leaf purity)",
                )
            steps.append(f"Order frequency ({int(frequency)} orders) is above 2.5")
            if recency_days <= 30.50:
                steps.append(f"Last purchase ({int(recency_days)} days ago) is within 30.5 days")
                return (
                    "Loyal",
                    steps,
                    "recency_days <= 30.50 AND frequency > 2.50 AND monetary <= £512.32 (52.5% leaf purity)",
                )
            steps.append(f"Last purchase ({int(recency_days)} days ago) is between 30.5 and 47.5 days")
            return (
                "At-Risk",
                steps,
                "30.50 < recency_days <= 47.50 AND frequency > 2.50 AND monetary <= £512.32 (84.6% leaf purity)",
            )
        steps.append(f"Last purchase ({int(recency_days)} days ago) is more than 47.5 days ago")
        if frequency <= 1.50:
            steps.append(f"Order frequency ({int(frequency)} order) is at or below 1.5")
            if monetary <= 21.38:
                steps.append(f"9-month spend (£{monetary:,.2f}) is at or below £21.38")
                return (
                    "Hibernating",
                    steps,
                    "recency_days > 47.50 AND frequency <= 1.50 AND monetary <= £21.38 (50.0% leaf purity)",
                )
            steps.append(f"9-month spend (£{monetary:,.2f}) is between £21.38 and £512.32")
            return (
                "Hibernating",
                steps,
                "recency_days > 47.50 AND frequency <= 1.50 AND £21.38 < monetary <= £512.32 (97.7% leaf purity)",
            )
        steps.append(f"Order frequency ({int(frequency)} orders) is above 1.5")
        if monetary <= 336.74:
            steps.append(f"9-month spend (£{monetary:,.2f}) is at or below £336.74")
            return (
                "Hibernating",
                steps,
                "recency_days > 47.50 AND frequency > 1.50 AND monetary <= £336.74 (82.4% leaf purity)",
            )
        steps.append(f"9-month spend (£{monetary:,.2f}) is between £336.74 and £512.32")
        return (
            "At-Risk",
            steps,
            "recency_days > 47.50 AND frequency > 1.50 AND £336.74 < monetary <= £512.32 (80.3% leaf purity)",
        )

    steps.append(f"9-month spend (£{monetary:,.2f}) is above £512.32")
    if recency_days <= 36.50:
        steps.append(f"Last purchase ({int(recency_days)} days ago) is within 36.5 days")
        if frequency <= 9.50:
            steps.append(f"Order frequency ({int(frequency)} orders) is at or below 9.5")
            if frequency <= 2.50:
                steps.append(f"Order frequency ({int(frequency)} orders) is at or below 2.5")
                return (
                    "Loyal",
                    steps,
                    "recency_days <= 36.50 AND frequency <= 2.50 AND monetary > £512.32 (43.1% leaf purity)",
                )
            steps.append(f"Order frequency ({int(frequency)} orders) is between 2.5 and 9.5")
            return (
                "Loyal",
                steps,
                "recency_days <= 36.50 AND 2.50 < frequency <= 9.50 AND monetary > £512.32 (92.7% leaf purity)",
            )
        steps.append(f"Order frequency ({int(frequency)} orders) is above 9.5")
        if frequency <= 10.50:
            steps.append(f"Order frequency ({int(frequency)} orders) is between 9.5 and 10.5")
            return (
                "Champions",
                steps,
                "recency_days <= 36.50 AND 9.50 < frequency <= 10.50 AND monetary > £512.32 (63.3% leaf purity)",
            )
        steps.append(f"Order frequency ({int(frequency)} orders) is above 10.5")
        return (
            "Champions",
            steps,
            "recency_days <= 36.50 AND frequency > 10.50 AND monetary > £512.32 (96.5% leaf purity)",
        )

    steps.append(f"Last purchase ({int(recency_days)} days ago) is more than 36.5 days ago")
    if frequency <= 4.50:
        steps.append(f"Order frequency ({int(frequency)} orders) is at or below 4.5")
        if monetary <= 2139.39:
            steps.append(f"9-month spend (£{monetary:,.2f}) is between £512.32 and £2,139.39")
            return (
                "At-Risk",
                steps,
                "recency_days > 36.50 AND frequency <= 4.50 AND £512.32 < monetary <= £2,139.39 (92.8% leaf purity)",
            )
        steps.append(f"9-month spend (£{monetary:,.2f}) is above £2,139.39")
        return (
            "At-Risk",
            steps,
            "recency_days > 36.50 AND frequency <= 4.50 AND monetary > £2,139.39 (60.8% leaf purity)",
        )
    steps.append(f"Order frequency ({int(frequency)} orders) is above 4.5")
    if monetary <= 1252.86:
        steps.append(f"9-month spend (£{monetary:,.2f}) is between £512.32 and £1,252.86")
        return (
            "Loyal",
            steps,
            "recency_days > 36.50 AND frequency > 4.50 AND £512.32 < monetary <= £1,252.86 (56.5% leaf purity)",
        )
    steps.append(f"9-month spend (£{monetary:,.2f}) is above £1,252.86")
    return (
        "Loyal",
        steps,
        "recency_days > 36.50 AND frequency > 4.50 AND monetary > £1,252.86 (94.7% leaf purity)",
    )


@app.get("/api/health", response_model=schemas.HealthResponse)
def get_health() -> schemas.HealthResponse:
    """Health check endpoint."""
    return schemas.HealthResponse(status="ok")


@app.get("/api/meta", response_model=schemas.MetaResponse)
def get_meta() -> schemas.MetaResponse:
    """Return dataset metadata, segment colours, hedge lexicon and gate headline."""
    con = get_readonly_con()
    try:
        n_customers = int(
            con.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
        )
        seg_rows = con.execute(
            "SELECT segment, description FROM segments"
        ).fetchall()
        desc_map = {str(r[0]): str(r[1]) for r in seg_rows}
    finally:
        con.close()

    s2_df = pd.read_csv(config.TABLES_DIR / "lapse_s2_eval.csv")
    prim_s2 = s2_df[s2_df["model"] == "logistic_calibrated"].iloc[0]
    gate_df = pd.read_csv(config.TABLES_DIR / "gate.csv")
    gmm_gate = gate_df[gate_df["method"] == "gmm"].iloc[0]
    boot_gate = gate_df[gate_df["method"] == "bootstrap"].iloc[0]

    segments_info = [
        schemas.SegmentColorInfo(
            name=seg_name,
            description=desc_map.get(seg_name, config.SEGMENT_DESCRIPTIONS.get(seg_name, "")),
            color_light=SEGMENT_COLORS[seg_name]["light"],
            color_dark=SEGMENT_COLORS[seg_name]["dark"],
            css_var=SEGMENT_COLORS[seg_name]["css_var"],
        )
        for seg_name in SEGMENT_ORDER
    ]

    hedge_entries = [
        schemas.HedgeEntry(
            words=["possibly", "might"],
            operator=">=",
            threshold=0.33,
            anchor="IPCC AR5 'about as likely as not' starts at 33%",
        ),
        schemas.HedgeEntry(
            words=["probably", "likely"],
            operator=">=",
            threshold=0.66,
            anchor="IPCC AR5 'likely' (66–100%); Sherman Kent 'probable' (63–87%)",
        ),
        schemas.HedgeEntry(
            words=["very likely", "highly likely"],
            operator=">=",
            threshold=0.90,
            anchor="IPCC AR5 'very likely' (90–100%)",
        ),
        schemas.HedgeEntry(
            words=["almost certainly", "definitely"],
            operator=">=",
            threshold=0.95,
            anchor="Sherman Kent 'almost certain' (93% ± 6%)",
        ),
        schemas.HedgeEntry(
            words=["unlikely"],
            operator="<=",
            threshold=0.33,
            anchor="IPCC AR5 'unlikely' (0–33%)",
        ),
    ]

    s3_cfg = config.SNAPSHOTS["S3"]
    headline = schemas.HeadlineInfo(
        focus="lapse_risk",
        title="When we say a customer is 70% likely to lapse, about that share really do.",
        subtitle=(
            f"Calibrated 90-day lapse model verified on held-out S2 (3,247 customers): "
            f"Brier score {float(prim_s2['brier_score']):.4f}, Brier skill score +{100 * float(prim_s2['brier_skill_score']):.1f}% vs base rate, "
            f"ROC-AUC {float(prim_s2['roc_auc']):.4f}, 10-bin calibration error {float(prim_s2['ece_10_bins']):.4f}. "
            f"Paired with soft GMM segment memberships ({float(gmm_gate['boundary_share_pct']):.2f}% boundary share)."
        ),
        brier_score=round(float(prim_s2["brier_score"]), 4),
        brier_skill_score=round(float(prim_s2["brier_skill_score"]), 4),
        roc_auc=round(float(prim_s2["roc_auc"]), 4),
        ece_10_bins=round(float(prim_s2["ece_10_bins"]), 4),
        gmm_boundary_share_pct=round(float(gmm_gate["boundary_share_pct"]), 2),
        bootstrap_boundary_share_pct=round(float(boot_gate["boundary_share_pct"]), 2),
    )

    return schemas.MetaResponse(
        dataset_name="UCI Online Retail II",
        dataset_id=502,
        doi="10.24432/C5CG6D",
        licence="CC BY 4.0",
        snapshot="S3",
        snapshot_date=str(s3_cfg["snapshot_date"]),
        snapshot_date_display="10 Dec 2011",
        feature_window=f"{s3_cfg['feature_start']} to {s3_cfg['feature_end']}",
        customer_count=n_customers,
        default_method=config.DEFAULT_METHOD,
        methods=["gmm", "bootstrap"],
        segments=segments_info,
        hedge_lexicon=hedge_entries,
        headline=headline,
        example_questions=EXAMPLE_QUESTIONS,
    )


@app.post("/api/ask", response_model=schemas.AskResponse)
def post_ask(req: schemas.AskRequest) -> schemas.AskResponse:
    """Parse a natural-language question, bind safe SQL parameters, and return rows."""
    overrides = req.overrides or schemas.AskOverrides()
    method = overrides.method if overrides.method in ("gmm", "bootstrap") else config.DEFAULT_METHOD

    parsed = parser.parse_question(req.question, default_method=method)
    if not parsed.is_supported or parsed.template_id is None:
        tokens = extract_recognized_tokens(req.question)
        return schemas.AskResponse(
            status="refused",
            question=req.question,
            interpretation=parsed.interpretation,
            refusal_reason=parsed.refusal_reason,
            suggestions=REFUSAL_SUGGESTIONS,
            tokens=tokens,
            thresholds={},
            threshold_controls=[],
            template_id=None,
            sql="",
            params={},
            columns=[],
            rows=[],
            row_count=0,
            summary=schemas.AskSummary(matched=0),
        )

    params = dict(parsed.params)
    if overrides.method in ("gmm", "bootstrap"):
        params["method"] = overrides.method

    # Build threshold controls and apply slider overrides (tau, tau2)
    threshold_controls: list[schemas.ThresholdControlItem] = []
    thresholds_map: dict[str, float] = {}

    if parsed.template_id == "Q1":
        is_upper = params.get("max_p", 1.0) < 1.0 and params.get("tau", 0.0) == 0.0
        base_val = float(params["max_p"]) if is_upper else float(params.get("tau", 0.66))
        if overrides.tau is not None:
            base_val = float(overrides.tau)
            if is_upper:
                params["max_p"] = base_val
            else:
                params["tau"] = base_val
                params["only_top_segment"] = False
            parsed.interpretation = (
                f"Showing customers"
                f"{' in ' + params['country'] if params.get('country') else ''} "
                f"with P({params['seg']}) {'≤' if is_upper else '≥'} {base_val:.2f} "
                f"(method = '{params['method']}')."
            )
        hedge_word = str(parsed.thresholds_used.get("hedge", "threshold"))
        thresholds_map[hedge_word] = round(base_val, 2)
        threshold_controls.append(
            schemas.ThresholdControlItem(
                param_key="tau",
                hedge_word=hedge_word,
                predicate=f"P({params['seg']})",
                operator="<=" if is_upper else ">=",
                value=round(base_val, 2),
            )
        )

    elif parsed.template_id == "Q2":
        base_val = float(overrides.tau) if overrides.tau is not None else float(params.get("boundary", config.BOUNDARY_P))
        params["boundary"] = base_val
        if overrides.tau is not None:
            parsed.interpretation = (
                f"Showing boundary customers"
                f"{' in ' + params['country'] if params.get('country') else ''} "
                f"with max(p) < {base_val:.2f} and their normalised entropy "
                f"(method = '{params['method']}')."
            )
        thresholds_map["boundary"] = round(base_val, 2)
        threshold_controls.append(
            schemas.ThresholdControlItem(
                param_key="tau",
                hedge_word="boundary",
                predicate="max(p)",
                operator="<",
                value=round(base_val, 2),
            )
        )

    elif parsed.template_id == "Q6":
        # First threshold: segment (if present)
        seg_name = params.get("seg")
        if seg_name is not None:
            is_upper1 = params.get("max_p1", 1.0) < 1.0 and params.get("tau1", 0.0) == 0.0
            val1 = float(params["max_p1"]) if is_upper1 else float(params.get("tau1", 0.66))
            if overrides.tau is not None:
                val1 = float(overrides.tau)
                if is_upper1:
                    params["max_p1"] = val1
                else:
                    params["tau1"] = val1
                    params["only_top_segment"] = False
            thresholds_map[f"P({seg_name})"] = round(val1, 2)
            threshold_controls.append(
                schemas.ThresholdControlItem(
                    param_key="tau",
                    hedge_word=f"P({seg_name})",
                    predicate=f"P({seg_name})",
                    operator="<=" if is_upper1 else ">=",
                    value=round(val1, 2),
                )
            )
        # Second threshold: lapse risk
        is_upper2 = params.get("max_p2", 1.0) < 1.0 and params.get("tau2", 0.0) == 0.0
        val2 = float(params["max_p2"]) if is_upper2 else float(params.get("tau2", 0.66))
        if overrides.tau2 is not None:
            val2 = float(overrides.tau2)
            if is_upper2:
                params["max_p2"] = val2
            else:
                params["tau2"] = val2
        elif overrides.tau is not None and seg_name is None:
            val2 = float(overrides.tau)
            if is_upper2:
                params["max_p2"] = val2
            else:
                params["tau2"] = val2

        thresholds_map["P(lapse)"] = round(val2, 2)
        threshold_controls.append(
            schemas.ThresholdControlItem(
                param_key="tau2" if seg_name is not None else "tau",
                hedge_word="P(lapse)",
                predicate="P(lapse in 90d)",
                operator="<=" if is_upper2 else ">=",
                value=round(val2, 2),
            )
        )
        if overrides.tau is not None or overrides.tau2 is not None:
            seg_part = (
                f"P({seg_name}) {'≤' if params.get('max_p1', 1.0) < 1.0 and params.get('tau1', 0.0) == 0.0 else '≥'} {thresholds_map[f'P({seg_name})']:.2f}"
                if seg_name is not None
                else "their most probable segment"
            )
            lapse_part = f"P(lapse) {'≤' if is_upper2 else '≥'} {val2:.2f}"
            parsed.interpretation = (
                f"Showing customers"
                f"{' in ' + params['country'] if params.get('country') else ''} "
                f"with {seg_part} and {lapse_part} (method = '{params['method']}')."
            )

    con = get_readonly_con()
    try:
        sql_text = prob_queries.load_template_sql(parsed.template_id)
        df = prob_queries.run_template(con, parsed.template_id, params)

        # Compute summary metrics (matched, hard_count, expected_count, expected_revenue)
        matched = len(df)
        hard_count: int | None = None
        expected_count: float | None = None
        expected_revenue: float | None = None

        if parsed.template_id in ("Q1", "Q5"):
            expected_count = round(float(df["p"].sum()), 2) if not df.empty else 0.0
            expected_revenue = (
                round(float((df["p"] * df["monetary"]).sum()), 2) if not df.empty else 0.0
            )
            seg_target = params.get("seg")
            if seg_target:
                q3_df = prob_queries.run_template(
                    con, "Q3", {"method": params["method"], "country": params.get("country")}
                )
                seg_row = q3_df[q3_df["segment"] == seg_target]
                if not seg_row.empty:
                    hard_count = int(seg_row.iloc[0]["hard_count"])
        elif parsed.template_id == "Q2":
            expected_count = float(matched)
            expected_revenue = round(float(df["monetary"].sum()), 2) if not df.empty else 0.0
        elif parsed.template_id == "Q3" and not df.empty:
            hard_count = int(df["hard_count"].sum())
            expected_count = round(float(df["expected_size"].sum()), 2)
        elif parsed.template_id == "Q4" and not df.empty:
            hard_count = int(df["hard_count"].sum())
            expected_revenue = round(float(df["expected_revenue"].sum()), 2)
        elif parsed.template_id == "Q6":
            expected_count = round(float(df["p_segment"].sum()), 2) if not df.empty else 0.0
            expected_revenue = (
                round(float((df["p_segment"] * df["monetary"]).sum()), 2)
                if not df.empty
                else 0.0
            )
            hard_count = matched
    finally:
        con.close()

    tokens = extract_recognized_tokens(req.question, thresholds_map)
    return schemas.AskResponse(
        status="ok",
        question=req.question,
        interpretation=parsed.interpretation,
        refusal_reason=None,
        suggestions=[],
        tokens=tokens,
        thresholds=thresholds_map,
        threshold_controls=threshold_controls,
        template_id=parsed.template_id,
        sql=sql_text,
        params=params,
        columns=list(df.columns),
        rows=_clean_records(df),
        row_count=len(df),
        summary=schemas.AskSummary(
            matched=matched,
            hard_count=hard_count,
            expected_count=expected_count,
            expected_revenue=expected_revenue,
        ),
    )


@app.get("/api/segments", response_model=schemas.SegmentsResponse)
def get_segments(
    method: str = Query(default=config.DEFAULT_METHOD),
) -> schemas.SegmentsResponse:
    """Return segment profiles, expected sizes, tree rules and max-p histograms."""
    if method not in ("gmm", "bootstrap"):
        raise HTTPException(status_code=400, detail="method must be 'gmm' or 'bootstrap'")

    con = get_readonly_con()
    try:
        q3_df = prob_queries.run_template(con, "Q3", {"method": method, "country": None})
        q4_df = prob_queries.run_template(con, "Q4", {"method": method, "country": None})
        seg_meta_df = con.execute("SELECT segment, description, tree_rule FROM segments").df()

        # Per-customer top segment and max_p under `method`
        cust_top_df = con.execute(
            """
            WITH ranked AS (
                SELECT
                    sm.customer_id,
                    sm.segment,
                    sm.p,
                    ROW_NUMBER() OVER (
                        PARTITION BY sm.customer_id
                        ORDER BY sm.p DESC,
                        CASE sm.segment
                            WHEN 'Champions' THEN 1
                            WHEN 'Loyal' THEN 2
                            WHEN 'At-Risk' THEN 3
                            WHEN 'New' THEN 4
                            ELSE 5
                        END
                    ) AS rn
                FROM segment_membership AS sm
                WHERE sm.snapshot = 'S3' AND sm.method = ?
            )
            SELECT
                r.customer_id,
                r.segment,
                r.p AS max_p,
                cf.recency_days,
                cf.frequency,
                cf.monetary
            FROM ranked AS r
            JOIN customer_features AS cf
              ON cf.customer_id = r.customer_id AND cf.snapshot = 'S3'
            WHERE r.rn = 1
            """,
            [method],
        ).df()
    finally:
        con.close()

    km_exp_df = pd.read_csv(config.TABLES_DIR / "kmeans_vs_expected_sizes.csv")
    stab_df = pd.read_csv(config.TABLES_DIR / "segment_stability.csv")
    gate_df = pd.read_csv(config.TABLES_DIR / "gate.csv")
    gate_row = gate_df[gate_df["method"] == method].iloc[0]

    q3_map = q3_df.set_index("segment").to_dict(orient="index")
    q4_map = q4_df.set_index("segment").to_dict(orient="index")
    meta_map = seg_meta_df.set_index("segment").to_dict(orient="index")
    km_map = km_exp_df.set_index("segment").to_dict(orient="index")
    stab_map = stab_df.set_index("segment").to_dict(orient="index")

    total_customers = len(cust_top_df)
    edges = np.linspace(0.2, 1.0, 9)  # 8 clean bins from 0.20 to 1.00

    details: list[schemas.SegmentDetail] = []
    for seg_name in SEGMENT_ORDER:
        sub = cust_top_df[cust_top_df["segment"] == seg_name]
        counts, _ = np.histogram(sub["max_p"].to_numpy(), bins=edges)
        hist_bins = [
            schemas.HistogramBin(
                bin_lower=round(float(edges[i]), 2),
                bin_upper=round(float(edges[i + 1]), 2),
                count=int(counts[i]),
            )
            for i in range(len(counts))
        ]

        q3_item = q3_map[seg_name]
        q4_item = q4_map[seg_name]
        meta_item = meta_map[seg_name]
        km_item = km_map[seg_name]
        stab_item = stab_map[seg_name]

        details.append(
            schemas.SegmentDetail(
                name=seg_name,
                description=str(meta_item["description"]),
                tree_rule=str(meta_item["tree_rule"]),
                hard_count=int(q3_item["hard_count"]),
                expected_size=round(float(q3_item["expected_size"]), 2),
                std_dev=round(float(q3_item["std_dev_independent"]), 2),
                kmeans_hard_count=int(km_item["kmeans_hard_count"]),
                share_of_customers_pct=round(100.0 * int(q3_item["hard_count"]) / total_customers, 2),
                mean_recency_days=round(float(sub["recency_days"].mean()), 2),
                median_recency_days=round(float(sub["recency_days"].median()), 1),
                mean_frequency=round(float(sub["frequency"].mean()), 2),
                median_frequency=round(float(sub["frequency"].median()), 1),
                mean_monetary=round(float(sub["monetary"].mean()), 2),
                median_monetary=round(float(sub["monetary"].median()), 2),
                hard_revenue=round(float(q4_item["hard_revenue"]), 2),
                expected_revenue=round(float(q4_item["expected_revenue"]), 2),
                ave_pp=round(float(sub["max_p"].mean()), 4),
                jaccard_mean=round(float(stab_item["jaccard_mean"]), 4),
                max_p_histogram=hist_bins,
            )
        )

    return schemas.SegmentsResponse(
        method=method,
        customer_count=total_customers,
        boundary_count=int(gate_row["n_boundary_max_p_lt_0_6"]),
        boundary_share_pct=round(float(gate_row["boundary_share_pct"]), 2),
        mean_normalised_entropy=round(float(gate_row["mean_normalised_entropy"]), 4),
        segments=details,
    )


@app.get("/api/segments/map", response_model=schemas.SegmentsMapResponse)
def get_segments_map(
    method: str = Query(default=config.DEFAULT_METHOD),
) -> schemas.SegmentsMapResponse:
    """Return one point per S3 customer for the 3,961-point uncertainty scatter map."""
    if method not in ("gmm", "bootstrap"):
        raise HTTPException(status_code=400, detail="method must be 'gmm' or 'bootstrap'")

    con = get_readonly_con()
    try:
        df = con.execute(
            """
            WITH ranked AS (
                SELECT
                    sm.customer_id,
                    sm.segment,
                    sm.p,
                    ROW_NUMBER() OVER (
                        PARTITION BY sm.customer_id
                        ORDER BY sm.p DESC,
                        CASE sm.segment
                            WHEN 'Champions' THEN 1
                            WHEN 'Loyal' THEN 2
                            WHEN 'At-Risk' THEN 3
                            WHEN 'New' THEN 4
                            ELSE 5
                        END
                    ) AS rn
                FROM segment_membership AS sm
                WHERE sm.snapshot = 'S3' AND sm.method = ?
            )
            SELECT
                cf.customer_id AS id,
                c.country,
                cf.recency_days,
                ROUND(cf.monetary, 2) AS monetary,
                cf.frequency,
                r.segment,
                ROUND(r.p, 4) AS max_p,
                ROUND(lr.p_lapse_90d, 4) AS p_lapse_90d
            FROM customer_features AS cf
            JOIN customers AS c ON c.customer_id = cf.customer_id
            JOIN ranked AS r ON r.customer_id = cf.customer_id AND r.rn = 1
            JOIN lapse_risk AS lr ON lr.customer_id = cf.customer_id AND lr.snapshot = 'S3'
            WHERE cf.snapshot = 'S3'
            ORDER BY cf.customer_id
            """,
            [method],
        ).df()
    finally:
        con.close()

    points = [
        schemas.CustomerMapPoint(
            id=int(row.id),
            country=str(row.country),
            recency_days=int(row.recency_days),
            monetary=float(row.monetary),
            frequency=int(row.frequency),
            segment=str(row.segment),
            max_p=float(row.max_p),
            p_lapse_90d=float(row.p_lapse_90d),
        )
        for row in df.itertuples(index=False)
    ]
    return schemas.SegmentsMapResponse(
        method=method,
        customer_count=len(points),
        points=points,
    )


@app.get("/api/customers/{customer_id}", response_model=schemas.CustomerDetailResponse)
def get_customer_detail(customer_id: int) -> schemas.CustomerDetailResponse:
    """Return full customer features, GMM + bootstrap membership bars, lapse risk and tree rule path."""
    con = get_readonly_con()
    try:
        cust_row = con.execute(
            """
            SELECT
                c.customer_id,
                c.country,
                CAST(c.first_purchase AS VARCHAR) AS first_purchase,
                CAST(c.last_purchase AS VARCHAR) AS last_purchase,
                cf.recency_days,
                cf.frequency,
                ROUND(cf.monetary, 2) AS monetary,
                cf.tenure_days,
                ROUND(cf.avg_basket, 2) AS avg_basket,
                ROUND(lr.p_lapse_90d, 4) AS p_lapse_90d,
                lr.model_version
            FROM customers AS c
            JOIN customer_features AS cf
              ON cf.customer_id = c.customer_id AND cf.snapshot = 'S3'
            JOIN lapse_risk AS lr
              ON lr.customer_id = c.customer_id AND lr.snapshot = 'S3'
            WHERE c.customer_id = ?
            """,
            [customer_id],
        ).fetchone()

        if cust_row is None:
            raise HTTPException(
                status_code=404,
                detail=f"Customer {customer_id} is not present in snapshot S3.",
            )

        mem_rows = con.execute(
            """
            SELECT method, segment, ROUND(p, 4) AS p
            FROM segment_membership
            WHERE customer_id = ? AND snapshot = 'S3'
            """,
            [customer_id],
        ).fetchall()
    finally:
        con.close()

    gmm_dict = {seg: 0.0 for seg in SEGMENT_ORDER}
    boot_dict = {seg: 0.0 for seg in SEGMENT_ORDER}
    for m_name, seg_name, prob in mem_rows:
        if m_name == "gmm":
            gmm_dict[str(seg_name)] = float(prob)
        elif m_name == "bootstrap":
            boot_dict[str(seg_name)] = float(prob)

    top_gmm = max(SEGMENT_ORDER, key=lambda s: gmm_dict[s])
    top_boot = max(SEGMENT_ORDER, key=lambda s: boot_dict[s])

    recency_days = int(cust_row[4])
    frequency = int(cust_row[5])
    monetary = float(cust_row[6])
    tree_seg, tree_steps, leaf_rule = evaluate_tree_rule_path(
        recency_days=recency_days,
        frequency=frequency,
        monetary=monetary,
    )

    return schemas.CustomerDetailResponse(
        customer_id=int(cust_row[0]),
        country=str(cust_row[1]),
        first_purchase=str(cust_row[2]),
        last_purchase=str(cust_row[3]),
        recency_days=recency_days,
        frequency=frequency,
        monetary=monetary,
        tenure_days=int(cust_row[7]),
        avg_basket=float(cust_row[8]),
        top_segment_gmm=top_gmm,
        max_p_gmm=round(gmm_dict[top_gmm], 4),
        top_segment_bootstrap=top_boot,
        max_p_bootstrap=round(boot_dict[top_boot], 4),
        membership_gmm=[
            schemas.SegmentProbabilityItem(segment=s, p=round(gmm_dict[s], 4))
            for s in SEGMENT_ORDER
        ],
        membership_bootstrap=[
            schemas.SegmentProbabilityItem(segment=s, p=round(boot_dict[s], 4))
            for s in SEGMENT_ORDER
        ],
        p_lapse_90d=float(cust_row[9]),
        model_version=str(cust_row[10]),
        tree_predicted_segment=tree_seg,
        tree_rule_path=tree_steps,
        tree_leaf_rule=leaf_rule,
    )


@app.get("/api/lapse", response_model=schemas.LapseResponse)
def get_lapse() -> schemas.LapseResponse:
    """Return S2 lapse metrics, reliability diagram bins, baseline comparison, and top 20 high-monetary at-risk customers."""
    s2_df = pd.read_csv(config.TABLES_DIR / "lapse_s2_eval.csv")
    s1_df = pd.read_csv(config.TABLES_DIR / "lapse_s1_cv.csv")
    bins_df = pd.read_csv(config.TABLES_DIR / "lapse_reliability_bins_s2.csv")
    base_rates_df = pd.read_csv(config.TABLES_DIR / "lapse_baseline_s1_rates.csv")
    s3_seg_df = pd.read_csv(config.TABLES_DIR / "lapse_s3_by_segment.csv")

    con = get_readonly_con()
    try:
        high_val_df = con.execute(
            """
            WITH ranked_gmm AS (
                SELECT
                    customer_id,
                    segment,
                    p,
                    ROW_NUMBER() OVER (
                        PARTITION BY customer_id
                        ORDER BY p DESC,
                        CASE segment
                            WHEN 'Champions' THEN 1
                            WHEN 'Loyal' THEN 2
                            WHEN 'At-Risk' THEN 3
                            WHEN 'New' THEN 4
                            ELSE 5
                        END
                    ) AS rn
                FROM segment_membership
                WHERE snapshot = 'S3' AND method = 'gmm'
            ),
            q75 AS (
                SELECT QUANTILE_CONT(monetary, 0.75) AS p75_monetary
                FROM customer_features
                WHERE snapshot = 'S3'
            )
            SELECT
                cf.customer_id,
                c.country,
                rg.segment,
                ROUND(rg.p, 4) AS p_segment,
                cf.recency_days,
                cf.frequency,
                ROUND(cf.monetary, 2) AS monetary,
                ROUND(cf.avg_basket, 2) AS avg_basket,
                ROUND(lr.p_lapse_90d, 4) AS p_lapse_90d
            FROM customer_features AS cf
            JOIN customers AS c ON c.customer_id = cf.customer_id
            JOIN lapse_risk AS lr ON lr.customer_id = cf.customer_id AND lr.snapshot = 'S3'
            JOIN ranked_gmm AS rg ON rg.customer_id = cf.customer_id AND rg.rn = 1
            CROSS JOIN q75
            WHERE cf.snapshot = 'S3'
              AND cf.monetary >= q75.p75_monetary
            ORDER BY lr.p_lapse_90d DESC, cf.monetary DESC
            LIMIT 20
            """
        ).df()
    finally:
        con.close()

    return schemas.LapseResponse(
        s2_metrics=_clean_records(s2_df),
        s1_cv_metrics=_clean_records(s1_df),
        reliability_bins=_clean_records(bins_df),
        baseline_s1_rates=_clean_records(base_rates_df)[0],
        s3_by_segment=_clean_records(s3_seg_df),
        high_value_at_risk=_clean_records(high_val_df),
    )


@app.get("/api/quality", response_model=schemas.QualityResponse)
def get_quality() -> schemas.QualityResponse:
    """Return cleaning funnel, BIC grid, bootstrap ARI distribution, Jaccard, tree fidelity and NL metrics."""
    funnel_df = pd.read_csv(config.TABLES_DIR / "cleaning_funnel.csv")
    raw_tot_df = pd.read_csv(config.TABLES_DIR / "raw_totals.csv")
    clean_sum_df = pd.read_csv(config.TABLES_DIR / "clean_sales_summary.csv")
    gmm_df = pd.read_csv(config.TABLES_DIR / "gmm_grid.csv")
    km_df = pd.read_csv(config.TABLES_DIR / "kmeans_grid.csv")
    boot_stab_df = pd.read_csv(config.TABLES_DIR / "bootstrap_stability.csv")
    seg_stab_df = pd.read_csv(config.TABLES_DIR / "segment_stability.csv")
    gate_df = pd.read_csv(config.TABLES_DIR / "gate.csv")
    tree_fid_df = pd.read_csv(config.TABLES_DIR / "tree_fidelity.csv")
    tree_seg_df = pd.read_csv(config.TABLES_DIR / "tree_fidelity_by_segment.csv")
    nl_sum_df = pd.read_csv(config.TABLES_DIR / "nl_summary.csv")
    nl_dev_df = pd.read_csv(config.TABLES_DIR / "nl_dev_results.csv")
    nl_err_df = pd.read_csv(config.TABLES_DIR / "nl_error_analysis.csv")

    ari_samples_path = config.TABLES_DIR / "bootstrap_ari_samples.csv"
    ari_hist: list[schemas.HistogramBin] = []
    if ari_samples_path.exists():
        ari_samples = pd.read_csv(ari_samples_path)["ari"].to_numpy()
        edges = np.linspace(0.45, 1.00, 12)
        counts, _ = np.histogram(ari_samples, bins=edges)
        ari_hist = [
            schemas.HistogramBin(
                bin_lower=round(float(edges[i]), 3),
                bin_upper=round(float(edges[i + 1]), 3),
                count=int(counts[i]),
            )
            for i in range(len(counts))
        ]

    test_csv = config.PROJECT_ROOT / "eval" / "questions_test.csv"
    test_count = 0
    if test_csv.exists():
        tdf = pd.read_csv(test_csv)
        test_count = len(tdf)

    test_status = (
        "Test set: waiting for questions written by someone else"
        if test_count == 0
        else f"Test set evaluated ({test_count} questions)"
    )

    return schemas.QualityResponse(
        cleaning_funnel=_clean_records(funnel_df),
        raw_totals=_clean_records(raw_tot_df)[0],
        clean_sales_summary=_clean_records(clean_sum_df)[0],
        gmm_grid=_clean_records(gmm_df),
        kmeans_grid=_clean_records(km_df),
        bootstrap_stability=_clean_records(boot_stab_df)[0],
        bootstrap_ari_histogram=ari_hist,
        segment_stability=_clean_records(seg_stab_df),
        gate=_clean_records(gate_df),
        tree_fidelity=_clean_records(tree_fid_df)[0],
        tree_fidelity_by_segment=_clean_records(tree_seg_df),
        nl_summary=_clean_records(nl_sum_df),
        nl_dev_results=_clean_records(nl_dev_df),
        nl_error_analysis=_clean_records(nl_err_df),
        test_set_status=test_status,
        test_set_question_count=test_count,
    )


@app.get("/api/assets/architecture.png")
def get_architecture_diagram() -> FileResponse:
    """Serve `docs/architecture.png` for the About page."""
    arch_path = config.PROJECT_ROOT / "docs" / "architecture.png"
    if not arch_path.exists():
        raise HTTPException(status_code=404, detail="architecture.png not found")
    return FileResponse(arch_path, media_type="image/png")


# Serve built React app from `web/dist` when present
WEB_DIST = config.PROJECT_ROOT / "web" / "dist"
if (WEB_DIST / "assets").exists():
    app.mount("/assets", StaticFiles(directory=str(WEB_DIST / "assets")), name="assets")


@app.get("/{full_path:path}", include_in_schema=False)
def serve_spa(full_path: str):
    """Serve `web/dist/index.html` for client-side routes when built."""
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="API endpoint not found")
    candidate = WEB_DIST / full_path
    if full_path and candidate.is_file():
        return FileResponse(candidate)
    index_file = WEB_DIST / "index.html"
    if index_file.is_file():
        return FileResponse(index_file)
    return {
        "message": "Probably API is running. Build `web/dist` with `npm run build` to serve the UI here."
    }
