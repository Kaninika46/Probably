-- q3_expected_size.sql: Q3 Expected segment size SUM(p) and Poisson-binomial variance SUM(p*(1-p)).
--
-- Semantics note (CLAUDE.md section 7.8):
--   * expected_size = SUM(p) is exact by linearity of expectation.
--   * variance = SUM(p * (1 - p)) assumes independence across customers (blocks),
--     which holds in the BID model because each customer's block is independent.
--
-- Parameters:
--   $method  : 'bootstrap' (default) or 'gmm'
--   $country : country name filter, or NULL for all countries

WITH ranked AS (
    SELECT
        sm.customer_id,
        sm.segment,
        sm.p,
        ROW_NUMBER() OVER (
            PARTITION BY sm.customer_id
            ORDER BY sm.p DESC,
                CASE sm.segment
                    WHEN 'Champions' THEN 1
                    WHEN 'Loyal' THEN 2
                    WHEN 'At-Risk' THEN 3
                    WHEN 'New' THEN 4
                    ELSE 5
                END ASC
        ) AS rn
    FROM segment_membership AS sm
    JOIN customers AS c
      ON c.customer_id = sm.customer_id
    WHERE sm.snapshot = 'S3'
      AND sm.method = $method
      AND ($country IS NULL OR c.country = $country)
)
SELECT
    r.segment,
    COUNT(*) FILTER (WHERE r.rn = 1) AS hard_count,
    ROUND(SUM(r.p), 2) AS expected_size,
    ROUND(SUM(r.p) - COUNT(*) FILTER (WHERE r.rn = 1), 2) AS expected_minus_hard,
    ROUND(SUM(r.p * (1.0 - r.p)), 2) AS variance_independent,
    ROUND(SQRT(SUM(r.p * (1.0 - r.p))), 2) AS std_dev_independent
FROM ranked AS r
GROUP BY r.segment
ORDER BY expected_size DESC, r.segment ASC;
