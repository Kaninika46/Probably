"""Phase 1, step 1: load the raw workbook into DuckDB without changing any values.

Reading a 45 MB xlsx takes minutes, so the first run caches both sheets to a
parquet file and later runs read the parquet instead.
"""

import openpyxl
import pandas as pd

from src import config, db


def read_sheet_names() -> list[str]:
    """Read the sheet names from the workbook instead of assuming them."""
    workbook = openpyxl.load_workbook(config.RAW_XLSX, read_only=True)
    names = workbook.sheetnames
    workbook.close()
    return names


def fix_column_types(df: pd.DataFrame) -> pd.DataFrame:
    """Give each column one consistent type, without changing any values.

    Excel stores most invoice numbers as numbers but cancellations as text
    ("C489449"), so pandas gives these columns mixed types. We turn them into
    text so that "starts with C" works for every row. A few descriptions are
    also stored as numbers in Excel, so all four text columns get the same
    treatment. The "string" type keeps blank cells as missing (NULL) instead of
    turning them into the word "nan".

    Customer IDs arrive as decimals (13085.0) only because the column contains
    blanks. We store them as whole numbers and keep the blanks as NULL. We
    check first that no ID has a fractional part, so nothing is rounded.
    """
    for column in ["invoice", "stock_code", "description", "country"]:
        df[column] = df[column].astype("string")

    ids = df["customer_id"].dropna()
    if not (ids == ids.round()).all():
        raise ValueError("Some customer IDs have a fractional part; refusing to convert.")
    df["customer_id"] = df["customer_id"].astype("Int64")
    return df


def read_workbook() -> pd.DataFrame:
    """Read both sheets, rename the columns to snake_case and tag the source sheet."""
    frames = []
    for sheet in read_sheet_names():
        print(f"Reading sheet '{sheet}' (this is slow the first time)...")
        sheet_df = pd.read_excel(config.RAW_XLSX, sheet_name=sheet)
        sheet_df = sheet_df.rename(columns=config.COLUMN_RENAMES)
        # Remember which sheet each row came from; rule 1 of cleaning needs it.
        sheet_df["source_sheet"] = sheet
        frames.append(sheet_df)
    combined = pd.concat(frames, ignore_index=True)
    return fix_column_types(combined)


def load_raw_frame() -> pd.DataFrame:
    """Return the raw rows, using the parquet cache if it exists."""
    if config.RAW_PARQUET.exists():
        print(f"Using cached {config.RAW_PARQUET.name}")
        return pd.read_parquet(config.RAW_PARQUET)
    df = read_workbook()
    df.to_parquet(config.RAW_PARQUET, index=False)
    print(f"Cached to {config.RAW_PARQUET.name}")
    return df


def load_into_duckdb(df: pd.DataFrame) -> None:
    """Create the schema and copy the rows into raw_transactions exactly as read."""
    con = db.connect_pipeline()
    db.run_sql_file(con, config.SQL_DIR / "01_schema.sql")
    # DuckDB can read a pandas DataFrame that is in scope by its variable name.
    con.execute("INSERT INTO raw_transactions SELECT * FROM df")
    print_row_counts(con)
    con.close()


def print_row_counts(con) -> None:
    """Print rows per sheet and the total, as CLAUDE.md section 7.1 asks.

    The same numbers, plus each sheet's first and last date, are saved to
    reports/tables/raw_row_counts.csv so the report can cite them. The dates
    show where the two sheets overlap, which is why cleaning rule 1 exists.
    """
    counts = con.execute("""
        SELECT
            source_sheet,
            COUNT(*) AS n_rows,
            MIN(invoice_date) AS first_invoice_date,
            MAX(invoice_date) AS last_invoice_date
        FROM raw_transactions
        GROUP BY source_sheet
        ORDER BY source_sheet
    """).df()
    for row in counts.itertuples():
        print(f"  {row.source_sheet}: {row.n_rows:,} rows")
    print(f"  Total: {counts['n_rows'].sum():,} rows")

    config.TABLES_DIR.mkdir(parents=True, exist_ok=True)
    counts.to_csv(config.TABLES_DIR / "raw_row_counts.csv", index=False)


def run() -> None:
    df = load_raw_frame()
    load_into_duckdb(df)


if __name__ == "__main__":
    run()
