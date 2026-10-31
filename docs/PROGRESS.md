# Progress

## Phase 0: Scaffold (done)

**What was done**
- Created the repo layout, `.gitignore`, `requirements.txt`, `src/config.py`, `src/db.py`, `data/download.py`, `pytest.ini` and `tests/test_setup.py`.
- `requirements.txt` pins the exact versions pip installed into a fresh Python 3.12.10 venv.
- `data/download.py` checked the UCI URL `https://archive.ics.uci.edu/static/public/502/online+retail+ii.zip` (HTTP 200). It downloaded the zip (45,622,418 bytes) and extracted `online_retail_II.xlsx` (45,622,278 bytes).
- `pytest`: 2 passed. One test checks that the snapshot windows are ordered and the other checks that the app connection refuses writes.

**Changes to the spec (agreed with the user)**
- Python version changed from 3.11 to **3.12** (CLAUDE.md section 4). The machine only had 3.10, so the user installed 3.12.10.
- `clean_sales` keeps rows without a `customer_id`, flagged with `has_customer = false`, so revenue totals stay complete. Every customer-level table filters on `customer_id IS NOT NULL` (CLAUDE.md section 6 reworded so the spec no longer contradicts itself).
- Added `src/eda.py` for the Phase 1 exploratory figures (CLAUDE.md section 5).

**Open items**
- The spaCy model `en_core_web_sm` is not installed yet. It will be pinned by wheel URL in Phase 7 (CLAUDE.md section 7.11).

## Phase 1: Ingest, cleaning, EDA (done)

**What was done**
- `src/ingest.py` reads the sheet names from the workbook (they are `Year 2009-2010` and `Year 2010-2011`, as CLAUDE.md expected). It renames the columns to snake_case, adds `source_sheet`, caches the data to `data/raw/online_retail_II.parquet` and loads `raw_transactions`.
  - Text columns (`invoice`, `stock_code`, `description`, `country`) are stored as text, because Excel mixes numbers and text in them.
  - `customer_id` is stored as a whole number. The code first checks that no ID has a fractional part.
- `sql/02_clean_views.sql` implements the six rules as a chain of views. The non-product codes are kept in a `non_product_codes` table, with a comment on each code.
- `src/clean.py` fills `data_quality_log` and writes `reports/tables/raw_totals.csv`, `reports/tables/cleaning_funnel.csv`, `reports/tables/non_product_codes.csv`, `reports/tables/non_product_reasons.csv` and `reports/figures/cleaning_funnel.png`.
- `src/eda.py` writes three figures (`eda_monthly_revenue.png`, `eda_top_countries.png`, `eda_quantity_price.png`) and their tables, plus `reports/tables/clean_sales_summary.csv`.
- `src/pipeline.py` runs Phase 1 with `--phase 1` or `--all`.
- `pytest`: 11 passed (9 cleaning tests and 2 setup tests).

**Key numbers** (from `reports/tables/`)
- Raw rows: 525,461 (Year 2009-2010) + 541,910 (Year 2010-2011) = 1,067,371; raw net revenue: £19,287,250.57 (`raw_totals.csv`).
- The sheets overlap: the first sheet ends 2010-12-09 20:01 and the second starts 2010-12-01 08:26.

| Step | Rule | Rows before | Rows after | Revenue affected (£) | Share before step | Share of raw |
|---|---|---|---|---|---|---|
| 1 | Overlap duplicates between sheets | 1,067,371 | 1,044,848 | 377,488.45 | 1.96% | 1.96% |
| 2 | Remaining exact duplicates | 1,044,848 | 1,033,036 | 54,228.42 | 0.29% | 0.28% |
| 3 | Cancellations moved to returns | 1,033,036 | 1,013,932 | -1,462,050.61 | -7.75% | -7.58% |
| 4 | Quantity or price not positive | 1,013,932 | 1,007,913 | -158,676.14 | -0.78% | -0.82% |
| 5 | Non-product stock codes | 1,007,913 | 1,003,357 | 832,398.81 | 4.07% | 4.32% |
| 6 | Missing customer_id (excluded from customer analysis) | 1,003,357 | 776,596 | 2,575,278.90 | 13.11% | 13.35% |

- `clean_sales`: 1,003,357 lines, 39,516 invoices, 5,852 customers, 4,896 products, 43 countries, £19,643,861.64 revenue. Of that revenue, £17,068,582.74 has a customer.

**Decisions made in this phase**
- Rule 1 drops a row from the second sheet when the first sheet has an identical row in every other column.
- Rule 5 excludes 21 stock codes (listed in `reports/tables/non_product_codes.csv`, totals per reason in `reports/tables/non_product_reasons.csv`): postage, carriage, manual adjustments, bad debt, bank and Amazon fees, a discount code, test products, `S` (samples) and seven gift-voucher codes.
  - The user confirmed excluding `S` and the gift vouchers. Samples are adjustments, not product sales. Vouchers are a payment method, so counting the voucher purchase and its later redemption would double-count revenue.
  - The 7 voucher codes are 0.0086% of the revenue that reached rule 5 (0.0091% of raw revenue).
- Both the funnel and the non-product tables report two revenue shares (`share_of_revenue_before_step_pct` and `share_of_raw_revenue_pct`, where the raw base is £19,287,250.57 from `raw_totals.csv`).
- `revenue_affected` = revenue before the step minus revenue after. It is negative for steps 3 and 4 because the rows removed there have negative quantities or prices.

**Housekeeping after Phase 1**
- Added the architecture diagram as `docs/architecture.png`.

## Phase 2: Snapshots, customer features, outcomes (done)

**What was done**
- `src/features.py` copies `config.SNAPSHOTS` into a `snapshots` table in DuckDB and executes `sql/03_features.sql`, then exports `reports/tables/snapshot_summary.csv`.
- `sql/03_features.sql` builds:
  - `customers`: 5,852 unique customers (`customer_id` PK, `country`, `first_purchase`, `last_purchase`). For the 12 customers whose orders span two countries, `ARG_MAX(country, invoice_date)` selects the country on their most recent order.
  - `customer_features`: 10,464 rows across S1, S2 and S3 (`customer_id`, `snapshot`, `recency_days`, `frequency`, `monetary`, `tenure_days`, `avg_basket`).
  - `outcomes`: 6,503 rows across S1 and S2 (`customer_id`, `snapshot`, `purchased_next_90d`). S3 has no rows in `outcomes` because its outcome window is in the future.
- `src/pipeline.py` now runs Phase 2 with `--phase 2` or `--all`.
- `tests/test_features.py`: 5 new tests verifying customer PK uniqueness, `(customer_id, snapshot)` uniqueness, feature-window membership, zero feature leakage from dates `>= S`, and zero outcome leakage outside `[outcome_start, outcome_end]`.
- `pytest`: 16 passed.

**Key numbers** (from `reports/tables/snapshot_summary.csv`)

| Snapshot | Date (S) | Feature window | Outcome window | Customers | Mean / median recency (d) | Mean / median frequency | Mean / median monetary (£) | Mean / median tenure (d) | Mean / median basket (£) | Purchased next 90d | Lapsed next 90d | Base lapse rate |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| S1 | 2010-09-10 | 2009-12-10 – 2010-09-09 | 2010-09-10 – 2010-12-09 | 3,256 | 87.89 / 72.0 | 3.53 / 2.0 | 1,598.59 / 585.77 | 181.07 / 192.0 | 366.80 / 287.52 | 1,908 (58.60%) | 1,348 | 41.40% |
| S2 | 2011-09-10 | 2010-12-10 – 2011-09-09 | 2011-09-10 – 2011-12-09 | 3,247 | 88.36 / 69.0 | 3.40 / 2.0 | 1,555.65 / 552.00 | 405.23 / 460.0 | 401.43 / 283.12 | 1,871 (57.62%) | 1,376 | 42.38% |
| S3 | 2011-12-10 | 2011-03-10 – 2011-12-09 | — | 3,961 | 71.38 / 43.0 | 3.70 / 2.0 | 1,768.34 / 631.89 | 436.50 / 478.0 | 408.99 / 296.64 | — | — | — |

## Phase 3: Segmentation grids and candidate profiles (done)

**What was done**
- `src/segment.py` preprocesses S3 RFM (`3,961` customers): caps `frequency` at the 99th percentile (`26.00` invoices, 35 customers capped) and `monetary` at the 99th percentile (`£15,942.81`, 40 customers capped), applies `log1p`, and standardizes with `StandardScaler` (`reports/tables/s3_preprocessing.csv`).
- Runs the K-Means grid for $K = 2\dots 8$ (`reports/tables/kmeans_grid.csv`, `reports/figures/kmeans_selection.png`).
- Runs the GMM grid for $K = 2\dots 8 \times \text{covariance\_type} \in \{\text{spherical, tied, diag, full}\}$ with `n_init=10` (`reports/tables/gmm_grid.csv`, `reports/figures/gmm_bic_aic.png`).
- Documents why `diag` and `full` produce artificially negative BIC (`reports/tables/gmm_diag_degeneracy.csv`): components collapse onto discrete integer planes `frequency = 1` (`1,480` customers, `min = max = 1`) and `frequency = 2` (`781` customers, `min = max = 2`).
- Exports original-unit centroid profiles and $B = 100$ bootstrap stability metrics for the primary proposal (`spherical, K=5`: `reports/tables/segment_profiles_spherical_k5.csv`, `reports/figures/segment_profiles_s3.png`) and the 4-cluster alternatives (`segment_profiles_spherical_k4.csv`, `segment_profiles_tied_k4.csv`).
- `tests/test_segment.py`: 4 new tests; `pytest`: 20 passed.

**Provisional choice at Phase 3 checkpoint (`docs/DECISIONS.md`): `covariance_type = 'spherical'`, `K = 5` (PROVISIONAL)**

| Segment | Cluster ID | Customers | Share (%) | Mean / median recency (d) | Mean / median frequency | Mean / median monetary (£) | Mean tenure (d) | Mean basket (£) | AvePP | Mean Jaccard ($B=100$) |
|---|---|---|---|---|---|---|---|---|---|---|
| **Champions** | 4 | 258 | 6.51% | 8.60 / 5.0 | 18.66 / 14.0 | 12,635.95 / 5,455.26 | 620.17 | 620.79 | 0.8934 | 0.8669 |
| **Loyal** | 0 | 1,105 | 27.90% | 21.72 / 17.0 | 5.04 / 5.0 | 2,154.78 / 1,579.14 | 478.98 | 530.84 | 0.8490 | 0.8775 |
| **At-Risk** | 1 | 933 | 23.55% | 86.66 / 72.0 | 2.36 / 2.0 | 978.14 / 786.57 | 447.68 | 517.56 | 0.7880 | 0.8449 |
| **New** | 2 | 636 | 16.06% | 23.19 / 22.0 | 1.42 / 1.0 | 301.97 / 284.55 | 320.97 | 234.11 | 0.8086 | 0.8758 |
| **Hibernating** | 3 | 1,029 | 25.98% | 156.38 / 159.0 | 1.14 / 1.0 | 251.34 / 229.23 | 406.09 | 234.67 | 0.8723 | 0.9009 |

- `K = 5`, `covariance_type = 'spherical'`, and segment names `Champions`, `Loyal`, `At-Risk`, `New`, `Hibernating` are marked **PROVISIONAL** in `docs/DECISIONS.md` (with `spherical, K=4` and `tied, K=4` preserved in `reports/tables/`).

## Phase 4: Membership probabilities, gate report, tree rules (done)

**What was done**
- `src/membership.py` builds the `segments` table (5 rows) and the BID `segment_membership` table (`39,610` rows = `3,961` S3 customers × 5 segments × 2 methods `'gmm'` and `'bootstrap'`).
- Exports bootstrap stability (`reports/tables/bootstrap_stability.csv`, `reports/tables/segment_stability.csv`) and the go/no-go gate report (`reports/tables/gate.csv`, `reports/tables/gate_ave_pp.csv`, `reports/figures/gate_max_p_hist.png`).
- `src/rules.py` fits a depth-4 `DecisionTreeClassifier` in original units on a 70/30 stratified split (`2,772` train / `1,189` test), writes readable rules to `segments.tree_rule` and `reports/tables/tree_rules.md`, and saves `reports/tables/tree_fidelity.csv` and `reports/tables/tree_fidelity_by_segment.csv`.
- `tests/test_membership.py`: 5 new tests verifying BID invariants ($\sum p = 1$ per block, $p \in [0, 1]$, expected sizes sum to 3,961) and rule/gate exports; `pytest`: 25 passed.

**Key numbers** (from `reports/tables/gate.csv` and `reports/tables/tree_fidelity.csv`)

| Method | Customers | Boundary ($\max p < 0.6$) | Boundary share (%) | Mean $\max p$ | Median $\max p$ | Mean norm. entropy | AvePP Champions | AvePP Loyal | AvePP At-Risk | AvePP New | AvePP Hibernating |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `gmm` | 3,961 | 495 | **12.50%** | 0.8371 | 0.8996 | 0.2526 | 0.8934 | 0.8490 | 0.7880 | 0.8086 | 0.8723 |
| `bootstrap` | 3,961 | 152 | **3.84%** | 0.9329 | 0.9900 | 0.1041 | 0.9490 | 0.9339 | 0.9191 | 0.9409 | 0.9352 |

- **Surrogate decision tree (`max_depth=4`):** 16 leaves, training fidelity **89.72%**, held-out 30% test fidelity **86.80%** (`Loyal` 91.87%, `Hibernating` 90.94%, `Champions` 87.01%, `New` 81.68%, `At-Risk` 79.64%).
- **Provisional decision at Phase 4 Gate Checkpoint (`docs/DECISIONS.md`):** keep both `gmm` (`12.50%` boundary share, provisional default for UI/API) and `bootstrap` (`3.84%` boundary share, stability check), lead the Overview with 90-day lapse risk, and pair segment confidence with 90-day lapse risk (`Q6`).

## Phase 5: Lapse model, S2 evaluation, S3 scoring (done)

**What was done**
- `src/lapse.py` trains the primary calibrated logistic regression (`log1p` $\to$ `StandardScaler` $\to$ `LogisticRegression` wrapped in `CalibratedClassifierCV(method='sigmoid', cv=5)`) on S1 only (`3,256` customers, base lapse rate `41.40%`), alongside the two-bin recency rule (`recency_days > 90`: `54.71%` vs `<= 90`: `31.74%`, `reports/tables/lapse_baseline_s1_rates.csv`) and a calibrated depth-4 decision tree.
- Evaluates 5-fold out-of-fold CV on S1 (`reports/tables/lapse_s1_cv.csv`) and tests once on held-out S2 (`3,247` customers, base lapse rate `42.38%`, `reports/tables/lapse_s2_eval.csv`, `reports/tables/lapse_reliability_bins_s2.csv`, `reports/figures/lapse_reliability_s2.png`).
- Scores all `3,961` S3 customers into the tuple-independent `lapse_risk` table (`model_version = '4cfb5e3'`) and exports `reports/tables/lapse_s3_by_segment.csv`.
- `tests/test_lapse.py`: 3 new tests; `pytest`: 28 passed.

**Key numbers** (from `reports/tables/lapse_s1_cv.csv` and `reports/tables/lapse_s2_eval.csv`)

| Split | Model | Customers | Base lapse rate | Mean predicted $P$ | Brier score $\downarrow$ | Brier skill score $\uparrow$ | ROC-AUC $\uparrow$ | Log loss $\downarrow$ | 10-bin ECE $\downarrow$ |
|---|---|---|---|---|---|---|---|---|---|
| **S1 (5-fold OOF CV)** | `logistic_calibrated` (primary) | 3,256 | 0.4140 | 0.4140 | **0.2087** | 0.1397 | 0.7177 | **0.6020** | **0.0081** |
| **S1 (5-fold OOF CV)** | `tree_depth4_calibrated` | 3,256 | 0.4140 | 0.4134 | **0.2087** | **0.1398** | **0.7186** | 0.6032 | 0.0267 |
| **S1 (5-fold OOF CV)** | `two_bin_recency_90d` | 3,256 | 0.4140 | 0.4140 | 0.2299 | 0.0523 | 0.6060 | 0.6521 | 0.0001 |
| **S2 (Held-out test)** | `logistic_calibrated` (primary) | 3,247 | 0.4238 | 0.4008 | **0.2034** | **0.1672** | **0.7390** | **0.5870** | 0.0343 |
| **S2 (Held-out test)** | `tree_depth4_calibrated` | 3,247 | 0.4238 | 0.3801 | 0.2143 | 0.1225 | 0.7106 | 0.6145 | 0.0774 |
| **S2 (Held-out test)** | `two_bin_recency_90d` | 3,247 | 0.4238 | 0.4125 | 0.2264 | 0.0730 | 0.6371 | 0.6448 | **0.0206** |

## Phase 6: Probabilistic SQL templates Q1–Q6, possible-worlds check, `app.duckdb` (done)

**What was done**
- Created `sql/templates/q1_confident.sql` … `q6_segment_and_lapse.sql` using DuckDB named parameters (`$method`, `$seg`, `$tau`, `$k`, `$country`, etc.).
- `src/prob_queries.py` validates parameters against allow-lists (`ALLOWED_METHODS`, `ALLOWED_SEGMENTS`, valid DB countries, probability bounds) before binding them, and exports `reports/tables/kmeans_vs_expected_sizes.csv`, `q3_expected_sizes_bootstrap.csv`, `q3_expected_sizes_gmm.csv`, `q4_expected_revenue_bootstrap.csv` and `q4_expected_revenue_gmm.csv`.
- `src/worlds.py` (stretch item) draws $M = 10,000$ possible worlds (`random_state=42`) to verify Q3 expected sizes and variances numerically and estimate $P(\text{size} \ge N)$ (`reports/tables/possible_worlds_q3_check.csv`).
- `src/export_app_db.py` builds `app/app.duckdb` (`1,847,296` bytes) containing only the 5 S3 customer-level tables (`customers`: 3,961 rows, `customer_features`: 3,961 rows, `segments`: 5 rows, `segment_membership`: 39,610 rows, `lapse_risk`: 3,961 rows).
- `tests/test_templates.py`: 9 new tests; `pytest`: 37 passed.

**Key numbers** (from `reports/tables/kmeans_vs_expected_sizes.csv` and `q4_expected_revenue_bootstrap.csv`)

| Segment | K-Means hard count | GMM hard count | GMM expected size $\sum p$ (± std) | Bootstrap hard count | Bootstrap expected size $\sum p$ (± std) | Bootstrap hard revenue (£) | Bootstrap expected revenue (£) | Share of S3 revenue |
|---|---|---|---|---|---|---|---|---|
| **Champions** | 364 | 258 | 278.63 (± 7.43) | 278 | 290.55 (± 5.63) | 3,338,480.84 | 3,419,094.68 | 48.81% |
| **Loyal** | 887 | 1,105 | 1,073.79 (± 14.71) | 1,116 | 1,110.32 (± 10.22) | 2,339,218.02 | 2,259,067.53 | 32.25% |
| **At-Risk** | 901 | 933 | 943.04 (± 16.99) | 928 | 941.95 (± 10.91) | 889,769.42 | 893,534.57 | 12.76% |
| **New** | 736 | 636 | 670.19 (± 14.07) | 634 | 643.37 (± 7.81) | 188,798.36 | 193,135.37 | 2.76% |
| **Hibernating** | 1,073 | 1,029 | 995.35 (± 12.79) | 1,005 | 974.81 (± 8.60) | 248,126.01 | 239,560.51 | 3.42% |

## Phase 7: NL engine, dev set, evaluation harness (done)

**What was done**
- Built `src/nl/lexicon.py` (hedge lexicon mapping IPCC/Kent phrases to thresholds, segment synonyms, country aliases and intent phrases), `src/nl/parser.py` (spaCy + `EntityRuler` pipeline attaching hedges to the nearest `SEGMENT` or `LAPSE` predicate and returning `ParsedQuery`), and `src/nl/engine.py` (executes `ParsedQuery` via `prob_queries.run_template` with optional threshold slider override).
- Created `eval/questions_dev.csv` (26 development questions: 21 in-scope across Q1–Q6 and all hedge levels + 5 out-of-scope/injection/ambiguous cases) and `eval/questions_test.csv` (headers only, `q_id,question,gold_sql,author`, per Rule 6) plus `docs/how_to_write_test_questions.md`.
- `src/evaluate.py` runs the NL evaluation harness (`reports/tables/nl_dev_results.csv`, `reports/tables/nl_summary.csv`, `reports/tables/nl_error_analysis.csv`) and consolidates 41 headline metrics across Phases 1–7 into `eval_results` (`reports/tables/eval_results.csv`).
- `tests/test_nl.py`: 5 new tests verifying the hedge lexicon, SQL injection refusal, out-of-scope refusal, 100% dev execution accuracy, and `questions_test.csv` header format; `pytest`: 42 passed.

**Key numbers** (from `reports/tables/nl_summary.csv`)

| Split | Total questions | In-scope | Out-of-scope | Overall execution accuracy | In-scope execution accuracy | Template match rate | Out-of-scope rejection rate | Hedge-threshold accuracy |
|---|---|---|---|---|---|---|---|---|
| `dev` | 26 | 21 | 5 | **100.00%** | **100.00%** | **100.00%** | **100.00%** | **100.00%** |

- **Note on `eval/questions_test.csv`:** currently header-only as required by Rule 6; `python -m src.evaluate` will automatically score the human test set once a human adds rows and freezes it.

## Phase 8: Streamlit app and deployment prep (done)

**What was done**
- Built `app/streamlit_app.py` with four tabs (`Ask (NL -> SQL)`, `Segments & Tree Rules`, `Model Quality`, `About & Limitations`), example question chips, probability threshold override slider (`0.05`–`0.99`), SQL expander, results dataframe and Altair charts for Q1–Q6.
- Connected to `app/app.duckdb` via `duckdb.connect("app/app.duckdb", read_only=True)` cached with `@st.cache_resource`.
- Pinned `en_core_web_sm @ https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl` in `requirements.txt` to match `spacy==3.8.18`.
- `tests/test_app.py`: 3 new tests verifying read-only enforcement, Altair chart construction across all 6 example questions, and the `requirements.txt` spaCy wheel pin; `pytest`: 45 passed.

## Phase 9: README, automated report tables, references, and presentation notebook (done)

**What was done**
- Built `src/report_tables.py` and wired `run_phase_9` into `src/pipeline.py`. It reads `cleaning_funnel.csv`, `snapshot_summary.csv`, `segment_profiles_spherical_k5.csv`, `tree_fidelity.csv`, `gate.csv`, `kmeans_vs_expected_sizes.csv`, `lapse_s2_eval.csv`, and `nl_summary.csv`, writes `reports/tables/readme_results.md`, and synchronises the auto-generated results block in `README.md`.
- Updated `README.md` with the ABAI2009L topic alignment table, `docs/architecture.png`, a Mermaid system and query-flow diagram, the auto-generated empirical tables, figure links, and setup/execution instructions.
- Created `docs/references.md` with verified citations for all 9 required references in `CLAUDE.md` Section 11 (UCI Online Retail II DOI `10.24432/C5CG6D` by Daqing Chen; Fayyad et al. 1996; Pedregosa et al. 2011 & scikit-learn GMM BIC doc; Dalvi & Suciu 2007, Suciu et al. 2011, Van den Broeck & Suciu 2017 & MayBMS manual; IPCC AR5 Uncertainty Guidance Note Mastrandrea et al. 2010 & Sherman Kent 1964; Spider Yu et al. 2018 & BIRD Li et al. 2023; Dasgupta et al. ICML 2020; Hennig 2007; Fader, Hardie & Lee 2005 BG/NBD).
- Created `notebooks/presentation_walkthrough.ipynb` calling `src/` modules and displaying key tables and a live NL query for the viva presentation.
- Wrote `docs/explainers/phase-9.md` and `tests/test_phase9.py` (5 new tests verifying `report_tables.py` vs `README.md`, `docs/references.md` citations, zero placeholders across all deliverables, `eval/questions_test.csv` header-only rule, and notebook validity); `pytest`: 50 passed.


## Phase 10: Morning fixes, FastAPI read-only API, React web app, and Streamlit removal (done)

**What was done**
- **Morning review fixes:**
  - Standardised and verified the exact revenue figures across all tables, reports, and tests:
    - Raw net revenue: £19,287,250.57 across 1,067,371 rows (`raw_totals.csv`).
    - Clean product sales revenue: £19,643,861.64 across 1,003,357 rows (`clean_sales_summary.csv`).
    - Customer-identified clean revenue: £17,068,582.74 across 776,596 rows (`clean_sales_summary.csv`).
    - S3 9-month customer revenue: £7,004,392.65 across 3,961 customers (`snapshot_summary.csv`).
    - Added automated consistency test `test_revenue_numbers_are_consistent_across_tables` in `tests/test_cleaning.py`.
  - Created `docs/DECISIONS.md` documenting confirmed Phase 1 decisions and formally marking Phase 3 (`K = 5`, `covariance_type = 'spherical'`) and Phase 4 (`DEFAULT_METHOD = 'gmm'`, bootstrap stability validation) as **PROVISIONAL**.
  - Added `brier_skill_score` across all lapse evaluation modules, CSV tables, and reports: S2 `logistic_calibrated` achieves `0.1672` (+16.72% skill over the S2 base lapse rate of 42.38%), compared to `0.1225` (+12.25%) for calibrated depth-4 tree and `0.0730` (+7.30%) for the two-bin recency baseline.
  - Added `test_all_text_files_are_valid_utf8` in `tests/test_setup.py` verifying zero U+FFFD replacement characters.
- **FastAPI backend (`api/main.py`, `api/schemas.py`):**
  - Built a clean, read-only REST boundary exposing `/api/health`, `/api/meta`, `POST /api/ask`, `/api/segments`, `/api/segments/map`, `/api/customers/{customer_id}`, `/api/lapse`, `/api/quality`, `/api/assets/architecture.png`, and SPA static file serving from `web/dist`.
  - Enforced storage-level read-only DuckDB connection (`duckdb.connect(..., read_only=True)`) and allow-listed template execution (zero string-interpolated SQL).
  - Built `tests/test_api.py` verifying all endpoints, hedge word parsing, injection refusal, and read-only write protection.
- **React + TypeScript + Tailwind web application (`web/`):**
  - Implemented the strict design specification: neutral chrome in light mode (default) and dark mode, Okabe–Ito color-blind safe segment palette (`Champions` `#009E73`, `Loyal` `#0072B2`, `New` `#CC79A7`, `At-Risk` `#E69F00`, `Hibernating` `#7A7F87`), 4-step sequential red ramp for 90-day lapse risk, self-hosted fonts (`Bricolage Grotesque`, `Figtree`, `JetBrains Mono`), tabular numbers on all metrics, and zero raw hex literals in component source code.
  - Five custom signature components: `ProbabilityBar`, `ParseStrip`, `ThresholdControl` (with 150ms debounce), `UncertaintyMap` (HTML5 `<canvas>` scatter plot rendering all 3,961 S3 customers with halo uncertainty at 60fps), and `CustomerDrawer` (slide-over detail view).
  - Six pages: `/` (Overview with headline tile & S2 calibration curve), `/ask` (Command bar, 6 example chips, interpretation sentence, ParseStrip, threshold sliders, summary metrics, sortable results table, companion distribution chart, collapsible SQL panel), `/segments` (Uncertainty map, 5 segment cards, expected size chart), `/lapse` (4 metric tiles, 10-bin reliability diagram with count histogram, comparator table), `/quality` (stepped cleaning funnel, GMM BIC grid across 4 covariance types, bootstrap ARI histogram, Hennig Jaccard bars with 0.75 reference line, NL dev summary), and `/about` (architecture diagram, timeline, topic mapping, limitations, citation).
- **Run scripts & browser verification:**
  - Added `run_app.bat` (production launch on `http://localhost:8000`) and `run_dev.bat` (dual development servers).
  - Verified background uvicorn server serving `/api/health` and `/` (`web/dist/index.html`).
  - Captured 13 high-resolution 1440×900 screenshots across light and dark modes in `docs/screenshots/`.
- **Streamlit decommissioning:**
  - Removed `streamlit==1.66.1` and `altair==6.3.0` from `requirements.txt`.
  - Removed `app/streamlit_app.py` and `tests/test_app.py`.
  - Migrated spaCy wheel pin test into `tests/test_setup.py`.
  - Updated `CLAUDE.md`, `README.md`, `docs/explainers/phase-8.md`, and created `docs/explainers/phase-10.md` and `docs/FRONTEND_REPORT.md`.
- **Test suite:** all 54 tests pass cleanly in `pytest`.


## Phase 11: Presentation polish (POLISH.md)

### P1: presentation blockers (done)
- **Light theme by default:** a first visit always opens in light mode; the theme is saved to `localStorage` only after the user toggles it. Light-mode segment colours darkened slightly (`#00876A`, `#0072B2`, `#B5608F`, `#B07800`, `#666B73`) so every hue reaches at least 3:1 contrast on white; uncertainty-map opacity floor raised from 0.25 to 0.35.
- **Jargon removed from headers:** Segments H1 is now "Customer segments and boundary uncertainty" with a small `K = 5 · provisional` pill; the Topic eyebrows on Segments and Lapse risk are gone (the topic mapping stays on About and in the footer); the Overview eyebrow is "Headline finding".
- **Reliability diagram:** moved below the headline at full width (400px tall), 13px tick labels, axis titles "Predicted P(lapse within 90 days)" and "Observed lapse rate", an in-plot "perfect calibration" label, dots sized by bin count with the count on hover. A caption computed from `/api/lapse` states: "The highest bin over-predicts: 2 customers predicted at 81%, observed 50%. That bin holds only 2 of 3,247 test customers, so the gap rests on very few cases."
- **Numbers out of prose:** the Overview subtitle is one sentence ("Checked on 3,247 customers the model never saw, held out a full year after training."), with the count read from `lapse_s2_eval.csv` through a new `headline.s2_customer_count` API field; an ECE pill joins the Brier, skill-score and ROC-AUC pills. The Segments boundary share (12.50%, 495 of 3,961) and mean normalised entropy (0.2526) are now two stat tiles.
- **Hard-coded number removed:** the S2 count `3,247` was typed into the API subtitle and the Overview ECE tile; both now read it from the evaluation table. New test `test_headline_s2_count_comes_from_the_evaluation_table`.
- **Screenshots:** recaptured over the Chrome DevTools protocol with real-time waits, which fixes the blank Recharts plots in the earlier Lapse and Segments captures.
- `pytest`: 56 passed. `npm run build`: no TypeScript errors.

### P2: chart and layout quality (done)
- **Uncertainty map:** recency axis on a square-root scale (reversed, recent on the right), ticks at 270, 120, 60, 30, 14, 7 and 1 days. Square root was chosen over log after measuring axis occupancy on the S3 points: no fifth of the axis holds more than 33% of customers under either, but log squeezes the long Hibernating tail into 6% of the width. Horizontal jitter of ±0.4 days, fixed per customer by a hash of the customer id, breaks up whole-day stripes; the caption says so. Dot radius reduced (3.2/2.8px from 3.6/3.2px).
- **Overview segment strip:** each card says "% of customers" and has a Hard vs Σp bar pair drawn on one scale shared by all five cards. A line under the strip, computed from `/api/segments`, reads "Expected sizes sum to 3,961, exactly the number of customers…"; the word "exactly" appears only if the sum matches the customer count to within 0.01.
- **Typography:** Tailwind `text-xs` raised from 12px to 13px (captions), label caps from 11px to 12px, uncertainty-map ticks from 11px to 12px, Quality-page chart ticks from 11px to 12px. Sidebar recent questions now wrap in full instead of being cut off with an ellipsis. Segment-card headers wrap their Jaccard/AvePP pill onto a new line instead of squeezing, and the median tiles read "Recency / Orders / Spend" under a "Median per customer" caption so the labels no longer break mid-phrase.
- Screenshots recaptured at 1440×900: 7 light (including the customer drawer) and 6 dark.
- `pytest`: 56 passed. `npm run build`: no TypeScript errors. `/api/health` returned `{"status":"ok"}`.

