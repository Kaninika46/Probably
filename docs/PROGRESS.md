# Progress

## Phase 0: Scaffold (done)

**What was done**
- Created the repo layout, `.gitignore`, `requirements.txt`, `src/config.py`, `src/db.py`, `data/download.py`, `pytest.ini` and `tests/test_setup.py`.
- `requirements.txt` pins the exact versions pip installed into a fresh Python 3.12.10 venv.
- `data/download.py` checked the UCI URL `https://archive.ics.uci.edu/static/public/502/online+retail+ii.zip` (HTTP 200). It downloaded the zip (45,622,418 bytes) and extracted `online_retail_II.xlsx` (45,622,278 bytes).
- `pytest`: 2 passed. One test checks that the snapshot windows are ordered and the other checks that the app connection refuses writes.

**Changes to the spec (agreed with the user)**
- Python version changed from 3.11 to **3.12** (CLAUDE.md section 4). The machine only had 3.10, so the user installed 3.12.10.
- `clean_sales` keeps rows without a `customer_id`, flagged with `has_customer = false`, so revenue totals stay complete. Every customer-level table filters on `customer_id IS NOT NULL` (CLAUDE.md section 6 reworded so the spec no longer contradicts itself).
- Added `src/eda.py` for the Phase 1 exploratory figures (CLAUDE.md section 5).

**Open items**
- `docs/architecture.png` is missing. The architecture diagram was not found on this machine.
- The spaCy model `en_core_web_sm` is not installed yet. It will be pinned by wheel URL in Phase 7 (CLAUDE.md section 7.11).

## Phase 1: Ingest, cleaning, EDA (done)

**What was done**
- `src/ingest.py` reads the sheet names from the workbook (they are `Year 2009-2010` and `Year 2010-2011`, as CLAUDE.md expected). It renames the columns to snake_case, adds `source_sheet`, caches the data to `data/raw/online_retail_II.parquet` and loads `raw_transactions`.
  - Text columns (`invoice`, `stock_code`, `description`, `country`) are stored as text, because Excel mixes numbers and text in them.
  - `customer_id` is stored as a whole number. The code first checks that no ID has a fractional part.
- `sql/02_clean_views.sql` implements the six rules as a chain of views. The non-product codes are kept in a `non_product_codes` table, with a comment on each code.
- `src/clean.py` fills `data_quality_log` and writes `reports/tables/cleaning_funnel.csv`, `reports/tables/non_product_codes.csv` and `reports/figures/cleaning_funnel.png`.
- `src/eda.py` writes three figures (`eda_monthly_revenue.png`, `eda_top_countries.png`, `eda_quantity_price.png`) and their tables, plus `reports/tables/clean_sales_summary.csv`.
- `src/pipeline.py` runs Phase 1 with `--phase 1` or `--all`.
- `pytest`: 11 passed (9 cleaning tests and 2 setup tests).

**Key numbers** (from `reports/tables/`)
- Raw rows: 525,461 (Year 2009-2010) + 541,910 (Year 2010-2011) = 1,067,371.
- The sheets overlap: the first sheet ends 2010-12-09 20:01 and the second starts 2010-12-01 08:26.

| Step | Rule | Rows before | Rows after | Revenue affected (£) |
|---|---|---|---|---|
| 1 | Overlap duplicates between sheets | 1,067,371 | 1,044,848 | 377,488.45 |
| 2 | Remaining exact duplicates | 1,044,848 | 1,033,036 | 54,228.42 |
| 3 | Cancellations moved to returns | 1,033,036 | 1,013,932 | -1,462,050.61 |
| 4 | Quantity or price not positive | 1,013,932 | 1,007,913 | -158,676.14 |
| 5 | Non-product stock codes | 1,007,913 | 1,003,357 | 832,398.81 |
| 6 | Missing customer_id (excluded from customer analysis) | 1,003,357 | 776,596 | 2,575,278.90 |

- `clean_sales`: 1,003,357 lines, 39,516 invoices, 5,852 customers, 4,896 products, 43 countries, £19,643,861.64 revenue. Of that revenue, £17,068,582.74 has a customer.

**Decisions made in this phase**
- Rule 1 drops a row from the second sheet when the first sheet has an identical row in every other column.
- Rule 5 excludes 21 stock codes (listed in `reports/tables/non_product_codes.csv`, totals per reason in `reports/tables/non_product_reasons.csv`): postage, carriage, manual adjustments, bad debt, bank and Amazon fees, a discount code, test products, `S` (samples) and seven gift-voucher codes.
  - The user confirmed excluding `S` and the gift vouchers. Samples are adjustments, not product sales. Vouchers are a payment method, so counting the voucher purchase and its later redemption would double-count revenue.
  - The 7 voucher codes are 0.0086% of the revenue that reached rule 5.
- `revenue_share_pct` in both non-product tables uses the revenue that reached rule 5 as its base, the same base as the funnel's rule 5 share.
- `revenue_affected` = revenue before the step minus revenue after. It is negative for steps 3 and 4 because the rows removed there have negative quantities or prices.

**Open items**
- `docs/architecture.png` is still missing.
