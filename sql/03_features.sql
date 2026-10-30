-- 03_features.sql: build customers, customer_features (S1, S2, S3) and outcomes (S1, S2).
--
-- Before running this file, src/features.py loads the snapshot dates from
-- src/config.py into the `snapshots` table so that dates live in one place.
-- Every table here filters clean_sales on `WHERE has_customer`, because rows
-- without a customer_id cannot belong to a customer profile.

DROP TABLE IF EXISTS outcomes;
DROP TABLE IF EXISTS customer_features;
DROP TABLE IF EXISTS customers;

-- One row per known customer across all cleaned product sales.
-- Twelve of the 5,852 customers have orders recorded under two countries;
-- ARG_MAX(country, invoice_date) picks the country on their most recent order
-- so that customer_id is a strict primary key.
CREATE TABLE customers (
    customer_id    BIGINT PRIMARY KEY,
    country        VARCHAR,
    first_purchase DATE,
    last_purchase  DATE
);

INSERT INTO customers
SELECT
    customer_id,
    ARG_MAX(country, invoice_date) AS country,
    MIN(CAST(invoice_date AS DATE)) AS first_purchase,
    MAX(CAST(invoice_date AS DATE)) AS last_purchase
FROM clean_sales
WHERE has_customer
GROUP BY customer_id;

-- RFM + tenure + average basket for each customer active in a snapshot's
-- 9-month feature window (CLAUDE.md section 7.3).
--
-- Leakage rule:
--   * recency_days, frequency, monetary and avg_basket use ONLY sales with
--     invoice_date (as a date) between feature_start and feature_end.
--   * tenure_days uses the customer's earliest purchase across all data
--     strictly before snapshot_date (CAST(invoice_date AS DATE) < snapshot_date).
--   * No feature ever reads a row on or after snapshot_date.
CREATE TABLE customer_features (
    customer_id  BIGINT,
    snapshot     VARCHAR,
    recency_days INTEGER,
    frequency    INTEGER,
    monetary     DOUBLE,
    tenure_days  INTEGER,
    avg_basket   DOUBLE,
    PRIMARY KEY (customer_id, snapshot)
);

INSERT INTO customer_features
WITH first_seen_before_snapshot AS (
    SELECT
        sn.snapshot,
        cs.customer_id,
        MIN(CAST(cs.invoice_date AS DATE)) AS first_date_before_s
    FROM snapshots AS sn
    JOIN clean_sales AS cs
      ON cs.has_customer
     AND CAST(cs.invoice_date AS DATE) < sn.snapshot_date
    GROUP BY sn.snapshot, cs.customer_id
),
window_activity AS (
    SELECT
        sn.snapshot,
        sn.snapshot_date,
        cs.customer_id,
        MAX(CAST(cs.invoice_date AS DATE)) AS last_date_in_window,
        COUNT(DISTINCT cs.invoice) AS frequency,
        SUM(cs.line_revenue) AS monetary
    FROM snapshots AS sn
    JOIN clean_sales AS cs
      ON cs.has_customer
     AND CAST(cs.invoice_date AS DATE) BETWEEN sn.feature_start AND sn.feature_end
    GROUP BY sn.snapshot, sn.snapshot_date, cs.customer_id
)
SELECT
    w.customer_id,
    w.snapshot,
    CAST(w.snapshot_date - w.last_date_in_window AS INTEGER) AS recency_days,
    w.frequency,
    w.monetary,
    CAST(w.snapshot_date - f.first_date_before_s AS INTEGER) AS tenure_days,
    w.monetary / w.frequency AS avg_basket
FROM window_activity AS w
JOIN first_seen_before_snapshot AS f
  ON f.snapshot = w.snapshot
 AND f.customer_id = w.customer_id;

-- Outcomes for S1 and S2 only (S3 is in the future, so its outcome window is NULL).
-- purchased_next_90d = 1 if the customer made at least one clean sale in the
-- 90-day outcome window [outcome_start, outcome_end], else 0.
-- Lapse is defined as 1 - purchased_next_90d.
CREATE TABLE outcomes (
    customer_id        BIGINT,
    snapshot           VARCHAR,
    purchased_next_90d INTEGER,
    PRIMARY KEY (customer_id, snapshot)
);

INSERT INTO outcomes
SELECT
    cf.customer_id,
    cf.snapshot,
    CASE
        WHEN EXISTS (
            SELECT 1
            FROM clean_sales AS cs
            WHERE cs.has_customer
              AND cs.customer_id = cf.customer_id
              AND CAST(cs.invoice_date AS DATE) BETWEEN sn.outcome_start AND sn.outcome_end
        ) THEN 1
        ELSE 0
    END AS purchased_next_90d
FROM customer_features AS cf
JOIN snapshots AS sn
  ON sn.snapshot = cf.snapshot
WHERE sn.outcome_start IS NOT NULL
  AND sn.outcome_end IS NOT NULL;
