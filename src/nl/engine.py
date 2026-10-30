"""NL query execution engine (Phase 7, CLAUDE.md section 7.9).

Maps a plain-English question -> ParsedQuery -> SQL template + bound parameters
-> DataFrame of rows + human-readable interpretation sentence.
"""

from dataclasses import dataclass

import pandas as pd

from src import prob_queries
from src.nl import parser


@dataclass
class EngineResponse:
    """Result of running a natural-language question through the NL engine."""

    parsed: parser.ParsedQuery
    rows: pd.DataFrame
    sql_text: str


def answer_question(
    con,
    question: str,
    default_method: str = "bootstrap",
    threshold_override: float | None = None,
) -> EngineResponse:
    """Parse `question`, optionally override the primary threshold, and run its template."""
    parsed = parser.parse_question(question, default_method=default_method)
    if not parsed.is_supported or parsed.template_id is None:
        return EngineResponse(parsed=parsed, rows=pd.DataFrame(), sql_text="")

    params = dict(parsed.params)
    if threshold_override is not None:
        thr = float(threshold_override)
        if parsed.template_id == "Q1":
            if params.get("max_p", 1.0) < 1.0 and params.get("tau", 0.0) == 0.0:
                params["max_p"] = thr
            else:
                params["tau"] = thr
                params["only_top_segment"] = False
            parsed.interpretation = (
                f"{parsed.interpretation} [Slider override: threshold = {thr:.2f}]"
            )
        elif parsed.template_id == "Q2":
            params["boundary"] = thr
            parsed.interpretation = (
                f"{parsed.interpretation} [Slider override: boundary = {thr:.2f}]"
            )
        elif parsed.template_id == "Q6":
            params["tau2"] = thr
            parsed.interpretation = (
                f"{parsed.interpretation} [Slider override: lapse threshold = {thr:.2f}]"
            )
        parsed.params = params

    sql_text = prob_queries.load_template_sql(parsed.template_id)
    rows = prob_queries.run_template(con, parsed.template_id, params)
    return EngineResponse(parsed=parsed, rows=rows, sql_text=sql_text)
