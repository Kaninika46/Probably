"""Phase 4, part 1: probabilistic segment memberships, stability and gate report.

Follows CLAUDE.md section 7.5:
1. Fit the confirmed GMM (spherical, K=5, n_init=10, random_state=42) on S3.
2. Compute method='gmm' membership probabilities via predict_proba.
3. Run B=100 bootstrap resamples of S3 customers (with replacement), refit the
   GMM on each resample, predict labels for all customers, and align labels to
   the reference fit using scipy.optimize.linear_sum_assignment.
4. Store both probability distributions in the BID table `segment_membership`
   (block key = (customer_id, snapshot, method); sum of p = 1 per block).
5. Export bootstrap ARI and Hennig per-segment Jaccard stability tables.
6. Export the go/no-go gate report (reports/tables/gate.csv + gate_ave_pp.csv)
   and max-p histogram (reports/figures/gate_max_p_hist.png).
"""

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment
from sklearn.metrics import adjusted_rand_score
from sklearn.metrics.cluster import contingency_matrix
from sklearn.mixture import GaussianMixture

from src import config, db, segment


def build_cluster_to_segment_map(s3_df: pd.DataFrame, labels: np.ndarray) -> dict[int, str]:
    """Map integer cluster IDs (0..K-1) to the confirmed segment names from original-unit centroids."""
    tmp = s3_df.copy()
    tmp["cluster_id"] = labels
    prof = tmp.groupby("cluster_id", as_index=False).agg(
        mean_recency_days=("recency_days", "mean"),
        mean_frequency=("frequency", "mean"),
        mean_monetary=("monetary", "mean"),
    )
    if config.CHOSEN_K == 5:
        names = segment.assign_proposed_names_k5(prof)
    else:
        names = segment.assign_proposed_names_k4(prof)
    return dict(zip(prof["cluster_id"].astype(int), names))


def normalised_entropy(prob_matrix: np.ndarray) -> np.ndarray:
    """Compute normalised Shannon entropy -sum(p * ln(p)) / ln(K) for each customer row.

    Zero probabilities contribute 0 to the sum (since lim_{p->0+} p ln(p) = 0).
    Returns values in [0, 1], where 0 means complete certainty (one p = 1) and
    1 means uniform uncertainty across all K segments (every p = 1/K).
    """
    k = prob_matrix.shape[1]
    with np.errstate(divide="ignore", invalid="ignore"):
        log_p = np.where(prob_matrix > 0, np.log(prob_matrix), 0.0)
    raw_entropy = -np.sum(prob_matrix * log_p, axis=1)
    return raw_entropy / np.log(k)


def stability_band(jaccard_value: float) -> str:
    """Hennig (2007) cluster stability bands from CLAUDE.md section 7.5."""
    if jaccard_value >= config.JACCARD_STABLE:
        return "stable (>= 0.75)"
    if jaccard_value >= config.JACCARD_DOUBTFUL:
        return "doubtful (0.60-0.75)"
    return "unstable (< 0.60)"


def compute_memberships_and_stability(
    s3_df: pd.DataFrame,
    x_scaled: np.ndarray,
) -> tuple[list[str], np.ndarray, np.ndarray, pd.DataFrame, pd.DataFrame]:
    """Return (segment_names, gmm_probs, boot_probs, ari_df, jaccard_df)."""
    k = config.CHOSEN_K
    cov_type = config.CHOSEN_GMM_COV

    ref_gmm = GaussianMixture(
        n_components=k,
        covariance_type=cov_type,
        n_init=config.GMM_N_INIT,
        random_state=config.RANDOM_STATE,
    ).fit(x_scaled)
    ref_labels = ref_gmm.predict(x_scaled)
    ref_probs_raw = ref_gmm.predict_proba(x_scaled)

    cluster_to_seg = build_cluster_to_segment_map(s3_df, ref_labels)
    # Order segments consistently by descending mean spend
    seg_order = ["Champions", "Loyal", "At-Risk", "New", "Hibernating"][:k]
    seg_to_col = {seg_name: idx for idx, seg_name in enumerate(seg_order)}

    # Reorder columns of ref_probs_raw to match seg_order
    gmm_probs = np.zeros_like(ref_probs_raw)
    ref_seg_idx = np.zeros_like(ref_labels)
    for cid, seg_name in cluster_to_seg.items():
        col_idx = seg_to_col[seg_name]
        gmm_probs[:, col_idx] = ref_probs_raw[:, cid]
        ref_seg_idx[ref_labels == cid] = col_idx

    # Bootstrap co-assignment (B = 100 resamples with replacement)
    rng = np.random.default_rng(config.RANDOM_STATE)
    n = len(x_scaled)
    vote_counts = np.zeros((n, k), dtype=np.int64)
    aris = []
    jaccards = np.zeros((config.BOOTSTRAP_B, k))

    for b in range(config.BOOTSTRAP_B):
        sample_idx = rng.integers(0, n, size=n)
        boot_gmm = GaussianMixture(
            n_components=k,
            covariance_type=cov_type,
            n_init=config.GMM_N_INIT,
            random_state=config.RANDOM_STATE + b + 1,
        ).fit(x_scaled[sample_idx])
        boot_labels = boot_gmm.predict(x_scaled)

        # Align bootstrap cluster IDs to reference segment indices (0..K-1)
        cm = contingency_matrix(ref_seg_idx, boot_labels)
        r_ind, c_ind = linear_sum_assignment(-cm)
        remap = {boot_c: ref_r for ref_r, boot_c in zip(r_ind, c_ind)}
        aligned = np.array([remap[val] for val in boot_labels])

        vote_counts[np.arange(n), aligned] += 1
        aris.append(adjusted_rand_score(ref_seg_idx, aligned))

        for s_idx in range(k):
            inter = np.sum((ref_seg_idx == s_idx) & (aligned == s_idx))
            union = np.sum((ref_seg_idx == s_idx) | (aligned == s_idx))
            jaccards[b, s_idx] = inter / union if union > 0 else 0.0

    boot_probs = vote_counts / float(config.BOOTSTRAP_B)

    q25, q50, q75 = np.percentile(aris, [25, 50, 75])
    ari_df = pd.DataFrame([{
        "covariance_type": cov_type,
        "k": k,
        "bootstrap_b": config.BOOTSTRAP_B,
        "ari_median": round(float(q50), 4),
        "ari_iqr": round(float(q75 - q25), 4),
        "ari_q25": round(float(q25), 4),
        "ari_q75": round(float(q75), 4),
        "ari_mean": round(float(np.mean(aris)), 4),
        "ari_min": round(float(np.min(aris)), 4),
        "ari_max": round(float(np.max(aris)), 4),
    }])

    jaccard_rows = []
    for s_idx, seg_name in enumerate(seg_order):
        vals = jaccards[:, s_idx]
        jq25, jq50, jq75 = np.percentile(vals, [25, 50, 75])
        mean_j = float(np.mean(vals))
        jaccard_rows.append({
            "segment": seg_name,
            "n_reference_customers": int(np.sum(ref_seg_idx == s_idx)),
            "jaccard_mean": round(mean_j, 4),
            "jaccard_median": round(float(jq50), 4),
            "jaccard_iqr": round(float(jq75 - jq25), 4),
            "stability_band": stability_band(mean_j),
        })
    jaccard_df = pd.DataFrame(jaccard_rows)

    return seg_order, gmm_probs, boot_probs, ari_df, jaccard_df


def write_probabilistic_tables(
    con,
    s3_df: pd.DataFrame,
    seg_order: list[str],
    gmm_probs: np.ndarray,
    boot_probs: np.ndarray,
) -> None:
    """Create `segments` and BID `segment_membership` tables in DuckDB."""
    con.execute("DROP TABLE IF EXISTS segment_membership")
    con.execute("DROP TABLE IF EXISTS segments")

    con.execute("""
        CREATE TABLE segments (
            segment     VARCHAR PRIMARY KEY,
            description VARCHAR,
            tree_rule   VARCHAR
        )
    """)
    for seg_name in seg_order:
        con.execute(
            "INSERT INTO segments VALUES (?, ?, ?)",
            [seg_name, config.SEGMENT_DESCRIPTIONS.get(seg_name, ""), ""],
        )

    con.execute("""
        CREATE TABLE segment_membership (
            customer_id BIGINT,
            snapshot    VARCHAR,
            method      VARCHAR,
            segment     VARCHAR,
            p           DOUBLE,
            PRIMARY KEY (customer_id, snapshot, method, segment)
        )
    """)

    frames = []
    customer_ids = s3_df["customer_id"].to_numpy()
    for method_name, prob_mat in [("gmm", gmm_probs), ("bootstrap", boot_probs)]:
        for col_idx, seg_name in enumerate(seg_order):
            frames.append(pd.DataFrame({
                "customer_id": customer_ids,
                "snapshot": "S3",
                "method": method_name,
                "segment": seg_name,
                "p": prob_mat[:, col_idx],
            }))
    all_rows = pd.concat(frames, ignore_index=True)
    con.execute("INSERT INTO segment_membership SELECT * FROM all_rows")


def save_gate_report_and_histogram(
    seg_order: list[str],
    gmm_probs: np.ndarray,
    boot_probs: np.ndarray,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Compute gate metrics (boundary share, normalised entropy, AvePP) and draw histogram."""
    gate_rows = []
    ave_pp_rows = []

    for method_name, prob_mat in [("gmm", gmm_probs), ("bootstrap", boot_probs)]:
        max_p = prob_mat.max(axis=1)
        top_seg_idx = prob_mat.argmax(axis=1)
        norm_ent = normalised_entropy(prob_mat)
        n_cust = len(max_p)
        n_bound = int(np.sum(max_p < config.BOUNDARY_P))

        row = {
            "method": method_name,
            "n_customers": n_cust,
            "n_boundary_max_p_lt_0_6": n_bound,
            "boundary_share_pct": round(100.0 * n_bound / n_cust, 2),
            "mean_max_p": round(float(np.mean(max_p)), 4),
            "median_max_p": round(float(np.median(max_p)), 4),
            "mean_normalised_entropy": round(float(np.mean(norm_ent)), 4),
            "median_normalised_entropy": round(float(np.median(norm_ent)), 4),
        }

        for s_idx, seg_name in enumerate(seg_order):
            mask = top_seg_idx == s_idx
            ave_pp = float(np.mean(max_p[mask])) if np.any(mask) else 0.0
            row[f"ave_pp_{seg_name}"] = round(ave_pp, 4)
            ave_pp_rows.append({
                "method": method_name,
                "segment": seg_name,
                "n_assigned_most_probable": int(np.sum(mask)),
                "expected_size_sum_p": round(float(np.sum(prob_mat[:, s_idx])), 2),
                "ave_pp": round(ave_pp, 4),
            })

        gate_rows.append(row)

    gate_df = pd.DataFrame(gate_rows)
    ave_pp_df = pd.DataFrame(ave_pp_rows)

    config.TABLES_DIR.mkdir(parents=True, exist_ok=True)
    gate_df.to_csv(config.TABLES_DIR / "gate.csv", index=False)
    ave_pp_df.to_csv(config.TABLES_DIR / "gate_ave_pp.csv", index=False)

    # Histogram of max(p) per customer for GMM vs bootstrap
    config.FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2), sharey=True)
    bins = np.linspace(0.2, 1.0, 25)
    for ax, (method_name, prob_mat), color in [
        (axes[0], ("gmm", gmm_probs), "#4C72B0"),
        (axes[1], ("bootstrap", boot_probs), "#55A868"),
    ]:
        max_p = prob_mat.max(axis=1)
        b_share = 100.0 * np.mean(max_p < config.BOUNDARY_P)
        ax.hist(max_p, bins=bins, color=color, edgecolor="white")
        ax.axvline(
            config.BOUNDARY_P,
            color="#C44E52",
            linestyle="--",
            linewidth=1.5,
            label=f"Boundary threshold ({config.BOUNDARY_P:.2f})\n{b_share:.2f}% below",
        )
        ax.set_title(f"method = '{method_name}'")
        ax.set_xlabel("Maximum membership probability max(p)")
        ax.legend(fontsize=8.5)
        ax.grid(alpha=0.3)
    axes[0].set_ylabel("Number of S3 customers")
    fig.suptitle("Go/no-go gate: distribution of max(p) across 3,961 S3 customers", fontsize=11)
    fig.tight_layout()
    fig.savefig(config.FIGURES_DIR / "gate_max_p_hist.png", dpi=150)
    plt.close(fig)

    return gate_df, ave_pp_df


def run() -> None:
    con = db.connect_pipeline()
    s3_df = segment.load_s3_features(con)
    x_scaled, _ = segment.preprocess_s3_rfm(s3_df)

    seg_order, gmm_probs, boot_probs, ari_df, jaccard_df = compute_memberships_and_stability(
        s3_df, x_scaled
    )
    write_probabilistic_tables(con, s3_df, seg_order, gmm_probs, boot_probs)
    con.close()

    config.TABLES_DIR.mkdir(parents=True, exist_ok=True)
    ari_df.to_csv(config.TABLES_DIR / "bootstrap_stability.csv", index=False)
    jaccard_df.to_csv(config.TABLES_DIR / "segment_stability.csv", index=False)
    gate_df, ave_pp_df = save_gate_report_and_histogram(seg_order, gmm_probs, boot_probs)

    print("=== Bootstrap ARI Stability (B=100) ===")
    print(ari_df.to_string(index=False))
    print("\n=== Per-Segment Jaccard Stability (B=100) ===")
    print(jaccard_df.to_string(index=False))
    print("\n=== Gate Report (reports/tables/gate.csv) ===")
    print(gate_df.to_string(index=False))
    print("\n=== Per-Segment AvePP & Expected Sizes ===")
    print(ave_pp_df.to_string(index=False))


if __name__ == "__main__":
    run()
