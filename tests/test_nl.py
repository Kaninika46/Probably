"""Phase 7 NL engine and security tests (CLAUDE.md sections 7.9, 7.10, 10).

Verifies:
1. The hedge lexicon returns the exact thresholds from CLAUDE.md section 7.9.
2. Dev questions (`eval/questions_dev.csv`) map to their expected templates and
   match gold SQL result sets.
3. Injection strings (`'; DROP TABLE customers; --`, `1 OR 1=1`) are refused and
   never reach SQL text.
4. Out-of-scope questions are refused politely with a supported example.
5. `eval/questions_test.csv` has the required 4-column header (`q_id,question,gold_sql,author`).
"""

import pandas as pd
import pytest

from src import config, db, evaluate
from src.nl import engine, lexicon, parser

if not config.APP_DB_PATH.exists():
    pytest.skip("Run `python -m src.pipeline --phase 6` first", allow_module_level=True)


@pytest.fixture(scope="module")
def app_con():
    con = db.connect_app(config.APP_DB_PATH)
    yield con
    con.close()


def test_hedge_lexicon_returns_documented_thresholds():
    expected = {
        "possibly": (">=", 0.33),
        "might": (">=", 0.33),
        "probably": (">=", 0.66),
        "likely": (">=", 0.66),
        "very likely": (">=", 0.90),
        "highly likely": (">=", 0.90),
        "almost certainly": (">=", 0.95),
        "definitely": (">=", 0.95),
        "unlikely": ("<=", 0.33),
    }
    for word, (op, thr) in expected.items():
        assert lexicon.lookup_hedge(word) == (op, thr)


def test_injection_strings_never_reach_sql(app_con):
    injections = [
        "'; DROP TABLE customers; --",
        "1 OR 1=1",
        "Show Champions WHERE 1=1; DROP TABLE segments; --",
        "Which customers in Germany UNION SELECT * FROM customers",
    ]
    for q in injections:
        resp = engine.answer_question(app_con, q)
        assert not resp.parsed.is_supported
        assert resp.parsed.template_id is None
        assert resp.sql_text == ""
        assert len(resp.rows) == 0


def test_out_of_scope_questions_are_refused(app_con):
    oos_questions = [
        "What will the weather in London be tomorrow?",
        "Which stock_code sold the most units in 2010?",
        "Show customers who are Champions or Loyal",
        "What is the CEO's salary?",
    ]
    for q in oos_questions:
        parsed = parser.parse_question(q)
        assert not parsed.is_supported
        assert parsed.template_id is None
        assert "Try a question such as:" in parsed.interpretation


def test_dev_questions_map_to_expected_templates_and_match_gold(app_con):
    res_df, sum_df, _ = evaluate.evaluate_question_file(app_con, evaluate.DEV_CSV, "dev")
    assert len(res_df) >= 20
    assert (res_df["template_match"]).all(), res_df[~res_df["template_match"]].to_string()
    assert (res_df["hedge_threshold_match"]).all(), res_df[~res_df["hedge_threshold_match"]].to_string()
    assert (res_df["execution_correct"]).all(), res_df[~res_df["execution_correct"]].to_string()
    assert float(sum_df["overall_execution_accuracy_pct"].iloc[0]) == 100.0


def test_questions_test_csv_exists_with_required_headers():
    test_df = pd.read_csv(evaluate.TEST_CSV)
    assert list(test_df.columns) == ["q_id", "question", "gold_sql", "author"]
