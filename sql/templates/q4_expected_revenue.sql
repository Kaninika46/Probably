-- q4_expected_revenue.sql: Q4 Expected revenue SUM(p * monetary) per segment (exact).
--
-- Parameters:
--   $method  : 'bootstrap' (default) or 'gmm'
--   $country : country name filter, or NULL for all countries

WITH ranked AS (
    SELECT
        sm.customer_id,
        sm.segment,
        sm.p,
        cf.monetary,
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
    JOIN customer_features AS cf
      ON cf.customer_id = sm.customer_id
     AND cf.snapshot = sm.snapshot
    JOIN customers AS c
      ON c.customer_id = sm.customer_id
    WHERE sm.snapshot = 'S3'
      AND sm.method = $method
      AND ($country IS NULL OR c.country = $country)
)
SELECT
    r.segment,
    ROUND(SUM(CASE WHEN r.rn = 1 THEN r.monetary ELSE 0.0 END), 2) AS hard_revenue,
    ROUND(SUM(r.p * r.monetary), 2) AS expected_revenue,
    ROUND(
        SUM(r.p * r.monetary) - SUM(CASE WHEN r.rn = 1 THEN r.monetary ELSE 0.0 END),
        2
    ) AS expected_minus_hard_revenue,
    ROUND(
        100.0 * SUM(r.p * r.monetary) / NULLIF(SUM(SUM(r.p * r.monetary)) OVER (), 0.0),
        2
    ) AS expected_revenue_share_pct
FROM ranked AS r
GROUP BY r.segment
ORDER BY expected_revenue DESC, r.segment ASC;
