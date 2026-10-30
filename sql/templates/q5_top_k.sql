-- q5_top_k.sql: Q5 Top-k members of a segment ordered by p DESC (exact).
--
-- Parameters:
--   $method  : 'bootstrap' (default) or 'gmm'
--   $seg     : segment name ('Champions', 'Loyal', 'At-Risk', 'New', 'Hibernating')
--   $k       : integer number of customers to return
--   $country : country name filter, or NULL for all countries

SELECT
    sm.customer_id,
    c.country,
    sm.segment,
    ROUND(sm.p, 4) AS p,
    cf.recency_days,
    cf.frequency,
    ROUND(cf.monetary, 2) AS monetary,
    ROUND(lr.p_lapse_90d, 4) AS p_lapse_90d
FROM segment_membership AS sm
JOIN customers AS c
  ON c.customer_id = sm.customer_id
JOIN customer_features AS cf
  ON cf.customer_id = sm.customer_id
 AND cf.snapshot = sm.snapshot
LEFT JOIN lapse_risk AS lr
  ON lr.customer_id = sm.customer_id
 AND lr.snapshot = sm.snapshot
WHERE sm.snapshot = 'S3'
  AND sm.method = $method
  AND sm.segment = $seg
  AND ($country IS NULL OR c.country = $country)
ORDER BY sm.p DESC, cf.monetary DESC, sm.customer_id ASC
LIMIT $k;
