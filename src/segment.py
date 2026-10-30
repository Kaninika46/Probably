"""Phase 3: customer segmentation on snapshot S3 using K-Means and GMM grids.

Follows CLAUDE.md section 7.4:
1. Features: recency_days, frequency, monetary on snapshot S3.
2. Preprocessing: cap frequency and monetary at the S3 99th percentile, apply
   log1p to all three features, then StandardScaler.
3. K-Means grid over K = 2..8 (silhouette, Davies-Bouldin, Calinski-Harabasz).
4. GMM grid over K = 2..8 x covariance_type in {spherical, tied, diag, full}
   with n_init=10 (BIC, AIC, silhouette, min cluster size, boundary share).
5. Candidate stability & centroid profile comparison in original units for the
   Phase 3 human checkpoint.
"""

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment
from sklearn.cluster import KMeans
from sklearn.metrics import (
    adjusted_rand_score,
    calinski_harabasz_score,
    davies_bouldin_score,
    silhouette_score,
)
from sklearn.metrics.cluster import contingency_matrix
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import StandardScaler

from src import config, db

FEATURE_COLS = ["recency_days", "frequency", "monetary"]

# Proposed default choice for the Phase 3 checkpoint (confirmed by human before Phase 4).
PROPOSED_COV_TYPE = "spherical"
PROPOSED_K = 5


def load_s3_features(con) -> pd.DataFrame:
    """Load S3 customer features ordered by customer_id so row order is fixed."""
    return con.execute("""
        SELECT
            customer_id,
            recency_days,
            frequency,
            monetary,
            tenure_days,
            avg_basket
        FROM customer_features
        WHERE snapshot = 'S3'
        ORDER BY customer_id
    """).df()


def preprocess_s3_rfm(df: pd.DataFrame) -> tuple[np.ndarray, pd.DataFrame]:
    """Cap frequency and monetary at the S3 99th percentile, then log1p, then scale.

    Returns (x_scaled, caps_table) so the exact cap thresholds and scaler
    statistics are recorded in reports/tables/s3_preprocessing.csv.
    """
    work = df[FEATURE_COLS].astype(float).copy()
    records = []
    for col in FEATURE_COLS:
        raw_max = float(work[col].max())
        if col in ("frequency", "monetary"):
            cap_val = float(np.percentile(work[col], config.CAP_PERCENTILE))
            n_capped = int((work[col] > cap_val).sum())
            work[col] = np.clip(work[col], None, cap_val)
        else:
            cap_val = raw_max
            n_capped = 0
        records.append({
            "feature": col,
            "raw_min": round(float(df[col].min()), 2),
            "raw_median": round(float(df[col].median()), 2),
            "raw_max": round(raw_max, 2),
            "cap_99th_pct": round(cap_val, 2),
            "n_customers_capped": n_capped,
        })

    log_work = np.log1p(work)
    scaler = StandardScaler()
    x_scaled = scaler.fit_transform(log_work)

    for i, row in enumerate(records):
        row["log1p_mean"] = round(float(scaler.mean_[i]), 4)
        row["log1p_std"] = round(float(scaler.scale_[i]), 4)

    return x_scaled, pd.DataFrame(records)


def run_kmeans_grid(x_scaled: np.ndarray) -> pd.DataFrame:
    """Fit K-Means for K = 2..8 and compute internal cluster validity metrics."""
    rows = []
    for k in config.K_RANGE:
        km = KMeans(
            n_clusters=k,
            n_init=config.GMM_N_INIT,
            random_state=config.RANDOM_STATE,
        )
        labels = km.fit_predict(x_scaled)
        rows.append({
            "k": k,
            "inertia": round(float(km.inertia_), 2),
            "silhouette": round(float(silhouette_score(x_scaled, labels)), 4),
            "davies_bouldin": round(float(davies_bouldin_score(x_scaled, labels)), 4),
            "calinski_harabasz": round(float(calinski_harabasz_score(x_scaled, labels)), 2),
        })
    return pd.DataFrame(rows)


def run_gmm_grid(x_scaled: np.ndarray) -> pd.DataFrame:
    """Fit GMM over K = 2..8 and covariance_type in {spherical, tied, diag, full}."""
    rows = []
    for cov_type in config.GMM_COVARIANCE_TYPES:
        for k in config.K_RANGE:
            gmm = GaussianMixture(
                n_components=k,
                covariance_type=cov_type,
                n_init=config.GMM_N_INIT,
                random_state=config.RANDOM_STATE,
            ).fit(x_scaled)
            labels = gmm.predict(x_scaled)
            probs = gmm.predict_proba(x_scaled)
            max_p = probs.max(axis=1)
            counts = np.bincount(labels, minlength=k)
            rows.append({
                "covariance_type": cov_type,
                "k": k,
                "bic": round(float(gmm.bic(x_scaled)), 2),
                "aic": round(float(gmm.aic(x_scaled)), 2),
                "silhouette": round(float(silhouette_score(x_scaled, labels)), 4),
                "min_cluster_size": int(counts.min()),
                "boundary_share_pct": round(float(100.0 * (max_p < config.BOUNDARY_P).mean()), 2),
            })
    return pd.DataFrame(rows)


def check_diag_frequency_collapse(s3_df: pd.DataFrame, x_scaled: np.ndarray) -> pd.DataFrame:
    """Show why diag/full get artificially negative BIC: components collapse onto integer frequency planes."""
    gmm = GaussianMixture(
        n_components=4,
        covariance_type="diag",
        n_init=config.GMM_N_INIT,
        random_state=config.RANDOM_STATE,
    ).fit(x_scaled)
    tmp = s3_df.copy()
    tmp["cluster"] = gmm.predict(x_scaled)
    summary = (
        tmp.groupby("cluster", as_index=False)
        .agg(
            n_customers=("customer_id", "count"),
            freq_min=("frequency", "min"),
            freq_median=("frequency", "median"),
            freq_max=("frequency", "max"),
            recency_mean=("recency_days", "mean"),
            monetary_mean=("monetary", "mean"),
        )
        .round(2)
    )
    return summary


def assign_proposed_names_k5(profile_df: pd.DataFrame) -> list[str]:
    """Map the 5 clusters of (spherical, K=5) to RFM names from their original-unit centroids.

    Rules based on the centroid ranks:
    - Highest monetary & frequency -> 'Champions'
    - Second-highest monetary & frequency -> 'Loyal'
    - Highest recency_days (longest inactive) -> 'Hibernating'
    - Lowest recency_days among the remaining low-frequency clusters -> 'New'
    - Remaining moderate-recency multi-order cluster -> 'At-Risk'
    """
    names = {}
    by_mon = profile_df.sort_values("mean_monetary", ascending=False)["cluster_id"].tolist()
    names[by_mon[0]] = "Champions"
    names[by_mon[1]] = "Loyal"

    remaining = [c for c in profile_df["cluster_id"] if c not in names]
    rem_df = profile_df[profile_df["cluster_id"].isin(remaining)]

    hibernating_id = int(rem_df.sort_values("mean_recency_days", ascending=False).iloc[0]["cluster_id"])
    names[hibernating_id] = "Hibernating"

    rem2_df = rem_df[rem_df["cluster_id"] != hibernating_id].sort_values("mean_recency_days", ascending=True)
    names[int(rem2_df.iloc[0]["cluster_id"])] = "New"
    names[int(rem2_df.iloc[1]["cluster_id"])] = "At-Risk"

    return [names[cid] for cid in profile_df["cluster_id"]]


def assign_proposed_names_k4(profile_df: pd.DataFrame) -> list[str]:
    """Map the 4 clusters of (spherical, K=4) to RFM names from their original-unit centroids."""
    names = {}
    by_mon = profile_df.sort_values("mean_monetary", ascending=False)["cluster_id"].tolist()
    names[by_mon[0]] = "Champions"
    names[by_mon[1]] = "Loyal"

    remaining = [c for c in profile_df["cluster_id"] if c not in names]
    rem_df = profile_df[profile_df["cluster_id"].isin(remaining)].sort_values(
        "mean_recency_days", ascending=True
    )
    names[int(rem_df.iloc[0]["cluster_id"])] = "New"
    names[int(rem_df.iloc[1]["cluster_id"])] = "At-Risk"
    return [names[cid] for cid in profile_df["cluster_id"]]


def build_candidate_profile(
    s3_df: pd.DataFrame,
    x_scaled: np.ndarray,
    cov_type: str,
    k: int,
) -> pd.DataFrame:
    """Fit a candidate GMM, compute B=100 bootstrap Jaccard stability, and summarize original-unit profiles."""
    ref_gmm = GaussianMixture(
        n_components=k,
        covariance_type=cov_type,
        n_init=config.GMM_N_INIT,
        random_state=config.RANDOM_STATE,
    ).fit(x_scaled)
    ref_labels = ref_gmm.predict(x_scaled)
    ref_probs = ref_gmm.predict_proba(x_scaled)

    # B = 100 bootstrap resamples to measure Hennig per-cluster Jaccard stability
    rng = np.random.default_rng(config.RANDOM_STATE)
    n = len(x_scaled)
    jaccards = np.zeros((config.BOOTSTRAP_B, k))
    aris = []
    for b in range(config.BOOTSTRAP_B):
        idx = rng.integers(0, n, size=n)
        boot_gmm = GaussianMixture(
            n_components=k,
            covariance_type=cov_type,
            n_init=config.GMM_N_INIT,
            random_state=config.RANDOM_STATE + b + 1,
        ).fit(x_scaled[idx])
        boot_labels = boot_gmm.predict(x_scaled)
        cm = contingency_matrix(ref_labels, boot_labels)
        r_ind, c_ind = linear_sum_assignment(-cm)
        remap = {c: r for r, c in zip(r_ind, c_ind)}
        aligned = np.array([remap[val] for val in boot_labels])
        aris.append(adjusted_rand_score(ref_labels, aligned))
        for c in range(k):
            inter = np.sum((ref_labels == c) & (aligned == c))
            union = np.sum((ref_labels == c) | (aligned == c))
            jaccards[b, c] = inter / union if union > 0 else 0.0

    tmp = s3_df.copy()
    tmp["cluster_id"] = ref_labels
    tmp["max_p"] = ref_probs.max(axis=1)

    prof = (
        tmp.groupby("cluster_id", as_index=False)
        .agg(
            n_customers=("customer_id", "count"),
            mean_recency_days=("recency_days", "mean"),
            median_recency_days=("recency_days", "median"),
            mean_frequency=("frequency", "mean"),
            median_frequency=("frequency", "median"),
            mean_monetary=("monetary", "mean"),
            median_monetary=("monetary", "median"),
            mean_tenure_days=("tenure_days", "mean"),
            mean_avg_basket=("avg_basket", "mean"),
            ave_pp=("max_p", "mean"),
        )
    )
    prof["share_of_customers_pct"] = (100.0 * prof["n_customers"] / len(s3_df)).round(2)
    prof["jaccard_mean"] = np.round(jaccards.mean(axis=0), 4)
    prof["bootstrap_ari_median"] = round(float(np.median(aris)), 4)
    prof["bootstrap_ari_iqr"] = round(
        float(np.percentile(aris, 75) - np.percentile(aris, 25)), 4
    )

    for col in [
        "mean_recency_days",
        "median_recency_days",
        "mean_frequency",
        "median_frequency",
        "mean_monetary",
        "median_monetary",
        "mean_tenure_days",
        "mean_avg_basket",
    ]:
        prof[col] = prof[col].round(2)
    prof["ave_pp"] = prof["ave_pp"].round(4)

    if k == 5:
        prof["proposed_segment"] = assign_proposed_names_k5(prof)
    elif k == 4:
        prof["proposed_segment"] = assign_proposed_names_k4(prof)
    else:
        prof["proposed_segment"] = [f"Cluster_{c}" for c in prof["cluster_id"]]

    return prof.sort_values("mean_monetary", ascending=False).reset_index(drop=True)


def plot_selection_curves(km_df: pd.DataFrame, gmm_df: pd.DataFrame) -> None:
    """Save K-Means validity curves and GMM BIC/AIC curves to reports/figures/."""
    config.FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    # 1. K-Means metrics across K = 2..8
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.8))
    axes[0].plot(km_df["k"], km_df["silhouette"], marker="o", color="#4C72B0")
    axes[0].set_title("K-Means Silhouette (higher is better)")
    axes[0].set_xlabel("Number of clusters K")
    axes[0].set_ylabel("Silhouette score")
    axes[0].grid(alpha=0.3)

    axes[1].plot(km_df["k"], km_df["davies_bouldin"], marker="o", color="#DD8452")
    axes[1].set_title("Davies-Bouldin (lower is better)")
    axes[1].set_xlabel("Number of clusters K")
    axes[1].set_ylabel("Davies-Bouldin index")
    axes[1].grid(alpha=0.3)

    axes[2].plot(km_df["k"], km_df["calinski_harabasz"], marker="o", color="#55A868")
    axes[2].set_title("Calinski-Harabasz (higher is better)")
    axes[2].set_xlabel("Number of clusters K")
    axes[2].set_ylabel("Calinski-Harabasz index")
    axes[2].grid(alpha=0.3)

    fig.tight_layout()
    fig.savefig(config.FIGURES_DIR / "kmeans_selection.png", dpi=150)
    plt.close(fig)

    # 2. GMM BIC & AIC curves across K = 2..8
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
    for cov_type in ["spherical", "tied"]:
        sub = gmm_df[gmm_df["covariance_type"] == cov_type]
        axes[0].plot(sub["k"], sub["bic"], marker="o", label=f"{cov_type} (BIC)")
        axes[0].plot(sub["k"], sub["aic"], marker="s", linestyle="--", label=f"{cov_type} (AIC)")
    axes[0].set_title("Non-degenerate GMMs: spherical & tied")
    axes[0].set_xlabel("Number of components K")
    axes[0].set_ylabel("Information Criterion (lower is better)")
    axes[0].legend(fontsize=8)
    axes[0].grid(alpha=0.3)

    for cov_type in config.GMM_COVARIANCE_TYPES:
        sub = gmm_df[gmm_df["covariance_type"] == cov_type]
        axes[1].plot(sub["k"], sub["bic"], marker="o", label=cov_type)
    axes[1].set_title("All 4 covariance types (diag/full collapse on integer freq)")
    axes[1].set_xlabel("Number of components K")
    axes[1].set_ylabel("BIC")
    axes[1].legend(fontsize=8)
    axes[1].grid(alpha=0.3)

    fig.tight_layout()
    fig.savefig(config.FIGURES_DIR / "gmm_bic_aic.png", dpi=150)
    plt.close(fig)


def plot_proposed_profiles(prof_k5: pd.DataFrame) -> None:
    """Bar chart of original-unit median RFM profiles for the proposed K=5 spherical GMM."""
    config.FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 3, figsize=(12, 4))
    segs = prof_k5["proposed_segment"]

    axes[0].barh(segs, prof_k5["mean_recency_days"], color="#4C72B0")
    axes[0].invert_yaxis()
    axes[0].set_title("Mean recency (days)")
    axes[0].set_xlabel("Days since last purchase")

    axes[1].barh(segs, prof_k5["mean_frequency"], color="#55A868")
    axes[1].invert_yaxis()
    axes[1].set_title("Mean frequency (invoices)")
    axes[1].set_xlabel("Invoices in 9m window")

    axes[2].barh(segs, prof_k5["mean_monetary"], color="#DD8452")
    axes[2].invert_yaxis()
    axes[2].set_title("Mean monetary (£)")
    axes[2].set_xlabel("Spend in 9m window (£)")

    fig.suptitle("Proposed S3 segments (GMM spherical, K=5) in original units", fontsize=11)
    fig.tight_layout()
    fig.savefig(config.FIGURES_DIR / "segment_profiles_s3.png", dpi=150)
    plt.close(fig)


def run() -> None:
    config.TABLES_DIR.mkdir(parents=True, exist_ok=True)
    config.FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    con = db.connect_app(config.DB_PATH)
    s3_df = load_s3_features(con)
    con.close()

    x_scaled, caps_df = preprocess_s3_rfm(s3_df)
    caps_df.to_csv(config.TABLES_DIR / "s3_preprocessing.csv", index=False)

    km_df = run_kmeans_grid(x_scaled)
    km_df.to_csv(config.TABLES_DIR / "kmeans_grid.csv", index=False)

    gmm_df = run_gmm_grid(x_scaled)
    gmm_df.to_csv(config.TABLES_DIR / "gmm_grid.csv", index=False)

    diag_df = check_diag_frequency_collapse(s3_df, x_scaled)
    diag_df.to_csv(config.TABLES_DIR / "gmm_diag_degeneracy.csv", index=False)

    prof_k5 = build_candidate_profile(s3_df, x_scaled, "spherical", 5)
    prof_k5.to_csv(config.TABLES_DIR / "segment_profiles_spherical_k5.csv", index=False)

    prof_k4 = build_candidate_profile(s3_df, x_scaled, "spherical", 4)
    prof_k4.to_csv(config.TABLES_DIR / "segment_profiles_spherical_k4.csv", index=False)

    prof_tied_k4 = build_candidate_profile(s3_df, x_scaled, "tied", 4)
    prof_tied_k4.to_csv(config.TABLES_DIR / "segment_profiles_tied_k4.csv", index=False)

    plot_selection_curves(km_df, gmm_df)
    plot_proposed_profiles(prof_k5)

    print("=== S3 Preprocessing Caps ===")
    print(caps_df.to_string(index=False))
    print("\n=== K-Means Grid (K=2..8) ===")
    print(km_df.to_string(index=False))
    print("\n=== Proposed Primary Candidate: GMM (spherical, K=5) ===")
    print(prof_k5.to_string(index=False))
    print("\n=== Alternative Candidate: GMM (spherical, K=4) ===")
    print(prof_k4.to_string(index=False))


if __name__ == "__main__":
    run()
