-- 02_clean_views.sql: the cleaning rules from CLAUDE.md section 7.2, as views.
--
-- Each rule is one view that reads from the previous one, so the funnel is:
--   raw_transactions -> step1 -> step2 -> step3 -> step4 -> clean_sales
-- Nothing is deleted from raw_transactions; views only choose which rows to show.
-- src/clean.py counts the rows and revenue of each view to fill data_quality_log.

DROP VIEW IF EXISTS clean_sales;
DROP VIEW IF EXISTS cleaning_step4_positive;
DROP VIEW IF EXISTS cleaning_step3_no_cancellations;
DROP VIEW IF EXISTS returns;
DROP VIEW IF EXISTS cleaning_step2_no_duplicates;
DROP VIEW IF EXISTS cleaning_step1_no_overlap;
DROP TABLE IF EXISTS non_product_codes;

-- Rule 1: overlap duplicates.
-- Sheet 'Year 2009-2010' runs to 2010-12-09 and sheet 'Year 2010-2011' starts
-- on 2010-12-01, so 1-9 Dec 2010 appears in both. We drop a row from the second
-- sheet when the first sheet has a row identical in every column except
-- source_sheet. IS NOT DISTINCT FROM treats two NULLs as equal, which a plain
-- "=" would not (description and customer_id can be NULL).
CREATE VIEW cleaning_step1_no_overlap AS
SELECT r.*
FROM raw_transactions AS r
WHERE NOT (
    r.source_sheet = 'Year 2010-2011'
    AND EXISTS (
        SELECT 1
        FROM raw_transactions AS s1
        WHERE s1.source_sheet = 'Year 2009-2010'
          AND s1.invoice = r.invoice
          AND s1.stock_code = r.stock_code
          AND s1.description IS NOT DISTINCT FROM r.description
          AND s1.quantity = r.quantity
          AND s1.invoice_date = r.invoice_date
          AND s1.price = r.price
          AND s1.customer_id IS NOT DISTINCT FROM r.customer_id
          AND s1.country = r.country
    )
);

-- Rule 2: remaining exact duplicates (identical in every column, same sheet).
-- DISTINCT keeps one copy of each identical row.
CREATE VIEW cleaning_step2_no_duplicates AS
SELECT DISTINCT *
FROM cleaning_step1_no_overlap;

-- Rule 3: cancellations. Invoices starting with 'C' are moved to the returns
-- view instead of being deleted, so return behaviour can still be studied.
CREATE VIEW returns AS
SELECT
    invoice,
    customer_id,
    stock_code,
    quantity,
    quantity * price AS line_revenue   -- negative, because quantity is negative
FROM cleaning_step2_no_duplicates
WHERE invoice LIKE 'C%';

CREATE VIEW cleaning_step3_no_cancellations AS
SELECT *
FROM cleaning_step2_no_duplicates
WHERE invoice NOT LIKE 'C%';

-- Rule 4: a sale needs a positive quantity and a positive price. Zero or
-- negative values are stock corrections, write-offs or free items, not sales.
CREATE VIEW cleaning_step4_positive AS
SELECT *
FROM cleaning_step3_no_cancellations
WHERE quantity > 0
  AND price > 0;

-- Rule 5: non-product stock codes.
-- Found by listing every code that is NOT "5 digits + optional letters" among
-- rows that survive rules 1-4, then reading each code's description.
-- Codes such as DCGS0058, SP1002, 47503J and PADS have product descriptions
-- (dog collars, a chalkboard easel, garden tools, cushion pads), so they stay.
CREATE TABLE non_product_codes (stock_code VARCHAR, reason VARCHAR);
INSERT INTO non_product_codes VALUES
    ('POST',         'postage'),                       -- "POSTAGE"
    ('DOT',          'postage'),                       -- "DOTCOM POSTAGE"
    ('C2',           'postage'),                       -- "CARRIAGE"
    ('M',            'manual adjustment'),             -- "Manual"
    ('m',            'manual adjustment'),             -- "Manual" (lower-case code)
    ('ADJUST',       'manual adjustment'),             -- "Adjustment by john on ..."
    ('ADJUST2',      'manual adjustment'),             -- "Adjustment by Peter on ..."
    ('B',            'manual adjustment'),             -- "Adjust bad debt"
    ('BANK CHARGES', 'fee'),                           -- "Bank Charges"
    ('AMAZONFEE',    'fee'),                           -- "AMAZON FEE"
    ('D',            'discount'),                      -- "Discount"
    ('TEST001',      'test'),                          -- "This is a test product."
    ('TEST002',      'test'),                          -- "This is a test product."
    -- "SAMPLES": these lines are adjustments, not product sales.
    ('S',            'samples'),
    -- Gift vouchers are a payment method, not goods. A voucher is sold once and
    -- later redeemed against real products, so counting both the voucher
    -- purchase and the products it pays for would double-count revenue.
    ('gift_0001_10', 'gift voucher'),
    ('gift_0001_20', 'gift voucher'),
    ('gift_0001_30', 'gift voucher'),
    ('gift_0001_40', 'gift voucher'),
    ('gift_0001_50', 'gift voucher'),
    ('gift_0001_70', 'gift voucher'),
    ('gift_0001_80', 'gift voucher');

-- clean_sales = product sales after rules 1-5.
-- Rule 6 (missing customer_id) is NOT applied here: those rows still count
-- towards revenue totals. has_customer lets every customer-level table filter
-- them out with "WHERE has_customer" (equivalent to customer_id IS NOT NULL).
CREATE VIEW clean_sales AS
SELECT
    s.*,
    s.quantity * s.price AS line_revenue,
    s.customer_id IS NOT NULL AS has_customer
FROM cleaning_step4_positive AS s
WHERE s.stock_code NOT IN (SELECT stock_code FROM non_product_codes);
