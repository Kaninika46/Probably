"""Phase 4, part 2: decision-tree surrogate rules for the S3 segments.

Follows CLAUDE.md section 7.6:
1. Fit a DecisionTreeClassifier(max_depth=4, random_state=42) on S3 features in
   original units (recency_days, frequency, monetary) predicting each customer's
   most probable GMM segment.
2. Use a 70/30 split and report fidelity (agreement with the clustering) on the
   30% held-out set, plus the number of leaves.
3. Export the rules as readable text into `segments.tree_rule` in DuckDB and
   `reports/tables/tree_rules.md` (plus `reports/tables/tree_fidelity.csv`).
4. State explicitly that axis-aligned tree explanations of spherical/elliptical
   clusters are approximations.
"""

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split
from sklearn.tree import DecisionTreeClassifier, _tree, export_text

from src import config, db

FEATURE_COLS = ["recency_days", "frequency", "monetary"]


def load_s3_with_most_probable_segment(con) -> pd.DataFrame:
    """Load S3 features in original units paired with each customer's top GMM segment."""
    return con.execute("""
        WITH top_seg AS (
            SELECT
                customer_id,
                ARG_MAX(segment, p) AS target_segment
            FROM segment_membership
            WHERE snapshot = 'S3'
              AND method = 'gmm'
            GROUP BY customer_id
        )
        SELECT
            cf.customer_id,
            cf.recency_days,
            cf.frequency,
            cf.monetary,
            ts.target_segment
        FROM customer_features AS cf
        JOIN top_seg AS ts
          ON ts.customer_id = cf.customer_id
        WHERE cf.snapshot = 'S3'
        ORDER BY cf.customer_id
    """).df()


def extract_segment_leaf_rules(
    clf: DecisionTreeClassifier,
    feature_names: list[str],
) -> dict[str, list[str]]:
    """Walk the fitted decision tree and format each leaf path in original units.

    Merges multiple thresholds on the same feature along a root-to-leaf path
    (e.g. `monetary > 500` and `monetary > 1200` becomes `monetary > 1200.00`)
    so every leaf rule is concise and easy to read in the viva and the app.
    """
    tree_ = clf.tree_
    classes = [str(c) for c in clf.classes_]
    seg_rules: dict[str, list[str]] = {c: [] for c in classes}

    def recurse(node: int, bounds: dict[str, tuple[float, float]]) -> None:
        if tree_.feature[node] == _tree.TREE_UNDEFINED:
            counts = tree_.value[node][0]
            total = int(tree_.n_node_samples[node])
            pred_idx = int(np.argmax(counts))
            pred_seg = classes[pred_idx]
            purity = 100.0 * float(counts[pred_idx])
            clauses = []
            for feat in feature_names:
                low, high = bounds[feat]
                unit = "£" if feat == "monetary" else ""
                if low > -np.inf and high < np.inf:
                    clauses.append(f"{unit}{low:,.2f} < {feat} <= {unit}{high:,.2f}")
                elif low > -np.inf:
                    clauses.append(f"{feat} > {unit}{low:,.2f}")
                elif high < np.inf:
                    clauses.append(f"{feat} <= {unit}{high:,.2f}")
            cond_str = " AND ".join(clauses) if clauses else "all customers"
            seg_rules[pred_seg].append(f"({cond_str}) [n={total}, purity={purity:.1f}%]")
            return

        feat_name = feature_names[tree_.feature[node]]
        thresh = float(tree_.threshold[node])

        # Left child: feat <= thresh
        left_bounds = dict(bounds)
        low, high = left_bounds[feat_name]
        left_bounds[feat_name] = (low, min(high, thresh))
        recurse(int(tree_.children_left[node]), left_bounds)

        # Right child: feat > thresh
        right_bounds = dict(bounds)
        low, high = right_bounds[feat_name]
        right_bounds[feat_name] = (max(low, thresh), high)
        recurse(int(tree_.children_right[node]), right_bounds)

    init_bounds = {f: (-np.inf, np.inf) for f in feature_names}
    recurse(0, init_bounds)
    return seg_rules


def run() -> None:
    con = db.connect_pipeline()
    df = load_s3_with_most_probable_segment(con)

    x = df[FEATURE_COLS]
    y = df["target_segment"]

    x_train, x_test, y_train, y_test = train_test_split(
        x,
        y,
        test_size=config.TREE_TEST_SIZE,
        random_state=config.RANDOM_STATE,
        stratify=y,
    )

    clf = DecisionTreeClassifier(
        max_depth=config.TREE_MAX_DEPTH,
        random_state=config.RANDOM_STATE,
    )
    clf.fit(x_train, y_train)

    train_pred = clf.predict(x_train)
    test_pred = clf.predict(x_test)

    train_fidelity = float(accuracy_score(y_train, train_pred))
    test_fidelity = float(accuracy_score(y_test, test_pred))
    n_leaves = int(clf.get_n_leaves())
    actual_depth = int(clf.get_depth())

    # Per-segment test fidelity (recall on the 30% test split)
    test_df = pd.DataFrame({"actual": y_test, "predicted": test_pred})
    per_seg_rows = []
    for seg_name in ["Champions", "Loyal", "At-Risk", "New", "Hibernating"]:
        sub = test_df[test_df["actual"] == seg_name]
        if len(sub) > 0:
            seg_fid = float((sub["actual"] == sub["predicted"]).mean())
            per_seg_rows.append({
                "segment": seg_name,
                "n_test_customers": len(sub),
                "n_matched": int((sub["actual"] == sub["predicted"]).sum()),
                "test_fidelity_pct": round(100.0 * seg_fid, 2),
            })
    per_seg_df = pd.DataFrame(per_seg_rows)

    fidelity_df = pd.DataFrame([{
        "max_depth": config.TREE_MAX_DEPTH,
        "actual_depth": actual_depth,
        "n_leaves": n_leaves,
        "n_train": len(x_train),
        "n_test": len(x_test),
        "train_fidelity_pct": round(100.0 * train_fidelity, 2),
        "test_fidelity_pct": round(100.0 * test_fidelity, 2),
    }])

    seg_leaf_rules = extract_segment_leaf_rules(clf, FEATURE_COLS)
    for seg_name, rules_list in seg_leaf_rules.items():
        combined_rule = " OR ".join(rules_list) if rules_list else "No leaf assigned"
        con.execute(
            "UPDATE segments SET tree_rule = ? WHERE segment = ?",
            [combined_rule, seg_name],
        )
    con.close()

    config.TABLES_DIR.mkdir(parents=True, exist_ok=True)
    fidelity_df.to_csv(config.TABLES_DIR / "tree_fidelity.csv", index=False)
    per_seg_df.to_csv(config.TABLES_DIR / "tree_fidelity_by_segment.csv", index=False)

    tree_ascii = export_text(clf, feature_names=FEATURE_COLS, decimals=2)
    md_lines = [
        "# Surrogate Decision-Tree Rules (Snapshot S3)",
        "",
        "> **Approximation note:** These axis-aligned decision-tree rules are a post-hoc",
        "> surrogate approximation to the GMM clustering in `log1p` + standardized RFM",
        "> space (following Dasgupta et al., ICML 2020). Because the GMM fits smooth",
        "> ellipsoids in log-scaled space while the tree makes axis-aligned cuts of",
        f"> depth {actual_depth} in original units (`recency_days`, `frequency`, `monetary`),",
        f"> the surrogate agrees with the GMM on **{100.0 * test_fidelity:.2f}%** of the",
        f"> held-out 30% test split (**{100.0 * train_fidelity:.2f}%** on the 70% training",
        f"> split) using **{n_leaves} leaves**.",
        "",
        "## 1. Summary Metrics",
        "",
        f"- **Max depth configured:** {config.TREE_MAX_DEPTH}",
        f"- **Actual depth fitted:** {actual_depth}",
        f"- **Number of leaves:** {n_leaves}",
        f"- **Training set (70%):** {len(x_train):,} customers — fidelity **{100.0 * train_fidelity:.2f}%**",
        f"- **Held-out test set (30%):** {len(x_test):,} customers — fidelity **{100.0 * test_fidelity:.2f}%**",
        "",
        "## 2. Per-Segment Rules in Original Units",
        "",
    ]
    for seg_name in ["Champions", "Loyal", "At-Risk", "New", "Hibernating"]:
        rules_list = seg_leaf_rules.get(seg_name, [])
        md_lines.append(f"### {seg_name}")
        for r in rules_list:
            md_lines.append(f"- `IF {r}`")
        md_lines.append("")

    md_lines.extend([
        "## 3. Full `sklearn.tree.export_text` Output",
        "",
        "```text",
        tree_ascii.rstrip(),
        "```",
        "",
    ])
    (config.TABLES_DIR / "tree_rules.md").write_text("\n".join(md_lines), encoding="utf-8")

    print("=== Surrogate Decision Tree Fidelity ===")
    print(fidelity_df.to_string(index=False))
    print("\n=== Per-Segment Test Fidelity ===")
    print(per_seg_df.to_string(index=False))


if __name__ == "__main__":
    run()
