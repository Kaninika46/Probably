# Surrogate Decision-Tree Rules (Snapshot S3)

> **Approximation note:** These axis-aligned decision-tree rules are a post-hoc
> surrogate approximation to the GMM clustering in `log1p` + standardized RFM
> space (following Dasgupta et al., ICML 2020). Because the GMM fits smooth
> ellipsoids in log-scaled space while the tree makes axis-aligned cuts of
> depth 4 in original units (`recency_days`, `frequency`, `monetary`),
> the surrogate agrees with the GMM on **86.80%** of the
> held-out 30% test split (**89.72%** on the 70% training
> split) using **16 leaves**.

## 1. Summary Metrics

- **Max depth configured:** 4
- **Actual depth fitted:** 4
- **Number of leaves:** 16
- **Training set (70%):** 2,772 customers — fidelity **89.72%**
- **Held-out test set (30%):** 1,189 customers — fidelity **86.80%**

## 2. Per-Segment Rules in Original Units

### Champions
- `IF (recency_days <= 36.50 AND 9.50 < frequency <= 10.50 AND monetary > £512.32) [n=30, purity=63.3%]`
- `IF (recency_days <= 36.50 AND frequency > 10.50 AND monetary > £512.32) [n=143, purity=96.5%]`

### Loyal
- `IF (recency_days <= 30.50 AND frequency > 2.50 AND monetary <= £512.32) [n=40, purity=52.5%]`
- `IF (recency_days <= 36.50 AND frequency <= 2.50 AND monetary > £512.32) [n=130, purity=43.1%]`
- `IF (recency_days <= 36.50 AND 2.50 < frequency <= 9.50 AND monetary > £512.32) [n=613, purity=92.7%]`
- `IF (recency_days > 36.50 AND frequency > 4.50 AND £512.32 < monetary <= £1,252.86) [n=23, purity=56.5%]`
- `IF (recency_days > 36.50 AND frequency > 4.50 AND monetary > £1,252.86) [n=76, purity=94.7%]`

### At-Risk
- `IF (30.50 < recency_days <= 47.50 AND frequency > 2.50 AND monetary <= £512.32) [n=13, purity=84.6%]`
- `IF (recency_days > 47.50 AND frequency > 1.50 AND £336.74 < monetary <= £512.32) [n=76, purity=80.3%]`
- `IF (recency_days > 36.50 AND frequency <= 4.50 AND £512.32 < monetary <= £2,139.39) [n=486, purity=92.8%]`
- `IF (recency_days > 36.50 AND frequency <= 4.50 AND monetary > £2,139.39) [n=51, purity=60.8%]`

### New
- `IF (recency_days <= 46.50 AND frequency <= 2.50 AND monetary <= £512.32) [n=369, purity=98.6%]`
- `IF (46.50 < recency_days <= 47.50 AND frequency <= 2.50 AND monetary <= £512.32) [n=9, purity=44.4%]`

### Hibernating
- `IF (recency_days > 47.50 AND frequency <= 1.50 AND monetary <= £21.38) [n=10, purity=50.0%]`
- `IF (recency_days > 47.50 AND frequency <= 1.50 AND £21.38 < monetary <= £512.32) [n=612, purity=97.7%]`
- `IF (recency_days > 47.50 AND frequency > 1.50 AND monetary <= £336.74) [n=91, purity=82.4%]`

## 3. Full `sklearn.tree.export_text` Output

```text
|--- monetary <= 512.32
|   |--- recency_days <= 47.50
|   |   |--- frequency <= 2.50
|   |   |   |--- recency_days <= 46.50
|   |   |   |   |--- class: New
|   |   |   |--- recency_days >  46.50
|   |   |   |   |--- class: New
|   |   |--- frequency >  2.50
|   |   |   |--- recency_days <= 30.50
|   |   |   |   |--- class: Loyal
|   |   |   |--- recency_days >  30.50
|   |   |   |   |--- class: At-Risk
|   |--- recency_days >  47.50
|   |   |--- frequency <= 1.50
|   |   |   |--- monetary <= 21.38
|   |   |   |   |--- class: Hibernating
|   |   |   |--- monetary >  21.38
|   |   |   |   |--- class: Hibernating
|   |   |--- frequency >  1.50
|   |   |   |--- monetary <= 336.74
|   |   |   |   |--- class: Hibernating
|   |   |   |--- monetary >  336.74
|   |   |   |   |--- class: At-Risk
|--- monetary >  512.32
|   |--- recency_days <= 36.50
|   |   |--- frequency <= 9.50
|   |   |   |--- frequency <= 2.50
|   |   |   |   |--- class: Loyal
|   |   |   |--- frequency >  2.50
|   |   |   |   |--- class: Loyal
|   |   |--- frequency >  9.50
|   |   |   |--- frequency <= 10.50
|   |   |   |   |--- class: Champions
|   |   |   |--- frequency >  10.50
|   |   |   |   |--- class: Champions
|   |--- recency_days >  36.50
|   |   |--- frequency <= 4.50
|   |   |   |--- monetary <= 2139.39
|   |   |   |   |--- class: At-Risk
|   |   |   |--- monetary >  2139.39
|   |   |   |   |--- class: At-Risk
|   |   |--- frequency >  4.50
|   |   |   |--- monetary <= 1252.86
|   |   |   |   |--- class: Loyal
|   |   |   |--- monetary >  1252.86
|   |   |   |   |--- class: Loyal
```
