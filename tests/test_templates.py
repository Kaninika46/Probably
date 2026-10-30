"""Phase 6 template and app database tests (CLAUDE.md sections 6, 7.8, 10).

Verifies:
1. `app/app.duckdb` exists, opens read-only, rejects writes, contains only the
   five S3 customer-level tables (`customers`, `customer_features`, `segments`,
   `segment_membership`, `lapse_risk`), and has no S1/S2 rows.
2. Every SQL template Q1..Q6 runs against `app/app.duckdb` with sample named
   parameters and returns the documented columns.
3. Parameter validation rejects unknown segments, methods, countries, or out-of-range
   probabilities.
4. Possible-worlds Monte Carlo mean matches Q3 analytical expected size.
"""

import duckdb
import pandas as pd
import pytest

from src import config, db, export_app_db, prob_queries

if not config.APP_DB_PATH.exists():
    pytest.skip("Run `python -m src.pipeline --phase 6` first", allow_module_level=True)


@pytest.fixture(scope="module")
def app_con():
    con = db.connect_app(config.APP_DB_PATH)
    yield con
    con.close()


def test_app_db_contains_only_five_s3_tables_and_is_read_only(app_con):
    tables = [r[0] for r in app_con.execute("SHOW TABLES").fetchall()]
    assert set(tables) == set(export_app_db.APP_TABLES)

    # No S1 or S2 rows anywhere in app.duckdb
    for tbl in ["customer_features", "segment_membership", "lapse_risk"]:
        non_s3 = app_con.execute(
            f"SELECT COUNT(*) FROM {tbl} WHERE snapshot <> 'S3'"
        ).fetchone()[0]
        assert non_s3 == 0

    with pytest.raises(duckdb.Error):
        app_con.execute("DROP TABLE customers")


def test_q1_confident_members_returns_documented_columns(app_con):
    df = prob_queries.run_template(
        app_con,
        "Q1",
        {"method": "bootstrap", "seg": "Champions", "tau": 0.66, "country": "United Kingdom"},
    )
    expected_cols = {
        "customer_id",
        "country",
        "segment",
        "p",
        "recency_days",
        "frequency",
        "monetary",
        "p_lapse_90d",
    }
    assert expected_cols.issubset(set(df.columns))
    assert len(df) > 0
    assert (df["p"] >= 0.66).all()
    assert (df["segment"] == "Champions").all()
    assert (df["country"] == "United Kingdom").all()


def test_q2_boundary_customers_returns_documented_columns(app_con):
    df = prob_queries.run_template(
        app_con,
        "Q2",
        {"method": "gmm", "boundary": 0.60},
    )
    expected_cols = {
        "customer_id",
        "country",
        "top_segment",
        "max_p",
        "second_segment",
        "second_p",
        "normalised_entropy",
        "recency_days",
        "frequency",
        "monetary",
    }
    assert expected_cols.issubset(set(df.columns))
    assert len(df) == 495
    assert (df["max_p"] < 0.60).all()
    assert (df["normalised_entropy"] > 0.0).all()


def test_q3_expected_size_returns_documented_columns(app_con):
    df = prob_queries.run_template(app_con, "Q3", {"method": "bootstrap"})
    expected_cols = {
        "segment",
        "hard_count",
        "expected_size",
        "expected_minus_hard",
        "variance_independent",
        "std_dev_independent",
    }
    assert expected_cols.issubset(set(df.columns))
    assert len(df) == config.CHOSEN_K
    assert abs(df["expected_size"].sum() - 3961.0) < 0.1


def test_q4_expected_revenue_returns_documented_columns(app_con):
    df = prob_queries.run_template(app_con, "Q4", {"method": "bootstrap"})
    expected_cols = {
        "segment",
        "hard_revenue",
        "expected_revenue",
        "expected_minus_hard_revenue",
        "expected_revenue_share_pct",
    }
    assert expected_cols.issubset(set(df.columns))
    assert len(df) == config.CHOSEN_K
    assert abs(df["expected_revenue_share_pct"].sum() - 100.0) < 0.1


def test_q5_top_k_members_returns_documented_columns(app_con):
    df = prob_queries.run_template(
        app_con,
        "Q5",
        {"method": "bootstrap", "seg": "Loyal", "k": 10},
    )
    assert len(df) == 10
    assert (df["segment"] == "Loyal").all()
    assert df["p"].is_monotonic_decreasing


def test_q6_segment_and_lapse_returns_documented_columns(app_con):
    df = prob_queries.run_template(
        app_con,
        "Q6",
        {"method": "bootstrap", "seg": "Hibernating", "tau1": 0.66, "tau2": 0.66},
    )
    expected_cols = {
        "customer_id",
        "country",
        "segment",
        "p",
        "p_lapse_90d",
        "recency_days",
        "frequency",
        "monetary",
    }
    assert expected_cols.issubset(set(df.columns))
    assert len(df) > 0
    assert (df["p"] >= 0.66).all()
    assert (df["p_lapse_90d"] >= 0.66).all()


def test_parameter_allowlists_reject_invalid_or_injection_inputs(app_con):
    with pytest.raises(ValueError):
        prob_queries.run_template(app_con, "Q1", {"seg": "'; DROP TABLE customers; --"})
    with pytest.raises(ValueError):
        prob_queries.run_template(app_con, "Q1", {"seg": "Champions", "country": "1 OR 1=1"})
    with pytest.raises(ValueError):
        prob_queries.run_template(app_con, "Q1", {"seg": "Champions", "method": "invalid"})
    with pytest.raises(ValueError):
        prob_queries.run_template(app_con, "Q1", {"seg": "Champions", "tau": 1.5})


def test_possible_worlds_matches_q3_analytical_mean():
    pw = pd.read_csv(config.TABLES_DIR / "possible_worlds_q3_check.csv")
    assert len(pw) == 2 * config.CHOSEN_K
    # With 10,000 worlds and std_dev <= 16, Monte Carlo mean is within 0.6 of exact SUM(p)
    assert (pw["abs_mean_diff"] < 0.6).all()
