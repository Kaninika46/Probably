"""Phase 8 Streamlit app and deployment prep tests (CLAUDE.md section 7.11).

Verifies:
1. `app/streamlit_app.py` imports cleanly, opens `app/app.duckdb` read-only,
   and builds an Altair chart for each template Q1..Q6.
2. `requirements.txt` pins the spaCy `en_core_web_sm` wheel URL matching the
   pinned spaCy version.
"""

import duckdb
import pytest

from app import streamlit_app
from src import config
from src.nl import engine


def test_app_readonly_connection_refuses_writes():
    con = streamlit_app.get_readonly_connection()
    with pytest.raises(duckdb.Error):
        con.execute("CREATE TABLE forbidden (x INT)")


def test_altair_charts_build_for_all_example_questions():
    con = streamlit_app.get_readonly_connection()
    for _, q_text in streamlit_app.EXAMPLE_QUESTIONS:
        resp = engine.answer_question(con, q_text)
        assert resp.parsed.is_supported
        chart = streamlit_app.build_altair_chart(resp.parsed.template_id, resp.rows)
        assert chart is not None
        spec = chart.to_dict()
        assert "mark" in spec or "layer" in spec


def test_requirements_pins_spacy_model_wheel_url():
    req_text = (config.PROJECT_ROOT / "requirements.txt").read_text(encoding="utf-8")
    assert "spacy==3.8.18" in req_text
    assert "en_core_web_sm-3.8.0-py3-none-any.whl" in req_text
