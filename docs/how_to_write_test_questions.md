# How to Write Human Test Questions (`eval/questions_test.csv`)

Per `CLAUDE.md` Rule 6, **`eval/questions_test.csv` is written by a human only** and is never edited by the AI assistant. This ensures the NL parser is evaluated on blind phrasing it was not tuned on.

## 1. CSV Columns

`eval/questions_test.csv` has four columns:

```csv
q_id,question,gold_sql,author
```

- **`q_id`**: A unique identifier such as `T01`, `T02`, …
- **`question`**: A natural-language question in plain English (enclosed in double quotes if it contains commas).
- **`gold_sql`**:
  - For **supported questions (Q1–Q6)**: a single SQL `SELECT` statement over `app/app.duckdb` (`customers`, `customer_features`, `segments`, `segment_membership`, `lapse_risk`, all at `snapshot = 'S3'`, defaulting to `method = 'bootstrap'`) that returns the same result set as the intended template.
  - For **out-of-scope or ambiguous questions** that should be refused: write `OUT_OF_SCOPE` in `gold_sql`.
- **`author`**: Your name or initials.

## 2. Supported Query Types & Hedge Thresholds

When writing `gold_sql`, use the project's published probability scale (`CLAUDE.md` section 7.9):

| Hedge phrase in question | SQL condition |
|---|---|
| `possibly`, `might` | `p >= 0.33` |
| `probably`, `likely` | `p >= 0.66` |
| `very likely`, `highly likely` | `p >= 0.90` |
| `almost certainly`, `definitely` | `p >= 0.95` |
| `unlikely` | `p <= 0.33` |
| *(no hedge word)* | customer's most probable segment (rank 1 by `p DESC`) |

## 3. Running the Evaluation

Once you have added your test questions and frozen the file, run:

```powershell
python -m src.evaluate
```

`src/evaluate.py` will compare the NL engine's result set against `gold_sql` (order-insensitive unless `gold_sql` contains `ORDER BY`) and write the accuracy and error breakdown to `reports/tables/`.
