"""Phase 5 lapse model and tuple-independent table tests (CLAUDE.md section 7.7).

Verifies on the real database:
1. `lapse_risk` has one row per S3 customer, with valid probabilities in [0, 1]
   and a non-empty `model_version`.
2. S1 cross-validation and S2 evaluation tables exist and compare the primary
   calibrated logistic model against the two-bin recency baseline and calibrated
   depth-4 tree on Brier score, ROC-AUC, log loss and 10-bin ECE.
3. The S2 reliability diagram exists.
"""

import pandas as pd
import pytest

from src import config, db

if not config.DB_PATH.exists():
    pytest.skip("Run `python -m src.pipeline --phase 5` first", allow_module_level=True)


@pytest.fixture(scope="module")
def con():
    connection = db.connect_app(config.DB_PATH)  # read-only
    tables = {row[0] for row in connection.execute("SHOW TABLES").fetchall()}
    if "lapse_risk" not in tables:
        connection.close()
        pytest.skip("Run `python -m src.pipeline --phase 5` first")
    yield connection
    connection.close()


def test_lapse_risk_covers_all_s3_customers(con):
    n_s3 = con.execute(
        "SELECT COUNT(*) FROM customer_features WHERE snapshot = 'S3'"
    ).fetchone()[0]
    n_lapse, n_distinct = con.execute(
        "SELECT COUNT(*), COUNT(DISTINCT customer_id) FROM lapse_risk WHERE snapshot = 'S3'"
    ).fetchone()
    assert n_lapse == n_distinct == n_s3


def test_lapse_risk_probabilities_and_model_version(con):
    bad = con.execute("""
        SELECT COUNT(*)
        FROM lapse_risk
        WHERE p_lapse_90d <= 0.0
           OR p_lapse_90d >= 1.0
           OR p_lapse_90d IS NULL
           OR model_version IS NULL
           OR LENGTH(TRIM(model_version)) = 0
    """).fetchone()[0]
    assert bad == 0


def test_s2_evaluation_and_reliability_outputs():
    s1_cv = pd.read_csv(config.TABLES_DIR / "lapse_s1_cv.csv")
    s2_eval = pd.read_csv(config.TABLES_DIR / "lapse_s2_eval.csv")
    expected_models = {"logistic_calibrated", "tree_depth4_calibrated", "two_bin_recency_90d"}

    assert set(s1_cv["model"]) == expected_models
    assert set(s2_eval["model"]) == expected_models

    for col in ["brier_score", "brier_skill_score", "roc_auc", "log_loss", "ece_10_bins"]:
        assert (s2_eval[col] > 0).all()

    # Primary model must outperform the two-bin baseline on S2 Brier, Brier skill, ROC-AUC and log loss.
    log_row = s2_eval[s2_eval["model"] == "logistic_calibrated"].iloc[0]
    base_row = s2_eval[s2_eval["model"] == "two_bin_recency_90d"].iloc[0]
    assert log_row["brier_score"] < base_row["brier_score"]
    assert log_row["brier_skill_score"] > base_row["brier_skill_score"]
    assert log_row["roc_auc"] > base_row["roc_auc"]
    assert log_row["log_loss"] < base_row["log_loss"]

    assert (config.FIGURES_DIR / "lapse_reliability_s2.png").exists()
