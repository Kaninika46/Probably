"""Phase 6, part 1: parameterised probabilistic SQL queries Q1-Q6 and K-Means comparison.

Follows CLAUDE.md sections 7.8 and 7.9:
1. Loads SQL templates from sql/templates/q1_confident.sql .. q6_segment_and_lapse.sql.
2. Executes them using DuckDB named parameters ($seg, $tau, $k, $method, $country, ...)
   after strict type and allow-list validation. User strings are never interpolated
   into SQL text.
3. Produces the comparison table of hard K-Means counts vs GMM/bootstrap expected
   segment sizes (reports/tables/kmeans_vs_expected_sizes.csv) and Q3/Q4 tables.
"""

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment
from sklearn.cluster import KMeans
from sklearn.metrics.cluster import contingency_matrix
from sklearn.mixture import GaussianMixture

from src import config, db, segment

TEMPLATE_FILES = {
    "Q1": "q1_confident.sql",
    "Q2": "q2_boundary.sql",
    "Q3": "q3_expected_size.sql",
    "Q4": "q4_expected_revenue.sql",
    "Q5": "q5_top_k.sql",
    "Q6": "q6_segment_and_lapse.sql",
}

ALLOWED_METHODS = {"bootstrap", "gmm"}
ALLOWED_SEGMENTS = set(config.SEGMENT_DESCRIPTIONS.keys())
DEFAULT_ROW_LIMIT = 500


def load_template_sql(template_id: str) -> str:
    """Read the SQL text for template Q1..Q6 from sql/templates/."""
    key = template_id.upper()
    if key not in TEMPLATE_FILES:
        raise ValueError(f"Unknown template_id: {template_id!r}")
    sql_path: Path = config.TEMPLATES_DIR / TEMPLATE_FILES[key]
    return sql_path.read_text(encoding="utf-8")


def get_allowed_countries(con) -> set[str]:
    """Return the set of valid country names present in the `customers` table."""
    rows = con.execute("SELECT DISTINCT country FROM customers WHERE country IS NOT NULL").fetchall()
    return {str(r[0]) for r in rows}


def validate_common_params(
    con,
    method: str = "bootstrap",
    country: str | None = None,
) -> tuple[str, str | None]:
    """Validate $method and $country against allow-lists."""
    if method not in ALLOWED_METHODS:
        raise ValueError(f"Disallowed method {method!r}; must be one of {sorted(ALLOWED_METHODS)}")
    if country is not None:
        allowed_countries = get_allowed_countries(con)
        if country not in allowed_countries:
            raise ValueError(f"Disallowed country {country!r}")
    return method, country


def validate_segment(seg: str | None, allow_none: bool = False) -> str | None:
    """Validate $seg against the 5 confirmed segment names."""
    if seg is None and allow_none:
        return None
    if seg not in ALLOWED_SEGMENTS:
        raise ValueError(f"Disallowed segment {seg!r}; must be one of {sorted(ALLOWED_SEGMENTS)}")
    return seg


def validate_probability(val: float, name: str) -> float:
    """Validate a probability threshold in [0.0, 1.0]."""
    fval = float(val)
    if not (0.0 <= fval <= 1.0):
        raise ValueError(f"{name}={val!r} must lie in [0.0, 1.0]")
    return fval


def run_template(
    con,
    template_id: str,
    params: dict[str, Any] | None = None,
) -> pd.DataFrame:
    """Validate named parameters and run one of Q1..Q6 with DuckDB parameter binding."""
    key = template_id.upper()
    raw = dict(params or {})

    method, country = validate_common_params(
        con,
        method=str(raw.get("method", "bootstrap")),
        country=raw.get("country", None),
    )
    limit = int(raw.get("limit", DEFAULT_ROW_LIMIT))
    if limit < 1 or limit > 10000:
        raise ValueError(f"Invalid row limit: {limit}")

    if key == "Q1":
        bound = {
            "method": method,
            "seg": validate_segment(raw.get("seg")),
            "tau": validate_probability(raw.get("tau", 0.66), "tau"),
            "max_p": validate_probability(raw.get("max_p", 1.0), "max_p"),
            "only_top_segment": bool(raw.get("only_top_segment", False)),
            "country": country,
            "limit": limit,
        }
    elif key == "Q2":
        bound = {
            "method": method,
            "boundary": validate_probability(raw.get("boundary", config.BOUNDARY_P), "boundary"),
            "country": country,
            "limit": limit,
        }
    elif key in ("Q3", "Q4"):
        bound = {
            "method": method,
            "country": country,
        }
    elif key == "Q5":
        k_val = int(raw.get("k", 10))
        if k_val < 1 or k_val > 1000:
            raise ValueError(f"Invalid k={k_val}; must be between 1 and 1000")
        bound = {
            "method": method,
            "seg": validate_segment(raw.get("seg")),
            "k": k_val,
            "country": country,
        }
    elif key == "Q6":
        seg_val = validate_segment(raw.get("seg"), allow_none=True)
        only_top = bool(raw.get("only_top_segment", seg_val is None))
        bound = {
            "method": method,
            "seg": seg_val,
            "tau1": validate_probability(raw.get("tau1", 0.0 if only_top else 0.66), "tau1"),
            "max_p1": validate_probability(raw.get("max_p1", 1.0), "max_p1"),
            "only_top_segment": only_top,
            "tau2": validate_probability(raw.get("tau2", 0.66), "tau2"),
            "max_p2": validate_probability(raw.get("max_p2", 1.0), "max_p2"),
            "country": country,
            "limit": limit,
        }
    else:
        raise ValueError(f"Unsupported template_id: {template_id!r}")

    sql_text = load_template_sql(key)
    return con.execute(sql_text, bound).df()


def build_kmeans_vs_expected_sizes(con) -> pd.DataFrame:
    """Compare hard K-Means (K=5) counts with GMM/bootstrap hard and expected sizes on S3."""
    s3_df = segment.load_s3_features(con)
    x_scaled, _ = segment.preprocess_s3_rfm(s3_df)

    # Fit reference GMM and K-Means (K=5) and align K-Means labels to the 5 segments
    ref_gmm = GaussianMixture(
        n_components=config.CHOSEN_K,
        covariance_type=config.CHOSEN_GMM_COV,
        n_init=config.GMM_N_INIT,
        random_state=config.RANDOM_STATE,
    ).fit(x_scaled)
    gmm_labels = ref_gmm.predict(x_scaled)

    # Map GMM cluster IDs to segment names
    tmp = s3_df.copy()
    tmp["cluster_id"] = gmm_labels
    prof = tmp.groupby("cluster_id", as_index=False).agg(
        mean_recency_days=("recency_days", "mean"),
        mean_frequency=("frequency", "mean"),
        mean_monetary=("monetary", "mean"),
    )
    seg_names = segment.assign_proposed_names_k5(prof)
    cid_to_seg = dict(zip(prof["cluster_id"].astype(int), seg_names))

    seg_order = ["Champions", "Loyal", "At-Risk", "New", "Hibernating"]
    seg_to_idx = {s: i for i, s in enumerate(seg_order)}
    ref_seg_idx = np.array([seg_to_idx[cid_to_seg[int(c)]] for c in gmm_labels])

    km = KMeans(
        n_clusters=config.CHOSEN_K,
        n_init=config.GMM_N_INIT,
        random_state=config.RANDOM_STATE,
    ).fit(x_scaled)
    km_labels = km.predict(x_scaled)
    cm = contingency_matrix(ref_seg_idx, km_labels)
    r_ind, c_ind = linear_sum_assignment(-cm)
    remap = {km_c: ref_r for ref_r, km_c in zip(r_ind, c_ind)}
    km_aligned = np.array([remap[val] for val in km_labels])
    km_counts = {seg_order[i]: int(np.sum(km_aligned == i)) for i in range(config.CHOSEN_K)}

    q3_boot = run_template(con, "Q3", {"method": "bootstrap"}).set_index("segment")
    q3_gmm = run_template(con, "Q3", {"method": "gmm"}).set_index("segment")

    rows = []
    for seg_name in seg_order:
        km_n = km_counts[seg_name]
        gmm_hard = int(q3_gmm.loc[seg_name, "hard_count"])
        gmm_exp = float(q3_gmm.loc[seg_name, "expected_size"])
        gmm_std = float(q3_gmm.loc[seg_name, "std_dev_independent"])
        boot_hard = int(q3_boot.loc[seg_name, "hard_count"])
        boot_exp = float(q3_boot.loc[seg_name, "expected_size"])
        boot_std = float(q3_boot.loc[seg_name, "std_dev_independent"])
        rows.append({
            "segment": seg_name,
            "kmeans_hard_count": km_n,
            "gmm_hard_count": gmm_hard,
            "gmm_expected_size": round(gmm_exp, 2),
            "gmm_std_dev": round(gmm_std, 2),
            "bootstrap_hard_count": boot_hard,
            "bootstrap_expected_size": round(boot_exp, 2),
            "bootstrap_std_dev": round(boot_std, 2),
        })
    return pd.DataFrame(rows)


def run() -> None:
    con = db.connect_app(config.DB_PATH)
    config.TABLES_DIR.mkdir(parents=True, exist_ok=True)

    comp_df = build_kmeans_vs_expected_sizes(con)
    comp_df.to_csv(config.TABLES_DIR / "kmeans_vs_expected_sizes.csv", index=False)

    q3_boot = run_template(con, "Q3", {"method": "bootstrap"})
    q3_boot.to_csv(config.TABLES_DIR / "q3_expected_sizes_bootstrap.csv", index=False)

    q3_gmm = run_template(con, "Q3", {"method": "gmm"})
    q3_gmm.to_csv(config.TABLES_DIR / "q3_expected_sizes_gmm.csv", index=False)

    q4_boot = run_template(con, "Q4", {"method": "bootstrap"})
    q4_boot.to_csv(config.TABLES_DIR / "q4_expected_revenue_bootstrap.csv", index=False)

    q4_gmm = run_template(con, "Q4", {"method": "gmm"})
    q4_gmm.to_csv(config.TABLES_DIR / "q4_expected_revenue_gmm.csv", index=False)
    con.close()

    print("=== Hard K-Means Counts vs GMM & Bootstrap Expected Sizes (S3) ===")
    print(comp_df.to_string(index=False))
    print("\n=== Q4 Expected Revenue by Segment (Bootstrap) ===")
    print(q4_boot.to_string(index=False))


if __name__ == "__main__":
    run()
