"""Every setting the project uses, in one place.

CLAUDE.md rule 4 says all config values live here, so that changing a date or
a threshold means editing exactly one line, and nobody has to hunt through the
code for a hard-coded number.
"""

from datetime import date
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
# PROJECT_ROOT is the folder that contains CLAUDE.md. We build every other
# path from it, so the code works no matter which folder you run it from.
PROJECT_ROOT = Path(__file__).resolve().parent.parent

DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
RAW_ZIP = RAW_DIR / "online_retail_ii.zip"
RAW_XLSX = RAW_DIR / "online_retail_II.xlsx"
RAW_PARQUET = RAW_DIR / "online_retail_II.parquet"

DB_PATH = DATA_DIR / "retail.duckdb"
APP_DB_PATH = PROJECT_ROOT / "app" / "app.duckdb"

SQL_DIR = PROJECT_ROOT / "sql"
TEMPLATES_DIR = SQL_DIR / "templates"

REPORTS_DIR = PROJECT_ROOT / "reports"
TABLES_DIR = REPORTS_DIR / "tables"
FIGURES_DIR = REPORTS_DIR / "figures"

# ---------------------------------------------------------------------------
# Dataset
# ---------------------------------------------------------------------------
DATASET_URL = "https://archive.ics.uci.edu/static/public/502/online+retail+ii.zip"

# Original column name in the workbook -> snake_case name we use everywhere.
COLUMN_RENAMES = {
    "Invoice": "invoice",
    "StockCode": "stock_code",
    "Description": "description",
    "Quantity": "quantity",
    "InvoiceDate": "invoice_date",
    "Price": "price",
    "Customer ID": "customer_id",
    "Country": "country",
}

# ---------------------------------------------------------------------------
# Snapshots (CLAUDE.md section 7.3)
# ---------------------------------------------------------------------------
# Each snapshot has a date S. Features use the 9 months before S; outcomes use
# the 90 days from S. S3 has no outcome window because it is in the future.
SNAPSHOTS = {
    "S1": {
        "snapshot_date": date(2010, 9, 10),
        "feature_start": date(2009, 12, 10),
        "feature_end": date(2010, 9, 9),
        "outcome_start": date(2010, 9, 10),
        "outcome_end": date(2010, 12, 9),
    },
    "S2": {
        "snapshot_date": date(2011, 9, 10),
        "feature_start": date(2010, 12, 10),
        "feature_end": date(2011, 9, 9),
        "outcome_start": date(2011, 9, 10),
        "outcome_end": date(2011, 12, 9),
    },
    "S3": {
        "snapshot_date": date(2011, 12, 10),
        "feature_start": date(2011, 3, 10),
        "feature_end": date(2011, 12, 9),
        "outcome_start": None,
        "outcome_end": None,
    },
}

LAPSE_WINDOW_DAYS = 90

# ---------------------------------------------------------------------------
# Modelling
# ---------------------------------------------------------------------------
RANDOM_STATE = 42  # used for every random step so results are reproducible

K_RANGE = range(2, 9)  # K = 2..8 for K-Means and GMM
GMM_COVARIANCE_TYPES = ["spherical", "tied", "diag", "full"]
GMM_N_INIT = 10
CAP_PERCENTILE = 99  # frequency and monetary are capped here before log1p

BOOTSTRAP_B = 100
BOUNDARY_P = 0.6  # a customer whose max p is below this is a "boundary" case

# Hennig-style Jaccard stability bands
JACCARD_STABLE = 0.75
JACCARD_DOUBTFUL = 0.6

TREE_MAX_DEPTH = 4
TREE_TEST_SIZE = 0.3

CALIBRATION_CV = 5
ECE_BINS = 10
BASELINE_RECENCY_DAYS = 90  # two-bin rule baseline splits at this recency

# ---------------------------------------------------------------------------
# NL hedge words -> probability thresholds (CLAUDE.md section 7.9)
# ---------------------------------------------------------------------------
HEDGE_THRESHOLDS = {
    "possibly": (">=", 0.33),
    "might": (">=", 0.33),
    "probably": (">=", 0.66),
    "likely": (">=", 0.66),
    "very likely": (">=", 0.90),
    "highly likely": (">=", 0.90),
    "almost certainly": (">=", 0.95),
    "definitely": (">=", 0.95),
    "unlikely": ("<=", 0.33),
}
