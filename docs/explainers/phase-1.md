# Phase 1 explained: loading and cleaning the data

## What we did, in plain words

**1. Load the raw data without changing it.** The UCI workbook has two sheets, one per year. `src/ingest.py` reads both, gives the columns simple names (`Customer ID` becomes `customer_id`), and records which sheet each row came from. The rows go into the `raw_transactions` table exactly as they were. Every cleaning step after this is a *view*: a saved query that chooses rows to show. So the raw data is never edited, and any rule can be undone by changing its view.

**2. Clean in six steps, and measure every step.** Each rule is one view that reads from the previous one. `src/clean.py` counts the rows and revenue of every view and writes the difference to `data_quality_log`. That table is our *cleaning funnel*: it shows exactly what each rule removed, measured from the data.

| Step | Rule | Rows before | Rows after | Revenue affected (£) |
|---|---|---|---|---|
| 1 | Overlap duplicates between sheets | 1,067,371 | 1,044,848 | 377,488.45 |
| 2 | Remaining exact duplicates | 1,044,848 | 1,033,036 | 54,228.42 |
| 3 | Cancellations moved to returns | 1,033,036 | 1,013,932 | -1,462,050.61 |
| 4 | Quantity or price not positive | 1,013,932 | 1,007,913 | -158,676.14 |
| 5 | Non-product stock codes | 1,007,913 | 1,003,357 | 832,398.81 |
| 6 | Missing customer_id (excluded from customer analysis) | 1,003,357 | 776,596 | 2,575,278.90 |

Source: `reports/tables/cleaning_funnel.csv`; chart: `reports/figures/cleaning_funnel.png`.

- **Step 1:** the first sheet ends on 2010-12-09 and the second starts on 2010-12-01, so the first nine days of December 2010 appear twice. We keep the first sheet's copy.
- **Step 2:** some lines appear twice even within one sheet. We keep one copy of each.
- **Step 3:** invoices starting with `C` are cancellations. They go to a separate `returns` view instead of being thrown away. Their revenue is negative because their quantities are negative.
- **Step 4:** a real sale must have a positive quantity and a positive price. Lines with zero or negative values are stock corrections or write-offs.
- **Step 5:** some stock codes aren't products, for example `POST` (postage), `M` (manual adjustments) and `AMAZONFEE`. We found them by listing every code that does not look like a normal product code (5 digits, sometimes followed by letters) and reading its description. The 21 excluded codes, with their rows and revenue, are in `reports/tables/non_product_codes.csv`.
- **Step 6:** some sales have no customer ID. We keep them in `clean_sales` so total revenue is complete, but every customer-level table will leave them out (`has_customer` = false).

**3. Look at the data (EDA).** `src/eda.py` draws three figures from `clean_sales`:
- Monthly revenue peaks in November both years: £1,429,700.78 in November 2010 and £1,452,115.98 in November 2011 (`reports/tables/eda_monthly_revenue.csv`). The last point, £614,490.92 for December 2011, is low only because the data ends on 9 December 2011. The chart says so.
- The United Kingdom brings in £16,801,019.39 of the £19,643,861.64 clean revenue (`eda_top_countries.csv`, `clean_sales_summary.csv`).
- Quantity and price are both very skewed: most lines are small, a few are huge wholesale orders. That's why we plot them on log scales, and why Phase 3 will apply `log1p` before clustering.

After cleaning, `clean_sales` has 1,003,357 lines, 39,516 invoices, 5,852 customers, 4,896 products and 43 countries (`reports/tables/clean_sales_summary.csv`).

## Likely viva questions

**1. Why didn't you just delete the bad rows?**
The raw table is never edited, so we can always check our work against the original. Each rule is a view, which is a saved query, so changing a rule means editing one SQL statement and re-running. Cancellations in particular go to the `returns` view (19,104 rows) rather than being deleted, because returns may matter later.

**2. How do you know your cleaning didn't create or lose rows by mistake?**
`tests/test_cleaning.py` checks that the funnel starts from all 1,067,371 raw rows, that no step increases the row count, and that each step starts where the previous one ended. It also checks that `clean_sales` has no zero or negative quantity or price, no cancellations and no excluded stock codes, and that `returns` only contains `C` invoices. All 11 tests pass.

**3. Why are the revenue numbers for steps 3 and 4 negative?**
`revenue_affected` is the revenue before a step minus the revenue after it, which is the total `quantity × price` of the rows removed. Cancelled lines have negative quantities, so removing them takes away -£1,462,050.61. In step 4 some of the removed lines have negative quantities or prices, and they outweigh the rest, so the total is also negative (-£158,676.14).

**4. Rows without a customer are 13.11% of clean revenue. Why not throw them away?**
They are real sales, so dropping them would understate the business's revenue. But we can't build customer features for a row with no customer. So we keep them in `clean_sales` for totals (£19,643,861.64) and leave them out of every customer table. The revenue that has a customer is £17,068,582.74, and step 6 of the funnel shows the difference: 226,761 rows and £2,575,278.90.

**5. How did you decide which stock codes are not products?**
We listed every code that doesn't match the normal pattern (5 digits, optionally followed by letters) among rows that survived steps 1–4, then read each one's description. Postage, carriage, manual adjustments, bad debt, bank and Amazon fees, a discount code and test products were clearly not merchandise. Samples (`S`) and gift vouchers were judgement calls. We excluded vouchers because they are prepaid money rather than goods. Codes with real product descriptions, like the `DCGS…` pet products, were kept. Together, the 21 excluded codes cover 4,556 rows and £832,398.81, and each code's numbers are in `reports/tables/non_product_codes.csv`.
