# Phase 6 explained: probabilistic SQL templates Q1–Q6, possible-worlds verification and `app.duckdb`

## What we did, in plain words

**1. Write the six parameterised probabilistic SQL templates (`sql/templates/q1_confident.sql` … `q6_segment_and_lapse.sql`).**
Every query from the online app or NL engine runs through one of six DuckDB parameterised SQL files (`$method`, `$seg`, `$tau`, `$k`, `$country`, etc.), validated by `src/prob_queries.py`:

| ID | Template file | Purpose | Probabilistic semantics |
|---|---|---|---|
| **Q1** | `q1_confident.sql` | Customers in `$seg` with membership probability $p \ge \tau$ (or $p \le 0.33$ for *"unlikely"*, or top segment when unhedged) | **Exact** tuple-level confidence threshold |
| **Q2** | `q2_boundary.sql` | Boundary customers with $\max_s p_s < \text{boundary}$ (default $0.60$) and normalised Shannon entropy $-\frac{1}{\ln 5}\sum_s p_s \ln p_s$ | **Exact** per-block uncertainty query |
| **Q3** | `q3_expected_size.sql` | Expected segment size $\sum_i p_{i,s}$ and Poisson-binomial variance $\sum_i p_{i,s}(1 - p_{i,s})$ | Mean **exact** by linearity of expectation; variance **assumes independence** across customer blocks |
| **Q4** | `q4_expected_revenue.sql` | Expected 9-month revenue $\sum_i p_{i,s} \times \text{monetary}_i$ per segment | **Exact** by linearity of expectation |
| **Q5** | `q5_top_k.sql` | Top-$k$ most confident members of `$seg` (`ORDER BY p DESC, monetary DESC LIMIT $k`) | **Exact** ranking on posterior probability |
| **Q6** | `q6_segment_and_lapse.sql` | Joint filter $p \ge \tau_1 \text{ AND } p_{\text{lapse\_90d}} \ge \tau_2$ | Two **separate** threshold predicates; **never multiply** $p \times p_{\text{lapse\_90d}}$ because both depend on recency and frequency |

**2. Compare hard K-Means counts with GMM and bootstrap expected sizes (`reports/tables/kmeans_vs_expected_sizes.csv`).**

| Segment | K-Means hard count | GMM hard count | GMM expected size $\sum p$ (± std dev) | Bootstrap hard count | Bootstrap expected size $\sum p$ (± std dev) |
|---|---|---|---|---|---|
| **Champions** | 364 | 258 | 278.63 (± 7.43) | 278 | 290.55 (± 5.63) |
| **Loyal** | 887 | 1,105 | 1,073.79 (± 14.71) | 1,116 | 1,110.32 (± 10.22) |
| **At-Risk** | 901 | 933 | 943.04 (± 16.99) | 928 | 941.95 (± 10.91) |
| **New** | 736 | 636 | 670.19 (± 14.07) | 634 | 643.37 (± 7.81) |
| **Hibernating** | 1,073 | 1,029 | 995.35 (± 12.79) | 1,005 | 974.81 (± 8.60) |
| **Total** | **3,961** | **3,961** | **3,961.00** | **3,961** | **3,961.00** |

**3. Compare hard vs expected segment revenue (`reports/tables/q4_expected_revenue_bootstrap.csv`, `reports/tables/q4_expected_revenue_gmm.csv`).**
Under hard labels, a high-spending customer on the border between `Champions` (`p = 0.48`) and `Loyal` (`p = 0.52`) gives 100% of their spend to `Loyal` and £0 to `Champions`. Q4 weights each customer's spend by $p_{i,s}$:
- Under `bootstrap`, `Champions` expected revenue is **£3,419,094.68** (48.81% of total S3 revenue £7,004,392.66), which is **+£80,613.84 higher** than their hard-label revenue (£3,338,480.84), while `Loyal` expected revenue is **£2,259,067.53** (**-£80,150.49** vs hard revenue £2,339,218.02).
- Under `gmm`, `Champions` expected revenue is **£3,319,358.44** (**+£59,283.40** vs hard revenue £3,260,075.04), and `Loyal` is **£2,279,463.10** (**-£101,569.43** vs hard revenue £2,381,032.53).

**4. Verify Q3 with a 10,000-world Monte Carlo sampler (`src/worlds.py`, `reports/tables/possible_worlds_q3_check.csv`).**
We draw $M = 10,000$ independent possible worlds (`random_state=42`) by sampling one segment per customer according to their BID probability vector:

| Method | Segment | Hard count $N$ | SQL expected size $\sum p$ | Monte Carlo mean | $|\text{MC} - \text{SQL}|$ | SQL variance $\sum p(1-p)$ | MC variance | 95% MC interval | $P(\text{size} \ge N)$ |
|---|---|---|---|---|---|---|---|---|---|
| `bootstrap` | Champions | 278 | 290.55 | 290.59 | 0.0448 | 31.75 | 31.91 | [280, 302] | **0.9912** |
| `bootstrap` | Loyal | 1,116 | 1,110.32 | 1,110.36 | 0.0354 | 104.49 | 104.04 | [1,090, 1,130] | 0.3089 |
| `bootstrap` | At-Risk | 928 | 941.95 | 941.92 | 0.0306 | 119.03 | 119.21 | [921, 963] | 0.9081 |
| `bootstrap` | New | 634 | 643.37 | 643.46 | 0.0934 | 60.92 | 60.06 | [628, 659] | 0.9044 |
| `bootstrap` | Hibernating | 1,005 | 974.81 | 974.67 | 0.1430 | 74.03 | 75.08 | [958, 991] | 0.0001 |
| `gmm` | Champions | 258 | 278.63 | 278.65 | 0.0184 | 55.20 | 54.87 | [264, 293] | **0.9984** |
| `gmm` | Loyal | 1,105 | 1,073.79 | 1,073.81 | 0.0179 | 216.27 | 218.82 | [1,045, 1,103] | 0.0183 |
| `gmm` | At-Risk | 933 | 943.04 | 942.93 | 0.1087 | 288.77 | 288.50 | [909, 976] | 0.7300 |
| `gmm` | New | 636 | 670.19 | 670.37 | 0.1805 | 197.89 | 201.19 | [642, 698] | 0.9930 |
| `gmm` | Hibernating | 1,029 | 995.35 | 995.24 | 0.1081 | 163.64 | 167.78 | [970, 1,021] | 0.0055 |

**5. Export the read-only S3 database `app/app.duckdb` (`src/export_app_db.py`).**
`app/app.duckdb` is **1,847,296 bytes (1.80 MB)** and contains only the five S3 tables: `customers` (3,961 rows), `customer_features` (3,961 rows), `segments` (5 rows), `segment_membership` (39,610 rows) and `lapse_risk` (3,961 rows).

## Likely viva questions

**1. Why is `SUM(p)` in Q3 exact without assuming independence, whereas the variance `SUM(p * (1 - p))` requires independence?**
For a fixed segment $s$, let $I_{i,s} \in \{0, 1\}$ be the indicator random variable that customer $i$ belongs to segment $s$, with $\mathbb{E}[I_{i,s}] = p_{i,s}$ and $\text{Var}(I_{i,s}) = p_{i,s}(1 - p_{i,s})$. By **linearity of expectation**, $\mathbb{E}[\sum_i I_{i,s}] = \sum_i \mathbb{E}[I_{i,s}] = \sum_i p_{i,s}$ always holds, even if customers were correlated. In contrast, $\text{Var}(\sum_i I_{i,s}) = \sum_i \text{Var}(I_{i,s}) + 2\sum_{i < j}\text{Cov}(I_{i,s}, I_{j,s})$ equals $\sum_i p_{i,s}(1 - p_{i,s})$ only when covariance between different customers is zero—which is true under our BID assumption that distinct customer blocks are independent.

**2. Why is the expected size of `Champions` higher than its hard count under both GMM (278.63 vs 258) and bootstrap (290.55 vs 278)?**
`Champions` is the smallest, highest-spend segment (`258` hard GMM customers vs `1,105` in `Loyal`). Along the border between `Loyal` and `Champions`, there are many more `Loyal` customers with a secondary 15%–45% probability of being a `Champions` member than the reverse. When Q3 sums $p$ across all 3,961 customers, those fractional probabilities add +20.63 expected customers (`gmm`) and +12.55 (`bootstrap`), and Q4 adds **+£80,613.84** in expected `Champions` revenue (`bootstrap`).

**3. What does the possible-worlds sampler (`src/worlds.py`) compute that Q3 cannot compute directly in SQL?**
Q3 gives the mean $\mu = \sum p$ and variance $\sigma^2 = \sum p(1-p)$ of segment size, which follows a **Poisson-binomial distribution** (a sum of 3,961 non-identically distributed Bernoulli trials). Computing exact tail probabilities like $P(\text{Champions size} \ge 278)$ analytically requires convolving 3,961 distinct Bernoulli distributions. Sampling 10,000 possible worlds (`reports/tables/possible_worlds_q3_check.csv`) both confirms that the SQL mean and variance are exact to within $\le 0.18$ customers and gives the 95% credible intervals (e.g., `Champions` `[280, 302]` under `bootstrap`, with $P(\text{size} \ge 278) = 99.12\%$).

**4. How does `src/prob_queries.py` prevent SQL injection?**
First, the SQL query structure is never built by concatenating user strings: `run_template` loads one of six static `.sql` files (`Q1`–`Q6`) and passes parameters via DuckDB's parameterised execution (`con.execute(sql_text, bound)`). Second, before calling DuckDB, `run_template` checks every parameter against strict allow-lists (`ALLOWED_METHODS`, `ALLOWED_SEGMENTS`, `get_allowed_countries(con)`) and numeric bounds (`0.0 <= tau <= 1.0`, `1 <= limit <= 10000`). `tests/test_templates.py::test_parameter_allowlists_reject_invalid_or_injection_inputs` verifies that strings like `"'; DROP TABLE customers; --"` and `"1 OR 1=1"` are rejected with a `ValueError`.

**5. Why do we build a separate `app/app.duckdb` instead of pointing the Streamlit app at `data/retail.duckdb`?**
`data/retail.duckdb` holds over 1 million raw transaction lines plus snapshots S1 and S2, so it is large and gitignored. `app/app.duckdb` exports only the 3,961 S3 customers and their five customer-level tables (`1.80 MB`), so it can be committed to git for Streamlit Community Cloud deployment, contains zero historical S1/S2 data, and is always opened with `read_only=True`.
