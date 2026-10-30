"""Feature and leakage tests from CLAUDE.md sections 7.3 and 10.

They verify on the real database that:
1. Each (customer_id, snapshot) pair appears at most once.
2. No feature uses a transaction with a date >= snapshot_date S.
3. No outcome uses a transaction outside its [outcome_start, outcome_end] window.
"""

import pytest

from src import config, db

if not config.DB_PATH.exists():
    pytest.skip("Run `python -m src.pipeline --phase 2` first", allow_module_level=True)


@pytest.fixture(scope="module")
def con():
    connection = db.connect_app(config.DB_PATH)  # read-only
    tables = {row[0] for row in connection.execute("SHOW TABLES").fetchall()}
    if "customer_features" not in tables:
        connection.close()
        pytest.skip("Run `python -m src.pipeline --phase 2` first")
    yield connection
    connection.close()


def test_customers_has_one_row_per_customer(con):
    total, distinct_ids = con.execute(
        "SELECT COUNT(*), COUNT(DISTINCT customer_id) FROM customers"
    ).fetchone()
    expected = con.execute(
        "SELECT COUNT(DISTINCT customer_id) FROM clean_sales WHERE has_customer"
    ).fetchone()[0]
    assert total == distinct_ids == expected
    bad_dates = con.execute(
        "SELECT COUNT(*) FROM customers WHERE first_purchase > last_purchase"
    ).fetchone()[0]
    assert bad_dates == 0


def test_one_row_per_customer_and_snapshot(con):
    total, distinct_pairs = con.execute(
        "SELECT COUNT(*), COUNT(DISTINCT (customer_id, snapshot)) FROM customer_features"
    ).fetchone()
    assert total == distinct_pairs
    assert total > 0


def test_snapshot_inclusion_matches_feature_window(con):
    """A customer belongs to a snapshot iff they had >= 1 clean sale in [feature_start, feature_end]."""
    for name, snap in config.SNAPSHOTS.items():
        in_table = con.execute(
            "SELECT COUNT(*) FROM customer_features WHERE snapshot = ?",
            [name],
        ).fetchone()[0]
        in_window = con.execute(
            """
            SELECT COUNT(DISTINCT customer_id)
            FROM clean_sales
            WHERE has_customer
              AND CAST(invoice_date AS DATE) BETWEEN ? AND ?
            """,
            [snap["feature_start"], snap["feature_end"]],
        ).fetchone()[0]
        assert in_table == in_window, f"Mismatch for {name}"


def test_no_feature_leakage_from_on_or_after_snapshot_date(con):
    """Every feature must equal the value computed exclusively from dates < S."""
    # 1. recency_days >= 1 and tenure_days >= recency_days proves no purchase date >= S was used.
    bad_bounds = con.execute("""
        SELECT COUNT(*)
        FROM customer_features
        WHERE recency_days < 1
           OR tenure_days < recency_days
           OR frequency < 1
           OR monetary <= 0
           OR ABS(avg_basket - monetary / frequency) > 1e-9
    """).fetchone()[0]
    assert bad_bounds == 0

    # 2. Recompute features after explicitly discarding all rows with date >= S.
    for name, snap in config.SNAPSHOTS.items():
        mismatches = con.execute(
            """
            WITH strictly_before_s AS (
                SELECT *
                FROM clean_sales
                WHERE has_customer
                  AND CAST(invoice_date AS DATE) < $s_date
            ),
            first_seen AS (
                SELECT
                    customer_id,
                    MIN(CAST(invoice_date AS DATE)) AS first_date
                FROM strictly_before_s
                GROUP BY customer_id
            ),
            window_agg AS (
                SELECT
                    customer_id,
                    MAX(CAST(invoice_date AS DATE)) AS last_date,
                    COUNT(DISTINCT invoice) AS frequency,
                    SUM(line_revenue) AS monetary
                FROM strictly_before_s
                WHERE CAST(invoice_date AS DATE) >= $f_start
                  AND CAST(invoice_date AS DATE) <= $f_end
                GROUP BY customer_id
            ),
            expected AS (
                SELECT
                    w.customer_id,
                    CAST($s_date - w.last_date AS INTEGER) AS recency_days,
                    w.frequency,
                    w.monetary,
                    CAST($s_date - f.first_date AS INTEGER) AS tenure_days
                FROM window_agg AS w
                JOIN first_seen AS f
                  ON f.customer_id = w.customer_id
            ),
            actual AS (
                SELECT *
                FROM customer_features
                WHERE snapshot = $snap
            )
            SELECT COUNT(*)
            FROM actual AS cf
            FULL OUTER JOIN expected AS e
              ON e.customer_id = cf.customer_id
            WHERE cf.customer_id IS NULL
               OR e.customer_id IS NULL
               OR cf.recency_days <> e.recency_days
               OR cf.frequency <> e.frequency
               OR ABS(cf.monetary - e.monetary) > 1e-6
               OR cf.tenure_days <> e.tenure_days
            """,
            {
                "snap": name,
                "s_date": snap["snapshot_date"],
                "f_start": snap["feature_start"],
                "f_end": snap["feature_end"],
            },
        ).fetchone()[0]
        assert mismatches == 0, f"Feature leakage or mismatch found in {name}"


def test_no_outcome_leakage_outside_outcome_window(con):
    """Outcomes exist only for S1 and S2, and use only sales inside [outcome_start, outcome_end]."""
    s3_rows = con.execute("SELECT COUNT(*) FROM outcomes WHERE snapshot = 'S3'").fetchone()[0]
    assert s3_rows == 0

    for name in ["S1", "S2"]:
        snap = config.SNAPSHOTS[name]
        mismatches = con.execute(
            """
            WITH expected AS (
                SELECT
                    cf.customer_id,
                    CASE
                        WHEN EXISTS (
                            SELECT 1
                            FROM clean_sales AS cs
                            WHERE cs.has_customer
                              AND cs.customer_id = cf.customer_id
                              AND CAST(cs.invoice_date AS DATE) >= $o_start
                              AND CAST(cs.invoice_date AS DATE) <= $o_end
                        ) THEN 1
                        ELSE 0
                    END AS purchased_next_90d
                FROM customer_features AS cf
                WHERE cf.snapshot = $snap
            ),
            actual AS (
                SELECT *
                FROM outcomes
                WHERE snapshot = $snap
            )
            SELECT COUNT(*)
            FROM actual AS o
            FULL OUTER JOIN expected AS e
              ON e.customer_id = o.customer_id
            WHERE o.customer_id IS NULL
               OR e.customer_id IS NULL
               OR o.purchased_next_90d <> e.purchased_next_90d
            """,
            {
                "snap": name,
                "o_start": snap["outcome_start"],
                "o_end": snap["outcome_end"],
            },
        ).fetchone()[0]
        assert mismatches == 0, f"Outcome leakage or mismatch found in {name}"
