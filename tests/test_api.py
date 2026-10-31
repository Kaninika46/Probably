"""FastAPI backend tests (`FRONTEND.md` section 7.1).

Verifies:
1. Every API endpoint (`/api/health`, `/api/meta`, `/api/ask`, `/api/segments`,
   `/api/segments/map`, `/api/customers/{id}`, `/api/lapse`, `/api/quality`)
   returns HTTP 200 with valid typed payloads.
2. `/api/ask` handles a 'probably' question, an 'almost certainly' question,
   an out-of-scope question, and an injection string (`'; DROP TABLE customers; --`
   never reaches SQL).
3. The API's database connection (`get_readonly_con`) refuses writes.
"""

from __future__ import annotations

import duckdb
from fastapi.testclient import TestClient
import pytest

from api.main import app, get_readonly_con

client = TestClient(app)



def test_headline_s2_count_comes_from_the_evaluation_table():
    """The Overview's held-out customer count must be read from lapse_s2_eval.csv, never typed in."""
    import pandas as pd
    from src import config

    s2 = pd.read_csv(config.TABLES_DIR / "lapse_s2_eval.csv")
    expected_n = int(s2.loc[s2["model"] == "logistic_calibrated", "n_customers"].iloc[0])
    headline = client.get("/api/meta").json()["headline"]
    assert headline["s2_customer_count"] == expected_n
    assert f"{expected_n:,}" in headline["subtitle"]

def test_every_api_endpoint_returns_200():
    """Every documented GET endpoint must return HTTP 200 and non-empty data."""
    r_health = client.get("/api/health")
    assert r_health.status_code == 200
    assert r_health.json() == {"status": "ok"}

    r_meta = client.get("/api/meta")
    assert r_meta.status_code == 200
    meta = r_meta.json()
    assert meta["customer_count"] == 3961
    assert meta["default_method"] == "gmm"
    assert len(meta["segments"]) == 5
    assert meta["headline"]["brier_skill_score"] > 0.15

    r_seg_gmm = client.get("/api/segments?method=gmm")
    assert r_seg_gmm.status_code == 200
    seg_data = r_seg_gmm.json()
    assert seg_data["customer_count"] == 3961
    assert len(seg_data["segments"]) == 5

    r_seg_boot = client.get("/api/segments?method=bootstrap")
    assert r_seg_boot.status_code == 200
    assert r_seg_boot.json()["method"] == "bootstrap"

    r_map = client.get("/api/segments/map?method=gmm")
    assert r_map.status_code == 200
    map_data = r_map.json()
    assert map_data["customer_count"] == 3961
    assert len(map_data["points"]) == 3961

    sample_id = map_data["points"][0]["id"]
    r_cust = client.get(f"/api/customers/{sample_id}")
    assert r_cust.status_code == 200
    cust_data = r_cust.json()
    assert cust_data["customer_id"] == sample_id
    assert len(cust_data["membership_gmm"]) == 5
    assert len(cust_data["membership_bootstrap"]) == 5
    assert len(cust_data["tree_rule_path"]) >= 2

    r_lapse = client.get("/api/lapse")
    assert r_lapse.status_code == 200
    lapse_data = r_lapse.json()
    assert len(lapse_data["s2_metrics"]) == 3
    assert len(lapse_data["high_value_at_risk"]) == 20

    r_qual = client.get("/api/quality")
    assert r_qual.status_code == 200
    qual_data = r_qual.json()
    assert len(qual_data["cleaning_funnel"]) == 6
    assert len(qual_data["gmm_grid"]) == 28
    assert len(qual_data["bootstrap_ari_histogram"]) > 0
    assert "waiting for questions" in qual_data["test_set_status"]


def test_api_ask_probably_and_almost_certainly():
    """Verify `/api/ask` handles 'probably' (0.66) and 'almost certainly' (0.95) questions."""
    r_prob = client.post(
        "/api/ask",
        json={"question": "Which German customers are probably Champions?"},
    )
    assert r_prob.status_code == 200
    data_prob = r_prob.json()
    assert data_prob["status"] == "ok"
    assert data_prob["template_id"] == "Q1"
    assert data_prob["params"]["country"] == "Germany"
    assert abs(data_prob["params"]["tau"] - 0.66) < 1e-6
    assert any(t["label"] == "HEDGE" for t in data_prob["tokens"])

    r_cert = client.post(
        "/api/ask",
        json={"question": "Which customers are almost certainly Champions?"},
    )
    assert r_cert.status_code == 200
    data_cert = r_cert.json()
    assert data_cert["status"] == "ok"
    assert data_cert["template_id"] == "Q1"
    assert abs(data_cert["params"]["tau"] - 0.95) < 1e-6
    assert data_cert["row_count"] > 0


def test_api_ask_out_of_scope_and_sql_injection():
    """Verify `/api/ask` refuses out-of-scope and SQL injection strings safely."""
    r_oos = client.post(
        "/api/ask",
        json={"question": "What was the weather in London in December 2011?"},
    )
    assert r_oos.status_code == 200
    data_oos = r_oos.json()
    assert data_oos["status"] == "refused"
    assert data_oos["sql"] == ""
    assert len(data_oos["suggestions"]) == 3

    inj = "'; DROP TABLE customers; --"
    r_inj = client.post("/api/ask", json={"question": inj})
    assert r_inj.status_code == 200
    data_inj = r_inj.json()
    assert data_inj["status"] == "refused"
    assert data_inj["sql"] == ""
    assert "DROP TABLE" not in data_inj["sql"]


def test_api_readonly_connection_refuses_writes():
    """A write through the API's database connection must raise a DuckDB error."""
    con = get_readonly_con()
    try:
        with pytest.raises(duckdb.Error):
            con.execute("DROP TABLE customers")
    finally:
        con.close()


def test_meta_fields_shown_in_the_header_and_overview_are_not_null():
    """The header count, Active S3 tile, metric pills and example chips all read /api/meta."""
    meta = client.get("/api/meta").json()
    assert isinstance(meta["customer_count"], int) and meta["customer_count"] > 0
    for field in ("brier_score", "brier_skill_score", "roc_auc", "ece_10_bins", "s2_customer_count"):
        assert meta["headline"][field] is not None, field
    assert len(meta["example_questions"]) == 6


def test_lapse_returns_an_ece_for_the_primary_model():
    """The Lapse page's 10-bin ECE tile reads the calibrated logistic row of s2_metrics."""
    s2_rows = client.get("/api/lapse").json()["s2_metrics"]
    primary = [row for row in s2_rows if row["model"] == "logistic_calibrated"]
    assert len(primary) == 1
    assert primary[0]["ece_10_bins"] is not None


def _required_ts_fields(interface_name: str) -> list[str]:
    """Read the non-optional field names of a TypeScript interface in web/src/lib/api.ts."""
    import re
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] / "web/src/lib/api.ts").read_text(encoding="utf-8")
    body = re.search(rf"export interface {interface_name} \{{(.*?)\n\}}", source, re.S).group(1)
    # "  name: type;" is required; "  name?: type;" is optional and skipped
    return re.findall(r"^\s+(\w+):", body, re.M)


def test_api_meta_matches_the_fields_the_frontend_reads():
    """Every required field in the frontend's MetaResponse/HeadlineInfo types must arrive non-null.

    This catches a renamed or dropped API field, which would otherwise render as "—" in the UI
    while every other test still passes.
    """
    meta = client.get("/api/meta").json()
    for field in _required_ts_fields("MetaResponse"):
        assert meta.get(field) is not None, f"/api/meta is missing {field}"
    for field in _required_ts_fields("HeadlineInfo"):
        assert meta["headline"].get(field) is not None, f"/api/meta headline is missing {field}"



def test_lapse_watchlist_summary_and_comparison_inputs_are_present():
    """The watchlist caption and the calibration-vs-discrimination caption read these fields."""
    lapse = client.get("/api/lapse").json()
    summary = lapse["high_value_summary"]
    assert summary["customer_count"] > 0
    assert summary["min_monetary"] > 0
    assert 0.0 <= summary["max_p_lapse_90d"] <= 1.0
    # The 20 rows shown are the top of the same pool, so the first row carries the pool maximum
    assert lapse["high_value_at_risk"][0]["p_lapse_90d"] == summary["max_p_lapse_90d"]
    models = {row["model"]: row for row in lapse["s2_metrics"]}
    for model in ("logistic_calibrated", "two_bin_recency_90d"):
        for metric in ("ece_10_bins", "roc_auc", "brier_score"):
            assert models[model][metric] is not None, (model, metric)
