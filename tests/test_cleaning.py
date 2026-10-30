"""Cleaning tests from CLAUDE.md section 10.

They read the real database built by `python -m src.pipeline --phase 1`, opened
read-only so a test can never change the data it checks.
"""

import pytest

from src import config, db

if not config.DB_PATH.exists():
    pytest.skip("Run `python -m src.pipeline --phase 1` first", allow_module_level=True)


@pytest.fixture(scope="module")
def con():
    connection = db.connect_app(config.DB_PATH)  # read-only
    yield connection
    connection.close()


def test_funnel_row_counts_never_increase(con):
    rows = con.execute(
        "SELECT step_no, rows_before, rows_after FROM data_quality_log ORDER BY step_no"
    ).fetchall()
    assert len(rows) == 6
    for step_no, rows_before, rows_after in rows:
        assert rows_after <= rows_before, f"step {step_no} increased the row count"


def test_funnel_steps_chain_together(con):
    """Steps 1-5 each start where the previous one ended."""
    rows = con.execute(
        "SELECT rows_before, rows_after FROM data_quality_log WHERE step_no <= 5 ORDER BY step_no"
    ).fetchall()
    for previous, current in zip(rows, rows[1:]):
        assert current[0] == previous[1]


def test_funnel_starts_from_all_raw_rows(con):
    raw = con.execute("SELECT COUNT(*) FROM raw_transactions").fetchone()[0]
    first = con.execute("SELECT rows_before FROM data_quality_log WHERE step_no = 1").fetchone()[0]
    assert first == raw


def test_clean_sales_has_only_positive_quantity_and_price(con):
    bad = con.execute("SELECT COUNT(*) FROM clean_sales WHERE quantity <= 0 OR price <= 0").fetchone()[0]
    assert bad == 0


def test_returns_only_contains_c_invoices(con):
    bad = con.execute("SELECT COUNT(*) FROM returns WHERE invoice NOT LIKE 'C%'").fetchone()[0]
    assert bad == 0


def test_clean_sales_has_no_cancellations(con):
    bad = con.execute("SELECT COUNT(*) FROM clean_sales WHERE invoice LIKE 'C%'").fetchone()[0]
    assert bad == 0


def test_clean_sales_has_no_non_product_codes(con):
    bad = con.execute(
        "SELECT COUNT(*) FROM clean_sales WHERE stock_code IN (SELECT stock_code FROM non_product_codes)"
    ).fetchone()[0]
    assert bad == 0


def test_has_customer_matches_customer_id(con):
    bad = con.execute(
        "SELECT COUNT(*) FROM clean_sales WHERE has_customer <> (customer_id IS NOT NULL)"
    ).fetchone()[0]
    assert bad == 0


def test_line_revenue_is_quantity_times_price(con):
    bad = con.execute(
        "SELECT COUNT(*) FROM clean_sales WHERE ABS(line_revenue - quantity * price) > 1e-9"
    ).fetchone()[0]
    assert bad == 0


def test_revenue_numbers_are_consistent_across_tables(con):
    """Verify raw_totals.csv, cleaning_funnel.csv and clean_sales_summary.csv agree."""
    import pandas as pd

    raw_tot = pd.read_csv(config.TABLES_DIR / "raw_totals.csv").iloc[0]
    funnel = pd.read_csv(config.TABLES_DIR / "cleaning_funnel.csv")
    summary = pd.read_csv(config.TABLES_DIR / "clean_sales_summary.csv").iloc[0]

    # Steps 1-5 transform raw_transactions into clean_sales
    removed_steps_1_to_5 = float(funnel.loc[funnel["step_no"] <= 5, "revenue_affected"].sum())
    expected_clean_rev = float(raw_tot["total_revenue"]) - removed_steps_1_to_5
    assert abs(expected_clean_rev - float(summary["total_revenue"])) < 0.05

    # Step 6 accounts for the difference between total clean revenue and customer-identified revenue
    step6_removed = float(funnel.loc[funnel["step_no"] == 6, "revenue_affected"].iloc[0])
    expected_cust_rev = float(summary["total_revenue"]) - step6_removed
    assert abs(expected_cust_rev - float(summary["revenue_with_customer"])) < 0.05
