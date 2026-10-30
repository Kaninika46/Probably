"""Phase 2: build customer snapshots (S1, S2, S3), RFM features and 90-day outcomes.

The snapshot dates live in src/config.py. We copy them into a small `snapshots`
table in DuckDB and then run sql/03_features.sql, so the SQL never hard-codes a
date and can be read on its own in the viva.
"""

from src import config, db


def create_snapshots_table(con) -> None:
    """Write config.SNAPSHOTS into DuckDB so sql/03_features.sql can join against it."""
    con.execute("DROP TABLE IF EXISTS snapshots")
    con.execute("""
        CREATE TABLE snapshots (
            snapshot      VARCHAR PRIMARY KEY,
            snapshot_date DATE,
            feature_start DATE,
            feature_end   DATE,
            outcome_start DATE,
            outcome_end   DATE
        )
    """)
    for name, dates in config.SNAPSHOTS.items():
        con.execute(
            "INSERT INTO snapshots VALUES (?, ?, ?, ?, ?, ?)",
            [
                name,
                dates["snapshot_date"],
                dates["feature_start"],
                dates["feature_end"],
                dates["outcome_start"],
                dates["outcome_end"],
            ],
        )


def save_snapshot_summary(con) -> None:
    """Save per-snapshot customer counts, feature averages and base lapse rates."""
    summary = con.execute("""
        SELECT
            sn.snapshot,
            sn.snapshot_date,
            sn.feature_start,
            sn.feature_end,
            sn.outcome_start,
            sn.outcome_end,
            COUNT(cf.customer_id) AS n_customers,
            ROUND(AVG(cf.recency_days), 2) AS mean_recency_days,
            ROUND(MEDIAN(cf.recency_days), 2) AS median_recency_days,
            ROUND(AVG(cf.frequency), 2) AS mean_frequency,
            ROUND(MEDIAN(cf.frequency), 2) AS median_frequency,
            ROUND(AVG(cf.monetary), 2) AS mean_monetary,
            ROUND(MEDIAN(cf.monetary), 2) AS median_monetary,
            ROUND(AVG(cf.tenure_days), 2) AS mean_tenure_days,
            ROUND(MEDIAN(cf.tenure_days), 2) AS median_tenure_days,
            ROUND(AVG(cf.avg_basket), 2) AS mean_avg_basket,
            ROUND(MEDIAN(cf.avg_basket), 2) AS median_avg_basket,
            SUM(o.purchased_next_90d) AS n_purchased_next_90d,
            COUNT(o.purchased_next_90d) - SUM(o.purchased_next_90d) AS n_lapsed_next_90d,
            ROUND(100.0 * AVG(o.purchased_next_90d), 2) AS purchase_rate_pct,
            ROUND(100.0 * (1.0 - AVG(o.purchased_next_90d)), 2) AS lapse_rate_pct
        FROM snapshots AS sn
        LEFT JOIN customer_features AS cf
          ON cf.snapshot = sn.snapshot
        LEFT JOIN outcomes AS o
          ON o.snapshot = cf.snapshot
         AND o.customer_id = cf.customer_id
        GROUP BY
            sn.snapshot,
            sn.snapshot_date,
            sn.feature_start,
            sn.feature_end,
            sn.outcome_start,
            sn.outcome_end
        ORDER BY sn.snapshot
    """).df()

    config.TABLES_DIR.mkdir(parents=True, exist_ok=True)
    summary.to_csv(config.TABLES_DIR / "snapshot_summary.csv", index=False)
    print(summary.to_string(index=False))


def run() -> None:
    con = db.connect_pipeline()
    create_snapshots_table(con)
    db.run_sql_file(con, config.SQL_DIR / "03_features.sql")
    save_snapshot_summary(con)
    con.close()


if __name__ == "__main__":
    run()
