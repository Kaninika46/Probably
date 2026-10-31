# Report Source Material: *Probably High-Value?*

This is raw material for writing the project report. It is **not** the report.

**How to read the sources**
- Every number has its source file next to it in brackets. Paths are relative to the repository root.
- `tables/` is short for `reports/tables/`.
- Derived numbers (differences, ratios and shares that no table held) were computed by `src/report_derived.py` and saved to `tables/report_derived_numbers.csv` before being quoted here. That script reads `reports/tables/` and `app/app.duckdb` (read-only) and nothing else.
- Compiled on 2026-10-31 from the files as they stand at commit `2d2bcb6`.
- Items marked **⚠ PROVISIONAL** are defaults that a human has not yet confirmed. Items marked **⚠ INCONSISTENCY** are places where two project files disagree; fix these before quoting either value.

---

## 1. Abstract material

1. **Dataset.** UCI Online Retail II (DOI 10.24432/C5CG6D, CC BY 4.0) [`docs/references.md`]. It has 1,067,371 raw transaction lines from a UK online retailer across two workbook sheets [`tables/raw_totals.csv`], covering 2009-12-01 07:45 to 2011-12-09 12:50 [`tables/raw_row_counts.csv`].
2. **Cleaning.** A logged six-rule SQL funnel produces 1,003,357 clean product-sale lines (£19,643,861.64). Of these, 776,596 lines carry a customer ID (£17,068,582.74), covering 5,852 customers [`tables/cleaning_funnel.csv`, `tables/clean_sales_summary.csv`].
3. **Design.** There are three leakage-tested snapshots: S1 (train, 3,256 customers), S2 (one-time test, 3,247) and S3 (score, 3,961) [`tables/snapshot_summary.csv`].
4. **Segmentation.** A spherical Gaussian mixture with K = 5 on log-scaled RFM features (⚠ PROVISIONAL [`docs/DECISIONS.md`]). The bootstrap ARI median is 0.8674 (IQR 0.0977) [`tables/bootstrap_stability.csv`]. All five segments are "stable" on Hennig's Jaccard scale, with the lowest mean being 0.8449 for At-Risk [`tables/segment_stability.csv`].
5. **Probabilistic database.** Segment membership is stored as a block-independent-disjoint (BID) table with 39,610 rows: 3,961 customers × 5 segments × 2 methods [`docs/PROGRESS.md`, Phase 4]. 90-day lapse probability is stored as a tuple-independent attribute.
6. **Headline result 1 (uncertainty is real).** Under GMM posteriors, 12.50% of S3 customers (495 of 3,961) have no segment with p ≥ 0.6. Under bootstrap co-assignment the figure is 3.84% (152) [`tables/gate.csv`].
7. **Headline result 2 (lapse model).** On the held-out S2 year, the calibrated logistic model scores Brier 0.2034, Brier skill score 0.1672, ROC-AUC 0.7390 and 10-bin ECE 0.0343. The two-bin recency rule reaches ROC-AUC 0.6371 [`tables/lapse_s2_eval.csv`].
8. **Explainability.** A depth-4 surrogate tree reproduces the GMM segments on 86.80% of a 30% held-out split, using 16 leaves [`tables/tree_fidelity.csv`].
9. **NL interface.** A rule-based spaCy parser maps plain-English questions, including hedge words such as "probably" (P ≥ 0.66) and "almost certainly" (P ≥ 0.95), onto six parameterised SQL templates. It scores 100.00% execution accuracy on 26 *development* questions [`tables/nl_summary.csv`]. **There is no held-out test-set result yet** (see §13).
10. **Main limitation.** Segment membership has no ground truth. The variance of segment sizes assumes customers are independent of each other. The NL accuracy is measured only on the questions the parser was tuned on.

---

## 2. Problem and aim

**Question answered.** Which customers belong to which value segment, how sure can we be of that, and which of them are likely to stop buying in the next 90 days? An analyst should be able to ask this in plain English, with the uncertainty kept visible rather than hidden.

**Why hard labels are not enough (evidence)**
- **Boundary customers.** Under the GMM, 495 of 3,961 S3 customers (12.50%) have max p < 0.6, so no single segment is a confident label for them. The mean normalised entropy is 0.2526 [`tables/gate.csv`].
- **Weak segments.** Hard labels hide differences between segments. AvePP (the average posterior probability of a segment's own members) ranges from 0.788 for At-Risk to 0.8934 for Champions [`tables/gate.csv`].
- **Size bias.** Hard counts and expected sizes differ:
  - Under the GMM, Hibernating has 1,029 hard members but an expected size of 995.35. New has 636 hard members but an expected size of 670.19 [`tables/q3_expected_sizes_gmm.csv`].
  - In 10,000 sampled possible worlds, P(Hibernating size ≥ its hard count) is 0.0055 under the GMM and 0.0001 under the bootstrap [`tables/possible_worlds_q3_check.csv`]. The hard label therefore overstates Hibernating almost surely.
- **Algorithm dependence.** K-Means and the GMM disagree on the hard counts. For Champions, K-Means gives 364 and the GMM gives 258 [`tables/kmeans_vs_expected_sizes.csv`].
- **Revenue concentration.** Champions are 6.51% of S3 customers [`tables/segment_profiles_spherical_k5.csv`] but hold 48.81% of expected S3 revenue (bootstrap) [`tables/q4_expected_revenue_bootstrap.csv`]. Misassigning a few of them is expensive.

**Aim (one sentence).** Build a database-backed knowledge-discovery pipeline that segments customers and predicts 90-day lapse. It stores both results as formally defined probabilistic tables, checks them against what customers actually did next, and lets analysts query them in plain English where hedge words map to published probability scales.

---

## 3. Objectives and research questions

### Objectives

| # | Objective | Where it is achieved |
|---|---|---|
| O1 | Clean a 1M-row transactional dataset with every rule logged and its revenue impact measured | `sql/02_clean_views.sql`, `src/clean.py`; §6.1 |
| O2 | Build leakage-free customer features at three snapshot dates | `sql/03_features.sql`, `tests/test_features.py`; §5.2, §6.3 |
| O3 | Segment S3 customers with K-Means and a GMM grid, and select a model by BIC, stability and interpretability | `src/segment.py`; §6.4–6.6 |
| O4 | Turn segmentation into membership probabilities (GMM posteriors and bootstrap co-assignment) and measure how informative they are | `src/membership.py`; §6.7–6.8 |
| O5 | Explain the segments with readable rules and measure how faithful those rules are | `src/rules.py`; §6.9 |
| O6 | Train a calibrated 90-day lapse model on S1 and evaluate it once on S2 against baselines | `src/lapse.py`; §6.10–6.11 |
| O7 | Store the results as BID and tuple-independent probabilistic tables and query them with six templates of stated semantics | `sql/01_schema.sql`, `sql/templates/`, `src/prob_queries.py`, `src/worlds.py`; §6.12 |
| O8 | Map natural-language questions, including hedge words, safely onto those templates and serve them through a read-only web app | `src/nl/`, `api/main.py`, `web/`; §6.13 |

### Research questions

| RQ | Question | Answered by |
|---|---|---|
| RQ1 | How many customers sit on segment boundaries, and does the answer depend on how membership probability is defined? | `tables/gate.csv`, `tables/report_derived_numbers.csv`; §10 F1 |
| RQ2 | Are the segments stable under resampling? | `tables/bootstrap_stability.csv`, `tables/segment_stability.csv`; §10 F2 |
| RQ3 | How far do hard-label segment sizes and revenues differ from their expected values under the probabilistic model? | `tables/kmeans_vs_expected_sizes.csv`, `tables/q4_expected_revenue_*.csv`, `tables/possible_worlds_q3_check.csv`; §10 F3 |
| RQ4 | Does a calibrated lapse model beat a simple recency rule on a later, unseen year, and on which kind of metric? | `tables/lapse_s2_eval.csv`; §10 F4 |
| RQ5 | Can a rule-based NL parser map hedged questions to the correct probabilistic query and refuse unsafe or out-of-scope ones? | `tables/nl_summary.csv` (dev only); test set still outstanding (§13) |

---

## 4. Dataset

| Item | Value | Source |
|---|---|---|
| Name | Online Retail II | `docs/references.md` |
| Creator | Daqing Chen | `docs/references.md` |
| Repository | UCI Machine Learning Repository, id 502 | `CLAUDE.md` §3 |
| DOI | 10.24432/C5CG6D | `docs/references.md` |
| Licence | CC BY 4.0 | `docs/references.md` |
| URL | https://archive.ics.uci.edu/dataset/502/online+retail+ii | `docs/references.md` |
| Download | zip of 45,622,418 bytes; extracted xlsx of 45,622,278 bytes | `docs/PROGRESS.md` Phase 0 |
| Sheet 1 | `Year 2009-2010`: 525,461 rows, 2009-12-01 07:45 to 2010-12-09 20:01 | `tables/raw_row_counts.csv` |
| Sheet 2 | `Year 2010-2011`: 541,910 rows, 2010-12-01 08:26 to 2011-12-09 12:50 | `tables/raw_row_counts.csv` |
| Total raw rows | 1,067,371 | `tables/raw_totals.csv` |
| Raw net revenue | £19,287,250.57 (includes negative cancellation lines) | `tables/raw_totals.csv` |
| Original columns | Invoice, StockCode, Description, Quantity, InvoiceDate, Price, Customer ID, Country → renamed to snake_case, plus `source_sheet` | `src/config.py` `COLUMN_RENAMES` |
| Clean lines / invoices / customers / products / countries | 1,003,357 / 39,516 / 5,852 / 4,896 / 43 | `tables/clean_sales_summary.csv` |
| UK share of clean-sales revenue | 85.53% | `tables/report_derived_numbers.csv` |
| Countries among S3 customers | 34, with the UK holding 90.71% of S3 customers | `tables/report_derived_numbers.csv` |

**Data-quality issues, with real counts** [`tables/cleaning_funnel.csv`]
- **Sheet overlap.** The two sheets overlap between 2010-12-01 and 2010-12-09 [`tables/raw_row_counts.csv`]. This produces 22,523 duplicate rows worth £377,488.45.
- **Other exact duplicates.** 11,812 rows, worth £54,228.42.
- **Cancellations.** 19,104 lines with invoices starting 'C', worth −£1,462,050.61. They are moved to the `returns` view, not deleted.
- **Non-positive quantity or price.** 6,019 lines, worth −£158,676.14.
- **Non-product stock codes.** 21 codes on 4,556 lines worth £832,398.81: postage, manual adjustments, bad debt, fees, discount, test products, samples and gift vouchers [`tables/non_product_codes.csv`].
- **Missing customer_id.** 226,761 lines worth £2,575,278.90, which is 13.35% of raw revenue. They are kept for revenue totals but excluded from customer tables.
- **Mixed types.** Text and numbers are mixed in invoice and stock_code (for example 'C489449' and 'POST'), so both are stored as text [`sql/01_schema.sql` comments].
- **Customers in two countries.** 12 customers have orders in two countries. Each is assigned the country of their latest order [`docs/PROGRESS.md` Phase 2].
- **Wholesale skew.** S3 monetary ranges from £5.90 to £221,437.00 and frequency from 1 to 173, against medians of £631.89 and 2 [`tables/s3_preprocessing.csv`].

---

## 5. Methodology

For each stage: what was done, why, and what was rejected.

### 5.1 Cleaning (`sql/02_clean_views.sql`, `src/clean.py`)
- **Done.** Six ordered rules run as a chain of SQL views. Each rule logs rows before and after and the revenue affected to `data_quality_log`. Raw rows are never edited.
- **Why.**
  - Every row and pound is accounted for, which gives the funnel shown in the report.
  - SQL views keep cleaning reproducible and inspectable inside the database, as KDD's selection and pre-processing stage requires.
- **Rejected: deleting cancellations.** They are kept in a `returns` view so the information survives.
- **Rejected: dropping rows without a customer_id.** They are kept with `has_customer = false`, so revenue totals stay complete.
- **Rejected: keeping gift vouchers and samples as products.** The user confirmed this exclusion. A voucher is a payment method, so counting both the voucher sale and its later redemption would count the same revenue twice. Samples are adjustments, not sales [`docs/DECISIONS.md` §1].

### 5.2 Snapshots and the leakage argument (`src/config.py`, `sql/03_features.sql`)
- **Done.** There are three snapshot dates S. Features come from the 9 months before S, and the outcome is any purchase in the 90 days from S [`src/config.py` `SNAPSHOTS`].

| Snapshot | S | Feature window | Outcome window | Role |
|---|---|---|---|---|
| S1 | 2010-09-10 | 2009-12-10 – 2010-09-09 | 2010-09-10 – 2010-12-09 | train |
| S2 | 2011-09-10 | 2010-12-10 – 2011-09-09 | 2011-09-10 – 2011-12-09 | test once |
| S3 | 2011-12-10 | 2011-03-10 – 2011-12-09 | none (future) | score and segment |

- **Leakage argument.** No feature uses a date ≥ S, and no outcome uses a date outside its window. Two tests enforce this: `test_no_feature_leakage_from_on_or_after_snapshot_date` and `test_no_outcome_leakage_outside_outcome_window` in `tests/test_features.py`.
- **Year-on-year design.** S1 and S2 sit at the same point in the calendar a year apart. The test is therefore a genuine forward-in-time evaluation, and both outcome windows contain the same seasonal peak. Monthly revenue rises each autumn: £1,429,700.78 in Nov 2010 and £1,452,115.98 in Nov 2011 [`tables/eda_monthly_revenue.csv`].
- **Rejected: a random train/test split of customers.** It would mix time periods and leak future behaviour into training.

### 5.3 Feature engineering
- **Features.** `recency_days`, `frequency` (distinct invoices), `monetary` (gross clean sales), `tenure_days` (from first-ever purchase before S) and `avg_basket`, as defined in `CLAUDE.md` §7.3.
- **Who is included.** A customer belongs to a snapshot only if they had at least one clean sale in its window.
- **Which features go where.** Segmentation uses R, F and M only. The lapse model uses all five [`src/lapse.py` `FEATURE_COLS`].

### 5.4 Capping, log and scaling (`src/segment.py` `preprocess_s3_rfm`)
- **Capping.** `frequency` and `monetary` are capped at the S3 99th percentile: 26 invoices (35 customers capped) and £15,942.81 (40 customers capped). Recency needs no cap, since its maximum is 275 days [`tables/s3_preprocessing.csv`].
- **Then** `log1p` and `StandardScaler`.
- **Why.** The variables are heavily right-skewed by wholesale buyers (monetary max £221,437.00 vs median £631.89 [`tables/s3_preprocessing.csv`]). Without the transform, a few accounts would dominate the Euclidean and Gaussian geometry.
- **Rejected: clustering raw values.** Wholesalers would dominate. **Rejected: clustering ranks or quintiles (classic RFM scoring).** Ranks throw away the magnitude of the differences.

### 5.5 K-Means vs GMM (`src/segment.py` `run_kmeans_grid`, `run_gmm_grid`)
- **K-Means.** K = 2…8, scored by silhouette, Davies–Bouldin and Calinski–Harabasz [`tables/kmeans_grid.csv`].
- **GMM.** K = 2…8 × {spherical, tied, diag, full}, `n_init=10`, scored by BIC and AIC [`tables/gmm_grid.csv`].
- **Why the GMM was chosen.** It gives a posterior probability per customer. A probabilistic database needs exactly that, and K-Means cannot supply it. K-Means is kept as a comparison.
- **Rejected: diag and full covariance.** Frequency is a discrete integer: 1,480 S3 customers have frequency = 1 and 781 have frequency = 2. Components collapse onto these zero-variance planes [`tables/gmm_diag_degeneracy.csv`]. This drives BIC artificially negative (for example diag K=5 has BIC −2,758.17 and full K=8 has BIC −9,638.22 [`tables/gmm_grid.csv`]).

### 5.6 Model selection ⚠ PROVISIONAL
- **Proposed model.** Spherical, K = 5 [`src/config.py` `CHOSEN_K`, `CHOSEN_GMM_COV`].
- **Recorded scores.** BIC 28,003.90, AIC 27,853.08, silhouette 0.3015, minimum cluster size 258 [`tables/gmm_grid.csv`; `tables/eval_results.csv`].
- **Stated rationale.** Among the non-degenerate types, it balances stability (ARI median 0.8674), interpretability (five nameable segments) and a Champions segment that separates out wholesale buyers [`docs/DECISIONS.md` §2].
- **Be honest in the report: BIC alone does not pick K = 5.**
  - Spherical BIC keeps falling to K = 8 (26,935.23), and tied K = 8 has the lowest non-degenerate BIC (26,809.39).
  - Silhouette is highest at K = 2 (0.4304 spherical; 0.4315 K-Means) [`tables/gmm_grid.csv`, `tables/kmeans_grid.csv`].
  - K = 5 is an interpretability and stability choice, not a BIC optimum.
- **Alternatives kept on file.** Spherical K = 4 (ARI median 0.9061) and tied K = 4 (ARI median 0.9146) were more stable but merge segments [`tables/segment_profiles_spherical_k4.csv`, `tables/segment_profiles_tied_k4.csv`].
- **⚠ INCONSISTENCY.** `docs/DECISIONS.md` §2 quotes BIC 23,604.24, AIC 23,453.42 and silhouette 0.3106 for spherical K = 5. These values appear in no table. `tables/gmm_grid.csv` and `tables/eval_results.csv` both give 28,003.90 / 27,853.08 / 0.3015. Quote the table values and correct `DECISIONS.md`.

### 5.7 Bootstrap membership (`src/membership.py` `compute_memberships_and_stability`)
- **Method `gmm`.** `predict_proba` from the reference GMM.
- **Method `bootstrap`.** B = 100 resamples of the S3 customers with replacement [`src/config.py` `BOOTSTRAP_B`]. On each resample:
  - refit the spherical K = 5 GMM;
  - predict labels for **all** customers;
  - align the labels to the reference with the Hungarian algorithm (`scipy.optimize.linear_sum_assignment`).

  p is the share of fits that assign each segment.
- **Why two methods.** They measure different uncertainty:
  - `gmm` measures *where a customer sits relative to fitted boundaries*;
  - `bootstrap` measures *whether the boundaries themselves move* when the data is resampled.
- **Rejected: reporting only hard labels.** That is the problem stated in §2.
- **Rejected: fuzzy c-means.** It was not considered in the code. It would give memberships but no probabilistic model behind them.

### 5.8 Surrogate tree (`src/rules.py`)
- **Done.** `DecisionTreeClassifier(max_depth=4)` on R, F and M in original units, predicting the most probable segment. 70/30 stratified split: 2,772 train / 1,189 test [`tables/tree_fidelity.csv`]. Rules go to `segments.tree_rule` and `tables/tree_rules.md`.
- **Why.** The GMM lives in log-standardised space, which an analyst cannot read. A shallow tree gives threshold rules in days, orders and pounds [`docs/references.md` §7, citing Dasgupta et al. 2020].
- **Rejected: describing segments by centroids alone.** Centroids are not decision rules. **Rejected: a deeper tree.** It would raise fidelity at the cost of readability.

### 5.9 Lapse model and baselines (`src/lapse.py`)
- **Primary model, fixed in advance.** `log1p` → `StandardScaler` → `LogisticRegression`, wrapped in `CalibratedClassifierCV(method='sigmoid', cv=5)`, trained on S1 only [`src/lapse.py` `make_primary_logistic_model`].
- **Baselines.**
  - The two-bin recency rule: S1 lapse rate 0.3174 if recency ≤ 90 days and 0.5471 if > 90 [`tables/lapse_baseline_s1_rates.csv`].
  - A sigmoid-calibrated depth-4 decision tree.
- **Selection and testing.** Models are compared by 5-fold out-of-fold CV on S1 [`tables/lapse_s1_cv.csv`]. S2 is used once [`tables/lapse_s2_eval.csv`].
- **Why logistic regression.** It is simple, monotone and explainable in a viva, and gives well-behaved probabilities after calibration. The goal is *trustworthy probabilities* to store in a probabilistic table, not maximum AUC.
- **Terminology.** The project calls this "lapse (no purchase in 90 days)", not "churn". In non-contractual retail nobody formally cancels [`docs/references.md` §9].
- **Rejected: BG/NBD (Fader, Hardie & Lee 2005).** It cannot easily use the monetary, tenure and basket features, and its output is not a direct 90-day probability checked against a held-out window [`docs/references.md` §9].
- **Rejected: gradient boosting and similar models.** Not tried. The spec fixed the primary model in advance, so no model was picked by peeking at test results.

### 5.10 BID and tuple-independent tables (`sql/01_schema.sql`, `src/membership.py` `write_probabilistic_tables`)
- **`segment_membership(customer_id, snapshot, method, segment, p)` is a BID table.**
  - The block key is (customer_id, snapshot, method).
  - The five tuples in a block are mutually exclusive alternatives with Σp = 1.
  - Blocks are assumed independent of each other. This is the same model as MayBMS `repair key` [`docs/references.md` §4].
  - Tested by `test_bid_block_probabilities_sum_to_one` and `test_bid_probabilities_in_unit_interval` [`tests/test_membership.py`].
- **`lapse_risk(customer_id, snapshot, p_lapse_90d, model_version)` is a tuple-independent table.** Each tuple holds one independent probabilistic event.
- **Rejected: storing only an argmax label column.** It loses the uncertainty. **Rejected: one wide table with five p columns.** That cannot express BID semantics in plain relational form.

### 5.11 Templates Q1–Q6 (`sql/templates/`, `src/prob_queries.py`)

| Id | Template | Logic | Semantics |
|---|---|---|---|
| Q1 | `q1_confident.sql` | p ≥ $tau for $seg (or p ≤ $max_p for "unlikely"; most-probable segment if no hedge) | exact |
| Q2 | `q2_boundary.sql` | max p < $boundary (default 0.6), with normalised entropy | exact |
| Q3 | `q3_expected_size.sql` | Σp per segment; variance Σp(1−p) | mean exact by linearity of expectation; variance assumes independence across customers |
| Q4 | `q4_expected_revenue.sql` | Σ(p × monetary) | exact |
| Q5 | `q5_top_k.sql` | ORDER BY p DESC LIMIT $k | exact |
| Q6 | `q6_segment_and_lapse.sql` | p ≥ $tau1 AND p_lapse ≥ $tau2, as two separate filters | the two probabilities are **never multiplied**, because both depend on recency and frequency |

- **Parameters.** All are DuckDB named parameters, validated against allow-lists (methods, segments, countries read from the DB, probability bounds) [`src/prob_queries.py` `validate_*`]. Row limit: 500 [`src/prob_queries.py` `DEFAULT_ROW_LIMIT`].
- **Monte Carlo check (stretch).** `src/worlds.py` samples 10,000 possible worlds and checks Q3 numerically [`tables/possible_worlds_q3_check.csv`].

### 5.12 NL engine and hedge lexicon (`src/nl/`)
- **Pipeline.**
  - spaCy `en_core_web_sm` + `EntityRuler` for segment names and synonyms, countries (loaded from the DB) and metrics;
  - extraction of numbers and comparison words;
  - attachment of each hedge word to the nearest SEGMENT or LAPSE predicate [`src/nl/parser.py` `_attach_hedges_to_predicates`].
- **Output.** A `ParsedQuery`: intent, template_id, typed params, thresholds and an interpretation sentence.
- **Hedge lexicon** [`src/config.py` `HEDGE_THRESHOLDS`; anchors in `docs/references.md` §5]:

| Words | Threshold | Anchor |
|---|---|---|
| possibly, might | P ≥ 0.33 | IPCC "about as likely as not" starts at 33% |
| probably, likely | P ≥ 0.66 | IPCC "likely" 66–100%; Kent "probable" 63–87% |
| very likely, highly likely | P ≥ 0.90 | IPCC "very likely" 90–100% |
| almost certainly, definitely | P ≥ 0.95 | Kent "almost certain" 93% ± 6 |
| unlikely | P ≤ 0.33 | IPCC "unlikely" 0–33% |
| (none) | most probable segment | hard label |

- **Security.**
  - User text never becomes SQL. It only fills typed, allow-listed parameters.
  - SQL comment markers and tautology/UNION patterns are refused [`tables/nl_dev_results.csv` D24, D25].
  - The app connection is `read_only=True` [`src/db.py` `connect_app`, `api/main.py` `get_readonly_con`].
- **Rejected: an LLM text-to-SQL model.** It cannot be explained line by line in a viva, it can produce arbitrary SQL (a security risk), and the course allows rule-based or pre-trained spaCy/NLTK.
- **Rejected: free-form SQL generation.** The closed template set guarantees that every answer has stated probabilistic semantics.

---

## 6. All results tables

### 6.1 Cleaning funnel [`tables/cleaning_funnel.csv`]

| Step | Rule | Rows before | Rows after | Rows removed | Revenue affected (£) | % of revenue before step | % of raw revenue |
|---|---|---|---|---|---|---|---|
| 1 | Overlap duplicates between sheets | 1,067,371 | 1,044,848 | 22,523 | 377,488.45 | 1.96 | 1.96 |
| 2 | Remaining exact duplicates | 1,044,848 | 1,033,036 | 11,812 | 54,228.42 | 0.29 | 0.28 |
| 3 | Cancellations moved to returns | 1,033,036 | 1,013,932 | 19,104 | −1,462,050.61 | −7.75 | −7.58 |
| 4 | Quantity or price not positive | 1,013,932 | 1,007,913 | 6,019 | −158,676.14 | −0.78 | −0.82 |
| 5 | Non-product stock codes | 1,007,913 | 1,003,357 | 4,556 | 832,398.81 | 4.07 | 4.32 |
| 6 | Missing customer_id (excluded from customer analysis) | 1,003,357 | 776,596 | 226,761 | 2,575,278.90 | 13.11 | 13.35 |

Revenue affected is negative at steps 3–4 because the removed lines carry negative values [`docs/PROGRESS.md` Phase 1].

### 6.2 Non-product codes

**By reason** [`tables/non_product_reasons.csv`]

| Reason | Codes | Rows | Revenue (£) | % of revenue before step | % of raw revenue |
|---|---|---|---|---|---|
| postage | 3 | 3,533 | 448,962.53 | 2.1926 | 2.3278 |
| manual adjustment | 5 | 891 | 359,932.33 | 1.7578 | 1.8662 |
| fee | 2 | 37 | 20,987.04 | 0.1025 | 0.1088 |
| gift voucher | 7 | 77 | 1,756.17 | 0.0086 | 0.0091 |
| discount | 1 | 5 | 397.89 | 0.0019 | 0.0021 |
| test | 2 | 10 | 226.00 | 0.0011 | 0.0012 |
| samples | 1 | 3 | 136.85 | 0.0007 | 0.0007 |

**By code** [`tables/non_product_codes.csv`]

| Code | Reason | Rows | Revenue (£) |
|---|---|---|---|
| POST | postage | 1,851 | 125,682.42 |
| DOT | postage | 1,415 | 309,854.11 |
| M | manual adjustment | 846 | 339,226.24 |
| C2 | postage | 267 | 13,426.00 |
| ADJUST | manual adjustment | 36 | 8,897.93 |
| BANK CHARGES | fee | 34 | 519.24 |
| gift_0001_20 | gift voucher | 26 | 471.06 |
| gift_0001_30 | gift voucher | 24 | 610.09 |
| gift_0001_10 | gift voucher | 14 | 126.21 |
| TEST001 | test | 9 | 225.00 |
| gift_0001_50 | gift voucher | 6 | 253.59 |
| D | discount | 5 | 397.89 |
| gift_0001_40 | gift voucher | 5 | 166.09 |
| m | manual adjustment | 5 | 15.05 |
| ADJUST2 | manual adjustment | 3 | 731.05 |
| AMAZONFEE | fee | 3 | 20,467.80 |
| S | samples | 3 | 136.85 |
| B | manual adjustment | 1 | 11,062.06 |
| TEST002 | test | 1 | 1.00 |
| gift_0001_70 | gift voucher | 1 | 59.57 |
| gift_0001_80 | gift voucher | 1 | 69.56 |

### 6.3 Snapshot sizes and base rates [`tables/snapshot_summary.csv`]

| Snapshot | Customers | Mean / median recency (d) | Mean / median frequency | Mean / median monetary (£) | Mean / median tenure (d) | Mean / median basket (£) | Purchased next 90d | Lapsed | Base lapse rate |
|---|---|---|---|---|---|---|---|---|---|
| S1 | 3,256 | 87.89 / 72.0 | 3.53 / 2.0 | 1,598.59 / 585.77 | 181.07 / 192.0 | 366.80 / 287.52 | 1,908 | 1,348 | 41.40% |
| S2 | 3,247 | 88.36 / 69.0 | 3.40 / 2.0 | 1,555.65 / 552.00 | 405.23 / 460.0 | 401.43 / 283.12 | 1,871 | 1,376 | 42.38% |
| S3 | 3,961 | 71.38 / 43.0 | 3.70 / 2.0 | 1,768.34 / 631.89 | 436.50 / 478.0 | 408.99 / 296.64 | — | — | — |

Note: S1 tenure is short (mean 181.07 d) because the data only starts on 2009-12-01. Tenure is truncated by the start of the dataset.

**S3 preprocessing** [`tables/s3_preprocessing.csv`]

| Feature | Raw min | Raw median | Raw max | 99th-pct cap | Customers capped | log1p mean | log1p std |
|---|---|---|---|---|---|---|---|
| recency_days | 1.0 | 43.0 | 275.0 | 275.0 | 0 | 3.6773 | 1.2198 |
| frequency | 1.0 | 2.0 | 173.0 | 26.0 | 35 | 1.2724 | 0.6155 |
| monetary | 5.9 | 631.89 | 221,437.0 | 15,942.81 | 40 | 6.4941 | 1.1849 |

### 6.4 Cluster validity: K-Means [`tables/kmeans_grid.csv`]

| K | Inertia | Silhouette ↑ | Davies–Bouldin ↓ | Calinski–Harabasz ↑ |
|---|---|---|---|---|
| 2 | 5,884.86 | 0.4315 | 0.8948 | 4,035.21 |
| 3 | 4,458.50 | 0.3337 | 1.0647 | 3,295.56 |
| 4 | 3,577.08 | 0.3325 | 1.0200 | 3,062.79 |
| 5 | 3,002.75 | 0.3089 | 0.9987 | 2,924.86 |
| 6 | 2,609.96 | 0.2982 | 1.0277 | 2,810.41 |
| 7 | 2,347.55 | 0.2964 | 0.9916 | 2,676.78 |
| 8 | 2,138.62 | 0.2952 | 1.0062 | 2,573.11 |

### 6.5 GMM BIC grid [`tables/gmm_grid.csv`]

| Cov | K | BIC | AIC | Silhouette | Min cluster | Boundary share % |
|---|---|---|---|---|---|---|
| spherical | 2 | 29,909.89 | 29,853.33 | 0.4304 | 1,538 | 3.89 |
| spherical | 3 | 28,985.08 | 28,897.10 | 0.3340 | 550 | 7.12 |
| spherical | 4 | 28,512.82 | 28,393.42 | 0.3306 | 581 | 11.01 |
| **spherical** | **5** | **28,003.90** | **27,853.08** | **0.3015** | **258** | **12.50** |
| spherical | 6 | 27,759.99 | 27,577.74 | 0.2980 | 378 | 17.42 |
| spherical | 7 | 27,523.86 | 27,310.20 | 0.2694 | 286 | 16.84 |
| spherical | 8 | 26,935.23 | 26,690.15 | 0.2191 | 222 | 15.27 |
| tied | 2 | 27,761.52 | 27,679.82 | 0.3964 | 726 | 4.90 |
| tied | 3 | 27,307.34 | 27,200.51 | 0.3150 | 310 | 0.56 |
| tied | 4 | 27,191.27 | 27,059.30 | 0.3041 | 274 | 13.99 |
| tied | 5 | 26,948.75 | 26,791.64 | 0.2448 | 191 | 9.92 |
| tied | 6 | 27,092.94 | 26,910.70 | 0.2440 | 267 | 30.60 |
| tied | 7 | 26,815.18 | 26,607.80 | 0.2031 | 169 | 25.12 |
| tied | 8 | 26,809.39 | 26,576.88 | 0.2307 | 181 | 26.38 |
| diag | 2 | 29,032.82 | 28,951.12 | 0.4146 | 1,707 | 2.98 |
| diag | 3 | 11,127.63 | 11,001.94 | 0.2740 | 836 | 2.15 |
| diag | 4 | 2,342.16 | 2,172.48 | 0.1844 | 651 | 1.64 |
| diag | 5 | −2,758.17 | −2,971.84 | 0.1477 | 377 | 0.96 |
| diag | 6 | −6,347.66 | −6,605.31 | 0.1275 | 283 | 0.40 |
| diag | 7 | −3,578.41 | −3,880.05 | 0.1370 | 197 | 2.65 |
| diag | 8 | −6,772.05 | −7,117.68 | 0.1267 | 228 | 3.53 |
| full | 2 | 10,958.26 | 10,838.85 | 0.3023 | 1,480 | 0.00 |
| full | 3 | 10,226.74 | 10,044.49 | 0.2583 | 818 | 2.30 |
| full | 4 | 1,823.76 | 1,578.67 | 0.1697 | 782 | 3.71 |
| full | 5 | −3,022.43 | −3,330.36 | 0.1406 | 393 | 0.68 |
| full | 6 | −6,427.10 | −6,797.87 | 0.1190 | 348 | 0.88 |
| full | 7 | −3,437.78 | −3,871.39 | 0.1345 | 284 | 4.52 |
| full | 8 | −9,638.22 | −10,134.67 | 0.1017 | 149 | 0.71 |

**Degeneracy evidence (diag K = 4)** [`tables/gmm_diag_degeneracy.csv`]

| Cluster | Customers | Freq min | Freq median | Freq max | Mean recency | Mean monetary (£) |
|---|---|---|---|---|---|---|
| 0 | 651 | 2 | 8.0 | 173 | 16.86 | 7,068.73 |
| 1 | 1,049 | 3 | 4.0 | 7 | 44.99 | 1,225.07 |
| 2 | 781 | 2 | 2.0 | 2 | 71.06 | 705.38 |
| 3 | 1,480 | 1 | 1.0 | 1 | 114.24 | 382.87 |

### 6.6 Bootstrap ARI and per-segment Jaccard

**ARI vs reference, B = 100** [`tables/bootstrap_stability.csv`; the 100 individual values are in `tables/bootstrap_ari_samples.csv`]

| Cov | K | B | ARI median | IQR | Q25 | Q75 | Mean | Min | Max |
|---|---|---|---|---|---|---|---|---|---|
| spherical | 5 | 100 | 0.8674 | 0.0977 | 0.8151 | 0.9128 | 0.8414 | 0.4532 | 0.9613 |

**Per-segment Jaccard** [`tables/segment_stability.csv`]

| Segment | Reference customers | Jaccard mean | Jaccard median | IQR | Band |
|---|---|---|---|---|---|
| Champions | 258 | 0.8669 | 0.9073 | 0.1291 | stable (≥ 0.75) |
| Loyal | 1,105 | 0.8775 | 0.9035 | 0.0572 | stable |
| At-Risk | 933 | 0.8449 | 0.8777 | 0.1297 | stable |
| New | 636 | 0.8758 | 0.8972 | 0.0839 | stable |
| Hibernating | 1,029 | 0.9009 | 0.9334 | 0.0807 | stable |

### 6.7 Segment profiles in original units (spherical K = 5) ⚠ PROVISIONAL names [`tables/segment_profiles_spherical_k5.csv`]

| Segment | Cluster | Customers | Share % | Mean / median recency (d) | Mean / median frequency | Mean / median monetary (£) | Mean tenure (d) | Mean basket (£) | AvePP |
|---|---|---|---|---|---|---|---|---|---|
| Champions | 4 | 258 | 6.51 | 8.60 / 5.0 | 18.66 / 14.0 | 12,635.95 / 5,455.26 | 620.17 | 620.79 | 0.8934 |
| Loyal | 0 | 1,105 | 27.90 | 21.72 / 17.0 | 5.04 / 5.0 | 2,154.78 / 1,579.14 | 478.98 | 530.84 | 0.8490 |
| At-Risk | 1 | 933 | 23.55 | 86.66 / 72.0 | 2.36 / 2.0 | 978.14 / 786.57 | 447.68 | 517.56 | 0.7880 |
| New | 2 | 636 | 16.06 | 23.19 / 22.0 | 1.42 / 1.0 | 301.97 / 284.55 | 320.97 | 234.11 | 0.8086 |
| Hibernating | 3 | 1,029 | 25.98 | 156.38 / 159.0 | 1.14 / 1.0 | 251.34 / 229.23 | 406.09 | 234.67 | 0.8723 |

**Alternatives preserved:**
- spherical K = 4 [`tables/segment_profiles_spherical_k4.csv`]: 698 / 1,198 / 581 / 1,484 customers; ARI median 0.9061.
- tied K = 4 [`tables/segment_profiles_tied_k4.csv`]: 274 / 1,259 / 336 / 2,092; ARI median 0.9146.

### 6.8 Membership informativeness (gate report) [`tables/gate.csv`, `tables/gate_ave_pp.csv`]

| Method | Customers | Boundary (max p < 0.6) | Boundary % | Mean max p | Median max p | Mean norm. entropy | Median norm. entropy |
|---|---|---|---|---|---|---|---|
| gmm | 3,961 | 495 | 12.50 | 0.8371 | 0.8996 | 0.2526 | 0.2253 |
| bootstrap | 3,961 | 152 | 3.84 | 0.9329 | 0.9900 | 0.1041 | 0.0348 |

| Method | Segment | Hard (most probable) | Expected size Σp | AvePP |
|---|---|---|---|---|
| gmm | Champions | 258 | 278.63 | 0.8934 |
| gmm | Loyal | 1,105 | 1,073.79 | 0.8490 |
| gmm | At-Risk | 933 | 943.04 | 0.7880 |
| gmm | New | 636 | 670.19 | 0.8086 |
| gmm | Hibernating | 1,029 | 995.35 | 0.8723 |
| bootstrap | Champions | 278 | 290.55 | 0.9490 |
| bootstrap | Loyal | 1,116 | 1,110.32 | 0.9339 |
| bootstrap | At-Risk | 928 | 941.95 | 0.9191 |
| bootstrap | New | 634 | 643.37 | 0.9409 |
| bootstrap | Hibernating | 1,005 | 974.81 | 0.9352 |

Derived [`tables/report_derived_numbers.csv`]: the boundary-share gap is 8.66 percentage points (GMM is 3.26× the bootstrap figure), which is 343 more boundary customers under the GMM.

### 6.9 Tree fidelity [`tables/tree_fidelity.csv`, `tables/tree_fidelity_by_segment.csv`]

| Max depth | Actual depth | Leaves | Train n | Test n | Train fidelity | Test fidelity |
|---|---|---|---|---|---|---|
| 4 | 4 | 16 | 2,772 | 1,189 | 89.72% | 86.80% |

| Segment | Test customers | Matched | Test fidelity |
|---|---|---|---|
| Champions | 77 | 67 | 87.01% |
| Loyal | 332 | 305 | 91.87% |
| At-Risk | 280 | 223 | 79.64% |
| New | 191 | 156 | 81.68% |
| Hibernating | 309 | 281 | 90.94% |

**Readable rules** (full list in [`tables/tree_rules.md`]). Two illustrative rules:
- Champions = `recency ≤ 36.5 AND frequency > 10.5 AND monetary > £512.32` (n = 143, purity 96.5%).
- New = `recency ≤ 46.5 AND frequency ≤ 2.5 AND monetary ≤ £512.32` (n = 369, purity 98.6%).

The weakest leaf is a Loyal rule with purity 43.1%.

### 6.10 Lapse model comparison

**S1, 5-fold out-of-fold CV** [`tables/lapse_s1_cv.csv`]

| Model | n | Base rate | Mean pred. | Brier ↓ | BSS ↑ | ROC-AUC ↑ | Log loss ↓ | ECE ↓ |
|---|---|---|---|---|---|---|---|---|
| logistic_calibrated (primary) | 3,256 | 0.4140 | 0.4140 | 0.2087 | 0.1397 | 0.7177 | 0.6020 | 0.0081 |
| tree_depth4_calibrated | 3,256 | 0.4140 | 0.4134 | 0.2087 | 0.1398 | 0.7186 | 0.6032 | 0.0267 |
| two_bin_recency_90d | 3,256 | 0.4140 | 0.4140 | 0.2299 | 0.0523 | 0.6060 | 0.6521 | 0.0001 |

**S2, held-out test (used once)** [`tables/lapse_s2_eval.csv`]

| Model | n | Base rate | Mean pred. | Brier ↓ | BSS ↑ | ROC-AUC ↑ | Log loss ↓ | ECE ↓ |
|---|---|---|---|---|---|---|---|---|
| logistic_calibrated (primary) | 3,247 | 0.4238 | 0.4008 | **0.2034** | **0.1672** | **0.7390** | **0.5870** | 0.0343 |
| tree_depth4_calibrated | 3,247 | 0.4238 | 0.3801 | 0.2143 | 0.1225 | 0.7106 | 0.6145 | 0.0774 |
| two_bin_recency_90d | 3,247 | 0.4238 | 0.4125 | 0.2264 | 0.0730 | 0.6371 | 0.6448 | **0.0206** |

**S3 lapse risk by (bootstrap) segment** [`tables/lapse_s3_by_segment.csv`]

| Segment | Customers | Mean P(lapse) | Median P(lapse) | With P ≥ 0.66 |
|---|---|---|---|---|
| Hibernating | 1,005 | 0.5746 | 0.5770 | 54 |
| New | 634 | 0.4972 | 0.5004 | 14 |
| At-Risk | 928 | 0.3801 | 0.3803 | 0 |
| Loyal | 1,116 | 0.2084 | 0.2027 | 0 |
| Champions | 278 | 0.0618 | 0.0645 | 0 |

S3 P(lapse) ranges from 0.0028 to 0.7852 [`tables/report_derived_numbers.csv`].

### 6.11 Calibration bins, S2 (logistic, primary) [`tables/lapse_reliability_bins_s2.csv`]

| Bin | Range | Customers | Mean predicted | Observed lapse rate | Gap |
|---|---|---|---|---|---|
| 1 | 0.0–0.1 | 187 | 0.0606 | 0.0160 | 0.0445 |
| 2 | 0.1–0.2 | 366 | 0.1507 | 0.1257 | 0.0251 |
| 3 | 0.2–0.3 | 463 | 0.2514 | 0.2527 | 0.0013 |
| 4 | 0.3–0.4 | 518 | 0.3520 | 0.3764 | 0.0245 |
| 5 | 0.4–0.5 | 476 | 0.4477 | 0.5021 | 0.0544 |
| 6 | 0.5–0.6 | 789 | 0.5567 | 0.5970 | 0.0403 |
| 7 | 0.6–0.7 | 429 | 0.6293 | 0.6807 | 0.0514 |
| 8 | 0.7–0.8 | 17 | 0.7284 | 0.7059 | 0.0225 |
| 9 | 0.8–0.9 | 2 | 0.8100 | 0.5000 | 0.3100 |
| 10 | 0.9–1.0 | 0 | — | — | — |

- **Two-bin rule bins.**
  - Bin 4: 1,903 customers, predicted 0.3174, observed 0.3095.
  - Bin 6: 1,344 customers, predicted 0.5471, observed 0.5856.

  The same file also holds the calibrated tree's bins.
- **Pattern to describe.** From bin 4 to bin 7, observed > predicted, so the model under-predicts lapse in its middle range. Overall, the mean prediction (0.4008) is 0.023 below the S2 base rate (0.4238) [`tables/report_derived_numbers.csv`]. Only 19 S2 customers are predicted ≥ 0.7.

### 6.12 Probabilistic query outputs

**Hard vs expected sizes** [`tables/kmeans_vs_expected_sizes.csv`]

| Segment | K-Means hard | GMM hard | GMM Σp (± sd) | Bootstrap hard | Bootstrap Σp (± sd) |
|---|---|---|---|---|---|
| Champions | 364 | 258 | 278.63 (± 7.43) | 278 | 290.55 (± 5.63) |
| Loyal | 887 | 1,105 | 1,073.79 (± 14.71) | 1,116 | 1,110.32 (± 10.22) |
| At-Risk | 901 | 933 | 943.04 (± 16.99) | 928 | 941.95 (± 10.91) |
| New | 736 | 636 | 670.19 (± 14.07) | 634 | 643.37 (± 7.81) |
| Hibernating | 1,073 | 1,029 | 995.35 (± 12.79) | 1,005 | 974.81 (± 8.60) |

**Expected revenue (Q4)** [`tables/q4_expected_revenue_bootstrap.csv`, `tables/q4_expected_revenue_gmm.csv`]

| Segment | Bootstrap hard (£) | Bootstrap expected (£) | Bootstrap share % | GMM hard (£) | GMM expected (£) | GMM share % |
|---|---|---|---|---|---|---|
| Champions | 3,338,480.84 | 3,419,094.68 | 48.81 | 3,260,075.04 | 3,319,358.44 | 47.39 |
| Loyal | 2,339,218.02 | 2,259,067.53 | 32.25 | 2,381,032.53 | 2,279,463.10 | 32.54 |
| At-Risk | 889,769.42 | 893,534.57 | 12.76 | 912,602.84 | 921,647.36 | 13.16 |
| Hibernating | 248,126.01 | 239,560.51 | 3.42 | 258,630.84 | 259,112.21 | 3.70 |
| New | 188,798.36 | 193,135.37 | 2.76 | 192,051.40 | 224,811.54 | 3.21 |

### 6.13 NL dev metrics [`tables/nl_summary.csv`, `tables/nl_error_analysis.csv`]

| Split | Questions | In-scope | Out-of-scope | Exec. accuracy | In-scope exec. acc. | Template match | OOS rejection | Hedge-threshold acc. |
|---|---|---|---|---|---|---|---|---|
| dev | 26 | 21 | 5 | 100.00% | 100.00% | 100.00% | 100.00% | 100.00% |

- **Error analysis.** All six failure types (wrong template, wrong hedge threshold, wrong entity or filter, false refusal, missed refusal, result-set mismatch) have 0 questions.
- **Template mix of the dev set** [`tables/report_derived_numbers.csv`]: Q1 10, Q2 2, Q3 2, Q4 2, Q5 2, Q6 3, out-of-scope 5.
- **Row limit.** 3 dev questions return exactly 500 rows, so they hit the row limit (D04, D07, D20 in `tables/nl_dev_results.csv`).
- **⚠ Test split: no result.** `eval/questions_test.csv` contains only its header line.

### 6.14 Monte Carlo possible-worlds check (M = 10,000) [`tables/possible_worlds_q3_check.csv`]

| Method | Segment | Hard | SQL E[size] | MC mean | abs diff | SQL var | MC var | MC 95% interval | P(size ≥ hard) |
|---|---|---|---|---|---|---|---|---|---|
| bootstrap | Champions | 278 | 290.55 | 290.59 | 0.0448 | 31.75 | 31.91 | 280–302 | 0.9912 |
| bootstrap | Loyal | 1,116 | 1,110.32 | 1,110.36 | 0.0354 | 104.49 | 104.04 | 1,090–1,130 | 0.3089 |
| bootstrap | At-Risk | 928 | 941.95 | 941.92 | 0.0306 | 119.03 | 119.21 | 921–963 | 0.9081 |
| bootstrap | New | 634 | 643.37 | 643.46 | 0.0934 | 60.92 | 60.06 | 628–659 | 0.9044 |
| bootstrap | Hibernating | 1,005 | 974.81 | 974.67 | 0.1430 | 74.03 | 75.08 | 958–991 | 0.0001 |
| gmm | Champions | 258 | 278.63 | 278.65 | 0.0184 | 55.20 | 54.87 | 264–293 | 0.9984 |
| gmm | Loyal | 1,105 | 1,073.79 | 1,073.81 | 0.0179 | 216.27 | 218.82 | 1,045–1,103 | 0.0183 |
| gmm | At-Risk | 933 | 943.04 | 942.93 | 0.1087 | 288.77 | 288.50 | 909–976 | 0.7300 |
| gmm | New | 636 | 670.19 | 670.37 | 0.1805 | 197.89 | 201.19 | 642–698 | 0.9930 |
| gmm | Hibernating | 1,029 | 995.35 | 995.24 | 0.1081 | 163.64 | 167.78 | 970–1,021 | 0.0055 |

This check confirms that the SQL formulas match the sampler. It does **not** test the independence assumption, because the sampler draws each customer independently too.

### 6.15 EDA tables
- **Top 10 countries by clean revenue** [`tables/eda_top_countries.csv`]: United Kingdom £16,801,019.39; EIRE £623,414.16; Netherlands £549,773.41; Germany £383,289.00; France £311,090.29; Australia £167,800.01; Spain £97,766.75; Switzerland £94,024.59; Sweden £86,319.14; Denmark £67,422.69.
- **Monthly revenue, Dec 2009 – Dec 2011** [`tables/eda_monthly_revenue.csv`]: the peak months are Nov 2010 (£1,429,700.78) and Nov 2011 (£1,452,115.98). Dec 2011 (£614,490.92) is a partial month that ends on the 9th.

---

## 7. Figures

| Path | What it shows | Report section |
|---|---|---|
| `docs/architecture.png` | System architecture: offline pipeline → DuckDB data layer → FastAPI/React/spaCy app | Methodology overview / system design |
| `reports/figures/cleaning_funnel.png` | Rows remaining after each of the 6 cleaning rules | Data preparation |
| `reports/figures/eda_monthly_revenue.png` | Monthly clean revenue Dec 2009–Dec 2011, showing the autumn peaks | Dataset / EDA |
| `reports/figures/eda_top_countries.png` | Top 10 countries by clean revenue (UK dominates) | Dataset / EDA |
| `reports/figures/eda_quantity_price.png` | Distributions of quantity and unit price (skew, outliers) | Dataset / EDA |
| `reports/figures/kmeans_selection.png` | K-Means silhouette, Davies–Bouldin and Calinski–Harabasz for K = 2…8 | Results: segmentation, model selection |
| `reports/figures/gmm_bic_aic.png` | GMM BIC/AIC across K and the 4 covariance types (shows the diag/full collapse) | Results: model selection |
| `reports/figures/segment_profiles_s3.png` | Original-unit R/F/M profiles of the 5 proposed segments | Results: segment profiles |
| `reports/figures/gate_max_p_hist.png` | Histogram of max p per customer, GMM vs bootstrap, with the 0.6 boundary | Results: membership informativeness (key figure) |
| `reports/figures/lapse_reliability_s2.png` | S2 reliability diagram, logistic vs baselines | Results: lapse calibration (key figure) |
| `docs/screenshots/overview_light.png`, `overview_dark.png` | App Overview: headline tile, S2 calibration curve, segment strip | Implementation / demo |
| `docs/screenshots/ask_light.png`, `ask_dark.png` | Ask page: NL question, interpretation sentence, ParseStrip, threshold sliders, results | NL interface (key screenshot) |
| `docs/screenshots/segments_light.png`, `segments_dark.png`, `segments_full_light.png` | Segments page: uncertainty map of the S3 customers, segment cards, hard vs expected chart (`segments_full_light` is a full-page capture) | Results / implementation |
| `docs/screenshots/lapse_light.png`, `lapse_dark.png` | Lapse page: metric tiles, reliability diagram, baseline comparison, watchlist | Results / implementation |
| `docs/screenshots/quality_light.png`, `quality_dark.png` | Model-quality page: funnel, BIC grid, ARI histogram, Jaccard bars, NL dev summary | Evaluation |
| `docs/screenshots/about_light.png`, `about_dark.png` | About page: architecture, timeline, topic mapping, limitations | Appendix |
| `docs/screenshots/customer_drawer_light.png` | Single-customer drawer: BID distribution, lapse gauge, tree path | Implementation (shows the probabilistic tuple for one customer) |

There are 14 screenshot files. `docs/PROGRESS.md` mentions 13; the extra file is `segments_full_light.png`. **No figure exists for:** the bootstrap ARI histogram as a static PNG (it exists only in the web app; the data is in `tables/bootstrap_ari_samples.csv`), the Jaccard bars, or the possible-worlds distributions.

---

## 8. KDD mapping (Fayyad, Piatetsky-Shapiro & Smyth 1996)

| KDD stage | File → function |
|---|---|
| Selection (acquire data) | `data/download.py`; `src/ingest.py` → `read_sheet_names`, `read_workbook`, `fix_column_types`, `load_raw_frame`, `load_into_duckdb`, `print_row_counts` |
| Pre-processing (cleaning) | `sql/01_schema.sql`, `sql/02_clean_views.sql`; `src/clean.py` → `fill_data_quality_log`, `count_rows_and_revenue`, `save_funnel_table`, `save_non_product_codes_table`, `save_funnel_chart`; `src/eda.py` → `plot_monthly_revenue`, `plot_top_countries`, `plot_quantity_and_price` |
| Transformation | `sql/03_features.sql`; `src/features.py` → `create_snapshots_table`, `save_snapshot_summary`; `src/segment.py` → `preprocess_s3_rfm` (cap, log1p, scale); `src/lapse.py` → `load_snapshot_dataset` |
| Data mining (clustering) | `src/segment.py` → `run_kmeans_grid`, `run_gmm_grid`, `check_diag_frequency_collapse`, `build_candidate_profile`; `src/membership.py` → `compute_memberships_and_stability` |
| Data mining (classification) | `src/lapse.py` → `make_primary_logistic_model`, `make_calibrated_tree_model`, `TwoBinRecencyBaseline`; `src/rules.py` → `run` (surrogate tree) |
| Interpretation / evaluation | `src/membership.py` → `save_gate_report_and_histogram`, `normalised_entropy`, `stability_band`; `src/rules.py` → `extract_segment_leaf_rules`; `src/lapse.py` → `evaluate_s1_cross_validation`, `expected_calibration_error`, `compute_metrics_row`, `plot_s2_reliability_diagram`; `src/evaluate.py` → `build_master_eval_results`; `src/report_tables.py` → `build_all_tables_md` |
| Knowledge consolidation (store and use the knowledge) | `src/membership.py` → `write_probabilistic_tables`; `src/prob_queries.py` → `run_template`; `src/worlds.py` → `sample_possible_worlds`; `src/export_app_db.py` → `build_app_db`; `api/main.py`; `src/nl/engine.py` → `answer_question` |
| Orchestration | `src/pipeline.py` → `run_phase_1` … `run_phase_9`, `main` |

---

## 9. Topic mapping

> **Note.** Course wording is quoted from the project spec (`CLAUDE.md` §1). The spec shortens Topic 3 with an ellipsis, so copy the full wording from the official course handout before quoting it in the report.

**Topic 3 (core): Data Mining and KDD.** Course wording: *"Apply classification or clustering algorithms… perform knowledge discovery on structured data from a database."*
- **"clustering algorithms":** K-Means and a GMM grid over K = 2…8 × four covariance types (`src/segment.py`); bootstrap co-assignment (`src/membership.py`).
- **"classification":** calibrated logistic lapse classifier plus two baselines (`src/lapse.py`); surrogate decision tree (`src/rules.py`).
- **"knowledge discovery":** segment profiles, readable rules [`tables/tree_rules.md`], and the calibration-vs-discrimination finding.
- **"structured data from a database":** everything is read from DuckDB (`data/retail.duckdb`). Cleaning and features are SQL views and tables (`sql/02_clean_views.sql`, `sql/03_features.sql`).

**Topic 1: Probabilistic and Uncertain Databases.** Course wording: *"Implement a small probabilistic database with uncertain values; query using confidence levels or probabilistic inference."*
- **"small probabilistic database with uncertain values":**
  - the `segment_membership` BID table (39,610 rows [`docs/PROGRESS.md` Phase 6]);
  - the tuple-independent `lapse_risk` table;
  - both exported to `app/app.duckdb`.
- **"query using confidence levels":** Q1 (p ≥ τ), Q2 (max p < 0.6), Q5 (top-k by p) and Q6 (two separate confidence filters).
- **"probabilistic inference":**
  - Q3 expected size by linearity of expectation, with Poisson-binomial variance;
  - Q4 expected revenue;
  - the possible-worlds Monte Carlo check (`src/worlds.py`).

**Topic 2: NLP for Database Interaction.** Course wording: *"Convert natural language queries to SQL; rule-based or pre-trained model like spaCy or NLTK."*
- **"convert natural language queries to SQL":** `src/nl/parser.py` → `parse_question` produces a `ParsedQuery` (template + typed parameters), and `src/nl/engine.py` → `answer_question` executes it. This is template-filling, not open SQL synthesis; say so.
- **"rule-based or pre-trained model like spaCy":** spaCy `en_core_web_sm` (pinned 3.8.0 wheel [`docs/PROGRESS.md` Phase 8]), `EntityRuler` and the hedge lexicon (`src/nl/lexicon.py`).

---

## 10. Key findings

- **F1. Membership uncertainty is real, but its size depends on what "probability" means.**
  - Under GMM posteriors, 12.50% (495) of S3 customers are boundary cases (max p < 0.6). Under bootstrap co-assignment the figure is 3.84% (152) [`tables/gate.csv`]. That is a gap of 8.66 percentage points, a ratio of 3.26× [`tables/report_derived_numbers.csv`].
  - Interpretation: the GMM measures *where a customer sits* between components, while the bootstrap measures *whether the clustering itself moves*. The segmentation is stable, but a meaningful minority of customers sit between segments.
- **F2. The five segments are stable under resampling.** Bootstrap ARI median is 0.8674 (IQR 0.0977) [`tables/bootstrap_stability.csv`]. Every segment's mean Jaccard is ≥ 0.75, the lowest being At-Risk at 0.8449 [`tables/segment_stability.csv`]. The worst single resample had ARI 0.4532, so stability is not uniform.
- **F3. Hard labels misstate segment size and revenue.**
  - Under the GMM, New is undercounted (636 hard vs 670.19 expected) and Hibernating overcounted (1,029 vs 995.35) [`tables/q3_expected_sizes_gmm.csv`].
  - P(Hibernating ≥ hard count) is 0.0055 under the GMM [`tables/possible_worlds_q3_check.csv`].
  - K-Means puts 364 customers in Champions where the GMM puts 258 [`tables/kmeans_vs_expected_sizes.csv`].
- **F4. Calibration and discrimination are different things.**
  - On S2, the two-bin recency rule has the *lowest* ECE (0.0206 vs 0.0343 for logistic). Its ROC-AUC is much lower (0.6371 vs 0.7390) and its Brier score is worse (0.2264 vs 0.2034) [`tables/lapse_s2_eval.csv`]. The AUC gap is 0.1019 [`tables/report_derived_numbers.csv`].
  - A two-valued predictor can be almost perfectly calibrated while barely ranking customers. ECE alone is therefore not a quality measure, and Brier and its skill score (0.1672 vs 0.0730) combine both properties.
- **F5. The lapse model generalises a year forward.**
  - Logistic S1 CV gives ROC-AUC 0.7177 and Brier 0.2087 [`tables/lapse_s1_cv.csv`]. On S2 it gives 0.7390 and 0.2034 [`tables/lapse_s2_eval.csv`], so there is no degradation.
  - The calibrated tree tied it in CV (AUC 0.7186) but generalised worse (S2 AUC 0.7106, ECE 0.0774). This supports fixing the simpler model in advance.
- **F6. Revenue is extremely concentrated.**
  - Champions are 6.51% of S3 customers [`tables/segment_profiles_spherical_k5.csv`] but 48.81% of expected revenue [`tables/q4_expected_revenue_bootstrap.csv`].
  - Their mean P(lapse) is 0.0618, and no Champion, Loyal or At-Risk customer reaches P(lapse) ≥ 0.66 [`tables/lapse_s3_by_segment.csv`].
  - Among the top-spending quartile (991 customers spending £1,475.81 or more), the highest P(lapse) is 0.4787 [`docs/PROGRESS.md` Close-out fixes].
- **F7. Simple rules explain most of the clustering.** A depth-4 tree with 16 leaves matches the GMM on 86.80% of held-out customers [`tables/tree_fidelity.csv`]. It is weakest on At-Risk (79.64%) and New (81.68%), the two lowest-AvePP segments (0.788, 0.8086) [`tables/tree_fidelity_by_segment.csv`, `tables/gate.csv`].
- **F8. GMM covariance choice is constrained by discrete data.** Diag and full GMMs reach negative BIC by collapsing onto integer frequency planes: 1,480 customers at frequency 1 and 781 at frequency 2 [`tables/gmm_diag_degeneracy.csv`]. BIC must not be read blindly on count features.

---

## 11. Limitations

1. **Cross-customer independence.**
   - The BID model assumes customer blocks are independent. Q3's variance Σp(1−p) and the Monte Carlo sampler both rely on that.
   - For the bootstrap method the assumption is clearly false: all customers' probabilities come from the *same* 100 refits, so they are correlated.
   - The Monte Carlo check matches the SQL formula (§6.14) only because it makes the same assumption. It cannot validate the assumption.
   - Note too that the comment in `sql/templates/q3_expected_size.sql` says independence "holds in the BID model". It holds *by definition of the model*, not in the data.
2. **No ground truth for segment membership.** The segments are model constructs. Stability (ARI, Jaccard) shows reproducibility, not correctness, and the membership probabilities cannot be calibrated the way lapse probabilities can.
3. **Two probability definitions give different answers.** GMM and bootstrap boundary shares differ 3.26× [`tables/report_derived_numbers.csv`]. Which one an analyst sees depends on a default: the web app uses `gmm` [`src/config.py` `DEFAULT_METHOD`], while the NL engine, CLI and dev evaluation default to `bootstrap` [`src/nl/parser.py`, `src/nl/engine.py`, `src/prob_queries.py`].
4. **K = 5 is not a BIC optimum.** It was chosen for interpretability and stability (§5.6), and is still provisional.
5. **The "New" segment name is misleading.** Its mean tenure is 320.97 days [`tables/segment_profiles_spherical_k5.csv`], so these are mostly low-frequency, low-spend recent buyers, not newly acquired customers. Tenure is not a clustering feature. The NL lexicon still maps "new customers", "newcomers" and "first-time" to it [`src/nl/lexicon.py`].
6. **Narrow NL question space.**
   - Only six templates exist. Each question may mention one segment: "Champions or Loyal" is refused as ambiguous (D26).
   - There are no joins to products or invoices and no time ranges, and the vocabulary is hand-built.
   - The 100.00% accuracy comes from 26 dev questions written and tuned by the developer. It says nothing about unseen phrasing.
   - Three dev answers are truncated at the 500-row limit.
7. **No held-out NL test result.** `eval/questions_test.csv` is header-only.
8. **Age and nature of the dataset.**
   - The data ends in 2011 [`tables/report_derived_numbers.csv`]: one UK retailer, many of them wholesalers.
   - 90.71% of S3 customers are in the UK.
   - Behaviour, channels and seasonality may not transfer to current retail.
9. **The surrogate tree is an approximation.** It agrees with the GMM on only 86.80% of held-out customers [`tables/tree_fidelity.csv`] and has a leaf with purity 43.1% [`tables/tree_rules.md`]. Its rules describe the clusters; they do not define them.
10. **Lapse calibration at the extremes.**
    - The model under-predicts in its middle range (bins 4–7 observed > predicted) and on average by 0.023.
    - Only 19 S2 customers are predicted ≥ 0.7 [`tables/lapse_reliability_bins_s2.csv`, `tables/report_derived_numbers.csv`], so the high-risk end is barely tested.
    - S3 predictions never exceed 0.7852.
11. **The S3 scores cannot be verified.** Their outcome window lies beyond the end of the data.
12. **Lapse model features.**
    - Only RFM, tenure and basket are used: no product, seasonality or country features.
    - Tenure is left-truncated by the data start, especially in S1 (mean 181.07 d [`tables/snapshot_summary.csv`]).
    - A 9-month feature window is used for an annual business.
13. **Q6 keeps two filters separate.** Correct, since the two probabilities are dependent. But the system cannot give a *joint* probability of "Champion AND lapsing", because no joint model exists.
14. **Customers without an ID** (13.35% of raw revenue) are invisible to every customer-level result.
15. **No statistical tests** (for example confidence intervals on AUC differences) and no business-impact evaluation.

---

## 12. Decisions and provisional items (from `docs/DECISIONS.md`)

| Decision | Status | Evidence |
|---|---|---|
| Exclude 21 non-product codes, including `S` samples and 7 gift-voucher codes | **CONFIRMED** by the user | Voucher double-counting argument; vouchers are 0.0086% of revenue reaching rule 5 [`tables/non_product_reasons.csv`] |
| Keep rows without a customer_id for revenue totals; exclude them from customer tables | **CONFIRMED** [`docs/PROGRESS.md` Phase 0] | Keeps revenue totals complete |
| Python 3.12 (spec originally said 3.11) | **CONFIRMED** [`docs/PROGRESS.md` Phase 0] | Machine constraint |
| GMM `spherical`, `K = 5` | **⚠ PROVISIONAL** | Diag/full degenerate [`tables/gmm_diag_degeneracy.csv`]; ARI median 0.8674; all Jaccard ≥ 0.8449. BIC does *not* single it out (§5.6) |
| Segment names Champions / Loyal / At-Risk / New / Hibernating | **⚠ PROVISIONAL** | Rank-based naming in `src/segment.py` → `assign_proposed_names_k5`; "New" questionable (§11.5) |
| Default membership method `gmm` in UI/API; `bootstrap` as stability check | **⚠ PROVISIONAL** | GMM 12.50% vs bootstrap 3.84% boundary share [`tables/gate.csv`] |
| Overview headline = calibrated 90-day lapse risk, paired with segment confidence via Q6 | **⚠ PROVISIONAL** | S2 Brier 0.2034, BSS 0.1672, AUC 0.7390, ECE 0.0343 |
| Replace Streamlit with FastAPI + React | **CONFIRMED** | Design and performance reasons [`docs/DECISIONS.md` §4] |

**Spec tension worth acknowledging.** `CLAUDE.md` §7.5 says: "if the boundary share is meaningful, the headline is segment confidence; if tiny, lapse risk". A 12.50% (GMM) share is arguably meaningful, yet the provisional headline is lapse risk. A 3.84% (bootstrap) share is arguably tiny. The human has not resolved this.

---

## 13. Still outstanding

Blunt list:

1. **Human-written NL test set: not done.**
   - `eval/questions_test.csv` has only its header line, so RQ5 has no unbiased answer.
   - A human must write it following `docs/how_to_write_test_questions.md`, freeze it, then run `python -m src.evaluate`.
   - Until then, the report must not present the dev-set 100.00% as the accuracy of the system.
2. **Phase 3 checkpoint not closed.** K = 5, spherical covariance and all five segment names are still provisional. The human must confirm them, and should reconsider the name "New".
3. **Phase 4 gate decision not closed.** The default method (`gmm` vs `bootstrap`) and the headline choice are still provisional.
4. **⚠ INCONSISTENCY: `docs/DECISIONS.md` §2 BIC/AIC/silhouette.** It quotes 23,604.24 / 23,453.42 / 0.3106. The tables say 28,003.90 / 27,853.08 / 0.3015. It also implies BIC supports K = 5, which the grid does not show. Fix `DECISIONS.md`.
5. **⚠ INCONSISTENCY: lapse `model_version`.** `docs/PROGRESS.md` Phase 5 and `docs/explainers/phase-5.md` say `4cfb5e3`. The committed `app/app.duckdb` holds `4bb9bc2` [`tables/report_derived_numbers.csv`]. Neither hash appears in the current `git log`, which suggests history was rewritten after scoring. Re-run Phase 5 and the export, or update the docs.
6. **Default method mismatch.** NL engine, CLI and dev evaluation use `bootstrap`; the web app uses `gmm` (§11.3). Choose one, or state the difference in the report.
7. **No static figures** for bootstrap ARI, Jaccard or the possible-worlds distributions. The data exists in `tables/`, but only the web app draws them.
8. **No logistic-regression coefficients exported.** An examiner may ask which feature drives lapse, and no file answers this yet.
9. **Full course wording for Topic 3** must be copied from the handout (§9).
10. **`docs/PROGRESS.md` Phase 8** still describes the removed Streamlit app (it is historical, but could confuse a reader). Phase 10 records the replacement.
11. **Not run this session:** the full pipeline (`python -m src.pipeline --all`). `pytest` was run: 60 passed, matching `docs/PROGRESS.md`.

---

## 14. References (current `docs/references.md`)

"Verification status" below is what `docs/references.md` records in its own audit block. **I did not re-verify any reference online in this session.** Spot-check each DOI before submission.

| # | Reference | Recorded status | Notes |
|---|---|---|---|
| 1 | Chen, D. (2019). *Online Retail II* [Dataset]. UCI ML Repository. DOI 10.24432/C5CG6D. CC BY 4.0 | Verified (DOI) | `CLAUDE.md` asks for the exact citation text from the UCI page; compare the year and wording |
| 2 | Chen, D., Sain, S. L., & Guo, K. (2012). Data mining for the online retail industry… *J. Database Marketing & Customer Strategy Mgmt*, 19(3), 197–208. DOI 10.1057/dbm.2012.17 | Verified (DOI) | Extra (not in the spec list); useful related work |
| 3 | Fayyad, Piatetsky-Shapiro & Smyth (1996). From data mining to knowledge discovery in databases. *AI Magazine* 17(3), 37–54 | Verified | |
| 4 | Pedregosa et al. (2011). Scikit-learn: Machine learning in Python. *JMLR* 12, 2825–2830 | Verified | |
| 5 | scikit-learn docs: Gaussian mixture models and the BIC model-selection example | Verified (URL) | Web page; cite with an access date |
| 6 | Dalvi & Suciu (2007). Efficient query evaluation on probabilistic databases. *VLDB J.* 16(4), 523–544 | Verified; DOI 10.1007/s00778-007-0064-2 in the audit block | The DOI is missing from the entry itself; add it |
| 7 | Suciu, Olteanu, Ré & Koch (2011). *Probabilistic Databases*. Morgan & Claypool | Verified; DOI 10.2200/S00362ED1V01Y201105DTM017 in the audit block | The DOI is missing from the entry itself |
| 8 | Van den Broeck & Suciu (2017). Query processing on probabilistic data: A survey. *Found. Trends Databases* 7(3–4), 197–341. DOI 10.1561/1900000052 | Verified | |
| 9 | Koch (2009). MayBMS: A system for managing large uncertain and probabilistic databases. Ch. 6 in Aggarwal (Ed.), *Managing and Mining Uncertain Data*, Springer | Verified; audit block gives pp. 149–180 | Page numbers appear only in the audit block; confirm them before citing |
| 10 | Huang, Antova, Koch & Olteanu (2009). MayBMS: a probabilistic database management system. *SIGMOD 2009*, 1071–1074. DOI 10.1145/1559845.1559981 | Verified | Replaced an earlier non-existent entry (recorded in the audit block) |
| 11 | MayBMS manual (`repair key`, `conf()`) | Mentioned inline in entry 10; no URL | Add a URL or drop it |
| 12 | Mastrandrea et al. (2010). IPCC AR5 Guidance Note on consistent treatment of uncertainties | Verified | |
| 13 | Kent, S. (1964). Words of estimative probability. *Studies in Intelligence* 8(4) | Verified | |
| 14 | Yu et al. (2018). Spider. *EMNLP 2018* | Verified | |
| 15 | Li et al. (2023). BIRD. *NeurIPS 2023* | Verified | |
| 16 | Dasgupta, Frost, Moshkovitz & Rashtchian (2020). Explainable k-means and k-medians clustering. *ICML 2020* (PMLR) | Verified | |
| 17 | Hennig (2007). Cluster-wise assessment of cluster stability. *CSDA* 52(1), 258–271. DOI 10.1016/j.csda.2006.11.025 | Verified | |
| 18 | Fader, Hardie & Lee (2005). "Counting your customers" the easy way. *Marketing Science* 24(2), 275–284. DOI 10.1287/mksc.1040.0098 | Verified | Cited as the alternative not used |

**Not in `references.md`, but used and worth citing:**
- Platt scaling (sigmoid calibration);
- the Brier score;
- ECE / reliability diagrams (for example Guo et al. 2017 or Niculescu-Mizil & Caruana 2005);
- the Hungarian algorithm (Kuhn 1955);
- the Adjusted Rand Index (Hubert & Arabie 1985);
- spaCy.

Verify any of these before adding them.

---

## 15. Viva question bank

1. **Why combine three topics instead of one?** Topic 3 produces the knowledge (segments and lapse), Topic 1 stores its uncertainty formally, and Topic 2 makes it queryable. Remove one and the USP disappears: hedged English questions over checked probabilities.
2. **What is a BID table, and why is `segment_membership` one?** The block key is (customer_id, snapshot, method). Tuples in a block are mutually exclusive with Σp = 1, and blocks are independent. A customer is in exactly one segment, and the five tuples give the distribution. The test `test_bid_block_probabilities_sum_to_one` enforces Σp = 1. The table has 39,610 rows [`docs/PROGRESS.md`].
3. **Why is `lapse_risk` tuple-independent rather than BID?** Each customer has one uncertain binary event, lapse or not, so a single tuple carries p. There are no mutually exclusive alternatives to group.
4. **Why does Q6 never multiply the two probabilities?** Both depend on recency and frequency, so they are not independent. Multiplying them would assume independence. Hibernating has mean P(lapse) 0.5746 vs 0.0618 for Champions [`tables/lapse_s3_by_segment.csv`], so the two are clearly related.
5. **Is Q3's expected size exact?** The mean, Σp, is exact by linearity of expectation without any independence assumption. The variance Σp(1−p) assumes independent customers. Monte Carlo agrees with the SQL to within 0.1805 customers [`tables/possible_worlds_q3_check.csv`], but the sampler shares the assumption.
6. **Why does the GMM say 12.50% boundary but the bootstrap 3.84%?** They measure different things: position between fitted components versus instability of the fit itself. A customer can sit midway between two components yet be assigned the same way in every refit [`tables/gate.csv`].
7. **Which method should an analyst trust?** Use the GMM for "how typical is this customer of the segment" and the bootstrap for "would a different sample label them differently". The default is provisionally `gmm` in the app.
8. **Why K = 5 when BIC keeps decreasing?** BIC on spherical models falls all the way to K = 8 (26,935.23) [`tables/gmm_grid.csv`]. K = 5 was chosen for stability (ARI 0.8674) and nameable segments, and it is provisional. Honest answer: BIC alone did not choose it.
9. **Why reject diag and full covariance?** Discrete frequency makes components collapse onto zero-variance planes (1,480 customers at frequency 1). The likelihood becomes unbounded and BIC goes negative, for example −9,638.22 for full K = 8 [`tables/gmm_diag_degeneracy.csv`, `tables/gmm_grid.csv`].
10. **Why cap, then log, then scale?** Monetary runs up to £221,437.00 against a median of £631.89. Capping at the 99th percentile (affecting 40 and 35 customers) plus log1p stops wholesalers dominating, and scaling puts R, F and M on equal footing [`tables/s3_preprocessing.csv`].
11. **How did you validate stability?** B = 100 bootstrap refits, Hungarian label alignment, ARI vs the reference (median 0.8674), and Hennig per-segment Jaccard (all ≥ 0.8449, "stable") [`tables/bootstrap_stability.csv`, `tables/segment_stability.csv`].
12. **Why is label alignment needed?** GMM component numbering is arbitrary on each refit. Without matching (`linear_sum_assignment` on the confusion matrix), "cluster 2" in two refits could mean different segments.
13. **How do you prevent leakage?** Features use only dates < S, and outcomes only the 90-day window from S. Two pytest tests check both. Training uses S1, and S2 is a full year later and used once.
14. **Why not a random train/test split?** It would mix time periods. The question is whether a model trained in 2010 predicts 2011.
15. **Your recency rule has better ECE than your model. Isn't it better?** No. ECE 0.0206 vs 0.0343, but AUC 0.6371 vs 0.7390 and Brier 0.2264 vs 0.2034 [`tables/lapse_s2_eval.csv`]. A two-value predictor is easy to calibrate but cannot rank customers. Brier rewards both.
16. **What does a Brier skill score of 0.1672 mean?** The model's Brier score is 16.72% lower than always predicting the S2 base rate of 0.4238 [`tables/lapse_s2_eval.csv`].
17. **Where is the model poorly calibrated?** In the 0.8–0.9 bin: 2 customers, predicted 0.81, observed 0.50. It also under-predicts in the middle bins (for example 0.4477 predicted vs 0.5021 observed) [`tables/lapse_reliability_bins_s2.csv`].
18. **Why "lapse" not "churn"?** Retail customers never formally cancel. "No purchase in 90 days" is observable and testable. BG/NBD is the classic alternative, not used because it does not give a held-out 90-day probability from these features.
19. **Why logistic regression over the tree?** It was fixed in advance. The tree tied it in S1 CV (AUC 0.7186 vs 0.7177) but generalised worse on S2 (0.7106 vs 0.7390; ECE 0.0774 vs 0.0343) [`tables/lapse_s1_cv.csv`, `tables/lapse_s2_eval.csv`].
20. **Why a surrogate tree, and how good is it?** It turns log-scaled ellipsoids into rules in days, orders and pounds. It agrees with the GMM on 86.80% of held-out customers with 16 leaves, and is weakest on At-Risk (79.64%) [`tables/tree_fidelity_by_segment.csv`]. It is an approximation.
21. **How does "probably" become 0.66?** IPCC AR5's "likely" band is 66–100%, and Kent's "probable" is 63–87%. The lexicon lives in `src/config.py` `HEDGE_THRESHOLDS`. The hedge attaches to the nearest segment or lapse mention, so "probable Hibernating customers will likely lapse" gives two thresholds (dev question D19).
22. **What stops SQL injection?** User text never becomes SQL. Only allow-listed, typed parameters are bound to fixed templates. Injection patterns are refused (D24, D25), and the DuckDB connection is `read_only=True`, so a write raises an error (tested).
23. **Your NL accuracy is 100%. Is that credible?** Only on 26 dev questions that the parser was tuned on [`tables/nl_summary.csv`]. The human test set has not been written, so there is no unbiased estimate yet. Say this plainly.
24. **What happens to an unsupported question?** It is refused politely with example questions: weather (D22), stock codes (D23), multiple segments (D26) [`tables/nl_dev_results.csv`].
25. **What is the biggest weakness?**
    - No ground truth for segments.
    - Independence is assumed across customers, which the bootstrap violates.
    - "New" is a misleading name (mean tenure 320.97 days).
    - The NL scope is narrow, and the data is 2011, UK, wholesale-heavy (90.71% UK customers in S3).

---

## What a report would normally contain that this project cannot supply (yet)

- **Unbiased NL accuracy** on a held-out human-written test set (`eval/questions_test.csv` is empty).
- **Ground-truth validation of segment membership.** None can exist for unsupervised segments.
- **Validation of the S3 lapse scores.** The outcome window lies beyond the end of the data.
- **User study or usability evaluation** with real analysts of the NL interface or web app.
- **Business-impact evidence** (campaign uplift, A/B tests, cost/benefit of acting on lapse risk).
- **Confidence intervals or significance tests** for metric differences (for example the AUC gap of 0.1019).
- **Feature importance or coefficients** for the lapse model (not exported).
- **Comparison with an LLM-based text-to-SQL baseline**, or with BG/NBD on the same windows.
- **External validation** on a second dataset or a more recent period.
- **Runtime or performance benchmarks** for the pipeline, queries or web app (none were measured into a file).
- **Final, human-confirmed K, segment names and gate decision.**
- **Team contribution statement.** No record in the repo of who did what.
