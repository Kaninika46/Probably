"""Derived numbers quoted in docs/REPORT_SOURCE.md.

Why this exists: CLAUDE.md rule 1 says every number in a deliverable must come
from a file produced by code. A few numbers the report needs are differences or
ratios of values already in reports/tables (for example the gap between the GMM
and bootstrap boundary shares). Rather than doing that arithmetic by hand in the
document, this script computes each one from the source tables and writes
reports/tables/report_derived_numbers.csv, with the inputs named in a column.

Run with:  python -m src.report_derived
"""

import duckdb
import pandas as pd

from src import config

TABLES = config.TABLES_DIR


def read_table(name: str) -> pd.DataFrame:
    """Read one CSV from reports/tables."""
    return pd.read_csv(TABLES / name)


def gate_numbers() -> list[dict]:
    """Gap between the GMM and bootstrap boundary shares (the gate finding)."""
    gate = read_table("gate.csv").set_index("method")
    gmm_share = gate.loc["gmm", "boundary_share_pct"]
    boot_share = gate.loc["bootstrap", "boundary_share_pct"]
    gmm_n = gate.loc["gmm", "n_boundary_max_p_lt_0_6"]
    boot_n = gate.loc["bootstrap", "n_boundary_max_p_lt_0_6"]
    return [
        {"metric": "boundary_share_gap_pct_points_gmm_minus_bootstrap",
         "value": round(gmm_share - boot_share, 2), "source": "gate.csv"},
        {"metric": "boundary_share_ratio_gmm_over_bootstrap",
         "value": round(gmm_share / boot_share, 2), "source": "gate.csv"},
        {"metric": "boundary_customers_gmm_minus_bootstrap",
         "value": int(gmm_n - boot_n), "source": "gate.csv"},
    ]


def lapse_numbers() -> list[dict]:
    """Calibration-vs-discrimination contrast between the logistic model and the recency rule on S2."""
    s2 = read_table("lapse_s2_eval.csv").set_index("model")
    logit = s2.loc["logistic_calibrated"]
    rule = s2.loc["two_bin_recency_90d"]
    bins = read_table("lapse_reliability_bins_s2.csv")
    logit_bins = bins[bins["model"] == "logistic_calibrated"]
    # Bins 8 and 9 (predicted P >= 0.7) are the sparse top end of the reliability diagram.
    top_bins_n = int(logit_bins[logit_bins["bin_lower"] >= 0.7]["n_customers"].sum())
    return [
        {"metric": "s2_auc_gap_logistic_minus_two_bin",
         "value": round(logit["roc_auc"] - rule["roc_auc"], 4), "source": "lapse_s2_eval.csv"},
        {"metric": "s2_ece_gap_logistic_minus_two_bin",
         "value": round(logit["ece_10_bins"] - rule["ece_10_bins"], 4), "source": "lapse_s2_eval.csv"},
        {"metric": "s2_brier_gap_two_bin_minus_logistic",
         "value": round(rule["brier_score"] - logit["brier_score"], 4), "source": "lapse_s2_eval.csv"},
        {"metric": "s2_logistic_base_rate_minus_mean_predicted",
         "value": round(logit["base_lapse_rate"] - logit["mean_predicted_p"], 4),
         "source": "lapse_s2_eval.csv"},
        {"metric": "s2_logistic_customers_predicted_p_ge_0_7",
         "value": top_bins_n, "source": "lapse_reliability_bins_s2.csv"},
    ]


def data_numbers() -> list[dict]:
    """Coverage and concentration facts about the dataset."""
    clean = read_table("clean_sales_summary.csv").iloc[0]
    countries = read_table("eda_top_countries.csv").set_index("country")
    snaps = read_table("snapshot_summary.csv").set_index("snapshot")
    uk_share = 100 * countries.loc["United Kingdom", "revenue"] / clean["total_revenue"]
    s3_share = 100 * snaps.loc["S3", "n_customers"] / clean["n_customers"]
    last_date = pd.Timestamp(clean["last_invoice_date"])
    return [
        {"metric": "uk_share_of_clean_sales_revenue_pct",
         "value": round(uk_share, 2), "source": "eda_top_countries.csv; clean_sales_summary.csv"},
        {"metric": "s3_customers_as_pct_of_all_customers",
         "value": round(s3_share, 2), "source": "snapshot_summary.csv; clean_sales_summary.csv"},
        {"metric": "dataset_last_invoice_year",
         "value": int(last_date.year), "source": "clean_sales_summary.csv"},
    ]


def nl_numbers() -> list[dict]:
    """How the 26 dev questions spread over templates, and how many hit the 500-row limit."""
    dev = read_table("nl_dev_results.csv")
    rows = []
    for template, count in dev["expected_template"].value_counts().sort_index().items():
        rows.append({"metric": f"dev_questions_expected_{template}",
                     "value": int(count), "source": "nl_dev_results.csv"})
    rows.append({"metric": "dev_questions_returning_500_rows_row_limit",
                 "value": int((dev["n_rows_returned"] == 500).sum()), "source": "nl_dev_results.csv"})
    return rows


def app_db_numbers() -> list[dict]:
    """S3 country mix and lapse-risk range, read from the read-only app database."""
    con = duckdb.connect(str(config.APP_DB_PATH), read_only=True)
    n_countries = con.execute("SELECT COUNT(DISTINCT country) FROM customers").fetchone()[0]
    uk_share = con.execute(
        "SELECT 100.0 * AVG(CASE WHEN country = 'United Kingdom' THEN 1 ELSE 0 END) FROM customers"
    ).fetchone()[0]
    min_p, max_p = con.execute("SELECT MIN(p_lapse_90d), MAX(p_lapse_90d) FROM lapse_risk").fetchone()
    model_version = con.execute("SELECT DISTINCT model_version FROM lapse_risk").fetchone()[0]
    con.close()
    return [
        {"metric": "s3_n_countries", "value": int(n_countries), "source": "app/app.duckdb customers"},
        {"metric": "s3_uk_customer_share_pct", "value": round(uk_share, 2),
         "source": "app/app.duckdb customers"},
        {"metric": "s3_min_p_lapse_90d", "value": round(min_p, 4), "source": "app/app.duckdb lapse_risk"},
        {"metric": "s3_max_p_lapse_90d", "value": round(max_p, 4), "source": "app/app.duckdb lapse_risk"},
        {"metric": f"s3_lapse_model_version_{model_version}", "value": 1,
         "source": "app/app.duckdb lapse_risk"},
    ]


def run() -> None:
    rows = gate_numbers() + lapse_numbers() + data_numbers() + nl_numbers() + app_db_numbers()
    out = TABLES / "report_derived_numbers.csv"
    pd.DataFrame(rows).to_csv(out, index=False)
    print(f"Wrote {len(rows)} derived numbers to {out}")


if __name__ == "__main__":
    run()
