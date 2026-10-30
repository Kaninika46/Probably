# Phase 8 explained: Streamlit app, read-only database safety and deployment prep

## What we did, in plain words

**1. Build the four-tab Streamlit application (`app/streamlit_app.py`).**
Following `CLAUDE.md` section 7.11, the app opens `app/app.duckdb` (`1,847,296` bytes, 3,961 S3 customers) using `duckdb.connect("app/app.duckdb", read_only=True)` cached via `@st.cache_resource`, and organises the interface into four tabs:

1. **Ask (`Ask (NL -> SQL)`):**
   - Radio toggle between `bootstrap` ($B=100$ resample co-assignment, default) and `gmm` (`predict_proba` posteriors).
   - Six one-click example question chips covering Q1–Q6.
   - Text input box for plain-English questions.
   - Displays the human-readable **interpretation sentence** (`resp.parsed.interpretation`), a checkbox + **slider (`0.05`–`0.99`) to override the active probability threshold** (`Q1`, `Q2`, `Q6`), an expander showing the exact **parameterised SQL template and bound parameters**, an **Altair chart** tailored to the template type, and the **results table**.
2. **Segments (`Segments & Tree Rules`):**
   - Original-unit centroid profiles for the 5 confirmed segments (`Champions`, `Loyal`, `At-Risk`, `New`, `Hibernating`, `reports/tables/segment_profiles_spherical_k5.csv`).
   - Comparison of hard K-Means counts ($K=5$) vs. GMM and bootstrap expected sizes (`reports/tables/kmeans_vs_expected_sizes.csv`) and expected revenue (`reports/tables/q4_expected_revenue_bootstrap.csv`).
   - Surrogate depth-4 decision-tree rules (`segments.tree_rule` and `reports/tables/tree_rules.md`), with the explicit note that axis-aligned tree explanations are approximations (86.80% test fidelity across 16 leaves).
3. **Model Quality (`Model Quality`):**
   - Displays the real evaluation tables and figures from `reports/tables/` and `reports/figures/`: the 6-step cleaning funnel (`cleaning_funnel.csv`, `cleaning_funnel.png`), GMM BIC/AIC selection curves (`gmm_bic_aic.png`), go/no-go gate report and $\max p$ histogram (`gate.csv`, `gate_max_p_hist.png`), S2 lapse evaluation and reliability diagram (`lapse_s2_eval.csv`, `lapse_reliability_s2.png`), and NL dev evaluation (`nl_summary.csv`).
4. **About (`About & Limitations`):**
   - Shows the system architecture (`docs/architecture.png`), the IPCC AR5 / Sherman Kent hedge lexicon table, the UCI Online Retail II citation, and the key methodological limitations.

**2. Pin the spaCy model wheel URL for Streamlit Community Cloud (`requirements.txt`).**
Streamlit Community Cloud installs packages directly from `requirements.txt` without running a post-install `python -m spacy download` step. We pinned `en_core_web_sm @ https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl` to match `spacy==3.8.18`.

## Likely viva questions

**1. How do you guarantee that a user of the Streamlit app cannot modify or drop tables in the database?**
We use defence in depth across three layers:
1. `src/nl/parser.py` refuses any question containing SQL syntax markers (`;`, `--`, `/*`, `1=1`, `UNION SELECT`) and outputs only a `template_id` (`Q1`–`Q6`) plus typed parameters.
2. `src/prob_queries.py` checks every parameter against strict allow-lists (`ALLOWED_METHODS`, `ALLOWED_SEGMENTS`, valid DB countries) and binds them as DuckDB parameters rather than formatting strings.
3. `get_readonly_connection()` in `app/streamlit_app.py` opens `app/app.duckdb` with `read_only=True`, so DuckDB itself rejects any `INSERT`, `UPDATE`, `CREATE` or `DROP` statement at the storage engine level (`tests/test_app.py::test_app_readonly_connection_refuses_writes`).

**2. What happens when the user moves the probability threshold slider in the Ask tab?**
When a question maps to a threshold-based template (`Q1`, `Q2` or `Q6`), the app first shows the threshold chosen by the hedge lexicon (for example, `0.66` for *"probably"*). If the user enables the override slider and moves it (say from `0.66` to `0.85`), `engine.answer_question(..., threshold_override=0.85)` re-runs the exact same parameterised SQL template with `$tau = 0.85` (for Q1), `$boundary = 0.85` (for Q2) or `$tau2 = 0.85` (for Q6), updating the interpretation sentence, the Altair chart and the returned customer rows in real time.

**3. Why does the app use `@st.cache_resource` for the DuckDB connection?**
Streamlit re-executes the Python script from top to bottom on every widget interaction. Opening a new DuckDB file handle on every click would waste I/O and could cause file-lock contention. Decorating `get_readonly_connection()` with `@st.cache_resource` opens `app/app.duckdb` once in `read_only=True` mode and shares that read-only connection across reruns.

**4. Why did you pin `en_core_web_sm` as a direct GitHub wheel URL in `requirements.txt`?**
In spaCy 3.8, language models are distributed as Python wheels hosted on GitHub releases rather than PyPI. On Streamlit Community Cloud, deployment only runs `pip install -r requirements.txt`. Pinning `en_core_web_sm @ https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl` ensures `pip` installs the exact 3.8.0 model compatible with `spacy==3.8.18`.

**5. Why does `app/app.duckdb` only include snapshot S3 (`3,961` customers) instead of all `5,852` historical customers?**
Snapshots S1 (`2010-09-10`) and S2 (`2011-09-10`) exist only in the offline pipeline to train and evaluate the 90-day lapse model without temporal leakage. Analysts using the live application are querying current customer segments and future 90-day lapse probabilities as of the end of the dataset (`S3 = 2011-12-10`, covering the `3,961` customers active in the 9-month window `2011-03-10` to `2011-12-09`).
