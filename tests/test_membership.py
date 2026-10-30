"""Phase 4 BID probabilistic database and surrogate tree tests (CLAUDE.md sections 7.5, 7.6, 10).

Verifies on the real database:
1. Block-independent-disjoint (BID) invariant: sum(p) = 1 (+-1e-6) per
   (customer_id, snapshot, method).
2. All membership probabilities p lie in [0, 1].
3. Q3 expected segment sizes (sum(p) across segments) add up to the exact number
   of S3 customers for both 'gmm' and 'bootstrap'.
4. `segments` contains all 5 confirmed segments with non-empty descriptions and
   decision-tree rules.
"""

import pytest

from src import config, db

if not config.DB_PATH.exists():
    pytest.skip("Run `python -m src.pipeline --phase 4` first", allow_module_level=True)


@pytest.fixture(scope="module")
def con():
    connection = db.connect_app(config.DB_PATH)  # read-only
    tables = {row[0] for row in connection.execute("SHOW TABLES").fetchall()}
    if "segment_membership" not in tables:
        connection.close()
        pytest.skip("Run `python -m src.pipeline --phase 4` first")
    yield connection
    connection.close()


def test_bid_probabilities_in_unit_interval(con):
    bad = con.execute(
        "SELECT COUNT(*) FROM segment_membership WHERE p < 0.0 OR p > 1.0 OR p IS NULL"
    ).fetchone()[0]
    assert bad == 0


def test_bid_block_probabilities_sum_to_one(con):
    """For every (customer_id, snapshot, method) block, sum(p) must equal 1 (+-1e-6)."""
    bad_blocks = con.execute("""
        SELECT COUNT(*)
        FROM (
            SELECT
                customer_id,
                snapshot,
                method,
                SUM(p) AS total_p,
                COUNT(*) AS n_segs
            FROM segment_membership
            GROUP BY customer_id, snapshot, method
        )
        WHERE ABS(total_p - 1.0) > 1e-6
           OR n_segs <> ?
    """, [config.CHOSEN_K]).fetchone()[0]
    assert bad_blocks == 0


def test_expected_segment_sizes_sum_to_customer_count(con):
    """Linearity of expectation: sum of expected segment sizes equals total S3 customers."""
    n_s3 = con.execute(
        "SELECT COUNT(*) FROM customer_features WHERE snapshot = 'S3'"
    ).fetchone()[0]

    for method_name in ["gmm", "bootstrap"]:
        total_expected = con.execute(
            "SELECT SUM(p) FROM segment_membership WHERE snapshot = 'S3' AND method = ?",
            [method_name],
        ).fetchone()[0]
        assert abs(total_expected - n_s3) < 1e-5, f"Expected size sum mismatch for {method_name}"


def test_segments_table_has_descriptions_and_tree_rules(con):
    rows = con.execute(
        "SELECT segment, description, tree_rule FROM segments ORDER BY segment"
    ).fetchall()
    assert len(rows) == config.CHOSEN_K
    for seg_name, desc, rule in rows:
        assert seg_name in config.SEGMENT_DESCRIPTIONS
        assert desc and len(desc.strip()) > 0
        assert rule and len(rule.strip()) > 0


def test_gate_and_tree_reports_exist():
    assert (config.TABLES_DIR / "gate.csv").exists()
    assert (config.TABLES_DIR / "gate_ave_pp.csv").exists()
    assert (config.FIGURES_DIR / "gate_max_p_hist.png").exists()
    assert (config.TABLES_DIR / "tree_rules.md").exists()
    assert (config.TABLES_DIR / "tree_fidelity.csv").exists()
