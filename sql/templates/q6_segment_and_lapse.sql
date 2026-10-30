-- q6_segment_and_lapse.sql: Q6 Segment + lapse filter (two separate conditions; never multiply).
--
-- Semantics note (CLAUDE.md section 7.8):
--   Segment membership p and 90-day lapse risk p_lapse_90d both depend on
--   recency_days and frequency, so they are NOT statistically independent.
--   Therefore we filter on two separate conditions (p >= $tau1 AND p_lapse_90d >= $tau2)
--   and never multiply the two probabilities together.
--
-- Parameters:
--   $method           : 'bootstrap' (default) or 'gmm'
--   $seg              : segment name, or NULL to filter lapse across each customer's top segment
--   $tau1             : lower segment probability threshold
--   $max_p1           : upper segment probability threshold (default 1.0; 0.33 for "unlikely")
--   $only_top_segment : TRUE when segment was unhedged (or when $seg IS NULL)
--   $tau2             : lower lapse probability threshold
--   $max_p2           : upper lapse probability threshold (default 1.0; 0.33 for "unlikely")
--   $country          : country name filter, or NULL for all countries
--   $limit            : maximum rows to return

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
        ) AS seg_rank
    FROM segment_membership AS sm
    WHERE sm.snapshot = 'S3'
      AND sm.method = $method
)
SELECT
    r.customer_id,
    c.country,
    r.segment,
    ROUND(r.p, 4) AS p,
    ROUND(lr.p_lapse_90d, 4) AS p_lapse_90d,
    cf.recency_days,
    cf.frequency,
    ROUND(cf.monetary, 2) AS monetary
FROM ranked AS r
JOIN customers AS c
  ON c.customer_id = r.customer_id
JOIN customer_features AS cf
  ON cf.customer_id = r.customer_id
 AND cf.snapshot = 'S3'
JOIN lapse_risk AS lr
  ON lr.customer_id = r.customer_id
 AND lr.snapshot = 'S3'
WHERE (($seg IS NULL AND r.seg_rank = 1) OR r.segment = $seg)
  AND r.p >= $tau1
  AND r.p <= $max_p1
  AND (NOT $only_top_segment OR r.seg_rank = 1)
  AND lr.p_lapse_90d >= $tau2
  AND lr.p_lapse_90d <= $max_p2
  AND ($country IS NULL OR c.country = $country)
ORDER BY lr.p_lapse_90d DESC, r.p DESC, cf.monetary DESC, r.customer_id ASC
LIMIT $limit;
