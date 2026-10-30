# Phase 2 explained: snapshots, customer features and outcomes

## What we did, in plain words

**1. Build one master `customers` table.** Every customer who appears in `clean_sales` (with `has_customer = true`) gets one row in `customers`: their `customer_id`, their `country`, and the dates of their first and last purchase (`first_purchase`, `last_purchase`). Out of 5,852 customers, 12 have orders recorded under two different countries; `ARG_MAX(country, invoice_date)` picks the country on their most recent order so that `customer_id` is a strict primary key.

**2. Cut the timeline into three snapshots (`S1`, `S2`, `S3`).** If we computed features and lapse labels from the whole two-year dataset at once, future purchases would leak into past features. Instead, we freeze the calendar at three snapshot dates defined in `src/config.py` and copied into the `snapshots` table by `src/features.py`:

- **S1 (`2010-09-10`):** feature window `2009-12-10` to `2010-09-09`; outcome window `2010-09-10` to `2010-12-09`. Used in Phase 5 to train and cross-validate the lapse model.
- **S2 (`2011-09-10`):** feature window `2010-12-10` to `2011-09-09`; outcome window `2011-09-10` to `2011-12-09`. Held out to test the lapse model once on a full year later.
- **S3 (`2011-12-10`):** feature window `2011-03-10` to `2011-12-09`; no outcome window because `2011-12-10` is the day after the dataset ends (`2011-12-09`). Used in Phases 3–6 to segment current customers and score their future 90-day lapse risk for the app.

**3. Compute five features per active customer (`customer_features`).** A customer belongs to a snapshot if they made at least one clean sale in its 9-month feature window:

- `recency_days`: `snapshot_date` minus the date of the customer's last purchase inside the feature window.
- `frequency`: count of distinct invoices inside the feature window.
- `monetary`: sum of `line_revenue` (gross product sales) inside the feature window.
- `tenure_days`: `snapshot_date` minus the customer's earliest purchase across all cleaned sales strictly before `snapshot_date`.
- `avg_basket`: `monetary / frequency`.

**4. Compute 90-day outcomes for S1 and S2 (`outcomes`).** For every customer in S1 and S2, `purchased_next_90d` is `1` if they made at least one clean sale in `[outcome_start, outcome_end]`, and `0` otherwise. Lapse (no purchase in 90 days) is `1 - purchased_next_90d`.

| Snapshot | Snapshot date | Feature window | Outcome window | Customers | Mean / median recency (d) | Mean / median frequency | Mean / median monetary (£) | Mean / median tenure (d) | Mean / median basket (£) | Purchased next 90d | Lapsed next 90d | Base lapse rate |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| S1 | 2010-09-10 | 2009-12-10 – 2010-09-09 | 2010-09-10 – 2010-12-09 | 3,256 | 87.89 / 72.0 | 3.53 / 2.0 | 1,598.59 / 585.77 | 181.07 / 192.0 | 366.80 / 287.52 | 1,908 (58.60%) | 1,348 | 41.40% |
| S2 | 2011-09-10 | 2010-12-10 – 2011-09-09 | 2011-09-10 – 2011-12-09 | 3,247 | 88.36 / 69.0 | 3.40 / 2.0 | 1,555.65 / 552.00 | 405.23 / 460.0 | 401.43 / 283.12 | 1,871 (57.62%) | 1,376 | 42.38% |
| S3 | 2011-12-10 | 2011-03-10 – 2011-12-09 | — | 3,961 | 71.38 / 43.0 | 3.70 / 2.0 | 1,768.34 / 631.89 | 436.50 / 478.0 | 408.99 / 296.64 | — | — | — |

Source: `reports/tables/snapshot_summary.csv`.

## Likely viva questions

**1. Why do we need three snapshots instead of computing RFM once on the whole dataset?**
To predict whether a customer will lapse in the next 90 days, we need a date `S` where we stop looking at features and start watching the next 90 days for the outcome. Using S1 (`2010-09-10`) for training and S2 (`2011-09-10`) for testing mimics how a real model is deployed: trained on past behaviour and tested a year later, with both outcome windows covering the same autumn/Christmas season (September to December). S3 (`2011-12-10`) sits at the end of the dataset so the app shows the most up-to-date customer base (3,961 active customers).

**2. How do you guarantee there is no data leakage between features and outcomes?**
In `sql/03_features.sql`, the feature window ends the day before `snapshot_date` (`feature_end = S - 1 day`), and `tenure_days` filters on `CAST(invoice_date AS DATE) < snapshot_date`. The outcome window starts on `snapshot_date` (`[outcome_start, outcome_end]`). `tests/test_features.py` verifies both: it checks that `recency_days >= 1` for every row and recomputes all features after discarding every transaction with `date >= S`, confirming zero mismatches across all 10,464 `(customer_id, snapshot)` rows.

**3. Why are S1 and S2 placed exactly one year apart (`2010-09-10` and `2011-09-10`)?**
As our Phase 1 EDA showed (`reports/tables/eda_monthly_revenue.csv`), retail revenue peaks sharply in November. Placing both S1 and S2 on 10 September means both 90-day outcome windows (`10 Sep – 9 Dec`) span the exact same pre-Christmas quarter. As a result, the base lapse rates are almost identical: 41.40% in S1 (1,348 of 3,256 customers) and 42.38% in S2 (1,376 of 3,247 customers).

**4. Why does S3 have more customers (3,961) and lower recency (median 43.0 days) than S1 (3,256; median 72.0 days) and S2 (3,247; median 69.0 days)?**
S3's feature window (`2011-03-10` to `2011-12-09`) includes November and early December 2011—the busiest shopping weeks of the year—whereas S1 and S2 stop on 9 September, before the autumn peak. More customers buy during the autumn surge, so more customers are active in the window and their most recent purchase is closer to the snapshot date.

**5. Why is `tenure_days` computed from all data before `S` while `frequency` and `monetary` use only the 9-month feature window?**
`frequency` and `monetary` measure *recent* activity level over a fixed 9-month horizon so that every snapshot compares customers over the same window length. `tenure_days` measures how long the business has known the customer up to date `S`, which requires looking back to their very first purchase prior to `S` (while still excluding anything on or after `S`). That is why mean tenure grows from 181.07 days in S1 to 405.23 days in S2 and 436.50 days in S3 as the dataset accumulates history.
