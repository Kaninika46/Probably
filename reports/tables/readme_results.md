### 1. Data Cleaning Funnel (`reports/tables/cleaning_funnel.csv`)

| Step | Rule | Rows Before | Rows After | Rows Removed | Revenue Affected (GBP) | % of Pre-Step Revenue | % of Raw Revenue |
|---:|---|---:|---:|---:|---:|---:|---:|
| 1 | Overlap duplicates between sheets | 1,067,371 | 1,044,848 | 22,523 | 377,488.45 | 1.96% | 1.96% |
| 2 | Remaining exact duplicates | 1,044,848 | 1,033,036 | 11,812 | 54,228.42 | 0.29% | 0.28% |
| 3 | Cancellations moved to returns | 1,033,036 | 1,013,932 | 19,104 | -1,462,050.61 | -7.75% | -7.58% |
| 4 | Quantity or price not positive | 1,013,932 | 1,007,913 | 6,019 | -158,676.14 | -0.78% | -0.82% |
| 5 | Non-product stock codes | 1,007,913 | 1,003,357 | 4,556 | 832,398.81 | 4.07% | 4.32% |
| 6 | Missing customer_id (excluded from customer analysis) | 1,003,357 | 776,596 | 226,761 | 2,575,278.90 | 13.11% | 13.35% |

- **Raw net revenue (`reports/tables/raw_totals.csv`):** `£19,287,250.57` across `1,067,371` rows.
- **Clean product sales revenue (`reports/tables/clean_sales_summary.csv`):** `£19,643,861.64` across `1,003,357` rows (`£17,068,582.74` across `776,596` customer-identified rows).

### 2. Temporal Snapshots & Base Lapse Rates (`reports/tables/snapshot_summary.csv`)

| Snapshot | Snapshot Date | Feature Window | Customers | Mean Recency (d) | Mean Frequency | Mean Monetary (GBP) | 90-Day Lapse Rate |
|---|---|---|---:|---:|---:|---:|---:|
| S1 | `2010-09-10` | `2009-12-10` to `2010-09-09` | 3,256 | 87.89 | 3.53 | 1,598.59 | 41.40% |
| S2 | `2011-09-10` | `2010-12-10` to `2011-09-09` | 3,247 | 88.36 | 3.40 | 1,555.65 | 42.38% |
| S3 | `2011-12-10` | `2011-03-10` to `2011-12-09` | 3,961 | 71.38 | 3.70 | 1,768.34 | N/A (future window) |

### 3. S3 Segment Profiles & Bootstrap Stability (`reports/tables/segment_profiles_spherical_k5.csv`)

| Segment | GMM Hard Count | Share (%) | Mean Recency (d) | Mean Frequency | Mean Monetary (GBP) | Mean AvePP | Mean Jaccard |
|---|---:|---:|---:|---:|---:|---:|---:|
| **Champions** | 258 | 6.51% | 8.60 | 18.66 | 12,635.95 | 0.8934 | 0.8669 |
| **Loyal** | 1,105 | 27.90% | 21.72 | 5.04 | 2,154.78 | 0.8490 | 0.8775 |
| **At-Risk** | 933 | 23.55% | 86.66 | 2.36 | 978.14 | 0.7880 | 0.8449 |
| **New** | 636 | 16.06% | 23.19 | 1.42 | 301.97 | 0.8086 | 0.8758 |
| **Hibernating** | 1,029 | 25.98% | 156.38 | 1.14 | 251.34 | 0.8723 | 0.9009 |

- **Bootstrap Adjusted Rand Index (B = 100):** median `0.8674` (IQR `0.0977`).
- **Decision-tree surrogate (`reports/tables/tree_fidelity.csv`):** depth `4` with `16` leaves; train fidelity `89.72%` (`n = 2,772`), held-out 30% test fidelity `86.80%` (`n = 1,189`).

### 4. Membership Probability Gate (`reports/tables/gate.csv`)

| Method | Customers | Boundary Customers (`max p < 0.60`) | Boundary Share (%) | Mean `max p` | Median `max p` | Mean Normalised Entropy |
|---|---:|---:|---:|---:|---:|---:|
| `gmm` | 3,961 | 495 | 12.50% | 0.8371 | 0.8996 | 0.2526 |
| `bootstrap` | 3,961 | 152 | 3.84% | 0.9329 | 0.9900 | 0.1041 |

### 5. Hard Counts vs Probabilistic Expected Segment Sizes (`reports/tables/kmeans_vs_expected_sizes.csv`)

| Segment | K-Means Hard Count | GMM Hard Count | GMM Expected Size `SUM(p)` | GMM SD | Bootstrap Hard Count | Bootstrap Expected Size `SUM(p)` | Bootstrap SD |
|---|---:|---:|---:|---:|---:|---:|---:|
| **Champions** | 364 | 258 | 278.63 | 7.43 | 278 | 290.55 | 5.63 |
| **Loyal** | 887 | 1,105 | 1073.79 | 14.71 | 1,116 | 1110.32 | 10.22 |
| **At-Risk** | 901 | 933 | 943.04 | 16.99 | 928 | 941.95 | 10.91 |
| **New** | 736 | 636 | 670.19 | 14.07 | 634 | 643.37 | 7.81 |
| **Hibernating** | 1,073 | 1,029 | 995.35 | 12.79 | 1,005 | 974.81 | 8.60 |

### 6. Held-Out S2 90-Day Lapse Model Evaluation (`reports/tables/lapse_s2_eval.csv`)

| Model | Test Customers (S2) | Base Lapse Rate | Mean Predicted `p` | Brier Score | Brier Skill Score | ROC-AUC | Log Loss | 10-Bin ECE |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `logistic_calibrated` | 3,247 | 0.4238 | 0.4008 | 0.2034 | 0.1672 | 0.7390 | 0.5870 | 0.0343 |
| `tree_depth4_calibrated` | 3,247 | 0.4238 | 0.3801 | 0.2143 | 0.1225 | 0.7106 | 0.6145 | 0.0774 |
| `two_bin_recency_90d` | 3,247 | 0.4238 | 0.4125 | 0.2264 | 0.0730 | 0.6371 | 0.6448 | 0.0206 |

### 7. Natural-Language Engine Evaluation (`reports/tables/nl_summary.csv`)

| Split | Total Questions | In-Scope | Out-of-Scope | Overall Execution Accuracy | In-Scope Execution Accuracy | Template Match Rate | Out-of-Scope Rejection Rate | Hedge Threshold Accuracy |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `dev` | 26 | 21 | 5 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
