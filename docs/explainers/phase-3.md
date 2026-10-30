# Phase 3 explained: K-Means and GMM customer segmentation on S3

## What we did, in plain words

**1. Preprocess S3 RFM features in three steps (`src/segment.py`).** Snapshot S3 has 3,961 active customers (`reports/tables/snapshot_summary.csv`). Because wholesale buyers create extreme right tails in order count and spend, clustering raw features would put a handful of wholesalers into their own cluster and lump everyone else together. Following `CLAUDE.md` section 7.4, we preprocess `recency_days`, `frequency` and `monetary` in three steps (`reports/tables/s3_preprocessing.csv`):

1. **Cap at the S3 99th percentile:** `frequency` is capped at **26.00 invoices** (35 customers capped; raw max 173.0) and `monetary` is capped at **£15,942.81** (40 customers capped; raw max £221,437.00). `recency_days` ranges from 1.0 to 275.0 days and is not capped.
2. **Apply `log1p`:** `np.log1p(x)` compresses the remaining positive skew on all three features.
3. **Standardise (`StandardScaler`):** each `log1p` feature is centred to mean 0 and scaled to standard deviation 1 (`recency_days`: mean 3.6773, std 1.2198; `frequency`: mean 1.2724, std 0.6155; `monetary`: mean 6.4941, std 1.1849) so all three dimensions have equal weight in Euclidean distance and Gaussian likelihoods.

**2. Run the K-Means grid ($K = 2\dots 8$).**

| $K$ | Inertia | Silhouette | Davies–Bouldin | Calinski–Harabasz |
|---|---|---|---|---|
| 2 | 5,884.86 | 0.4315 | 0.8948 | 4,035.21 |
| 3 | 4,458.50 | 0.3337 | 1.0647 | 3,295.56 |
| 4 | 3,577.08 | 0.3325 | 1.0200 | 3,062.79 |
| 5 | 3,002.75 | 0.3089 | 0.9987 | 2,924.86 |
| 6 | 2,609.96 | 0.2982 | 1.0277 | 2,810.41 |
| 7 | 2,347.55 | 0.2964 | 0.9916 | 2,676.78 |
| 8 | 2,138.62 | 0.2952 | 1.0062 | 2,573.11 |

Source: `reports/tables/kmeans_grid.csv`; chart: `reports/figures/kmeans_selection.png`.

**3. Run the GMM grid ($K = 2\dots 8 \times \text{covariance\_type} \in \{\text{spherical, tied, diag, full}\}$, `n_init=10`).**

| Covariance type | $K=2$ BIC | $K=3$ BIC | $K=4$ BIC | $K=5$ BIC | $K=6$ BIC | $K=7$ BIC | $K=8$ BIC |
|---|---|---|---|---|---|---|---|
| `spherical` | 29,909.89 | 28,985.08 | 28,512.82 | 28,003.90 | 27,759.99 | 27,523.86 | 26,935.23 |
| `tied` | 27,761.52 | 27,307.34 | 27,191.27 | 26,948.75 | 27,092.94 | 26,815.18 | 26,809.39 |
| `diag` | 29,032.82 | 11,127.63 | 2,342.16 | -2,758.17 | -6,347.66 | -3,578.41 | -6,772.05 |
| `full` | 10,958.26 | 10,226.74 | 1,823.76 | -3,022.43 | -6,427.10 | -3,437.78 | -9,638.22 |

Source: `reports/tables/gmm_grid.csv`; chart: `reports/figures/gmm_bic_aic.png`.

**4. Why `diag` and `full` are rejected despite negative BIC.** In S3, `frequency` is a discrete integer (`1, 2, 3, ...`). In `diag` and `full`, each component has its own variance parameter on the `frequency` axis. As shown in `reports/tables/gmm_diag_degeneracy.csv`, for `diag, K=4` one component collapses onto the exact plane `frequency = 1` (`n = 1,480` customers, `freq_min = 1, freq_max = 1`) and another onto `frequency = 2` (`n = 781` customers, `freq_min = 2, freq_max = 2`). Because the variance along `frequency` shrinks to the regularization floor (`1e-6`), the Gaussian density spikes, driving BIC to `-6,772.05` (`diag`) and `-9,638.22` (`full`) while slicing customers purely by integer order count and dropping silhouette to `0.10–0.18`. In contrast, `spherical` (one scalar variance per component across all 3 features) and `tied` (one shared $3 \times 3$ covariance matrix across all $K$ components) cannot collapse a single component onto an integer plane.

**5. Proposed choice for the Phase 3 checkpoint: `spherical, K=5` (with `spherical, K=4` and `tied, K=4` as alternatives).**

- **Why `spherical, K=5` (Primary Proposal):**
  - **BIC & geometry:** BIC drops by 508.92 from $K=4$ (`28,512.82`) to $K=5$ (`28,003.90`), while maintaining a clean 3D silhouette of **0.3015** (matching K-Means $K=5$ at `0.3089`) and a meaningful boundary share of **12.50%** (`max_p < 0.6`).
  - **Stability ($B = 100$ bootstrap resamples):** bootstrap ARI median is **0.8674** (IQR `0.0977`), and every single one of the 5 segments exceeds Hennig's `0.75` stability threshold (`jaccard_mean` between **0.8449** and **0.9009**). In contrast, `tied, K=5` has one doubtful segment (`jaccard_mean = 0.687 < 0.75`) and a wide ARI IQR (`0.2332`).
  - **Interpretability in original units:** the 5 centroids map directly onto the 5 classic RFM archetypes listed in `CLAUDE.md` section 7.4:

| Proposed segment | Cluster ID | Customers | Share (%) | Mean / median recency (d) | Mean / median frequency | Mean / median monetary (£) | Mean tenure (d) | Mean basket (£) | AvePP | Mean Jaccard ($B=100$) |
|---|---|---|---|---|---|---|---|---|---|---|
| **Champions** | 4 | 258 | 6.51% | 8.60 / 5.0 | 18.66 / 14.0 | 12,635.95 / 5,455.26 | 620.17 | 620.79 | 0.8934 | 0.8669 |
| **Loyal** | 0 | 1,105 | 27.90% | 21.72 / 17.0 | 5.04 / 5.0 | 2,154.78 / 1,579.14 | 478.98 | 530.84 | 0.8490 | 0.8775 |
| **At-Risk** | 1 | 933 | 23.55% | 86.66 / 72.0 | 2.36 / 2.0 | 978.14 / 786.57 | 447.68 | 517.56 | 0.7880 | 0.8449 |
| **New** | 2 | 636 | 16.06% | 23.19 / 22.0 | 1.42 / 1.0 | 301.97 / 284.55 | 320.97 | 234.11 | 0.8086 | 0.8758 |
| **Hibernating** | 3 | 1,029 | 25.98% | 156.38 / 159.0 | 1.14 / 1.0 | 251.34 / 229.23 | 406.09 | 234.67 | 0.8723 | 0.9009 |

Source: `reports/tables/segment_profiles_spherical_k5.csv`; chart: `reports/figures/segment_profiles_s3.png`.

- **Justification of each segment name from its numbers (`spherical, K=5`):**
  - **Champions (258 customers, 6.51%):** bought within the last week (median recency 5.0 days, mean 8.60), order very frequently (median 14.0 invoices, mean 18.66) and spend the most by far (median £5,455.26, mean £12,635.95).
  - **Loyal (1,105 customers, 27.90%):** regular repeat buyers who purchased recently (median recency 17.0 days, mean 21.72) with solid repeat frequency (median 5.0 invoices, mean 5.04) and spend (median £1,579.14, mean £2,154.78).
  - **At-Risk (933 customers, 23.55%):** previously repeat buyers with high average basket (£517.56, median 2.0 invoices, median spend £786.57) who have not bought for nearly three months (median recency 72.0 days, mean 86.66).
  - **New (636 customers, 16.06%):** bought recently (median recency 22.0 days, mean 23.19) and have the shortest tenure (mean 320.97 days), with 1–2 small orders so far (median 1.0 invoice, median spend £284.55).
  - **Hibernating (1,029 customers, 25.98%):** one-time or low-spend buyers (median 1.0 invoice, median spend £229.23) who have been inactive for over five months (median recency 159.0 days, mean 156.38).

- **Runner-up 4-segment alternative (`spherical, K=4`, `reports/tables/segment_profiles_spherical_k4.csv`):** merges `Champions` + top `Loyal` into `Champions` (`n = 698`, mean spend £6,559.32) and merges `At-Risk` + `Hibernating` into `At-Risk` (`n = 1,484`, mean recency 136.03 days), giving silhouette `0.3306`, bootstrap ARI median `0.9061`, and Jaccards `0.8369–0.9061`.

## Likely viva questions

**1. Why did you cap `frequency` and `monetary` at the 99th percentile before taking `log1p`?**
Even after `log1p`, extreme wholesale outliers (up to 173 invoices and £221,437.00 in S3) stretch the `StandardScaler` standard deviation and pull Gaussian centroids toward a tiny group of wholesalers. Capping at the 99th percentile (26.00 invoices affecting 35 customers, and £15,942.81 affecting 40 customers) bounds the tail before `log1p` and standardization, while keeping all 3,961 customers in the dataset (`reports/tables/s3_preprocessing.csv`).

**2. Why didn't you pick `full, K=8` even though it has the lowest BIC (-9,638.22)?**
Because `frequency` is an integer count of invoices, 1,480 of the 3,961 S3 customers have `frequency = 1` and 781 have `frequency = 2`. When a GMM allows each cluster its own variance on `frequency` (`diag` or `full`), components collapse onto those flat integer planes (`freq_min = freq_max = 1` and `freq_min = freq_max = 2` in `reports/tables/gmm_diag_degeneracy.csv`). A near-zero variance produces an artificially huge density spike and negative BIC, while silhouette collapses to `0.1017` (`full, K=8`). Using `spherical` or `tied` prevents single-axis variance collapse.

**3. Why choose a Gaussian Mixture Model (GMM) over K-Means when K-Means has a similar silhouette (0.3089 vs 0.3015 at K=5)?**
K-Means only outputs a hard cluster label for each customer. Our probabilistic database (`segment_membership`, Topic 1) requires calibrated membership probabilities $\sum_s p_s = 1$ per customer so analysts can query confidence thresholds (`Q1`) and boundary customers (`Q2`). At $K=5$, `spherical` GMM achieves virtually the same geometric separation as K-Means (`0.3015` vs `0.3089`) while providing full posterior probabilities.

**4. How did you decide between $K=4$ and $K=5$ for the `spherical` GMM?**
Both `spherical, K=4` and `spherical, K=5` are highly stable across $B=100$ bootstrap resamples (every cluster has mean Jaccard $\ge 0.8369 > 0.75$). However, $K=5$ lowers BIC by 508.92 (`28,003.90` vs `28,512.82`) and separates two business-critical groups that $K=4$ merges: multi-order **At-Risk** customers (`n = 933`, mean frequency 2.36, mean spend £978.14, mean recency 86.66 days) versus single-order **Hibernating** customers (`n = 1,029`, mean frequency 1.14, mean spend £251.34, mean recency 156.38 days), as well as isolating the top wholesale **Champions** (`n = 258`, mean spend £12,635.95) from regular **Loyal** buyers (`n = 1,105`, mean spend £2,154.78).

**5. Why do you report centroid profiles in original units (£, invoices, days) instead of scaled `log1p` units?**
A business analyst or examiner cannot interpret a `StandardScaler` score of `-0.42` on `log1p(monetary)`. Once customers are assigned to clusters in the preprocessed space, we aggregate their actual `recency_days`, `frequency` and `monetary` in original units (`reports/tables/segment_profiles_spherical_k5.csv`), Reporting both means and medians in original units shows the true business profile of each segment.
