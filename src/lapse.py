"""Phase 5: 90-day customer lapse model, S1 cross-validation, S2 evaluation and S3 scoring.

Follows CLAUDE.md section 7.7:
1. Target: lapse (no purchase in 90 days) = 1 - purchased_next_90d. Never called "churn".
2. Primary model (chosen in advance): LogisticRegression on log1p + StandardScaler
   features, calibrated with CalibratedClassifierCV(method='sigmoid', cv=5) on S1.
3. Comparisons on S1 (5-fold CV) and S2 (held-out temporal test set, used once):
   - Two-bin rule baseline: S1 empirical lapse rate for recency_days > 90 vs <= 90.
   - Calibrated depth-4 decision tree (CalibratedClassifierCV(method='sigmoid', cv=5)).
4. S2 metrics: Brier score, ROC-AUC, log loss, 10-bin ECE, and reliability diagram.
5. Score S3 into the tuple-independent probabilistic table `lapse_risk` with
   `model_version` set to the current git short hash.
"""

import subprocess

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, StandardScaler
from sklearn.tree import DecisionTreeClassifier

from src import config, db

FEATURE_COLS = [
    "recency_days",
    "frequency",
    "monetary",
    "tenure_days",
    "avg_basket",
]


def get_model_version() -> str:
    """Return the git short hash so every row in lapse_risk is traceable to code."""
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=config.PROJECT_ROOT,
            text=True,
        ).strip()
        if out:
            return out
    except Exception:
        pass
    return "2026-10-31"


def load_snapshot_dataset(con, snapshot_name: str) -> pd.DataFrame:
    """Load features (and outcome if S1/S2) for a snapshot, ordered by customer_id."""
    return con.execute(
        """
        SELECT
            cf.customer_id,
            cf.snapshot,
            cf.recency_days,
            cf.frequency,
            cf.monetary,
            cf.tenure_days,
            cf.avg_basket,
            CASE
                WHEN o.purchased_next_90d IS NULL THEN NULL
                ELSE 1 - o.purchased_next_90d
            END AS lapsed_next_90d
        FROM customer_features AS cf
        LEFT JOIN outcomes AS o
          ON o.customer_id = cf.customer_id
         AND o.snapshot = cf.snapshot
        WHERE cf.snapshot = ?
        ORDER BY cf.customer_id
        """,
        [snapshot_name],
    ).df()


class TwoBinRecencyBaseline:
    """Two-bin rule baseline: S1 lapse rate for recency_days > 90 vs <= 90."""

    def __init__(self, split_days: int = config.BASELINE_RECENCY_DAYS) -> None:
        self.split_days = split_days
        self.rate_low_: float = 0.0
        self.rate_high_: float = 0.0

    def fit(self, x_df: pd.DataFrame, y: np.ndarray) -> "TwoBinRecencyBaseline":
        mask_high = x_df["recency_days"].to_numpy() > self.split_days
        self.rate_high_ = float(np.mean(y[mask_high]))
        self.rate_low_ = float(np.mean(y[~mask_high]))
        return self

    def predict_proba(self, x_df: pd.DataFrame) -> np.ndarray:
        mask_high = x_df["recency_days"].to_numpy() > self.split_days
        p1 = np.where(mask_high, self.rate_high_, self.rate_low_)
        return np.column_stack([1.0 - p1, p1])


def make_primary_logistic_model() -> CalibratedClassifierCV:
    """Primary model: log1p -> StandardScaler -> LogisticRegression + sigmoid calibration."""
    base_pipe = Pipeline([
        ("log1p", FunctionTransformer(np.log1p, validate=False)),
        ("scaler", StandardScaler()),
        ("logreg", LogisticRegression(random_state=config.RANDOM_STATE, max_iter=1000)),
    ])
    return CalibratedClassifierCV(
        estimator=base_pipe,
        method="sigmoid",
        cv=config.CALIBRATION_CV,
    )


def make_calibrated_tree_model() -> CalibratedClassifierCV:
    """Comparison model: depth-4 DecisionTreeClassifier + sigmoid calibration."""
    base_tree = DecisionTreeClassifier(
        max_depth=config.TREE_MAX_DEPTH,
        random_state=config.RANDOM_STATE,
    )
    return CalibratedClassifierCV(
        estimator=base_tree,
        method="sigmoid",
        cv=config.CALIBRATION_CV,
    )


def expected_calibration_error(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    n_bins: int = config.ECE_BINS,
) -> tuple[float, pd.DataFrame]:
    """Compute 10-bin Expected Calibration Error (ECE) and per-bin reliability table.

    ECE = sum_{b=1..B} (n_b / N) * |observed_lapse_rate_b - mean_predicted_p_b|.
    """
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    # Assign each prediction to bin 0..n_bins-1 (rightmost edge included in last bin)
    bin_ids = np.clip(np.digitize(y_prob, edges, right=False) - 1, 0, n_bins - 1)
    n_total = len(y_true)
    ece = 0.0
    rows = []

    for b in range(n_bins):
        mask = bin_ids == b
        n_b = int(np.sum(mask))
        if n_b > 0:
            mean_p = float(np.mean(y_prob[mask]))
            obs_rate = float(np.mean(y_true[mask]))
            abs_gap = abs(obs_rate - mean_p)
            ece += (n_b / n_total) * abs_gap
        else:
            mean_p = np.nan
            obs_rate = np.nan
            abs_gap = np.nan
        rows.append({
            "bin_index": b + 1,
            "bin_lower": round(float(edges[b]), 2),
            "bin_upper": round(float(edges[b + 1]), 2),
            "n_customers": n_b,
            "mean_predicted_p": round(mean_p, 4) if not np.isnan(mean_p) else np.nan,
            "observed_lapse_rate": round(obs_rate, 4) if not np.isnan(obs_rate) else np.nan,
            "abs_calibration_gap": round(abs_gap, 4) if not np.isnan(abs_gap) else np.nan,
        })

    return float(ece), pd.DataFrame(rows)


def compute_metrics_row(model_name: str, split_name: str, y_true: np.ndarray, y_prob: np.ndarray) -> dict:
    """Compute Brier score, Brier skill score (vs base-rate climatology), ROC-AUC, log loss and 10-bin ECE."""
    ece, _ = expected_calibration_error(y_true, y_prob, config.ECE_BINS)
    brier = float(brier_score_loss(y_true, y_prob))
    base_rate = float(np.mean(y_true))
    # Climatology reference Brier score: predicting the constant split base rate for every customer
    brier_ref = base_rate * (1.0 - base_rate)
    brier_skill = 1.0 - (brier / brier_ref) if brier_ref > 0 else 0.0
    return {
        "split": split_name,
        "model": model_name,
        "n_customers": len(y_true),
        "base_lapse_rate": round(base_rate, 4),
        "mean_predicted_p": round(float(np.mean(y_prob)), 4),
        "brier_score": round(brier, 4),
        "brier_skill_score": round(brier_skill, 4),
        "roc_auc": round(float(roc_auc_score(y_true, y_prob)), 4),
        "log_loss": round(float(log_loss(y_true, y_prob)), 4),
        "ece_10_bins": round(ece, 4),
    }


def evaluate_s1_cross_validation(x_s1: pd.DataFrame, y_s1: np.ndarray) -> pd.DataFrame:
    """5-fold out-of-fold cross-validation on S1 only (for model selection)."""
    skf = StratifiedKFold(
        n_splits=config.CALIBRATION_CV,
        shuffle=True,
        random_state=config.RANDOM_STATE,
    )
    oof_preds = {
        "logistic_calibrated": np.zeros(len(y_s1)),
        "tree_depth4_calibrated": np.zeros(len(y_s1)),
        "two_bin_recency_90d": np.zeros(len(y_s1)),
    }

    for train_idx, val_idx in skf.split(x_s1, y_s1):
        x_tr, y_tr = x_s1.iloc[train_idx], y_s1[train_idx]
        x_va = x_s1.iloc[val_idx]

        m_log = make_primary_logistic_model().fit(x_tr, y_tr)
        oof_preds["logistic_calibrated"][val_idx] = m_log.predict_proba(x_va)[:, 1]

        m_tree = make_calibrated_tree_model().fit(x_tr, y_tr)
        oof_preds["tree_depth4_calibrated"][val_idx] = m_tree.predict_proba(x_va)[:, 1]

        m_base = TwoBinRecencyBaseline().fit(x_tr, y_tr)
        oof_preds["two_bin_recency_90d"][val_idx] = m_base.predict_proba(x_va)[:, 1]

    rows = [
        compute_metrics_row(name, "S1_5fold_oof", y_s1, preds)
        for name, preds in oof_preds.items()
    ]
    return pd.DataFrame(rows)


def plot_s2_reliability_diagram(
    s2_eval_df: pd.DataFrame,
    bins_by_model: dict[str, pd.DataFrame],
) -> None:
    """Plot the S2 reliability diagram comparing the primary model and baselines."""
    config.FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.4))

    # Left panel: calibration curve (observed vs predicted)
    axes[0].plot([0, 1], [0, 1], linestyle="--", color="gray", label="Perfect calibration")
    styles = [
        ("logistic_calibrated", "Calibrated Logistic (primary)", "#4C72B0", "o"),
        ("tree_depth4_calibrated", "Calibrated Depth-4 Tree", "#55A868", "s"),
        ("two_bin_recency_90d", "Two-bin Rule (recency > 90d)", "#C44E52", "^"),
    ]
    for key, label, color, marker in styles:
        bdf = bins_by_model[key].dropna(subset=["mean_predicted_p", "observed_lapse_rate"])
        axes[0].plot(
            bdf["mean_predicted_p"],
            bdf["observed_lapse_rate"],
            marker=marker,
            color=color,
            label=label,
        )
    axes[0].set_title("S2 Reliability diagram (90-day lapse)")
    axes[0].set_xlabel("Mean predicted P(lapse in 90d) in bin")
    axes[0].set_ylabel("Observed 90-day lapse rate in S2")
    axes[0].set_xlim(0, 1)
    axes[0].set_ylim(0, 1)
    axes[0].legend(fontsize=8.5)
    axes[0].grid(alpha=0.3)

    # Right panel: histogram of S2 predicted probabilities for the primary model
    prim_bins = bins_by_model["logistic_calibrated"]
    centers = 0.5 * (prim_bins["bin_lower"] + prim_bins["bin_upper"])
    axes[1].bar(centers, prim_bins["n_customers"], width=0.085, color="#4C72B0", edgecolor="white")
    axes[1].set_title("S2 customer counts per probability bin (primary model)")
    axes[1].set_xlabel("Predicted P(lapse in 90d) bin")
    axes[1].set_ylabel("Number of S2 customers")
    axes[1].set_xlim(0, 1)
    axes[1].grid(alpha=0.3)

    fig.tight_layout()
    fig.savefig(config.FIGURES_DIR / "lapse_reliability_s2.png", dpi=150)
    plt.close(fig)


def run() -> None:
    con = db.connect_pipeline()
    s1_df = load_snapshot_dataset(con, "S1")
    s2_df = load_snapshot_dataset(con, "S2")
    s3_df = load_snapshot_dataset(con, "S3")

    x_s1 = s1_df[FEATURE_COLS]
    y_s1 = s1_df["lapsed_next_90d"].to_numpy(dtype=int)

    x_s2 = s2_df[FEATURE_COLS]
    y_s2 = s2_df["lapsed_next_90d"].to_numpy(dtype=int)

    x_s3 = s3_df[FEATURE_COLS]

    # 1. Cross-validation on S1 only
    s1_cv_df = evaluate_s1_cross_validation(x_s1, y_s1)

    # 2. Fit models on full S1 and evaluate once on S2
    primary_model = make_primary_logistic_model().fit(x_s1, y_s1)
    tree_model = make_calibrated_tree_model().fit(x_s1, y_s1)
    baseline_model = TwoBinRecencyBaseline().fit(x_s1, y_s1)

    s2_Rows = []
    bins_by_model = {}
    all_bin_frames = []
    for name, model in [
        ("logistic_calibrated", primary_model),
        ("tree_depth4_calibrated", tree_model),
        ("two_bin_recency_90d", baseline_model),
    ]:
        p_s2 = model.predict_proba(x_s2)[:, 1]
        s2_Rows.append(compute_metrics_row(name, "S2_heldout_test", y_s2, p_s2))
        _, bdf = expected_calibration_error(y_s2, p_s2, config.ECE_BINS)
        bdf.insert(0, "model", name)
        bins_by_model[name] = bdf
        all_bin_frames.append(bdf)

    s2_eval_df = pd.DataFrame(s2_Rows)
    all_bins_df = pd.concat(all_bin_frames, ignore_index=True)

    # Record the two-bin baseline rates learned on S1
    baseline_rates_df = pd.DataFrame([{
        "split_recency_days": config.BASELINE_RECENCY_DAYS,
        "s1_lapse_rate_recency_le_90": round(baseline_model.rate_low_, 4),
        "s1_lapse_rate_recency_gt_90": round(baseline_model.rate_high_, 4),
    }])

    # 3. Score S3 into the tuple-independent `lapse_risk` table
    p_s3 = primary_model.predict_proba(x_s3)[:, 1]
    model_version = get_model_version()

    con.execute("DROP TABLE IF EXISTS lapse_risk")
    con.execute("""
        CREATE TABLE lapse_risk (
            customer_id   BIGINT,
            snapshot      VARCHAR,
            p_lapse_90d   DOUBLE,
            model_version VARCHAR,
            PRIMARY KEY (customer_id, snapshot)
        )
    """)
    s3_lapse_df = pd.DataFrame({
        "customer_id": s3_df["customer_id"].to_numpy(),
        "snapshot": "S3",
        "p_lapse_90d": p_s3,
        "model_version": model_version,
    })
    con.execute("INSERT INTO lapse_risk SELECT * FROM s3_lapse_df")

    # Summary of S3 predicted lapse risk per segment (under default bootstrap top segment)
    s3_seg_lapse = con.execute("""
        WITH top_seg AS (
            SELECT customer_id, ARG_MAX(segment, p) AS segment
            FROM segment_membership
            WHERE snapshot = 'S3' AND method = 'bootstrap'
            GROUP BY customer_id
        )
        SELECT
            ts.segment,
            COUNT(*) AS n_customers,
            ROUND(AVG(lr.p_lapse_90d), 4) AS mean_p_lapse_90d,
            ROUND(MEDIAN(lr.p_lapse_90d), 4) AS median_p_lapse_90d,
            COUNT(*) FILTER (WHERE lr.p_lapse_90d >= 0.66) AS n_probably_lapsing_ge_0_66
        FROM lapse_risk AS lr
        JOIN top_seg AS ts ON ts.customer_id = lr.customer_id
        WHERE lr.snapshot = 'S3'
        GROUP BY ts.segment
        ORDER BY mean_p_lapse_90d DESC
    """).df()
    con.close()

    config.TABLES_DIR.mkdir(parents=True, exist_ok=True)
    s1_cv_df.to_csv(config.TABLES_DIR / "lapse_s1_cv.csv", index=False)
    s2_eval_df.to_csv(config.TABLES_DIR / "lapse_s2_eval.csv", index=False)
    all_bins_df.to_csv(config.TABLES_DIR / "lapse_reliability_bins_s2.csv", index=False)
    baseline_rates_df.to_csv(config.TABLES_DIR / "lapse_baseline_s1_rates.csv", index=False)
    s3_seg_lapse.to_csv(config.TABLES_DIR / "lapse_s3_by_segment.csv", index=False)

    plot_s2_reliability_diagram(s2_eval_df, bins_by_model)

    print("=== S1 5-Fold Out-of-Fold Cross-Validation ===")
    print(s1_cv_df.to_string(index=False))
    print("\n=== S2 Held-Out Test Evaluation (Used Once) ===")
    print(s2_eval_df.to_string(index=False))
    print("\n=== S3 Lapse Risk by Segment ===")
    print(s3_seg_lapse.to_string(index=False))


if __name__ == "__main__":
    run()
