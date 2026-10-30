"""Phase 9: Generate Markdown results tables for README.md from reports/tables/*.csv.

Why this module exists:
- Rule 1 of CLAUDE.md requires that every number in the README, report, slides
  or explainers come from a file in `reports/tables/` or `eval_results` produced
  by code run on the real dataset.
- Instead of copying numbers by hand into `README.md`, this module reads the CSV
  outputs in `reports/tables/`, formats them as GitHub-Flavored Markdown tables,
  writes `reports/tables/readme_results.md`, and updates the auto-generated
  section of `README.md` between HTML comment markers.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src import config

BEGIN_MARKER = "<!-- BEGIN AUTO-GENERATED RESULTS -->"
END_MARKER = "<!-- END AUTO-GENERATED RESULTS -->"
README_PATH = config.PROJECT_ROOT / "README.md"
README_RESULTS_MD_PATH = config.TABLES_DIR / "readme_results.md"


def build_cleaning_table_md() -> str:
    """Format `reports/tables/cleaning_funnel.csv` as a Markdown table."""
    df = pd.read_csv(config.TABLES_DIR / "cleaning_funnel.csv")
    lines = [
        "### 1. Data Cleaning Funnel (`reports/tables/cleaning_funnel.csv`)",
        "",
        "| Step | Rule | Rows Before | Rows After | Rows Removed | Revenue Affected (GBP) | % of Pre-Step Revenue | % of Raw Revenue |",
        "|---:|---|---:|---:|---:|---:|---:|---:|",
    ]
    for _, row in df.iterrows():
        lines.append(
            f"| {int(row['step_no'])} | {row['rule']} | {int(row['rows_before']):,} | "
            f"{int(row['rows_after']):,} | {int(row['rows_removed']):,} | "
            f"{float(row['revenue_affected']):,.2f} | "
            f"{float(row['share_of_revenue_before_step_pct']):.2f}% | "
            f"{float(row['share_of_raw_revenue_pct']):.2f}% |"
        )
    return "\n".join(lines)


def build_snapshot_table_md() -> str:
    """Format `reports/tables/snapshot_summary.csv` as a Markdown table."""
    df = pd.read_csv(config.TABLES_DIR / "snapshot_summary.csv")
    lines = [
        "### 2. Temporal Snapshots & Base Lapse Rates (`reports/tables/snapshot_summary.csv`)",
        "",
        "| Snapshot | Snapshot Date | Feature Window | Customers | Mean Recency (d) | Mean Frequency | Mean Monetary (GBP) | 90-Day Lapse Rate |",
        "|---|---|---|---:|---:|---:|---:|---:|",
    ]
    for _, row in df.iterrows():
        lapse_str = (
            f"{float(row['lapse_rate_pct']):.2f}%"
            if pd.notna(row["lapse_rate_pct"])
            else "N/A (future window)"
        )
        lines.append(
            f"| {row['snapshot']} | `{row['snapshot_date']}` | "
            f"`{row['feature_start']}` to `{row['feature_end']}` | "
            f"{int(row['n_customers']):,} | {float(row['mean_recency_days']):.2f} | "
            f"{float(row['mean_frequency']):.2f} | {float(row['mean_monetary']):,.2f} | "
            f"{lapse_str} |"
        )
    return "\n".join(lines)


def build_segment_table_md() -> str:
    """Format `reports/tables/segment_profiles_spherical_k5.csv` and `tree_fidelity.csv`."""
    df = pd.read_csv(config.TABLES_DIR / "segment_profiles_spherical_k5.csv")
    tree_df = pd.read_csv(config.TABLES_DIR / "tree_fidelity.csv")
    t_row = tree_df.iloc[0]

    lines = [
        "### 3. S3 Segment Profiles & Bootstrap Stability (`reports/tables/segment_profiles_spherical_k5.csv`)",
        "",
        "| Segment | GMM Hard Count | Share (%) | Mean Recency (d) | Mean Frequency | Mean Monetary (GBP) | Mean AvePP | Mean Jaccard |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for _, row in df.iterrows():
        lines.append(
            f"| **{row['proposed_segment']}** | {int(row['n_customers']):,} | "
            f"{float(row['share_of_customers_pct']):.2f}% | "
            f"{float(row['mean_recency_days']):.2f} | {float(row['mean_frequency']):.2f} | "
            f"{float(row['mean_monetary']):,.2f} | {float(row['ave_pp']):.4f} | "
            f"{float(row['jaccard_mean']):.4f} |"
        )
    ari_med = float(df["bootstrap_ari_median"].iloc[0])
    ari_iqr = float(df["bootstrap_ari_iqr"].iloc[0])
    lines.extend(
        [
            "",
            f"- **Bootstrap Adjusted Rand Index (B = 100):** median `{ari_med:.4f}` (IQR `{ari_iqr:.4f}`).",
            f"- **Decision-tree surrogate (`reports/tables/tree_fidelity.csv`):** depth `{int(t_row['actual_depth'])}` with `{int(t_row['n_leaves'])}` leaves; train fidelity `{float(t_row['train_fidelity_pct']):.2f}%` (`n = {int(t_row['n_train']):,}`), held-out 30% test fidelity `{float(t_row['test_fidelity_pct']):.2f}%` (`n = {int(t_row['n_test']):,}`).",
        ]
    )
    return "\n".join(lines)


def build_gate_table_md() -> str:
    """Format `reports/tables/gate.csv` as a Markdown table."""
    df = pd.read_csv(config.TABLES_DIR / "gate.csv")
    lines = [
        "### 4. Membership Probability Gate (`reports/tables/gate.csv`)",
        "",
        "| Method | Customers | Boundary Customers (`max p < 0.60`) | Boundary Share (%) | Mean `max p` | Median `max p` | Mean Normalised Entropy |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for _, row in df.iterrows():
        lines.append(
            f"| `{row['method']}` | {int(row['n_customers']):,} | "
            f"{int(row['n_boundary_max_p_lt_0_6']):,} | "
            f"{float(row['boundary_share_pct']):.2f}% | "
            f"{float(row['mean_max_p']):.4f} | {float(row['median_max_p']):.4f} | "
            f"{float(row['mean_normalised_entropy']):.4f} |"
        )
    return "\n".join(lines)


def build_prob_vs_hard_table_md() -> str:
    """Format `reports/tables/kmeans_vs_expected_sizes.csv` as a Markdown table."""
    df = pd.read_csv(config.TABLES_DIR / "kmeans_vs_expected_sizes.csv")
    lines = [
        "### 5. Hard Counts vs Probabilistic Expected Segment Sizes (`reports/tables/kmeans_vs_expected_sizes.csv`)",
        "",
        "| Segment | K-Means Hard Count | GMM Hard Count | GMM Expected Size `SUM(p)` | GMM SD | Bootstrap Hard Count | Bootstrap Expected Size `SUM(p)` | Bootstrap SD |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for _, row in df.iterrows():
        lines.append(
            f"| **{row['segment']}** | {int(row['kmeans_hard_count']):,} | "
            f"{int(row['gmm_hard_count']):,} | {float(row['gmm_expected_size']):.2f} | "
            f"{float(row['gmm_std_dev']):.2f} | {int(row['bootstrap_hard_count']):,} | "
            f"{float(row['bootstrap_expected_size']):.2f} | {float(row['bootstrap_std_dev']):.2f} |"
        )
    return "\n".join(lines)


def build_lapse_table_md() -> str:
    """Format `reports/tables/lapse_s2_eval.csv` as a Markdown table."""
    df = pd.read_csv(config.TABLES_DIR / "lapse_s2_eval.csv")
    lines = [
        "### 6. Held-Out S2 90-Day Lapse Model Evaluation (`reports/tables/lapse_s2_eval.csv`)",
        "",
        "| Model | Test Customers (S2) | Base Lapse Rate | Mean Predicted `p` | Brier Score | ROC-AUC | Log Loss | 10-Bin ECE |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for _, row in df.iterrows():
        lines.append(
            f"| `{row['model']}` | {int(row['n_customers']):,} | "
            f"{float(row['base_lapse_rate']):.4f} | {float(row['mean_predicted_p']):.4f} | "
            f"{float(row['brier_score']):.4f} | {float(row['roc_auc']):.4f} | "
            f"{float(row['log_loss']):.4f} | {float(row['ece_10_bins']):.4f} |"
        )
    return "\n".join(lines)


def build_nl_table_md() -> str:
    """Format `reports/tables/nl_summary.csv` as a Markdown table."""
    df = pd.read_csv(config.TABLES_DIR / "nl_summary.csv")
    lines = [
        "### 7. Natural-Language Engine Evaluation (`reports/tables/nl_summary.csv`)",
        "",
        "| Split | Total Questions | In-Scope | Out-of-Scope | Overall Execution Accuracy | In-Scope Execution Accuracy | Template Match Rate | Out-of-Scope Rejection Rate | Hedge Threshold Accuracy |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for _, row in df.iterrows():
        lines.append(
            f"| `{row['split']}` | {int(row['n_total_questions'])} | "
            f"{int(row['n_in_scope'])} | {int(row['n_out_of_scope'])} | "
            f"{float(row['overall_execution_accuracy_pct']):.1f}% | "
            f"{float(row['in_scope_execution_accuracy_pct']):.1f}% | "
            f"{float(row['template_match_rate_pct']):.1f}% | "
            f"{float(row['out_of_scope_rejection_rate_pct']):.1f}% | "
            f"{float(row['hedge_threshold_accuracy_pct']):.1f}% |"
        )
    return "\n".join(lines)


def build_all_tables_md() -> str:
    """Combine all seven results tables into one Markdown document."""
    sections = [
        build_cleaning_table_md(),
        build_snapshot_table_md(),
        build_segment_table_md(),
        build_gate_table_md(),
        build_prob_vs_hard_table_md(),
        build_lapse_table_md(),
        build_nl_table_md(),
    ]
    return "\n\n".join(sections)


def update_readme_results(
    readme_path: Path = README_PATH, results_md: str | None = None
) -> bool:
    """Replace the block between BEGIN_MARKER and END_MARKER in README.md."""
    if not readme_path.exists():
        return False
    text = readme_path.read_text(encoding="utf-8")
    if BEGIN_MARKER not in text or END_MARKER not in text:
        return False
    if results_md is None:
        results_md = build_all_tables_md()

    before, remainder = text.split(BEGIN_MARKER, maxsplit=1)
    _, after = remainder.split(END_MARKER, maxsplit=1)
    updated = f"{before}{BEGIN_MARKER}\n\n{results_md}\n\n{END_MARKER}{after}"
    readme_path.write_text(updated, encoding="utf-8")
    return True


def run() -> Path:
    """Generate `reports/tables/readme_results.md` and sync `README.md`."""
    config.TABLES_DIR.mkdir(parents=True, exist_ok=True)
    results_md = build_all_tables_md()
    README_RESULTS_MD_PATH.write_text(results_md + "\n", encoding="utf-8")
    updated = update_readme_results(README_PATH, results_md)
    print(
        f"Phase 9 report tables written to {README_RESULTS_MD_PATH.name} "
        f"(README updated={updated})."
    )
    return README_RESULTS_MD_PATH


if __name__ == "__main__":
    run()
