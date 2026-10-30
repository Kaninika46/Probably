"""Streamlit application: Probably High-Value? (Phase 8, CLAUDE.md section 7.11).

Connects exclusively to `app/app.duckdb` with `read_only=True` and executes
all user queries solely through the parameterised templates Q1-Q6.
"""

from pathlib import Path
import sys

import altair as alt
import duckdb
import pandas as pd
import streamlit as st

# Ensure `from src import ...` works when launched via `streamlit run app/streamlit_app.py`
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src import config  # noqa: E402
from src.nl import engine, lexicon  # noqa: E402

EXAMPLE_QUESTIONS = [
    ("Probable Champions in Germany (Q1)", "Which customers in Germany are probably Champions?"),
    ("Boundary customers under GMM (Q2)", "Which boundary customers have uncertain segment membership under GMM?"),
    ("Expected segment sizes (Q3)", "What is the expected segment size for each segment?"),
    ("Expected revenue per segment (Q4)", "What is the expected revenue per segment?"),
    ("Top 10 Loyal customers (Q5)", "Show the top 10 Loyal customers"),
    ("At-Risk & likely lapsing (Q6)", "Which likely At-Risk customers might lapse in 90 days?"),
]


@st.cache_resource
def get_readonly_connection() -> duckdb.DuckDBPyConnection:
    """Open `app/app.duckdb` with `read_only=True` and cache the connection."""
    return duckdb.connect("app/app.duckdb", read_only=True)


def build_altair_chart(template_id: str | None, df: pd.DataFrame) -> alt.Chart | None:
    """Build an Altair chart matching the active template Q1..Q6."""
    if df is None or len(df) == 0 or template_id is None:
        return None

    if template_id in ("Q1", "Q5"):
        plot_df = df.head(40).copy()
        plot_df["customer_label"] = plot_df["customer_id"].astype(str)
        return (
            alt.Chart(plot_df)
            .mark_circle(size=90)
            .encode(
                x=alt.X("p:Q", title="Segment membership probability p", scale=alt.Scale(domain=[0, 1.05])),
                y=alt.Y("monetary:Q", title="9-month spend (£)"),
                color=alt.Color("segment:N", title="Segment"),
                tooltip=["customer_id:Q", "country:N", "segment:N", "p:Q", "recency_days:Q", "frequency:Q", "monetary:Q", "p_lapse_90d:Q"],
            )
            .properties(height=320, title="Customer spend (£) vs. segment membership probability p")
        )

    if template_id == "Q2":
        plot_df = df.head(100).copy()
        return (
            alt.Chart(plot_df)
            .mark_circle(size=85)
            .encode(
                x=alt.X("max_p:Q", title="Maximum membership probability max(p)"),
                y=alt.Y("normalised_entropy:Q", title="Normalised Shannon entropy"),
                color=alt.Color("top_segment:N", title="Most probable segment"),
                tooltip=["customer_id:Q", "country:N", "top_segment:N", "max_p:Q", "second_segment:N", "second_p:Q", "normalised_entropy:Q", "monetary:Q"],
            )
            .properties(height=320, title="Boundary customers: normalised entropy vs. max(p)")
        )

    if template_id == "Q3":
        melted = df.melt(
            id_vars=["segment"],
            value_vars=["hard_count", "expected_size"],
            var_name="count_type",
            value_name="customers",
        )
        return (
            alt.Chart(melted)
            .mark_bar()
            .encode(
                x=alt.X("segment:N", sort="-y", title="Segment"),
                y=alt.Y("customers:Q", title="Number of S3 customers"),
                color=alt.Color("count_type:N", title="Measure"),
                xOffset="count_type:N",
                tooltip=["segment:N", "count_type:N", "customers:Q"],
            )
            .properties(height=320, title="Q3: Hard count vs. expected segment size SUM(p)")
        )

    if template_id == "Q4":
        melted = df.melt(
            id_vars=["segment"],
            value_vars=["hard_revenue", "expected_revenue"],
            var_name="revenue_type",
            value_name="revenue_gbp",
        )
        return (
            alt.Chart(melted)
            .mark_bar()
            .encode(
                x=alt.X("segment:N", sort="-y", title="Segment"),
                y=alt.Y("revenue_gbp:Q", title="9-month revenue (£)"),
                color=alt.Color("revenue_type:N", title="Measure"),
                xOffset="revenue_type:N",
                tooltip=["segment:N", "revenue_type:N", "revenue_gbp:Q"],
            )
            .properties(height=320, title="Q4: Hard-label revenue vs. expected revenue SUM(p × monetary)")
        )

    if template_id == "Q6":
        plot_df = df.head(100).copy()
        return (
            alt.Chart(plot_df)
            .mark_circle(size=90)
            .encode(
                x=alt.X("p:Q", title="Segment probability p", scale=alt.Scale(domain=[0, 1.05])),
                y=alt.Y("p_lapse_90d:Q", title="90-day lapse probability P(lapse)", scale=alt.Scale(domain=[0, 1.05])),
                size=alt.Size("monetary:Q", title="9-month spend (£)"),
                color=alt.Color("segment:N", title="Segment"),
                tooltip=["customer_id:Q", "country:N", "segment:N", "p:Q", "p_lapse_90d:Q", "recency_days:Q", "frequency:Q", "monetary:Q"],
            )
            .properties(height=320, title="Q6: 90-day lapse risk vs. segment membership probability (separate conditions)")
        )

    return None


def render_ask_tab(con: duckdb.DuckDBPyConnection) -> None:
    st.subheader("Ask the Probabilistic Customer Database in Plain English")
    st.caption(
        "Questions are parsed with spaCy + EntityRuler and mapped to parameterised SQL templates Q1–Q6. "
        "Hedge words ('possibly', 'probably', 'very likely', 'almost certainly', 'unlikely') map to "
        "IPCC AR5 and Sherman Kent probability thresholds."
    )

    col_method, _ = st.columns([1, 2])
    with col_method:
        default_method = st.radio(
            "Default membership probability method",
            options=["bootstrap", "gmm"],
            index=0,
            horizontal=True,
            help="'bootstrap' = B=100 resample co-assignment; 'gmm' = GaussianMixture posterior predict_proba.",
        )

    st.markdown("**Example questions (click a chip to load):**")
    chip_cols = st.columns(3)
    if "active_question" not in st.session_state:
        st.session_state["active_question"] = EXAMPLE_QUESTIONS[0][1]

    for idx, (label, q_text) in enumerate(EXAMPLE_QUESTIONS):
        if chip_cols[idx % 3].button(label, key=f"chip_{idx}", use_container_width=True):
            st.session_state["active_question"] = q_text

    question = st.text_input(
        "Your question:",
        value=st.session_state["active_question"],
        key="question_input",
    )

    # First pass parse to check whether a threshold slider applies
    preview = engine.answer_question(con, question, default_method=default_method)
    parsed = preview.parsed

    override_val = None
    if parsed.is_supported and parsed.template_id in ("Q1", "Q2", "Q6"):
        if parsed.template_id == "Q1":
            default_thr = float(
                parsed.params.get("max_p", 0.33)
                if (parsed.params.get("max_p", 1.0) < 1.0 and parsed.params.get("tau", 0.0) == 0.0)
                else parsed.params.get("tau", 0.66)
            )
        elif parsed.template_id == "Q2":
            default_thr = float(parsed.params.get("boundary", config.BOUNDARY_P))
        else:
            default_thr = float(parsed.params.get("tau2", 0.66))

        use_override = st.checkbox(
            f"Override active probability threshold (parsed default = {default_thr:.2f})",
            value=False,
        )
        if use_override:
            override_val = st.slider(
                "Probability threshold override",
                min_value=0.05,
                max_value=0.99,
                value=min(max(default_thr, 0.05), 0.99),
                step=0.01,
            )

    resp = engine.answer_question(
        con,
        question,
        default_method=default_method,
        threshold_override=override_val,
    )

    if not resp.parsed.is_supported:
        st.warning(resp.parsed.interpretation)
        return

    st.info(f"**Interpretation:** {resp.parsed.interpretation}")

    m1, m2, m3 = st.columns(3)
    m1.metric("Template selected", resp.parsed.template_id or "—")
    m2.metric("Rows returned", f"{len(resp.rows):,}")
    m3.metric("Probability method", str(resp.parsed.params.get("method", default_method)))

    with st.expander("View parameterised SQL template & bound parameters"):
        st.code(resp.sql_text, language="sql")
        st.json(resp.parsed.params)

    chart = build_altair_chart(resp.parsed.template_id, resp.rows)
    if chart is not None:
        st.altair_chart(chart, use_container_width=True)

    st.dataframe(resp.rows, use_container_width=True, hide_index=True)


def render_segments_tab(con: duckdb.DuckDBPyConnection) -> None:
    st.subheader("S3 Customer Segments: Original-Unit Profiles, Expected Sizes & Tree Rules")

    prof_path = config.TABLES_DIR / "segment_profiles_spherical_k5.csv"
    if prof_path.exists():
        st.markdown("#### 1. Segment Centroid Profiles in Original Units (`spherical, K = 5`)")
        prof_df = pd.read_csv(prof_path)
        st.dataframe(prof_df, use_container_width=True, hide_index=True)

    comp_path = config.TABLES_DIR / "kmeans_vs_expected_sizes.csv"
    if comp_path.exists():
        st.markdown("#### 2. Hard K-Means Counts vs. GMM & Bootstrap Expected Sizes (`Q3`)")
        comp_df = pd.read_csv(comp_path)
        st.dataframe(comp_df, use_container_width=True, hide_index=True)

    q4_path = config.TABLES_DIR / "q4_expected_revenue_bootstrap.csv"
    if q4_path.exists():
        st.markdown("#### 3. Hard-Label Revenue vs. Expected Revenue (`Q4`, Bootstrap)")
        q4_df = pd.read_csv(q4_path)
        st.dataframe(q4_df, use_container_width=True, hide_index=True)

    st.markdown("#### 4. Surrogate Decision-Tree Explanations (`max_depth = 4`, Original Units)")
    st.caption(
        "Note: Axis-aligned decision-tree rules are post-hoc approximations to the smooth GMM clusters "
        "(86.80% agreement on the held-out 30% test split across 16 leaves)."
    )
    seg_rows = con.execute(
        "SELECT segment, description, tree_rule FROM segments ORDER BY segment"
    ).df()
    st.dataframe(seg_rows, use_container_width=True, hide_index=True)

    rules_md_path = config.TABLES_DIR / "tree_rules.md"
    if rules_md_path.exists():
        with st.expander("View full surrogate decision tree (`reports/tables/tree_rules.md`)"):
            st.markdown(rules_md_path.read_text(encoding="utf-8"))


def render_quality_tab() -> None:
    st.subheader("Model Quality & Evaluation Metrics")

    st.markdown("#### 1. Data Cleaning Funnel (`data_quality_log`)")
    funnel_path = config.TABLES_DIR / "cleaning_funnel.csv"
    if funnel_path.exists():
        st.dataframe(pd.read_csv(funnel_path), use_container_width=True, hide_index=True)
    funnel_fig = config.FIGURES_DIR / "cleaning_funnel.png"
    if funnel_fig.exists():
        st.image(str(funnel_fig), caption="Rows remaining after each SQL cleaning rule")

    st.markdown("#### 2. Clustering Validity, Stability & Go/No-Go Gate")
    gate_path = config.TABLES_DIR / "gate.csv"
    if gate_path.exists():
        st.dataframe(pd.read_csv(gate_path), use_container_width=True, hide_index=True)
    c1, c2 = st.columns(2)
    gmm_fig = config.FIGURES_DIR / "gmm_bic_aic.png"
    gate_fig = config.FIGURES_DIR / "gate_max_p_hist.png"
    if gmm_fig.exists():
        c1.image(str(gmm_fig), caption="GMM BIC & AIC curves across K = 2..8")
    if gate_fig.exists():
        c2.image(str(gate_fig), caption="Distribution of max(p): GMM (12.50% boundary) vs. Bootstrap (3.84% boundary)")

    st.markdown("#### 3. 90-Day Lapse Model: S1 5-Fold CV & Held-Out S2 Evaluation")
    s2_path = config.TABLES_DIR / "lapse_s2_eval.csv"
    if s2_path.exists():
        st.dataframe(pd.read_csv(s2_path), use_container_width=True, hide_index=True)
    rel_fig = config.FIGURES_DIR / "lapse_reliability_s2.png"
    if rel_fig.exists():
        st.image(str(rel_fig), caption="S2 Reliability Diagram (Calibrated Logistic vs. Depth-4 Tree & Two-Bin Baseline)")

    st.markdown("#### 4. NL Engine Evaluation (`eval/questions_dev.csv`)")
    nl_path = config.TABLES_DIR / "nl_summary.csv"
    if nl_path.exists():
        st.dataframe(pd.read_csv(nl_path), use_container_width=True, hide_index=True)


def render_about_tab() -> None:
    st.subheader("About Probably High-Value?")
    st.markdown(
        """
        **Course:** Data Management and AI Integration (`ABAI2009L`), Bennett University (Aug–Dec 2026)

        This project integrates three course topics:
        1. **Topic 3 (Core) — Data Mining & KDD:** 6-step SQL cleaning views, temporal snapshots S1–S3, K-Means & Gaussian Mixture Model (GMM) customer segmentation, depth-4 surrogate decision-tree rules, and calibrated 90-day lapse classification.
        2. **Topic 1 — Probabilistic & Uncertain Databases:** Block-Independent-Disjoint (BID) `segment_membership` table ($\\sum_s p_s = 1$ per customer block) and tuple-independent `lapse_risk` table, queried through exact parameterised SQL templates Q1–Q6 and checked against 10,000 Monte Carlo possible worlds.
        3. **Topic 2 — NLP for Database Interaction:** A rule-based spaCy `EntityRuler` pipeline that translates plain-English questions—including uncertainty hedge words anchored to IPCC AR5 and Sherman Kent scales—into safe, parameterised SQL queries over a `read_only=True` DuckDB connection.
        """
    )

    arch_img = config.PROJECT_ROOT / "docs" / "architecture.png"
    if arch_img.exists():
        st.image(str(arch_img), caption="System Architecture")

    st.markdown("#### Hedge Word Lexicon (IPCC AR5 & Sherman Kent)")
    hedge_rows = [
        {"Hedge phrase": k, "Operator": op, "Probability threshold": thr}
        for k, (op, thr) in lexicon.HEDGE_LEXICON.items()
    ]
    st.dataframe(pd.DataFrame(hedge_rows), use_container_width=True, hide_index=True)

    st.markdown(
        """
        #### Data & Limitations
        - **Dataset:** UCI Online Retail II (ID 502, creator Daqing Chen, DOI `10.24432/C5CG6D`, licence CC BY 4.0), covering 1,067,371 raw transaction lines from 01/12/2009 to 09/12/2011.
        - **Surrogate tree rules are approximations:** The depth-4 decision tree makes axis-aligned cuts in original RFM units to approximate curved GMM clusters in `log1p`-scaled space, achieving **86.80%** fidelity on the held-out 30% test set.
        - **Independence in Q3 variance:** Expected segment size $\\sum p$ is exact by linearity of expectation; the closed-form variance $\\sum p(1-p)$ assumes independence across customer blocks.
        - **Dependence between segment and lapse in Q6:** Because both `segment_membership.p` and `lapse_risk.p_lapse_90d` depend on `recency_days` and `frequency`, Q6 filters on two separate threshold conditions (`p >= $tau1 AND p_lapse_90d >= $tau2`) and never multiplies them.
        """
    )


def main() -> None:
    st.set_page_config(
        page_title="Probably High-Value? — Probabilistic Customer DB",
        layout="wide",
    )
    st.title("Probably High-Value?")
    st.caption(
        "Probabilistic customer segmentation & 90-day lapse risk queried in plain English "
        "(UCI Online Retail II, Snapshot S3: 3,961 active customers)"
    )

    con = get_readonly_connection()
    tab_ask, tab_segments, tab_quality, tab_about = st.tabs([
        "Ask (NL -> SQL)",
        "Segments & Tree Rules",
        "Model Quality",
        "About & Limitations",
    ])

    with tab_ask:
        render_ask_tab(con)
    with tab_segments:
        render_segments_tab(con)
    with tab_quality:
        render_quality_tab()
    with tab_about:
        render_about_tab()


if __name__ == "__main__":
    main()
