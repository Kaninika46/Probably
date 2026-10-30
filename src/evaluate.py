"""Phase 7: NL evaluation harness and master `eval_results` table builder.

Follows CLAUDE.md sections 6 and 7.10:
1. Evaluates the spaCy rule-based NL engine on `eval/questions_dev.csv` (and on
   `eval/questions_test.csv` only after a human adds rows to it).
2. Compares result sets (order-insensitive unless the gold SQL contains ORDER BY),
   and reports execution accuracy, template match rate, out-of-scope rejection
   rate, hedge-threshold accuracy, and an error analysis table by failure type.
3. Consolidates every headline number from cleaning, snapshots, clustering,
   probability informativeness, surrogate tree, lapse model and NL evaluation
   into the `eval_results` table in `data/retail.duckdb` and `reports/tables/eval_results.csv`.
"""

from pathlib import Path

import numpy as np
import pandas as pd

from src import config, db
from src.nl import engine

DEV_CSV = config.PROJECT_ROOT / "eval" / "questions_dev.csv"
TEST_CSV = config.PROJECT_ROOT / "eval" / "questions_test.csv"

FAILURE_TYPES = [
    "wrong_template",
    "wrong_hedge_threshold",
    "wrong_entity_or_filter",
    "false_refusal",
    "missed_refusal",
    "result_set_mismatch",
]


def has_top_level_order_by(sql_text: str) -> bool:
    """Return True iff `sql_text` has an ORDER BY clause outside all parentheses."""
    s = sql_text.lower()
    prev = None
    while prev != s:
        prev = s
        s = s.replace("()", "")
        import re
        s = re.sub(r"\([^()]*\)", "", s)
    return "order by" in s


def result_sets_match(pred_df: pd.DataFrame, gold_df: pd.DataFrame, ordered: bool) -> bool:
    """Compare two query result DataFrames (order-insensitive unless `ordered=True`)."""
    if len(pred_df) != len(gold_df) or list(pred_df.columns) != list(gold_df.columns):
        return False
    if len(pred_df) == 0:
        return True

    p = pred_df.copy().reset_index(drop=True)
    g = gold_df.copy().reset_index(drop=True)

    # Round float columns to 4 decimals so minor floating-point formatting never masks equality
    for col in p.columns:
        if pd.api.types.is_float_dtype(p[col]) or pd.api.types.is_float_dtype(g[col]):
            p[col] = p[col].astype(float).round(4)
            g[col] = g[col].astype(float).round(4)

    if not ordered:
        sort_cols = list(p.columns)
        p = p.sort_values(by=sort_cols, kind="mergesort").reset_index(drop=True)
        g = g.sort_values(by=sort_cols, kind="mergesort").reset_index(drop=True)

    return p.equals(g)


def extract_primary_threshold(parsed) -> float | None:
    """Return the main probability threshold used by `parsed` for hedge accuracy checks."""
    if not parsed.is_supported or parsed.template_id is None:
        return None
    params = parsed.params
    if parsed.template_id == "Q1":
        if params.get("only_top_segment"):
            return 1.0
        if params.get("max_p", 1.0) < 1.0 and params.get("tau", 0.0) == 0.0:
            return float(params["max_p"])
        return float(params.get("tau", 0.66))
    if parsed.template_id == "Q2":
        return float(params.get("boundary", config.BOUNDARY_P))
    if parsed.template_id == "Q6":
        if params.get("max_p2", 1.0) < 1.0 and params.get("tau2", 0.0) == 0.0:
            return float(params["max_p2"])
        return float(params.get("tau2", 0.66))
    return None


def evaluate_question_file(
    app_con,
    csv_path: Path,
    split_label: str,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Evaluate all questions in `csv_path` against `app_con` (opened read-only)."""
    q_df = pd.read_csv(csv_path)
    if len(q_df) == 0:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    detail_rows = []
    failure_counts = {ft: 0 for ft in FAILURE_TYPES}

    for row in q_df.itertuples():
        q_id = str(row.q_id)
        question = str(row.question)
        gold_sql = str(row.gold_sql).strip()
        exp_tmpl = (
            str(row.expected_template).strip()
            if hasattr(row, "expected_template") and pd.notna(row.expected_template)
            else ("OUT_OF_SCOPE" if gold_sql.upper() == "OUT_OF_SCOPE" else None)
        )
        exp_thr = (
            float(row.expected_hedge_threshold)
            if hasattr(row, "expected_hedge_threshold") and pd.notna(row.expected_hedge_threshold)
            else None
        )

        resp = engine.answer_question(app_con, question)
        parsed = resp.parsed
        pred_tmpl = parsed.template_id if parsed.is_supported else "OUT_OF_SCOPE"
        pred_thr = extract_primary_threshold(parsed)

        is_oos_gold = gold_sql.upper() == "OUT_OF_SCOPE"
        template_ok = (exp_tmpl is None) or (pred_tmpl == exp_tmpl)
        hedge_ok = (
            True
            if exp_thr is None
            else (pred_thr is not None and abs(pred_thr - exp_thr) < 1e-4)
        )

        if is_oos_gold:
            exec_ok = not parsed.is_supported
            failure_type = "none" if exec_ok else "missed_refusal"
        else:
            if not parsed.is_supported:
                exec_ok = False
                failure_type = "false_refusal"
            else:
                ordered = has_top_level_order_by(gold_sql)
                gold_df = app_con.execute(gold_sql).df()
                exec_ok = result_sets_match(resp.rows, gold_df, ordered=ordered)
                if exec_ok:
                    failure_type = "none"
                elif not template_ok:
                    failure_type = "wrong_template"
                elif not hedge_ok:
                    failure_type = "wrong_hedge_threshold"
                else:
                    failure_type = "result_set_mismatch"

        if failure_type != "none":
            failure_counts[failure_type] = failure_counts.get(failure_type, 0) + 1

        detail_rows.append({
            "split": split_label,
            "q_id": q_id,
            "question": question,
            "expected_template": exp_tmpl,
            "predicted_template": pred_tmpl,
            "template_match": template_ok,
            "expected_threshold": exp_thr,
            "predicted_threshold": pred_thr,
            "hedge_threshold_match": hedge_ok,
            "is_out_of_scope_gold": is_oos_gold,
            "execution_correct": exec_ok,
            "failure_type": failure_type,
            "n_rows_returned": len(resp.rows),
            "interpretation": parsed.interpretation,
        })

    res_df = pd.DataFrame(detail_rows)
    in_scope = res_df[~res_df["is_out_of_scope_gold"]]
    oos = res_df[res_df["is_out_of_scope_gold"]]
    with_hedge = res_df[res_df["expected_threshold"].notna()]

    summary_df = pd.DataFrame([{
        "split": split_label,
        "n_total_questions": len(res_df),
        "n_in_scope": len(in_scope),
        "n_out_of_scope": len(oos),
        "overall_execution_accuracy_pct": round(100.0 * float(res_df["execution_correct"].mean()), 2),
        "in_scope_execution_accuracy_pct": (
            round(100.0 * float(in_scope["execution_correct"].mean()), 2)
            if len(in_scope) > 0
            else np.nan
        ),
        "template_match_rate_pct": round(100.0 * float(res_df["template_match"].mean()), 2),
        "out_of_scope_rejection_rate_pct": (
            round(100.0 * float(oos["execution_correct"].mean()), 2)
            if len(oos) > 0
            else np.nan
        ),
        "hedge_threshold_accuracy_pct": (
            round(100.0 * float(with_hedge["hedge_threshold_match"].mean()), 2)
            if len(with_hedge) > 0
            else np.nan
        ),
    }])

    err_df = pd.DataFrame([
        {
            "split": split_label,
            "failure_type": ft,
            "n_questions": count,
            "share_of_questions_pct": round(100.0 * count / len(res_df), 2),
        }
        for ft, count in failure_counts.items()
    ])
    return res_df, summary_df, err_df


def build_master_eval_results(con, nl_summary_df: pd.DataFrame) -> pd.DataFrame:
    """Populate `eval_results` in DuckDB with traceable metrics across all phases."""
    con.execute("DROP TABLE IF EXISTS eval_results")
    con.execute("""
        CREATE TABLE eval_results (
            area   VARCHAR,
            metric VARCHAR,
            value  DOUBLE,
            detail VARCHAR
        )
    """)

    rows: list[tuple[str, str, float, str]] = []

    # 1. Cleaning metrics
    raw_tot = pd.read_csv(config.TABLES_DIR / "raw_totals.csv").iloc[0]
    clean_sum = pd.read_csv(config.TABLES_DIR / "clean_sales_summary.csv").iloc[0]
    rows.extend([
        ("cleaning", "raw_rows", float(raw_tot["n_rows"]), "Total rows in raw_transactions"),
        ("cleaning", "raw_net_revenue_gbp", float(raw_tot["total_revenue"]), "Net revenue in raw_transactions"),
        ("cleaning", "clean_sales_rows", float(clean_sum["n_lines"]), "Rows surviving rules 1-5"),
        ("cleaning", "clean_sales_with_customer_rows", float(clean_sum["n_lines_with_customer"]), "Rows surviving rules 1-6"),
        ("cleaning", "clean_sales_revenue_gbp", float(clean_sum["total_revenue"]), "Total clean product revenue"),
        ("cleaning", "clean_sales_customer_revenue_gbp", float(clean_sum["revenue_with_customer"]), "Clean product revenue with customer_id"),
        ("cleaning", "distinct_customers", float(clean_sum["n_customers"]), "Unique customer_id count in clean_sales"),
    ])

    # 2. Snapshot metrics
    snap_df = pd.read_csv(config.TABLES_DIR / "snapshot_summary.csv")
    for srow in snap_df.itertuples():
        rows.append(("snapshots", f"{srow.snapshot}_n_customers", float(srow.n_customers), f"Active customers in {srow.snapshot}"))
        if pd.notna(srow.lapse_rate_pct):
            rows.append(("snapshots", f"{srow.snapshot}_base_lapse_rate_pct", float(srow.lapse_rate_pct), f"90-day base lapse rate in {srow.snapshot}"))

    # 3. Clustering metrics (K=5 spherical GMM vs K-Means)
    km_df = pd.read_csv(config.TABLES_DIR / "kmeans_grid.csv")
    km5 = km_df[km_df["k"] == config.CHOSEN_K].iloc[0]
    gmm_df = pd.read_csv(config.TABLES_DIR / "gmm_grid.csv")
    gmm5 = gmm_df[(gmm_df["covariance_type"] == config.CHOSEN_GMM_COV) & (gmm_df["k"] == config.CHOSEN_K)].iloc[0]
    ari_df = pd.read_csv(config.TABLES_DIR / "bootstrap_stability.csv").iloc[0]
    jac_df = pd.read_csv(config.TABLES_DIR / "segment_stability.csv")
    rows.extend([
        ("clustering", "kmeans_k5_silhouette", float(km5["silhouette"]), "K-Means K=5 silhouette on S3"),
        ("clustering", "gmm_spherical_k5_bic", float(gmm5["bic"]), "GMM spherical K=5 BIC on S3"),
        ("clustering", "gmm_spherical_k5_aic", float(gmm5["aic"]), "GMM spherical K=5 AIC on S3"),
        ("clustering", "gmm_spherical_k5_silhouette", float(gmm5["silhouette"]), "GMM spherical K=5 silhouette on S3"),
        ("clustering", "bootstrap_ari_median", float(ari_df["ari_median"]), "B=100 bootstrap ARI median vs reference"),
        ("clustering", "bootstrap_ari_iqr", float(ari_df["ari_iqr"]), "B=100 bootstrap ARI IQR"),
        ("clustering", "min_segment_jaccard_mean", float(jac_df["jaccard_mean"].min()), "Lowest per-segment mean Jaccard (At-Risk)"),
    ])

    # 4. Probability informativeness (Gate report)
    gate_df = pd.read_csv(config.TABLES_DIR / "gate.csv")
    for grow in gate_df.itertuples():
        rows.extend([
            ("probability_informativeness", f"{grow.method}_boundary_share_pct", float(grow.boundary_share_pct), f"% of S3 customers with max(p) < 0.60 ({grow.method})"),
            ("probability_informativeness", f"{grow.method}_mean_normalised_entropy", float(grow.mean_normalised_entropy), f"Mean normalised Shannon entropy ({grow.method})"),
            ("probability_informativeness", f"{grow.method}_mean_max_p", float(grow.mean_max_p), f"Mean maximum membership probability ({grow.method})"),
        ])

    # 5. Surrogate decision tree
    tree_df = pd.read_csv(config.TABLES_DIR / "tree_fidelity.csv").iloc[0]
    rows.extend([
        ("tree", "n_leaves", float(tree_df["n_leaves"]), "Number of leaves in depth-4 surrogate tree"),
        ("tree", "train_fidelity_pct", float(tree_df["train_fidelity_pct"]), "70% train split agreement with GMM"),
        ("tree", "test_fidelity_pct", float(tree_df["test_fidelity_pct"]), "30% held-out test split agreement with GMM"),
    ])

    # 6. Lapse model (S2 held-out evaluation)
    s2_df = pd.read_csv(config.TABLES_DIR / "lapse_s2_eval.csv")
    for lrow in s2_df.itertuples():
        rows.extend([
            ("lapse", f"s2_{lrow.model}_brier", float(lrow.brier_score), f"S2 Brier score ({lrow.model})"),
            ("lapse", f"s2_{lrow.model}_brier_skill_score", float(lrow.brier_skill_score), f"S2 Brier skill score vs base rate ({lrow.model})"),
            ("lapse", f"s2_{lrow.model}_roc_auc", float(lrow.roc_auc), f"S2 ROC-AUC ({lrow.model})"),
            ("lapse", f"s2_{lrow.model}_log_loss", float(lrow.log_loss), f"S2 log loss ({lrow.model})"),
            ("lapse", f"s2_{lrow.model}_ece_10_bins", float(lrow.ece_10_bins), f"S2 10-bin ECE ({lrow.model})"),
        ])

    # 7. NL engine evaluation
    for nrow in nl_summary_df.itertuples():
        rows.extend([
            ("nl", f"{nrow.split}_overall_execution_accuracy_pct", float(nrow.overall_execution_accuracy_pct), f"Overall execution accuracy on {nrow.split}"),
            ("nl", f"{nrow.split}_template_match_rate_pct", float(nrow.template_match_rate_pct), f"Template match rate on {nrow.split}"),
            ("nl", f"{nrow.split}_out_of_scope_rejection_rate_pct", float(nrow.out_of_scope_rejection_rate_pct), f"Out-of-scope rejection rate on {nrow.split}"),
            ("nl", f"{nrow.split}_hedge_threshold_accuracy_pct", float(nrow.hedge_threshold_accuracy_pct), f"Hedge-threshold accuracy on {nrow.split}"),
        ])

    eval_df = pd.DataFrame(rows, columns=["area", "metric", "value", "detail"])
    con.execute("INSERT INTO eval_results SELECT * FROM eval_df")
    return eval_df


def run() -> None:
    app_con = db.connect_app(config.APP_DB_PATH)
    dev_res, dev_sum, dev_err = evaluate_question_file(app_con, DEV_CSV, "dev")

    summaries = [dev_sum]
    errors = [dev_err]

    # Run test set ONLY if a human has added questions to eval/questions_test.csv
    if TEST_CSV.exists():
        test_q_df = pd.read_csv(TEST_CSV)
        if len(test_q_df) > 0:
            test_res, test_sum, test_err = evaluate_question_file(app_con, TEST_CSV, "test")
            test_res.to_csv(config.TABLES_DIR / "nl_test_results.csv", index=False)
            summaries.append(test_sum)
            errors.append(test_err)
    app_con.close()

    nl_summary_df = pd.concat(summaries, ignore_index=True)
    nl_error_df = pd.concat(errors, ignore_index=True)

    config.TABLES_DIR.mkdir(parents=True, exist_ok=True)
    dev_res.to_csv(config.TABLES_DIR / "nl_dev_results.csv", index=False)
    nl_summary_df.to_csv(config.TABLES_DIR / "nl_summary.csv", index=False)
    nl_error_df.to_csv(config.TABLES_DIR / "nl_error_analysis.csv", index=False)

    pipe_con = db.connect_pipeline()
    eval_df = build_master_eval_results(pipe_con, nl_summary_df)
    pipe_con.close()
    eval_df.to_csv(config.TABLES_DIR / "eval_results.csv", index=False)

    print("=== NL Engine Evaluation Summary ===")
    print(nl_summary_df.to_string(index=False))
    print("\n=== NL Error Analysis by Failure Type ===")
    print(nl_error_df.to_string(index=False))


if __name__ == "__main__":
    run()
