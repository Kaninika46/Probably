# Phase 5 explained: 90-day lapse model, calibration, S2 evaluation and S3 scoring

## What we did, in plain words

**1. Define "lapse (no purchase in 90 days)" rather than permanent abandonment.** In non-contractual retail (unlike a mobile phone subscription), there is no cancellation event—a customer simply goes quiet for a while and may return later. Following `CLAUDE.md` section 7.7, we predict `lapsed_next_90d = 1 - purchased_next_90d`: the probability that an active customer makes zero clean product purchases in the 90 days starting at snapshot date $S$. (Classic stochastic counting models such as Fader, Hardie & Lee's 2005 BG/NBD model are noted in `docs/references.md` as the alternative not used here.)

**2. Train and cross-validate three models on S1 only (`2010-09-10`, 3,256 customers, base lapse rate 41.40%).**
- **Primary model (`logistic_calibrated`):** a `Pipeline` of `log1p` transform $\to$ `StandardScaler` $\to$ `LogisticRegression(random_state=42)` on all 5 snapshot features (`recency_days, frequency, monetary, tenure_days, avg_basket`), wrapped in `CalibratedClassifierCV(method='sigmoid', cv=5)`. Placing `StandardScaler` inside the pipeline ensures each of the 5 calibration folds scales using only its own training split.
- **Comparison 1 (`two_bin_recency_90d`):** the empirical S1 lapse rate for customers with `recency_days <= 90` (**31.74%**) versus `recency_days > 90` (**54.71%**, `reports/tables/lapse_baseline_s1_rates.csv`).
- **Comparison 2 (`tree_depth4_calibrated`):** a `DecisionTreeClassifier(max_depth=4, random_state=42)` calibrated with `CalibratedClassifierCV(method='sigmoid', cv=5)` on S1.

**3. Evaluate once on the held-out temporal test set S2 (`2011-09-10`, 3,247 customers, base lapse rate 42.38%).**

| Split | Model | Customers | Base lapse rate | Mean predicted $P$ | Brier score $\downarrow$ | Brier skill score $\uparrow$ | ROC-AUC $\uparrow$ | Log loss $\downarrow$ | 10-bin ECE $\downarrow$ |
|---|---|---|---|---|---|---|---|---|---|
| **S1 (5-fold OOF CV)** | `logistic_calibrated` (primary) | 3,256 | 0.4140 | 0.4140 | **0.2087** | 0.1397 | 0.7177 | **0.6020** | **0.0081** |
| **S1 (5-fold OOF CV)** | `tree_depth4_calibrated` | 3,256 | 0.4140 | 0.4134 | **0.2087** | **0.1398** | **0.7186** | 0.6032 | 0.0267 |
| **S1 (5-fold OOF CV)** | `two_bin_recency_90d` | 3,256 | 0.4140 | 0.4140 | 0.2299 | 0.0523 | 0.6060 | 0.6521 | 0.0001 |
| **S2 (Held-out test)** | `logistic_calibrated` (primary) | 3,247 | 0.4238 | 0.4008 | **0.2034** | **0.1672** | **0.7390** | **0.5870** | 0.0343 |
| **S2 (Held-out test)** | `tree_depth4_calibrated` | 3,247 | 0.4238 | 0.3801 | 0.2143 | 0.1225 | 0.7106 | 0.6145 | 0.0774 |
| **S2 (Held-out test)** | `two_bin_recency_90d` | 3,247 | 0.4238 | 0.4125 | 0.2264 | 0.0730 | 0.6371 | 0.6448 | **0.0206** |

Sources: `reports/tables/lapse_s1_cv.csv`, `reports/tables/lapse_s2_eval.csv`, `reports/tables/lapse_reliability_bins_s2.csv`; chart: `reports/figures/lapse_reliability_s2.png`.

**4. Score S3 into the tuple-independent probabilistic table `lapse_risk`.**
Every one of the 3,961 S3 customers gets a row in `lapse_risk` (`customer_id, snapshot='S3', p_lapse_90d, model_version`), where `model_version` is the git short hash (`4cfb5e3`). Across S3 segments (`reports/tables/lapse_s3_by_segment.csv`):

| Segment (bootstrap top) | Customers | Mean $P(\text{lapse 90d})$ | Median $P(\text{lapse 90d})$ | Customers with $P(\text{lapse 90d}) \ge 0.66$ ("probably lapsing") |
|---|---|---|---|---|
| **Hibernating** | 1,005 | 0.5746 | 0.5770 | 54 |
| **New** | 634 | 0.4972 | 0.5004 | 14 |
| **At-Risk** | 928 | 0.3801 | 0.3803 | 0 |
| **Loyal** | 1,116 | 0.2084 | 0.2027 | 0 |
| **Champions** | 278 | 0.0618 | 0.0645 | 0 |

## Likely viva questions

**1. Why is `lapse_risk` called a tuple-independent probabilistic table, whereas `segment_membership` is a BID table?**
In `lapse_risk`, each tuple represents one customer at snapshot S3 (`PRIMARY KEY (customer_id, snapshot)`), and its attribute `p_lapse_90d` is the Bernoulli probability that this specific customer will have no purchase in the next 90 days. There are no mutually exclusive alternative rows for the same customer inside `lapse_risk`, whereas `segment_membership` has 5 mutually exclusive rows per customer that must sum to 1.

**2. Why must probabilities be calibrated before storing them in a probabilistic database?**
When an analyst asks a natural-language question like *"Who will probably lapse?"*, the system translates *"probably"* to a numerical probability threshold $P \ge 0.66$ (IPCC scale). If a classifier's scores are uncalibrated, $0.66$ does not mean a 66% empirical chance of lapsing. Using `CalibratedClassifierCV(method='sigmoid', cv=5)` (Platt scaling) aligns predicted probabilities with empirical lapse frequencies, achieving a 10-bin ECE of **0.0081** on S1 OOF CV and **0.0343** on the held-out S2 test set (`reports/tables/lapse_s2_eval.csv`).

**3. Why did the calibrated logistic regression generalise better from S1 to S2 (Brier 0.2034, ROC-AUC 0.7390, ECE 0.0343) than the calibrated depth-4 tree (Brier 0.2143, ROC-AUC 0.7106, ECE 0.0774)?**
On S1 5-fold CV, the two models looked almost tied (`ROC-AUC 0.7177` vs `0.7186`, `Brier 0.2087` vs `0.2087`). However, between S1 (`2010-09-10`) and S2 (`2011-09-10`), mean `tenure_days` more than doubled from 181.07 days to 405.23 days (`reports/tables/snapshot_summary.csv`). A decision tree makes hard step-function splits that overfit S1's shorter tenure range, causing its mean predicted probability on S2 to drop to `0.3801` (vs actual `0.4238`) and its ECE to double to `0.0774`. The smooth `log1p` linear model adapts gracefully to S2 (`ROC-AUC = 0.7390`, `Brier = 0.2034`).

**4. Why does the two-bin rule (`recency_days > 90`) have a low ECE (0.0206 on S2) yet a poor Brier score (0.2264) and ROC-AUC (0.6371)?**
Calibration (ECE) only measures whether the average outcome inside each predicted bin matches the bin's predicted probability; a model that outputs only two numbers (`0.3174` for `recency <= 90` and `0.5471` for `recency > 90`, `reports/tables/lapse_baseline_s1_rates.csv`) lands in just two bins (`[0.3, 0.4)` and `[0.5, 0.6)`) whose averages stay close to the S2 rates (`0.3095` and `0.5856`). However, it cannot distinguish a 20-order Champion with `recency = 10` days (`p_lapse_90d = 0.0618`) from a 1-order customer with `recency = 85` days (`p_lapse_90d > 0.50`), so its discrimination (`ROC-AUC = 0.6371`) and Brier score (`0.2264` vs `0.2034`) are much worse.

**5. Why did `CLAUDE.md` forbid multiplying `p` (segment membership) and `p_lapse_90d` (lapse risk) in Q6?**
Multiplying $P(A) \times P(B)$ is only valid when events $A$ and $B$ are statistically independent. Here, both `segment_membership.p` and `lapse_risk.p_lapse_90d` are deterministic functions of the same underlying RFM features—especially `recency_days` and `frequency`. As `reports/tables/lapse_s3_by_segment.csv` shows, mean lapse probability ranges from **0.0618** in `Champions` to **0.5746** in `Hibernating`, proving strong dependence. Therefore Q6 filters on two separate threshold predicates (`p >= $tau1 AND p_lapse_90d >= $tau2`) without ever multiplying them.
