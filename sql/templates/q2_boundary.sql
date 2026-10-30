-- q2_boundary.sql: Q2 Boundary customers with MAX(p) < $boundary and normalised entropy.
--
-- Parameters:
--   $method   : 'bootstrap' (default) or 'gmm'
--   $boundary : upper bound on max(p), default 0.60
--   $country  : country name filter, or NULL for all countries
--   $limit    : maximum rows to return

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
        ) AS rn,
        COUNT(*) OVER (PARTITION BY sm.customer_id) AS k_segments
    FROM segment_membership AS sm
    WHERE sm.snapshot = 'S3'
      AND sm.method = $method
),
per_customer AS (
    SELECT
        customer_id,
        MAX(p) AS max_p,
        MAX(CASE WHEN rn = 1 THEN segment END) AS top_segment,
        MAX(CASE WHEN rn = 2 THEN segment END) AS second_segment,
        MAX(CASE WHEN rn = 2 THEN p END) AS second_p,
        SUM(
            CASE
                WHEN p > 0 THEN -p * LN(p) / LN(k_segments)
                ELSE 0.0
            END
        ) AS normalised_entropy
    FROM ranked
    GROUP BY customer_id
)
SELECT
    pc.customer_id,
    c.country,
    pc.top_segment,
    ROUND(pc.max_p, 4) AS max_p,
    pc.second_segment,
    ROUND(pc.second_p, 4) AS second_p,
    ROUND(pc.normalised_entropy, 4) AS normalised_entropy,
    cf.recency_days,
    cf.frequency,
    ROUND(cf.monetary, 2) AS monetary
FROM per_customer AS pc
JOIN customers AS c
  ON c.customer_id = pc.customer_id
JOIN customer_features AS cf
  ON cf.customer_id = pc.customer_id
 AND cf.snapshot = 'S3'
WHERE pc.max_p < $boundary
  AND ($country IS NULL OR c.country = $country)
ORDER BY pc.normalised_entropy DESC, pc.max_p ASC, pc.customer_id ASC
LIMIT $limit;
