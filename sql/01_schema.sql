-- 01_schema.sql: tables that hold raw data and the cleaning log.
-- Re-running the pipeline rebuilds them from scratch, so the database always
-- matches the code.

DROP VIEW IF EXISTS clean_sales;
DROP VIEW IF EXISTS returns;
DROP TABLE IF EXISTS raw_transactions;

-- Raw zone: one row per line in the workbook, values unchanged.
CREATE TABLE raw_transactions (
    invoice      VARCHAR,    -- text because cancellations look like 'C489449'
    stock_code   VARCHAR,    -- text because some codes contain letters ('79323P', 'POST')
    description  VARCHAR,
    quantity     INTEGER,
    invoice_date TIMESTAMP,
    price        DOUBLE,
    customer_id  BIGINT,     -- NULL when the workbook has no customer
    country      VARCHAR,
    source_sheet VARCHAR     -- which workbook sheet the row came from
);

-- One row per cleaning rule; this table becomes the cleaning funnel.
DROP TABLE IF EXISTS data_quality_log;
CREATE TABLE data_quality_log (
    step_no          INTEGER,
    rule             VARCHAR,
    rows_before      BIGINT,
    rows_after       BIGINT,
    revenue_affected DOUBLE   -- sum of quantity * price over the rows this step removed
);
