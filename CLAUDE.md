# CLAUDE.md: Probably High-Value?

This file is the project spec. Read all of it at the start of every session, then read `docs/PROGRESS.md` to see which phase is next.

## 1. What this project is

A university project for **Data Management and AI Integration (ABAI2009L)**, Bennett University, Aug–Dec 2026. The course only allows five topics or combinations of them. This project combines three:

| Topic | Course wording | What we build |
|---|---|---|
| **3 (core): Data Mining and KDD** | "Apply classification or clustering algorithms… perform knowledge discovery on structured data from a database" | SQL cleaning and features, K-Means + GMM segmentation, decision-tree rules, lapse classifier |
| **1: Probabilistic and Uncertain Databases** | "Implement a small probabilistic database with uncertain values; query using confidence levels or probabilistic inference" | BID `segment_membership` table, tuple-independent `lapse_risk` table, confidence queries Q1–Q6 |
| **2: NLP for Database Interaction** | "Convert natural language queries to SQL; rule-based or pre-trained model like spaCy or NLTK" | spaCy rule-based parser that maps questions (including hedge words) to parameterised SQL templates |

Grading is 5 marks for the presentation, 5 for execution and report, and 5 for the viva. **Every student must be able to explain every line in the viva, so clear code beats clever code.**

**USP:** segment-membership and lapse probabilities are stored as a formally defined probabilistic database and checked against what customers actually did next. Analysts query them in plain English, and words like "probably" and "almost certainly" map to published probability scales.

## 2. Architecture

The diagram is in `docs/architecture.png`. The system has three parts:

1. **Offline pipeline (Python, runs once):** ingest → mining engine (segmentation, lapse model) → evaluation. Entry point: `python -m src.pipeline --all`, or `--phase N`.
2. **Data layer:** `data/retail.duckdb`. Raw rows are loaded unchanged and never edited. Cleaning and features are SQL views and tables. Mining results are written back as probabilistic tables.
3. **Online app:** FastAPI read-only backend (`api/`) + React + TypeScript web app (`web/`) + spaCy NL engine. It queries `app/app.duckdb`, a small export of the customer-level S3 tables, opened with `read_only=True` and **only** through the templates Q1–Q6.

## 3. Data

- **Dataset:** UCI Online Retail II, id 502, DOI 10.24432/C5CG6D, licence CC BY 4.0. It has 1,067,371 rows covering 01/12/2009–09/12/2011 from a UK online retailer, and many of its customers are wholesalers.
- **Page:** https://archive.ics.uci.edu/dataset/502/online+retail+ii
- **Download:** `data/download.py` should try the UCI static zip. The URL is probably `https://archive.ics.uci.edu/static/public/502/online+retail+ii.zip`, so verify it. If the download fails, **stop and ask the user** to download the file manually into `data/raw/online_retail_II.xlsx`. Never commit raw data; add `data/raw/` and `*.duckdb` to `.gitignore`, except `app/app.duckdb`.
- **Workbook:** two sheets, expected to be "Year 2009-2010" and "Year 2010-2011". Verify the names by reading the workbook. Columns are `Invoice, StockCode, Description, Quantity, InvoiceDate, Price, Customer ID, Country`. Rename them to snake_case (`invoice, stock_code, description, quantity, invoice_date, price, customer_id, country`) and add `source_sheet`.
- Reading the xlsx is slow, so cache it once as `data/raw/online_retail_II.parquet`.

## 4. Stack

Python 3.12, with: duckdb, pandas, pyarrow, openpyxl, numpy, scipy, scikit-learn, matplotlib, spacy (+ `en_core_web_sm`), fastapi, uvicorn, httpx and pytest.
Frontend (`web/`): React 18, TypeScript, Vite, Tailwind CSS, Recharts, Lucide and self-hosted `@fontsource` fonts (`Bricolage Grotesque`, `Figtree`, `JetBrains Mono`).

- Pin exact versions in `requirements.txt`.
- Ask before adding any other dependency.
- Use `random_state=42` everywhere.

## 5. Repo layout

```
probably-high-value/
├── CLAUDE.md
├── README.md
├── requirements.txt
├── data/
│   ├── download.py
│   └── raw/                      # gitignored
├── sql/
│   ├── 01_schema.sql
│   ├── 02_clean_views.sql        # clean_sales, returns, data_quality_log
│   ├── 03_features.sql           # customer_features (S1, S2, S3), outcomes, customers
│   └── templates/                # q1_confident.sql … q6_segment_and_lapse.sql
├── src/
│   ├── config.py                 # paths, snapshot dates, thresholds, seeds (single source of truth)
│   ├── db.py                     # connections; app connection is read_only=True
│   ├── ingest.py
│   ├── clean.py                  # runs 02_clean_views.sql and fills data_quality_log
│   ├── eda.py                    # exploratory figures (Phase 1)
│   ├── features.py               # runs 03_features.sql
│   ├── segment.py                # K-Means, GMM grid, naming support
│   ├── membership.py             # GMM posteriors + bootstrap co-assignment, gate report
│   ├── rules.py                  # decision-tree surrogate + fidelity
│   ├── lapse.py                  # lapse model, calibration, S2 evaluation, S3 scoring
│   ├── prob_queries.py           # loads + runs templates with named params
│   ├── export_app_db.py          # builds app/app.duckdb
│   ├── nl/
│   │   ├── lexicon.py            # hedge words → thresholds, segment synonyms
│   │   ├── parser.py             # spaCy pipeline → ParsedQuery
│   │   └── engine.py             # ParsedQuery → template + params → rows + interpretation
│   ├── evaluate.py               # all metrics → reports/tables
│   ├── report_tables.py          # writes markdown results tables used by README
│   └── pipeline.py
├── eval/
│   ├── questions_dev.csv         # Claude may write and tune on these
│   └── questions_test.csv        # written by a HUMAN only; Claude never edits it
├── api/
│   ├── main.py                   # Read-only FastAPI app serving /api/* and web/dist
│   └── schemas.py                # Typed Pydantic response models
├── web/                          # React + TypeScript + Vite + Tailwind web app
│   ├── package.json
│   └── src/{pages,components,charts,lib,styles}/
├── app/
│   └── app.duckdb                # committed; customer-level S3 tables only
├── run_app.bat                   # Builds web/dist if needed and runs FastAPI on :8000
├── run_dev.bat                   # Starts FastAPI --reload and Vite dev server
├── reports/
│   ├── figures/
│   └── tables/
├── notebooks/                    # thin notebooks that call src/ for the presentation
├── tests/
└── docs/
    ├── architecture.png
    ├── PROGRESS.md
    ├── DECISIONS.md
    ├── FRONTEND_REPORT.md
    ├── screenshots/
    ├── references.md
    └── explainers/               # one plain-language explainer per phase
```

## 6. Database design

| Zone | Table | Columns | Notes |
|---|---|---|---|
| Raw | `raw_transactions` | invoice, stock_code, description, quantity, invoice_date, price, customer_id, country, source_sheet | Loaded unchanged |
| Clean | `clean_sales` (view) | raw columns + line_revenue (= quantity × price) + has_customer | Product sales with positive quantity and price. Rows without a `customer_id` are kept (has_customer = false) so revenue totals are complete; every customer-level table filters on `customer_id IS NOT NULL` |
| Clean | `returns` (view) | invoice, customer_id, stock_code, quantity, line_revenue | Cancellations, kept rather than deleted |
| Clean | `data_quality_log` | step_no, rule, rows_before, rows_after, revenue_affected | Becomes the cleaning funnel in the report |
| Features | `customers` | customer_id PK, country, first_purchase, last_purchase | |
| Features | `customer_features` | customer_id, snapshot, recency_days, frequency, monetary, tenure_days, avg_basket | PK (customer_id, snapshot) |
| Features | `outcomes` | customer_id, snapshot, purchased_next_90d | S1 and S2 only |
| Probabilistic | `segments` | segment PK, description, tree_rule | |
| Probabilistic | `segment_membership` | customer_id, snapshot, method ('gmm' / 'bootstrap'), segment, p | **BID table.** Block key = (customer_id, snapshot, method); Σp = 1 per block |
| Probabilistic | `lapse_risk` | customer_id, snapshot, p_lapse_90d, model_version | **Tuple-independent** probabilistic attribute |
| Eval | `eval_results` | area, metric, value, detail | Every reported number lives here or in reports/tables |

`app/app.duckdb` contains only `customers`, `customer_features`, `segments`, `segment_membership` and `lapse_risk`, all filtered to snapshot S3.

## 7. Pipeline spec

### 7.1 Ingest
- Read both sheets, add `source_sheet`, and cache to parquet.
- Load into `raw_transactions` exactly as read.
- Print the row count per sheet and the total.

### 7.2 Cleaning (SQL, logged)
Apply these rules in order. Log each one to `data_quality_log` with the rows before and after and the revenue affected.

1. **Overlap duplicates:** rows that are identical in every column except `source_sheet`, where the two sheets overlap. Keep one copy.
2. **Remaining exact duplicates:** drop them and report their revenue share.
3. **Cancellations:** invoices starting with `'C'` go to the `returns` view. They are not deleted from raw.
4. **Non-positive values:** rows with `quantity <= 0` or `price <= 0` are excluded from sales.
5. **Non-product stock codes:** postage, manual adjustments, bank charges, fees, discounts and test codes. Find them by inspecting the non-standard codes and their descriptions. List the exact codes with a comment in `02_clean_views.sql`.
6. **Missing `customer_id`:** keep these rows for revenue totals, but exclude them from every customer-level table.

Compute every count from the data. Never copy counts from blogs or GitHub. Save the funnel as `reports/tables/cleaning_funnel.csv`, plus a chart.

### 7.3 Snapshots and features

| Snapshot | Date (S) | Feature window | Outcome window | Use |
|---|---|---|---|---|
| S1 | 2010-09-10 | 2009-12-10 to 2010-09-09 | 2010-09-10 to 2010-12-09 | train lapse model |
| S2 | 2011-09-10 | 2010-12-10 to 2011-09-09 | 2011-09-10 to 2011-12-09 | test lapse model once |
| S3 | 2011-12-10 | 2011-03-10 to 2011-12-09 | none, it is in the future | segment + score for the app |

- **Who is included:** a customer belongs to a snapshot if they made at least one clean sale in its feature window.
- **`recency_days`:** S minus the date of the last purchase in the window.
- **`frequency`:** the number of distinct invoices in the window.
- **`monetary`:** the sum of `line_revenue` in the window (gross sales).
- **`tenure_days`:** S minus the customer's first purchase in all data before S.
- **`avg_basket`:** monetary / frequency.
- **`purchased_next_90d`:** 1 if there is any clean sale in the outcome window. Lapse = 1 − purchased.
- **Leakage test (required):** no feature uses a date ≥ S, and no outcome uses a date outside its window.

### 7.4 Segmentation (on S3)
- **Features:** recency_days, frequency, monetary.
- **Preprocessing:** cap frequency and monetary at the S3 99th percentile, then `log1p`, then `StandardScaler`.
- **K-Means:** K = 2…8. Record silhouette, Davies–Bouldin and Calinski–Harabasz scores.
- **GMM:** grid over K = 2…8 × covariance_type ∈ {spherical, tied, diag, full}, with `n_init=10`. Record BIC and AIC.
- **Choosing K:** propose a K and a covariance type using BIC, stability and interpretability, and explain the trade-off. **The human confirms K and the segment names at the Phase 3 checkpoint.**
- **Segment names:** derive them from the centroid profiles in original units (for example Champions, Loyal, At-risk, New, Hibernating), and justify each one with its numbers.

### 7.5 Membership probabilities and the go/no-go gate
- **`method='gmm'`:** `predict_proba` from the chosen GMM.
- **`method='bootstrap'`:** B = 100 resamples of the S3 customers, drawn with replacement.
  - Refit the chosen GMM on each resample and predict labels for **all** customers.
  - Align the labels to the reference labels with `scipy.optimize.linear_sum_assignment` on the confusion matrix.
  - p = the share of fits that put a customer in each segment.
- **Stability:** bootstrap Adjusted Rand Index vs the reference (median and IQR), and Hennig-style per-segment Jaccard. Read Jaccard ≥ 0.75 as stable, 0.6–0.75 as doubtful and < 0.6 as unstable.
- **Gate report (`reports/tables/gate.csv` + histogram):** for each method, the % of customers with max p < 0.6, the mean normalised entropy and the AvePP per segment. Write a recommendation:
  - if the boundary share is meaningful, the headline is segment confidence;
  - if it is tiny, the headline is lapse risk.

  **Stop and let the human decide.**

### 7.6 Decision-tree rules
- Fit a `DecisionTreeClassifier(max_depth=4)` on S3 features in **original units**, so the thresholds are readable, predicting the most probable segment.
- Use a 70/30 split and report fidelity (agreement with the clustering) on the 30%, plus the number of leaves.
- Export the rules as text into `segments.tree_rule` and `reports/tables/tree_rules.md`.
- State in the docs that tree explanations of clusters are approximations.

### 7.7 Lapse model
- **Training:** S1 features → lapse label.
- **Primary model, chosen in advance:** `LogisticRegression` on log1p + scaled features, calibrated with `CalibratedClassifierCV(method='sigmoid', cv=5)` on S1 only.
- **Comparisons:**
  - a two-bin rule baseline: the lapse rate in S1 for recency > 90 days vs ≤ 90;
  - a calibrated depth-4 decision tree.
- **Model selection:** use cross-validation on S1 only. **S2 is used once, for the final report.**
- **S2 metrics:** Brier score, ROC-AUC, log loss, ECE (10 bins) and a reliability diagram.
- **Scoring:** score S3 into `lapse_risk` (`model_version` = git short hash or date).
- Call it "lapse (no purchase in 90 days)", never "churn". Mention BG/NBD in `docs/references.md` as the classic alternative that was not used.

### 7.8 Probabilistic query templates
SQL files in `sql/templates/`. They use DuckDB named parameters (`$seg`, `$tau`, `$k`, …) and only these:

| Id | Name | Logic | Semantics |
|---|---|---|---|
| Q1 | Confident members | p ≥ $tau for $seg | exact |
| Q2 | Boundary customers | MAX(p) < $boundary (default 0.6), with normalised entropy | exact |
| Q3 | Expected segment size | SUM(p) per segment, plus variance SUM(p(1−p)) | mean exact by linearity of expectation; variance assumes independence (say so) |
| Q4 | Expected revenue | SUM(p × monetary) per segment | exact |
| Q5 | Top-k members | ORDER BY p DESC LIMIT $k | exact |
| Q6 | Segment + lapse filter | p ≥ $tau1 AND p_lapse_90d ≥ $tau2 | two separate conditions; **never multiply** (both depend on recency) |

Every template takes `$method` (default `'bootstrap'`) and an optional `$country`. Also produce a comparison table of hard K-Means counts vs expected sizes.

**Stretch:** a possible-worlds Monte Carlo sampler (`src/worlds.py`) that checks Q3 numerically and estimates P(segment size ≥ N).

### 7.9 NL engine (spaCy, rule-based)
- **Pipeline:** `en_core_web_sm` + `EntityRuler`/`PhraseMatcher` for segment names and synonyms, countries (loaded from the DB) and metrics (revenue, spend, orders).
- **Extraction:** numbers and comparison words ("more than", "at least", "under", "top 10").
- **Hedge lexicon:** attach each hedge word to the nearest predicate (the segment or lapse mention it modifies).

| Words | Threshold | Anchor (cite in docs/references.md) |
|---|---|---|
| possibly, might | P ≥ 0.33 | IPCC "about as likely as not" starts at 33% |
| probably, likely | P ≥ 0.66 | IPCC "likely" 66–100%; Kent "probable" 63–87% |
| very likely, highly likely | P ≥ 0.90 | IPCC "very likely" 90–100% |
| almost certainly, definitely | P ≥ 0.95 | Kent "almost certain" 93% ± 6 |
| unlikely | P ≤ 0.33 | IPCC "unlikely" 0–33% |
| (none) | most probable segment | same as a hard label |

- **Output:** a `ParsedQuery` dataclass with intent, template_id, params, thresholds_used and an interpretation sentence. For example: "Showing customers in Germany with P(Champions) ≥ 0.66 and P(lapse) ≥ 0.66."
- Out-of-scope or ambiguous questions get a polite refusal with an example of a supported question.
- **Security:** user text **never** becomes SQL. It only fills typed, allow-listed parameters. Use a row limit, and the app connection is read-only.

### 7.10 Evaluation (`src/evaluate.py` → `eval_results` + `reports/tables`)
- **Cleaning:** the funnel.
- **Clustering:** silhouette, Davies–Bouldin, Calinski–Harabasz, BIC/AIC curves, bootstrap ARI and per-segment Jaccard.
- **Probability informativeness:** max-p histogram, normalised entropy, AvePP and boundary share, GMM vs bootstrap.
- **Lapse:** S2 Brier, ROC-AUC, log loss, ECE and reliability diagram, compared with the rule baseline.
- **Tree:** fidelity and number of leaves.
- **NL:**
  - execution accuracy on `questions_test.csv` (compare result sets, order-insensitive unless the gold SQL has ORDER BY);
  - template match rate;
  - out-of-scope rejection rate;
  - hedge-threshold accuracy;
  - plus an error analysis table by failure type.

### 7.11 Web application (FastAPI read-only backend + React frontend)
- **Architecture:** Read-only FastAPI server (`api/main.py`) exposes `/api/*` and serves the production-built React SPA (`web/dist`).
- **Overview (`/`):** Gate headline tile, S2 calibration curve, command bar, example chips, and 5-segment summary strip.
- **Ask (`/ask`):** Command bar (`/` focuses), 6 template chips, interpretation sentence, ParseStrip, threshold sliders (150ms debounce), summary metrics, sortable results table with inline `ProbabilityBar`s, companion chart, and collapsible SQL drawer.
- **Segments (`/segments`):** Uncertainty map (`<canvas>` scatter plot of all 3,961 customers), 5 segment cards (median R/F/M, surrogate tree rule, max-p histogram), and hard vs expected size bar chart.
- **Lapse risk (`/lapse`):** 4 metric tiles (Brier score, skill score +16.72%, ROC-AUC, 10-bin ECE), 10-bin reliability diagram with count histogram, model vs baselines comparison table, and top high-value at-risk customers.
- **Model quality (`/quality`):** 6-step cleaning funnel horizontal bars, GMM BIC grid across K=2..8 and 4 covariance structures, bootstrap ARI histogram, Hennig per-segment Jaccard bars (0.75 reference line), and NL dev evaluation.
- **About (`/about`):** System architecture diagram, S1–S3 timeline, Topic 1/2/3 mapping, limitations, and UCI citation.
- **Customer Drawer:** Slide-over detail view showing 9-month facts, BID segment distribution, lapse risk gauge, recent clean transactions, and surrogate tree path.
- **Database safety:** Connects exclusively with `duckdb.connect("app/app.duckdb", read_only=True)`. All user queries execute strictly through parameterised templates Q1–Q6.
- **Run scripts:** `run_app.bat` (production on `:8000`) and `run_dev.bat` (development with hot reload).

## 8. Rules (always)

1. **Never invent, estimate or round up numbers.** Every number in the README, report, slides or explainers must come from a file in `reports/tables/` or from `eval_results`, produced by code you ran. If something fails or looks wrong, say so plainly.
2. **No placeholders** ("TBD", "[insert]", "TO CONFIRM", "XX%") in any deliverable. If a value doesn't exist yet, leave the section out and note it in `docs/PROGRESS.md`.
3. **Write viva-friendly code:**
   - small functions with descriptive names;
   - docstrings that explain *why*, not just *what*;
   - a comment on every non-obvious modelling line;
   - no clever one-liners or premature abstractions.
4. **Reproducibility:** a fresh clone plus the downloaded xlsx runs end to end with `python -m src.pipeline --all`. Every config value lives in `src/config.py`.
5. Raw data is never edited and never committed.
6. **Never write, edit or look at answers for `eval/questions_test.csv`.** Create it with headers only (`q_id,question,gold_sql,author`) plus `docs/how_to_write_test_questions.md`. A human writes it before parser tuning ends. Tune only on `questions_dev.csv`.
7. **Ask the user before** you:
   - change snapshot dates, thresholds or the topic scope;
   - add a dependency;
   - delete files;
   - rewrite git history.
8. **After every phase:**
   - run `pytest`;
   - update `docs/PROGRESS.md` (what was done, real key numbers, open decisions);
   - write `docs/explainers/phase-N.md` (plain-language explanation plus 5 likely viva questions answered with this project's real results);
   - commit with a clear message;
   - **stop for review.**

## 9. Phases

| Phase | Work | Done when |
|---|---|---|
| 0 | Scaffold repo, `.gitignore`, `requirements.txt`, `config.py`, `db.py`, `download.py`, pytest setup, `docs/PROGRESS.md` | `pytest` runs; the download works or the user has been asked |
| 1 | Ingest + cleaning views + `data_quality_log` + EDA figures | Cleaning funnel table and chart produced from real data; cleaning tests pass |
| 2 | Snapshots S1–S3, `customers`, `customer_features`, `outcomes` | Leakage tests pass; per-snapshot customer counts and base lapse rates reported |
| 3 | K-Means + GMM grids, proposed K, segment profiles | **Checkpoint:** human confirms K, covariance type and names |
| 4 | Membership probabilities (gmm + bootstrap), stability, gate report, tree rules | BID test passes (Σp = 1); **checkpoint:** human makes the gate decision |
| 5 | Lapse model, S2 evaluation, S3 scoring | Reliability diagram + metrics vs baseline produced |
| 6 | Templates Q1–Q6, `prob_queries.py`, `export_app_db.py` | Template tests pass; `app.duckdb` built and opens read-only |
| 7 | NL engine + dev set + evaluation harness | Dev accuracy reported; injection and out-of-scope tests pass; test set run only after the human says it is frozen |
| 8 | Web application (FastAPI + React) + deployment prep | Web app runs locally on :8000 from run_app.bat; read-only verified |
| 9 | README (results table generated by `report_tables.py`, architecture image, Mermaid diagram, how to run), final figures, `references.md` | No placeholders anywhere; every number traceable |

If time is short: Phases 0–6 plus a basic Phase 8 are the minimum complete project. Phase 7 and the stretch items come next.

## 10. Required tests (pytest)

- **Cleaning:** row counts never increase down the funnel; `clean_sales` has no quantity ≤ 0 or price ≤ 0; `returns` only contains invoices starting with `'C'`.
- **Features:** no leakage (see 7.3); one row per (customer_id, snapshot).
- **BID:** Σp = 1 (±1e-6) per (customer_id, snapshot, method); all p in [0, 1]; Q3 expected sizes sum to the number of customers.
- **Read-only:** a write through the app connection raises an error.
- **Templates:** each runs with sample parameters and returns the documented columns.
- **NL:**
  - dev questions map to their expected templates;
  - injection strings (`'; DROP TABLE customers; --`, `1 OR 1=1`) never reach SQL as text;
  - out-of-scope questions are refused;
  - the hedge lexicon returns the thresholds in the table above.

## 11. References to put in docs/references.md

- UCI Online Retail II, creator Daqing Chen, DOI 10.24432/C5CG6D (copy the exact citation from the dataset page)
- Fayyad, Piatetsky-Shapiro & Smyth (1996), *From data mining to knowledge discovery in databases*
- scikit-learn docs: GaussianMixture and the BIC model-selection example; Pedregosa et al. (2011)
- Dalvi & Suciu, and Van den Broeck & Suciu, on probabilistic databases (tuple-independent and BID tables, possible worlds); the MayBMS manual (`repair key`, `conf()`)
- IPCC AR5 Guidance Note on consistent treatment of uncertainties (likelihood scale); Sherman Kent, *Words of Estimative Probability*
- Yu et al. (2018), Spider (exact match vs execution accuracy); Li et al. (2023), BIRD
- Dasgupta, Frost, Moshkovitz & Rashtchian (ICML 2020), *Explainable k-means and k-medians clustering*
- Hennig (2007), clusterwise stability with the Jaccard coefficient
- Fader, Hardie & Lee (2005), BG/NBD, mentioned as an alternative that was not used

Verify every reference before adding it, and never invent page numbers or DOIs.
