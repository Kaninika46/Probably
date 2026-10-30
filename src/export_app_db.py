"""Phase 6, part 2: build the small customer-level S3 database `app/app.duckdb`.

Follows CLAUDE.md section 6:
`app/app.duckdb` contains ONLY `customers`, `customer_features`, `segments`,
`segment_membership` and `lapse_risk`, all filtered to snapshot S3.
"""

import duckdb

from src import config, db

APP_TABLES = [
    "customers",
    "customer_features",
    "segments",
    "segment_membership",
    "lapse_risk",
]


def build_app_db() -> None:
    """Export the 5 S3 customer-level tables from data/retail.duckdb into app/app.duckdb."""
    config.APP_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if config.APP_DB_PATH.exists():
        config.APP_DB_PATH.unlink()

    app_con = duckdb.connect(str(config.APP_DB_PATH))
    src_path_sql = str(config.DB_PATH).replace("'", "''")
    app_con.execute(f"ATTACH '{src_path_sql}' AS retail_src (READ_ONLY)")

    # 1. customers (filtered to customers active in S3)
    app_con.execute("""
        CREATE TABLE customers AS
        SELECT c.*
        FROM retail_src.customers AS c
        WHERE c.customer_id IN (
            SELECT customer_id
            FROM retail_src.customer_features
            WHERE snapshot = 'S3'
        )
        ORDER BY c.customer_id
    """)

    # 2. customer_features (filtered to S3)
    app_con.execute("""
        CREATE TABLE customer_features AS
        SELECT *
        FROM retail_src.customer_features
        WHERE snapshot = 'S3'
        ORDER BY customer_id
    """)

    # 3. segments
    app_con.execute("""
        CREATE TABLE segments AS
        SELECT *
        FROM retail_src.segments
        ORDER BY segment
    """)

    # 4. segment_membership (filtered to S3)
    app_con.execute("""
        CREATE TABLE segment_membership AS
        SELECT *
        FROM retail_src.segment_membership
        WHERE snapshot = 'S3'
        ORDER BY customer_id, method, segment
    """)

    # 5. lapse_risk (filtered to S3)
    app_con.execute("""
        CREATE TABLE lapse_risk AS
        SELECT *
        FROM retail_src.lapse_risk
        WHERE snapshot = 'S3'
        ORDER BY customer_id
    """)

    app_con.execute("DETACH retail_src")
    app_con.execute("CHECKPOINT")
    app_con.close()

    # Verify read-only connection and print row counts
    ro_con = db.connect_app(config.APP_DB_PATH)
    print(f"Built {config.APP_DB_PATH} ({config.APP_DB_PATH.stat().st_size:,} bytes):")
    for tbl in APP_TABLES:
        cnt = ro_con.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
        print(f"  {tbl}: {cnt:,} rows")
    ro_con.close()


def run() -> None:
    build_app_db()


if __name__ == "__main__":
    run()
