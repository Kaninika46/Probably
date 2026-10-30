# Phase 7 explained: spaCy rule-based NL engine, hedge lexicon and evaluation harness

## What we did, in plain words

**1. Map English uncertainty ("hedge words") to published probability thresholds (`src/nl/lexicon.py`, `src/config.py`).**
When an analyst asks *"Which customers in Germany are probably Champions?"*, words like *"probably"* or *"almost certainly"* express degrees of belief. Rather than inventing thresholds, we anchor each hedge phrase to the IPCC Fifth Assessment Report (AR5) likelihood scale (Mastrandrea et al., 2010) and Sherman Kent's *Words of Estimative Probability* (1964):

| Hedge words | SQL condition | Published anchor |
|---|---|---|
| `possibly`, `might` | $P \ge 0.33$ | IPCC *"about as likely as not"* ($33\text{–}66\%$) starts at $33\%$ |
| `probably`, `likely` | $P \ge 0.66$ | IPCC *"likely"* ($66\text{–}100\%$); Kent *"probable"* ($63\text{–}87\%$) |
| `very likely`, `highly likely` | $P \ge 0.90$ | IPCC *"very likely"* ($90\text{–}100\%$) |
| `almost certainly`, `definitely` | $P \ge 0.95$ | Kent *"almost certain"* ($93\% \pm 6\%$) |
| `unlikely` | $P \le 0.33$ | IPCC *"unlikely"* ($0\text{–}33\%$) |
| *(no hedge word)* | customer's most probable segment | Equivalent to a deterministic hard cluster label |

**2. Build the rule-based spaCy parser (`src/nl/parser.py`).**
`build_nlp_pipeline()` attaches a spaCy `EntityRuler` (`overwrite_ents=True`) with patterns for:
- `SEGMENT`: the 5 canonical segment names (`Champions`, `Loyal`, `At-Risk`, `New`, `Hibernating`) and 27 plain-English synonyms (e.g. `best customers`, `regular customers`, `slipping`, `dormant`).
- `COUNTRY`: all 37 countries present in `app/app.duckdb` (`customers.country`), loaded dynamically from the database, plus common shorthands (`UK` $\to$ `United Kingdom`, `Ireland` $\to$ `EIRE`, `South Africa` $\to$ `RSA`).
- `HEDGE`: multi-word phrases matched before single-word substrings so `"very likely"` ($0.90$) is never shadowed by `"likely"` ($0.66$).
- `LAPSE`, `BOUNDARY`, `EXP_SIZE`, `EXP_REV`: domain intent phrases corresponding to templates Q1–Q6.

When a sentence contains both a segment mention and a lapse mention (Q6), `_attach_hedges_to_predicates(doc)` attaches each `HEDGE` span to the nearest predicate (`SEGMENT` or `LAPSE`) by token distance in the spaCy `Doc`. For example, in *"Which likely At-Risk customers might lapse in 90 days?"*, `"likely"` attaches to `At-Risk` ($\tau_1 = 0.66$) and `"might"` attaches to `lapse` ($\tau_2 = 0.33$).

**3. Enforce strict SQL safety (`src/nl/engine.py`, `src/prob_queries.py`).**
User text **never** becomes SQL:
1. `_check_out_of_scope_or_injection()` rejects any input containing `;`, `--`, `/*`, `1=1`, `UNION SELECT`, or out-of-scope product/invoice/external topics.
2. `parse_question()` outputs a `ParsedQuery` dataclass containing only a `template_id` (`Q1`–`Q6`) and typed parameters (`seg`, `country`, `tau`, `k`, `method`).
3. `prob_queries.run_template()` validates every string parameter against allow-lists (`ALLOWED_METHODS`, `ALLOWED_SEGMENTS`, `get_allowed_countries(con)`) and binds parameters via DuckDB parameterised execution on a `read_only=True` connection.

**4. Evaluate on the 26-question dev benchmark (`eval/questions_dev.csv`, `src/evaluate.py`).**
Per `CLAUDE.md` Rule 6, `eval/questions_test.csv` is created with headers only (`q_id,question,gold_sql,author`) plus instructions in `docs/how_to_write_test_questions.md` so a human can write and freeze the blind test set. On the 26-question development set (`21` in-scope across Q1–Q6 + `5` out-of-scope/injection/ambiguous):

| Split | Total questions | In-scope | Out-of-scope | Overall execution accuracy | In-scope execution accuracy | Template match rate | Out-of-scope rejection rate | Hedge-threshold accuracy |
|---|---|---|---|---|---|---|---|---|
| `dev` | 26 | 21 | 5 | **100.00%** | **100.00%** | **100.00%** | **100.00%** | **100.00%** |

Source: `reports/tables/nl_summary.csv`, `reports/tables/nl_dev_results.csv`, `reports/tables/nl_error_analysis.csv`. All 41 headline project metrics across Phases 1–7 are also consolidated into `eval_results` (`reports/tables/eval_results.csv`).

## Likely viva questions

**1. Why use a rule-based spaCy parser + SQL templates instead of an LLM text-to-SQL generator?**
First, the course topic specifies a rule-based or pre-trained NLP pipeline like spaCy or NLTK. Second, an LLM generating raw SQL can hallucinate column names, multiply dependent probabilities ($p \times p_{\text{lapse\_90d}}$), or be tricked by prompt injection into running arbitrary queries. By mapping entities and hedge words to six vetted SQL templates (`Q1`–`Q6`) with allow-listed parameters, every supported query has guaranteed probabilistic semantics and zero SQL injection risk.

**2. How does your parser handle a sentence with two different hedge words, like *"Which likely At-Risk customers might lapse in 90 days?"*?**
In `src/nl/parser.py`, `_attach_hedges_to_predicates(doc)` inspects the token indices (`ent.start`, `ent.end`) of every `HEDGE` entity and every `SEGMENT` or `LAPSE` entity in the spaCy `Doc`. It computes the token distance between each hedge and each predicate, preferring the predicate that immediately follows the hedge in normal English word order. Thus `"likely"` (tokens 1–2) attaches to `"At-Risk"` (tokens 2–3, distance 0 $\to \tau_1 = 0.66$) and `"might"` (tokens 4–5) attaches to `"lapse"` (tokens 5–6, distance 0 $\to \tau_2 = 0.33$).

**3. What is the difference between template match accuracy and execution accuracy in text-to-SQL evaluation (Yu et al., 2018 Spider)?**
Template (or exact-match) accuracy checks whether the parser selected the right SQL structure (`Q1`–`Q6`). Execution accuracy runs both the predicted query and the human-written `gold_sql` against `app/app.duckdb` and checks whether the returned tables are identical (order-insensitive unless the gold query has a top-level `ORDER BY`). Execution accuracy is stricter because a query can pick the right template (`Q6`) yet fail execution accuracy if it extracted the wrong country or attached a hedge word to the wrong predicate.

**4. Why is `eval/questions_test.csv` empty right now?**
Per `CLAUDE.md` Rule 6, if the developer or AI tunes parser rules while looking at the test questions, the test accuracy is contaminated by overfitting to those exact phrasings. Therefore `eval/questions_test.csv` is created with headers only (`q_id,question,gold_sql,author`) alongside `docs/how_to_write_test_questions.md`, and `src/evaluate.py` automatically evaluates `questions_test.csv` as soon as a human adds rows and freezes it.

**5. How do you ensure multi-word hedge phrases like `"very likely"` ($0.90$) aren't misread as `"likely"` ($0.66$)?**
In `src/nl/lexicon.py`, `ORDERED_HEDGE_PHRASES` sorts phrases by descending word count and character length before adding patterns to spaCy's `EntityRuler`. Because spaCy's `EntityRuler` resolves overlapping spans in favour of longer matches (and earlier patterns of equal length), the two-token span `"very likely"` is tagged as a single `HEDGE` entity with `ent_id_ = "very likely"` ($\ge 0.90$) rather than matching `"likely"` alone.
