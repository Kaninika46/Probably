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

**Confirmed at Phase 3 human checkpoint: `covariance_type = 'spherical'`, `K = 5`**

| Segment | Cluster ID | Customers | Share (%) | Mean / median recency (d) | Mean / median frequency | Mean / median monetary (£) | Mean tenure (d) | Mean basket (£) | AvePP | Mean Jaccard ($B=100$) |
|---|---|---|---|---|---|---|---|---|---|---|
| **Champions** | 4 | 258 | 6.51% | 8.60 / 5.0 | 18.66 / 14.0 | 12,635.95 / 5,455.26 | 620.17 | 620.79 | 0.8934 | 0.8669 |
| **Loyal** | 0 | 1,105 | 27.90% | 21.72 / 17.0 | 5.04 / 5.0 | 2,154.78 / 1,579.14 | 478.98 | 530.84 | 0.8490 | 0.8775 |
| **At-Risk** | 1 | 933 | 23.55% | 86.66 / 72.0 | 2.36 / 2.0 | 978.14 / 786.57 | 447.68 | 517.56 | 0.7880 | 0.8449 |
| **New** | 2 | 636 | 16.06% | 23.19 / 22.0 | 1.42 / 1.0 | 301.97 / 284.55 | 320.97 | 234.11 | 0.8086 | 0.8758 |
| **Hibernating** | 3 | 1,029 | 25.98% | 156.38 / 159.0 | 1.14 / 1.0 | 251.34 / 229.23 | 406.09 | 234.67 | 0.8723 | 0.9009 |

- The user confirmed `K = 5`, `covariance_type = 'spherical'`, and segment names `Champions`, `Loyal`, `At-Risk`, `New`, `Hibernating`.

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
- **Confirmed at Phase 4 Gate Checkpoint:** user confirmed keeping both `gmm` (12.50% boundary share) and `bootstrap` (3.84% boundary share) and pairing segment confidence with 90-day lapse risk (`Q6`).

## Phase 5: Lapse model, S2 evaluation, S3 scoring (done)

**What was done**
- `src/lapse.py` trains the primary calibrated logistic regression (`log1p` $\to$ `StandardScaler` $\to$ `LogisticRegression` wrapped in `CalibratedClassifierCV(method='sigmoid', cv=5)`) on S1 only (`3,256` customers, base lapse rate `41.40%`), alongside the two-bin recency rule (`recency_days > 90`: `54.71%` vs `<= 90`: `31.74%`, `reports/tables/lapse_baseline_s1_rates.csv`) and a calibrated depth-4 decision tree.
- Evaluates 5-fold out-of-fold CV on S1 (`reports/tables/lapse_s1_cv.csv`) and tests once on held-out S2 (`3,247` customers, base lapse rate `42.38%`, `reports/tables/lapse_s2_eval.csv`, `reports/tables/lapse_reliability_bins_s2.csv`, `reports/figures/lapse_reliability_s2.png`).
- Scores all `3,961` S3 customers into the tuple-independent `lapse_risk` table (`model_version = '4cfb5e3'`) and exports `reports/tables/lapse_s3_by_segment.csv`.
- `tests/test_lapse.py`: 3 new tests; `pytest`: 28 passed.

**Key numbers** (from `reports/tables/lapse_s1_cv.csv` and `reports/tables/lapse_s2_eval.csv`)

| Split | Model | Customers | Base lapse rate | Mean predicted $P$ | Brier score $\downarrow$ | ROC-AUC $\uparrow$ | Log loss $\downarrow$ | 10-bin ECE $\downarrow$ |
|---|---|---|---|---|---|---|---|---|
| **S1 (5-fold OOF CV)** | `logistic_calibrated` (primary) | 3,256 | 0.4140 | 0.4140 | **0.2087** | 0.7177 | **0.6020** | **0.0081** |
| **S1 (5-fold OOF CV)** | `tree_depth4_calibrated` | 3,256 | 0.4140 | 0.4134 | **0.2087** | **0.7186** | 0.6032 | 0.0267 |
| **S1 (5-fold OOF CV)** | `two_bin_recency_90d` | 3,256 | 0.4140 | 0.4140 | 0.2299 | 0.6060 | 0.6521 | 0.0001 |
| **S2 (Held-out test)** | `logistic_calibrated` (primary) | 3,247 | 0.4238 | 0.4008 | **0.2034** | **0.7390** | **0.5870** | 0.0343 |
| **S2 (Held-out test)** | `tree_depth4_calibrated` | 3,247 | 0.4238 | 0.3801 | 0.2143 | 0.7106 | 0.6145 | 0.0774 |
| **S2 (Held-out test)** | `two_bin_recency_90d` | 3,247 | 0.4238 | 0.4125 | 0.2264 | 0.6371 | 0.6448 | **0.0206** |



