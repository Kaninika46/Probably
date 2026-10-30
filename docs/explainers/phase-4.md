# Phase 4 explained: BID membership probabilities, stability, gate report and surrogate tree rules

## What we did, in plain words

**1. Build the Block-Independent-Disjoint (BID) table `segment_membership` (`src/membership.py`).** In a deterministic database, each customer gets one hard segment label, hiding whether they sit right in the middle of a cluster or on the border between two clusters. Following Dalvi & Suciu's Block-Independent-Disjoint (BID) model (`CLAUDE.md` section 6 & 7.5), `segment_membership` has block key `(customer_id, snapshot, method)`: within each block, the five segment tuples (`Champions`, `Loyal`, `At-Risk`, `New`, `Hibernating`) are mutually exclusive possibilities whose probabilities sum to 1 ($\sum_s p_s = 1$), while different customers are independent across blocks.

We populate `segment_membership` for all 3,961 S3 customers using two methods (`3,961 × 5 × 2 = 39,610` rows):

- **`method = 'gmm'`:** the analytic posterior probabilities `predict_proba` from the provisional GMM (`covariance_type = 'spherical'`, $K = 5$, `n_init = 10`, `random_state = 42`, recorded in `docs/DECISIONS.md`).
- **`method = 'bootstrap'`:** $B = 100$ bootstrap resamples of the 3,961 S3 customers drawn with replacement. On each resample we refit the `spherical, K=5` GMM, predict hard labels for all 3,961 customers, and align the resample's cluster indices to the reference GMM labels using the Hungarian algorithm (`scipy.optimize.linear_sum_assignment`) on the contingency matrix. A customer's bootstrap probability $p_s$ is the fraction of the 100 fits that placed them in segment $s$.

**2. Measure clustering stability (`reports/tables/bootstrap_stability.csv`, `reports/tables/segment_stability.csv`).**
Across the $B = 100$ bootstrap resamples:
- **Adjusted Rand Index (ARI) vs reference:** median **0.8674**, IQR **0.0977** (25th percentile `0.8151`, 75th percentile `0.9128`, mean `0.8414`).
- **Hennig (2007) per-segment Jaccard similarity:** every segment is in the `stable (>= 0.75)` band:

| Segment | Reference customers | Mean Jaccard | Median Jaccard | Jaccard IQR | Hennig stability band |
|---|---|---|---|---|---|
| **Champions** | 258 | 0.8669 | 0.9073 | 0.1291 | `stable (>= 0.75)` |
| **Loyal** | 1,105 | 0.8775 | 0.9035 | 0.0572 | `stable (>= 0.75)` |
| **At-Risk** | 933 | 0.8449 | 0.8777 | 0.1297 | `stable (>= 0.75)` |
| **New** | 636 | 0.8758 | 0.8972 | 0.0839 | `stable (>= 0.75)` |
| **Hibernating** | 1,029 | 0.9009 | 0.9334 | 0.0807 | `stable (>= 0.75)` |

**3. Go/no-go gate report (`reports/tables/gate.csv`, `reports/tables/gate_ave_pp.csv`, `reports/figures/gate_max_p_hist.png`).**
For each method, we measure the share of boundary customers ($\max_s p_s < 0.60$), the mean and median normalised Shannon entropy $-\frac{1}{\ln 5}\sum_s p_s \ln p_s$, and the Average Posterior Probability (AvePP) per segment:

| Method | Customers | Boundary customers ($\max p < 0.6$) | Boundary share (%) | Mean $\max p$ | Median $\max p$ | Mean norm. entropy | Median norm. entropy | AvePP Champions | AvePP Loyal | AvePP At-Risk | AvePP New | AvePP Hibernating |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `gmm` | 3,961 | 495 | **12.50%** | 0.8371 | 0.8996 | 0.2526 | 0.2253 | 0.8934 | 0.8490 | 0.7880 | 0.8086 | 0.8723 |
| `bootstrap` | 3,961 | 152 | **3.84%** | 0.9329 | 0.9900 | 0.1041 | 0.0348 | 0.9490 | 0.9339 | 0.9191 | 0.9409 | 0.9352 |

| Method | Segment | Hard count (most probable) | Expected size $\sum p$ | AvePP |
|---|---|---|---|---|
| `gmm` | Champions | 258 | 278.63 | 0.8934 |
| `gmm` | Loyal | 1,105 | 1,073.79 | 0.8490 |
| `gmm` | At-Risk | 933 | 943.04 | 0.7880 |
| `gmm` | New | 636 | 670.19 | 0.8086 |
| `gmm` | Hibernating | 1,029 | 995.35 | 0.8723 |
| `bootstrap` | Champions | 278 | 290.55 | 0.9490 |
| `bootstrap` | Loyal | 1,116 | 1,110.32 | 0.9339 |
| `bootstrap` | At-Risk | 928 | 941.95 | 0.9191 |
| `bootstrap` | New | 634 | 643.37 | 0.9409 |
| `bootstrap` | Hibernating | 1,005 | 974.81 | 0.9352 |

- **Gate Recommendation:**
  - Under `method = 'gmm'`, the boundary share is **12.50%** (495 customers, 1 in 8 customers) and mean normalised entropy is **0.2526**, which is a meaningful boundary population where soft GMM posteriors differ substantially from hard labels (for example, `Champions` expected size is 278.63 vs 258 hard count, and `New` is 670.19 vs 636).
  - Under `method = 'bootstrap'`, the boundary share is **3.84%** (152 customers) and median $\max p = 0.9900$, because with $N = 3,961$ customers the cluster boundaries move very little across bootstrap resamples.
  - Therefore, if we emphasise `gmm` posteriors, **segment confidence** has a meaningful 12.50% boundary share; if we emphasise the default `bootstrap` method (`3.84%` boundary share), **lapse risk** is the stronger headline uncertainty while `segment_membership` still identifies the 152 boundary customers whose segment flips across resamples.

**4. Fit the depth-4 surrogate decision tree in original units (`src/rules.py`, `reports/tables/tree_rules.md`).**
We split S3 70/30 (`2,772` train / `1,189` test, stratified by top GMM segment) and fit `DecisionTreeClassifier(max_depth=4, random_state=42)` on raw `recency_days`, `frequency` and `monetary`:
- **Number of leaves:** 16 (depth 4).
- **Training fidelity (70%):** **89.72%** (`2,487 / 2,772`).
- **Held-out test fidelity (30%):** **86.80%** (`1,032 / 1,189`).
- **Per-segment test fidelity (`reports/tables/tree_fidelity_by_segment.csv`):** `Loyal` **91.87%** (`305/332`), `Hibernating` **90.94%** (`281/309`), `Champions` **87.01%** (`67/77`), `New` **81.68%** (`156/191`), `At-Risk` **79.64%** (`223/280`).
- As noted in `reports/tables/tree_rules.md`, these tree rules are **approximations**: the GMM fits curved boundaries in `log1p`-scaled 3D space, whereas the depth-4 tree makes axis-aligned rectangular cuts in original units, leaving a 13.20% approximation gap on the test set—precisely the customers near cluster boundaries.

## Likely viva questions

**1. What makes `segment_membership` a Block-Independent-Disjoint (BID) probabilistic table?**
In probabilistic database theory (Dalvi & Suciu), a BID table partitions rows into independent blocks, and the rows inside one block represent mutually exclusive alternatives whose probabilities sum to at most 1 (here exactly 1). In `segment_membership`, the block key is `(customer_id, snapshot, method)`: a given customer under a given method can belong to only one true segment in any possible world, so their five segment probabilities sum to 1.0 (`tests/test_membership.py::test_bid_block_probabilities_sum_to_one`).

**2. Why do we need `scipy.optimize.linear_sum_assignment` during the bootstrap?**
Clustering algorithms are permutation-invariant: cluster `0` in bootstrap resample #1 might correspond to `Champions`, while in resample #2 the same customers might be labelled cluster `3` ("label switching"). Before we can average cluster assignments across the 100 resamples, we build the $5 \times 5$ contingency matrix between the reference labels and the resample's labels and solve the linear assignment problem (Hungarian algorithm) to find the one-to-one mapping that maximises overlap.

**3. Why is the boundary share 12.50% (495 customers) for `gmm` but only 3.84% (152 customers) for `bootstrap`?**
They measure two different sources of uncertainty:
- `gmm` (`predict_proba`) measures **aleatoric / geometric overlap**: how close a customer's RFM point is to the midpoint between two Gaussian components.
- `bootstrap` measures **epistemic / sampling instability**: how often the decision boundary itself shifts across $B = 100$ resamples of $N = 3,961$ customers. Because $N = 3,961$ is large for 3 dimensions, the fitted centroids barely move from resample to resample, so a customer sitting 52%/48% on the `Loyal` side of the boundary gets assigned to `Loyal` in almost every resample.

**4. Why did you fit the surrogate decision tree on original units instead of the `log1p` + scaled features used by the GMM?**
The purpose of the decision tree is human interpretability: an analyst wants rules like `monetary > £512.32 AND recency_days <= 36.50 AND frequency > 10.50` (`Champions`), not thresholds on z-scored logarithms. Because any monotone transform of a single feature preserves the ordering of threshold splits on that feature, a decision tree on original units has the exact same expressive power as one on `log1p` + scaled features!

**5. Why does the decision tree agree with the GMM on 86.80% of test customers rather than 100%?**
The GMM defines cluster boundaries using Euclidean distance in 3D `log1p`-standardized space, which corresponds to curved surfaces that depend on all three features simultaneously. A depth-4 decision tree can only make 16 axis-aligned rectangular boxes (`feature <= threshold`). The 13.20% disagreement (`157` of `1,189` test customers, lowest on `At-Risk` at 79.64%) occurs along the diagonal boundaries between `Loyal`, `At-Risk` and `New`—the exact same region where the GMM reports boundary probabilities $\max p < 0.60$.
