"""Phase 1, step 2: build the cleaning views and log the funnel.

Each cleaning rule is a SQL view (sql/02_clean_views.sql). Here we count the
rows and revenue of every view, so the drop at each rule is measured from the
data and never typed in by hand.
"""

import matplotlib

matplotlib.use("Agg")  # draw to files only; no window needed
import matplotlib.pyplot as plt
from matplotlib.ticker import StrMethodFormatter

from src import config, db

# (step_no, rule name, view before the rule, view after the rule)
FUNNEL_STEPS = [
    (1, "Overlap duplicates between sheets", "raw_transactions", "cleaning_step1_no_overlap"),
    (2, "Remaining exact duplicates", "cleaning_step1_no_overlap", "cleaning_step2_no_duplicates"),
    (3, "Cancellations moved to returns", "cleaning_step2_no_duplicates", "cleaning_step3_no_cancellations"),
    (4, "Quantity or price not positive", "cleaning_step3_no_cancellations", "cleaning_step4_positive"),
    (5, "Non-product stock codes", "cleaning_step4_positive", "clean_sales"),
]


def count_rows_and_revenue(con, relation: str, where: str = "TRUE") -> tuple[int, float]:
    """Return (row count, total quantity * price) for a table or view."""
    sql = f"SELECT COUNT(*), COALESCE(SUM(quantity * price), 0) FROM {relation} WHERE {where}"
    rows, revenue = con.execute(sql).fetchone()
    return rows, revenue


def fill_data_quality_log(con) -> None:
    """Measure every rule and write one row per rule into data_quality_log.

    revenue_affected is the revenue of the rows a rule removed, calculated as
    revenue before minus revenue after. For cancellations it is negative,
    because cancelled lines have negative quantities.
    """
    con.execute("DELETE FROM data_quality_log")

    for step_no, rule, before_view, after_view in FUNNEL_STEPS:
        rows_before, revenue_before = count_rows_and_revenue(con, before_view)
        rows_after, revenue_after = count_rows_and_revenue(con, after_view)
        insert_log_row(con, step_no, rule, rows_before, rows_after, revenue_before - revenue_after)

    # Rule 6 does not remove rows from clean_sales. It records how many rows
    # and how much revenue are left out of customer-level analysis.
    rows_before, revenue_before = count_rows_and_revenue(con, "clean_sales")
    rows_after, revenue_after = count_rows_and_revenue(con, "clean_sales", where="has_customer")
    insert_log_row(
        con, 6, "Missing customer_id (excluded from customer analysis)",
        rows_before, rows_after, revenue_before - revenue_after,
    )


def insert_log_row(con, step_no, rule, rows_before, rows_after, revenue_affected) -> None:
    con.execute(
        "INSERT INTO data_quality_log VALUES (?, ?, ?, ?, ?)",
        [step_no, rule, rows_before, rows_after, revenue_affected],
    )


def save_funnel_table(con) -> None:
    """Write the funnel to CSV, adding rows removed and revenue share per step.

    revenue_share_pct is the removed revenue as a percentage of the revenue
    that existed before that step. CLAUDE.md asks for this share explicitly for
    duplicates; we show it for every step so the table is consistent.
    """
    funnel = con.execute("""
        SELECT
            step_no,
            rule,
            rows_before,
            rows_after,
            rows_before - rows_after AS rows_removed,
            ROUND(revenue_affected, 2) AS revenue_affected
        FROM data_quality_log
        ORDER BY step_no
    """).df()

    # Revenue that existed before each step: the "before" view of steps 1-5,
    # and all of clean_sales for step 6.
    revenue_before = []
    for step_no, rule, before_view, after_view in FUNNEL_STEPS:
        rows, revenue = count_rows_and_revenue(con, before_view)
        revenue_before.append(revenue)
    rows, revenue = count_rows_and_revenue(con, "clean_sales")
    revenue_before.append(revenue)

    funnel["revenue_share_pct"] = (100 * funnel["revenue_affected"] / revenue_before).round(2)

    config.TABLES_DIR.mkdir(parents=True, exist_ok=True)
    funnel.to_csv(config.TABLES_DIR / "cleaning_funnel.csv", index=False)
    print(funnel.to_string(index=False))


def save_non_product_codes_table(con) -> None:
    """List each excluded stock code with its description, rows, revenue and share.

    The counts are taken from the rows that reached rule 5, so they add up to
    the rule 5 line of the funnel. revenue_share_pct is the code's revenue as
    a percentage of all revenue that reached rule 5 (the "rows before" of that
    step), the same base the funnel uses for its rule 5 share.
    """
    rows, total_revenue = count_rows_and_revenue(con, "cleaning_step4_positive")
    codes = con.execute("""
        SELECT
            n.stock_code,
            n.reason,
            MODE(s.description) AS description,
            COUNT(s.stock_code) AS n_rows,
            ROUND(COALESCE(SUM(s.quantity * s.price), 0), 2) AS revenue,
            ROUND(100 * COALESCE(SUM(s.quantity * s.price), 0) / $total, 4) AS revenue_share_pct
        FROM non_product_codes AS n
        LEFT JOIN cleaning_step4_positive AS s ON s.stock_code = n.stock_code
        GROUP BY n.stock_code, n.reason
        ORDER BY n_rows DESC
    """, {"total": total_revenue}).df()
    codes.to_csv(config.TABLES_DIR / "non_product_codes.csv", index=False)


def save_non_product_reasons_table(con) -> None:
    """Same as above, but added up per reason (postage, gift voucher, ...).

    We let SQL do the adding up so that group totals, such as the share of all
    seven gift-voucher codes together, come from the data and not from hand
    arithmetic.
    """
    rows, total_revenue = count_rows_and_revenue(con, "cleaning_step4_positive")
    reasons = con.execute("""
        SELECT
            n.reason,
            COUNT(DISTINCT n.stock_code) AS n_codes,
            COUNT(s.stock_code) AS n_rows,
            ROUND(COALESCE(SUM(s.quantity * s.price), 0), 2) AS revenue,
            ROUND(100 * COALESCE(SUM(s.quantity * s.price), 0) / $total, 4) AS revenue_share_pct
        FROM non_product_codes AS n
        LEFT JOIN cleaning_step4_positive AS s ON s.stock_code = n.stock_code
        GROUP BY n.reason
        ORDER BY revenue DESC
    """, {"total": total_revenue}).df()
    reasons.to_csv(config.TABLES_DIR / "non_product_reasons.csv", index=False)


def save_funnel_chart(con) -> None:
    """Horizontal bar chart: rows left after each cleaning rule."""
    funnel = con.execute(
        "SELECT step_no, rule, rows_before, rows_after FROM data_quality_log ORDER BY step_no"
    ).df()
    labels = ["Raw rows"] + [f"{row.step_no}. {row.rule}" for row in funnel.itertuples()]
    counts = [funnel["rows_before"].iloc[0]] + funnel["rows_after"].tolist()

    fig, ax = plt.subplots(figsize=(10, 4.5))
    bars = ax.barh(labels, counts, color="#4C72B0")
    ax.invert_yaxis()  # first step at the top, like a funnel
    ax.bar_label(bars, labels=[f"{c:,}" for c in counts], padding=4, fontsize=9)
    ax.xaxis.set_major_formatter(StrMethodFormatter("{x:,.0f}"))
    ax.set_xlabel("Rows remaining")
    ax.set_title("Cleaning funnel: rows remaining after each rule")
    ax.set_xlim(0, max(counts) * 1.15)  # room for the labels
    fig.tight_layout()

    config.FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(config.FIGURES_DIR / "cleaning_funnel.png", dpi=150)
    plt.close(fig)


def run() -> None:
    con = db.connect_pipeline()
    db.run_sql_file(con, config.SQL_DIR / "02_clean_views.sql")
    fill_data_quality_log(con)
    save_funnel_table(con)
    save_non_product_codes_table(con)
    save_non_product_reasons_table(con)
    save_funnel_chart(con)
    con.close()


if __name__ == "__main__":
    run()
