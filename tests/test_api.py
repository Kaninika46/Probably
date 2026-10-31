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
