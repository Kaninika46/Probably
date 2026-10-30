-- q1_confident.sql: Q1 Confident segment members (exact semantics).
--
-- Parameters:
--   $method           : 'bootstrap' (default) or 'gmm'
--   $seg              : segment name ('Champions', 'Loyal', 'At-Risk', 'New', 'Hibernating')
--   $tau              : lower probability threshold (e.g. 0.66 for "probably")
--   $max_p            : upper probability threshold (default 1.0; 0.33 for "unlikely")
--   $only_top_segment : TRUE when no hedge word was given (hard-label most probable segment)
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
    cf.recency_days,
    cf.frequency,
    ROUND(cf.monetary, 2) AS monetary,
    ROUND(lr.p_lapse_90d, 4) AS p_lapse_90d
FROM ranked AS r
JOIN customers AS c
  ON c.customer_id = r.customer_id
JOIN customer_features AS cf
  ON cf.customer_id = r.customer_id
 AND cf.snapshot = 'S3'
LEFT JOIN lapse_risk AS lr
  ON lr.customer_id = r.customer_id
 AND lr.snapshot = 'S3'
WHERE r.segment = $seg
  AND r.p >= $tau
  AND r.p <= $max_p
  AND (NOT $only_top_segment OR r.seg_rank = 1)
  AND ($country IS NULL OR c.country = $country)
ORDER BY r.p DESC, cf.monetary DESC, r.customer_id ASC
LIMIT $limit;
