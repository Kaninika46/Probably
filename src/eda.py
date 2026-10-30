"""Phase 1, step 3: exploratory figures on the cleaned sales.

These figures are for understanding the data before modelling. They use all of
clean_sales, including rows without a customer, because they describe the
business as a whole, not individual customers.
"""

import matplotlib

matplotlib.use("Agg")  # draw to files only; no window needed
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.ticker import StrMethodFormatter

from src import config, db

# Show axis values as 1,400,000 instead of 1.4 with a "1e6" label in the corner.
THOUSANDS = StrMethodFormatter("{x:,.0f}")


def plot_monthly_revenue(con) -> None:
    """Revenue per calendar month, to show seasonality.

    The data stops part-way through the last month, so that month's point is
    low only because it is incomplete. We read the last date from the data and
    say so on the chart, so nobody mistakes it for a real drop.
    """
    monthly = con.execute("""
        SELECT DATE_TRUNC('month', invoice_date) AS month, ROUND(SUM(line_revenue), 2) AS revenue
        FROM clean_sales
        GROUP BY month
        ORDER BY month
    """).df()
    last_date = con.execute("SELECT MAX(invoice_date) FROM clean_sales").fetchone()[0]
    monthly.to_csv(config.TABLES_DIR / "eda_monthly_revenue.csv", index=False)

    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(monthly["month"], monthly["revenue"], marker="o", color="#4C72B0")
    ax.set_title("Monthly revenue (clean product sales)")
    ax.annotate(
        f"partial month: data ends {last_date:%d %b %Y}",
        xy=(monthly["month"].iloc[-1], monthly["revenue"].iloc[-1]),
        xytext=(-160, -5), textcoords="offset points", fontsize=8,
        arrowprops={"arrowstyle": "->"},
    )
    ax.yaxis.set_major_formatter(THOUSANDS)
    ax.set_ylabel("Revenue (£)")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(config.FIGURES_DIR / "eda_monthly_revenue.png", dpi=150)
    plt.close(fig)


def plot_top_countries(con, top_n: int = 10) -> None:
    """Revenue by country for the top N countries."""
    countries = con.execute(f"""
        SELECT country, ROUND(SUM(line_revenue), 2) AS revenue
        FROM clean_sales
        GROUP BY country
        ORDER BY revenue DESC
        LIMIT {int(top_n)}
    """).df()
    countries.to_csv(config.TABLES_DIR / "eda_top_countries.csv", index=False)

    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.barh(countries["country"], countries["revenue"], color="#4C72B0")
    ax.invert_yaxis()  # biggest country at the top
    ax.set_title(f"Top {top_n} countries by revenue (clean product sales)")
    ax.xaxis.set_major_formatter(THOUSANDS)
    ax.set_xlabel("Revenue (£)")
    fig.tight_layout()
    fig.savefig(config.FIGURES_DIR / "eda_top_countries.png", dpi=150)
    plt.close(fig)


def plot_quantity_and_price(con) -> None:
    """Histograms of quantity and unit price on log scales.

    Both are heavily skewed (many small orders, a few wholesale ones), so a
    linear axis would squash almost every row into the first bar.
    """
    lines = con.execute("SELECT quantity, price FROM clean_sales").df()

    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    for ax, column, label in [(axes[0], "quantity", "Quantity per line"),
                              (axes[1], "price", "Unit price (£)")]:
        values = lines[column]
        # Bins of equal width on a log axis: each bin covers the same ratio
        # (e.g. 1-2, 2-4, 4-8) rather than the same absolute width. This works
        # because clean_sales only has quantity > 0 and price > 0.
        bins = np.geomspace(values.min(), values.max(), 50)
        ax.hist(values, bins=bins, log=True, color="#4C72B0")
        ax.set_xscale("log")
        ax.set_title(label)
        ax.set_ylabel("Number of lines (log scale)")
    fig.tight_layout()
    fig.savefig(config.FIGURES_DIR / "eda_quantity_price.png", dpi=150)
    plt.close(fig)


def save_summary_table(con) -> None:
    """Headline facts about clean_sales, saved so the report can cite them."""
    summary = con.execute("""
        SELECT
            COUNT(*) AS n_lines,
            COUNT(*) FILTER (WHERE has_customer) AS n_lines_with_customer,
            COUNT(DISTINCT invoice) AS n_invoices,
            COUNT(DISTINCT customer_id) AS n_customers,
            COUNT(DISTINCT stock_code) AS n_products,
            COUNT(DISTINCT country) AS n_countries,
            ROUND(SUM(line_revenue), 2) AS total_revenue,
            ROUND(SUM(line_revenue) FILTER (WHERE has_customer), 2) AS revenue_with_customer,
            MIN(invoice_date) AS first_invoice_date,
            MAX(invoice_date) AS last_invoice_date
        FROM clean_sales
    """).df()
    summary.to_csv(config.TABLES_DIR / "clean_sales_summary.csv", index=False)


def run() -> None:
    config.FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    config.TABLES_DIR.mkdir(parents=True, exist_ok=True)
    con = db.connect_pipeline()
    save_summary_table(con)
    plot_monthly_revenue(con)
    plot_top_countries(con)
    plot_quantity_and_price(con)
    con.close()


if __name__ == "__main__":
    run()
