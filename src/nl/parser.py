"""spaCy rule-based natural-language parser (Phase 7, CLAUDE.md section 7.9).

Builds a spaCy pipeline with an EntityRuler covering:
- SEGMENT: segment names and synonyms -> canonical segment name as ent_id_
- COUNTRY: country names from the database + common aliases -> canonical country as ent_id_
- HEDGE: hedge words from HEDGE_LEXICON -> canonical hedge key as ent_id_
- LAPSE: 90-day lapse phrases
- BOUNDARY: boundary / uncertain customer phrases
- EXP_SIZE: expected segment size phrases
- EXP_REV: expected segment revenue phrases

Attaches each hedge word to the nearest predicate (SEGMENT or LAPSE) by token
distance and produces a typed `ParsedQuery` dataclass.
"""

from dataclasses import dataclass, field
import re
from typing import Any

import spacy
from spacy.language import Language

from src import config, db
from src.nl import lexicon

# Optional adjective forms mapped to canonical config.HEDGE_THRESHOLDS keys
HEDGE_SURFACE_TO_KEY: dict[str, str] = {
    **{k: k for k in lexicon.HEDGE_LEXICON},
    "probable": "probably",
    "possible": "possibly",
    "definite": "definitely",
    "almost certain": "almost certainly",
}


@dataclass
class ParsedQuery:
    """Structured output of the rule-based spaCy NL parser."""

    question: str
    is_supported: bool
    intent: str
    template_id: str | None
    params: dict[str, Any] = field(default_factory=dict)
    thresholds_used: dict[str, Any] = field(default_factory=dict)
    interpretation: str = ""
    refusal_reason: str | None = None


def load_countries_from_db(con=None) -> list[str]:
    """Load distinct country names from `customers` in app.duckdb or retail.duckdb."""
    close_after = False
    if con is None:
        target = config.APP_DB_PATH if config.APP_DB_PATH.exists() else config.DB_PATH
        con = db.connect_app(target)
        close_after = True
    try:
        rows = con.execute(
            "SELECT DISTINCT country FROM customers WHERE country IS NOT NULL ORDER BY country"
        ).fetchall()
        return [str(r[0]) for r in rows]
    finally:
        if close_after:
            con.close()


def build_nlp_pipeline(countries: list[str] | None = None) -> Language:
    """Create the spaCy pipeline with an EntityRuler for domain entities."""
    if countries is None:
        countries = load_countries_from_db()

    try:
        nlp = spacy.load("en_core_web_sm", disable=["ner", "lemmatizer"])
    except OSError:
        nlp = spacy.blank("en")

    ruler = nlp.add_pipe("entity_ruler", config={"overwrite_ents": True})
    patterns = []

    # 1. Segments and synonyms (longer phrases first)
    for phrase, canonical_seg in sorted(
        lexicon.SEGMENT_SYNONYMS.items(), key=lambda kv: -len(kv[0])
    ):
        tokens = [{"LOWER": part} for part in phrase.lower().split()]
        patterns.append({"label": "SEGMENT", "pattern": tokens, "id": canonical_seg})
        # Also match hyphenated tokens split by spaCy (e.g. "at - risk")
        if "-" in phrase:
            parts = phrase.lower().replace("-", " - ").split()
            patterns.append(
                {"label": "SEGMENT", "pattern": [{"LOWER": p} for p in parts], "id": canonical_seg}
            )

    # 2. Countries from DB + common aliases
    country_map = {c.lower(): c for c in countries}
    for alias, canonical_country in lexicon.COUNTRY_ALIASES.items():
        if canonical_country in countries:
            country_map[alias.lower()] = canonical_country

    for phrase, canonical_country in sorted(country_map.items(), key=lambda kv: -len(kv[0])):
        tokens = [{"LOWER": part} for part in phrase.split()]
        patterns.append({"label": "COUNTRY", "pattern": tokens, "id": canonical_country})

    # 3. Hedge words (multi-word phrases first so "very likely" beats "likely")
    for surface, canonical_key in sorted(
        HEDGE_SURFACE_TO_KEY.items(), key=lambda kv: (-len(kv[0].split()), -len(kv[0]))
    ):
        tokens = [{"LOWER": part} for part in surface.split()]
        patterns.append({"label": "HEDGE", "pattern": tokens, "id": canonical_key})

    # 4. Intent & predicate phrases
    for phrase in sorted(lexicon.EXPECTED_REVENUE_PHRASES, key=len, reverse=True):
        patterns.append({
            "label": "EXP_REV",
            "pattern": [{"LOWER": p} for p in phrase.split()],
            "id": "EXP_REV",
        })
    for phrase in sorted(lexicon.EXPECTED_SIZE_PHRASES, key=len, reverse=True):
        patterns.append({
            "label": "EXP_SIZE",
            "pattern": [{"LOWER": p} for p in phrase.split()],
            "id": "EXP_SIZE",
        })
    for phrase in sorted(lexicon.BOUNDARY_PHRASES, key=len, reverse=True):
        patterns.append({
            "label": "BOUNDARY",
            "pattern": [{"LOWER": p} for p in phrase.split()],
            "id": "BOUNDARY",
        })
    for phrase in sorted(lexicon.LAPSE_PHRASES, key=len, reverse=True):
        patterns.append({
            "label": "LAPSE",
            "pattern": [{"LOWER": p} for p in phrase.split()],
            "id": "LAPSE",
        })

    ruler.add_patterns(patterns)
    return nlp


_CACHED_NLP: Language | None = None


def get_nlp() -> Language:
    """Return a cached spaCy pipeline instance."""
    global _CACHED_NLP
    if _CACHED_NLP is None:
        _CACHED_NLP = build_nlp_pipeline()
    return _CACHED_NLP


def _refuse(question: str, reason: str) -> ParsedQuery:
    return ParsedQuery(
        question=question,
        is_supported=False,
        intent="out_of_scope",
        template_id=None,
        params={},
        thresholds_used={},
        interpretation=f"Sorry, this question cannot be answered safely by templates Q1–Q6 ({reason}). {lexicon.SUPPORTED_EXAMPLE}",
        refusal_reason=reason,
    )


def _check_out_of_scope_or_injection(text_lower: str) -> str | None:
    """Return a refusal reason if the question contains SQL injection or out-of-scope topics."""
    if ";" in text_lower or "--" in text_lower or "/*" in text_lower:
        return "SQL syntax or comment markers are not allowed"
    if re.search(r"\b1\s*=\s*1\b|\bor\s+1\s*=\s*1\b|\bunion\s+select\b", text_lower):
        return "SQL tautology or UNION injection patterns are not allowed"
    for phrase in lexicon.OUT_OF_SCOPE_PHRASES:
        if phrase in text_lower:
            return f"topic '{phrase}' is outside the scope of customer-level S3 templates Q1–Q6"
    return None


def _extract_top_k(text_lower: str) -> int | None:
    """Extract k from phrases like 'top 10', 'top 5', 'first 20'."""
    m = re.search(r"\b(?:top|first)\s+(\d+)\b", text_lower)
    if m:
        return int(m.group(1))
    if re.search(r"\b(?:most\s+confident|highest\s+probability)\b", text_lower):
        return 10
    return None


def _extract_explicit_prob(text_lower: str) -> tuple[str, float] | None:
    """Extract an explicit probability threshold like '>= 0.8', 'at least 0.75', 'over 80%', 'under 0.5'."""
    m = re.search(
        r"(?:(>=|<=|>|<|at\s+least|more\s+than|over|above|under|below|less\s+than)\s*)?"
        r"(?:p\s*(?:>=|<=|>|<|=)\s*)?"
        r"\b(0\.\d+|[1-9]\d?\s*%)\b",
        text_lower,
    )
    if not m:
        return None
    op_word = (m.group(1) or ">=").strip()
    raw_num = m.group(2).strip()
    val = float(raw_num[:-1].strip()) / 100.0 if raw_num.endswith("%") else float(raw_num)
    if not (0.0 < val <= 1.0):
        return None
    if op_word in ("<", "<=", "under", "below", "less than"):
        return ("<=", round(val, 4))
    return (">=", round(val, 4))


def _attach_hedges_to_predicates(doc) -> dict[str, tuple[str, str, float]]:
    """Attach each HEDGE entity in `doc` to the nearest SEGMENT or LAPSE entity.

    Returns a dict mapping 'SEGMENT' and/or 'LAPSE' to (hedge_key, operator, threshold).
    """
    hedges = [ent for ent in doc.ents if ent.label_ == "HEDGE"]
    predicates = [ent for ent in doc.ents if ent.label_ in ("SEGMENT", "LAPSE")]
    attached: dict[str, tuple[str, str, float]] = {}

    if not hedges or not predicates:
        return attached

    for h in hedges:
        best_pred = None
        best_score = (10**9, 10**9)
        for p in predicates:
            if h.end <= p.start:
                dist = p.start - h.end
                direction_penalty = 0  # natural English order: hedge before predicate
            elif p.end <= h.start:
                dist = h.start - p.end
                direction_penalty = 1
            else:
                dist = 0
                direction_penalty = 0
            score = (dist, direction_penalty)
            if score < best_score:
                best_score = score
                best_pred = p

        if best_pred is not None and best_pred.label_ not in attached:
            h_key = h.ent_id_
            op, thr = lexicon.lookup_hedge(h_key)
            attached[best_pred.label_] = (h_key, op, thr)

    return attached


def parse_question(
    question: str,
    default_method: str = "bootstrap",
    nlp: Language | None = None,
) -> ParsedQuery:
    """Parse a plain-English question into a typed `ParsedQuery`."""
    clean_q = (question or "").strip()
    if not clean_q:
        return _refuse(question, "empty question")

    text_lower = clean_q.lower()
    bad_reason = _check_out_of_scope_or_injection(text_lower)
    if bad_reason is not None:
        return _refuse(clean_q, bad_reason)

    # Check if the question explicitly asks for GMM vs bootstrap method
    method = default_method
    if re.search(r"\bgmm\b", text_lower):
        method = "gmm"
    elif re.search(r"\bbootstrap\b", text_lower):
        method = "bootstrap"

    pipeline = nlp or get_nlp()
    doc = pipeline(clean_q)

    seg_ents = [ent for ent in doc.ents if ent.label_ == "SEGMENT"]
    country_ents = [ent for ent in doc.ents if ent.label_ == "COUNTRY"]
    lapse_ents = [ent for ent in doc.ents if ent.label_ == "LAPSE"]
    boundary_ents = [ent for ent in doc.ents if ent.label_ == "BOUNDARY"]
    exp_size_ents = [ent for ent in doc.ents if ent.label_ == "EXP_SIZE"]
    exp_rev_ents = [ent for ent in doc.ents if ent.label_ == "EXP_REV"]

    distinct_segs = list(dict.fromkeys(ent.ent_id_ for ent in seg_ents))
    distinct_countries = list(dict.fromkeys(ent.ent_id_ for ent in country_ents))

    if len(distinct_countries) > 1:
        return _refuse(clean_q, f"multiple countries mentioned ({', '.join(distinct_countries)})")
    country = distinct_countries[0] if distinct_countries else None
    country_clause = f" in {country}" if country else ""

    # 1. Q4: Expected revenue per segment
    if exp_rev_ents or (
        any(w in text_lower for w in ["revenue", "spend", "monetary"])
        and any(w in text_lower for w in ["expected", "per segment", "by segment", "each segment"])
    ):
        return ParsedQuery(
            question=clean_q,
            is_supported=True,
            intent="expected_revenue",
            template_id="Q4",
            params={"method": method, "country": country},
            thresholds_used={},
            interpretation=(
                f"Showing expected 9-month revenue SUM(p × monetary) per segment"
                f"{country_clause} (method = '{method}')."
            ),
        )

    # 2. Q3: Expected segment size
    if exp_size_ents or (
        any(w in text_lower for w in ["expected", "how many", "count", "size", "sizes"])
        and any(w in text_lower for w in ["per segment", "each segment", "by segment", "segment size", "segment sizes"])
    ):
        return ParsedQuery(
            question=clean_q,
            is_supported=True,
            intent="expected_size",
            template_id="Q3",
            params={"method": method, "country": country},
            thresholds_used={},
            interpretation=(
                f"Showing expected customer count SUM(p) and independence variance SUM(p(1-p)) "
                f"per segment{country_clause} (method = '{method}')."
            ),
        )

    # 3. Q2: Boundary / uncertain customers
    if boundary_ents:
        explicit = _extract_explicit_prob(text_lower)
        b_thr = explicit[1] if explicit is not None else config.BOUNDARY_P
        return ParsedQuery(
            question=clean_q,
            is_supported=True,
            intent="boundary_customers",
            template_id="Q2",
            params={"method": method, "boundary": b_thr, "country": country, "limit": 500},
            thresholds_used={"boundary": ("<", b_thr)},
            interpretation=(
                f"Showing boundary customers{country_clause} with max(p) < {b_thr:.2f} "
                f"and their normalised entropy (method = '{method}')."
            ),
        )

    # Ambiguity check: more than one segment mentioned without a boundary intent
    if len(distinct_segs) > 1:
        return _refuse(
            clean_q,
            f"ambiguous question mentioning multiple segments ({', '.join(distinct_segs)})",
        )

    seg = distinct_segs[0] if distinct_segs else None

    # 4. Q5: Top-k members of a segment
    top_k = _extract_top_k(text_lower)
    if top_k is not None and seg is not None and not lapse_ents:
        return ParsedQuery(
            question=clean_q,
            is_supported=True,
            intent="top_k_members",
            template_id="Q5",
            params={"method": method, "seg": seg, "k": top_k, "country": country},
            thresholds_used={"k": top_k},
            interpretation=(
                f"Showing the top {top_k} customers{country_clause} ranked by P({seg}) "
                f"descending (method = '{method}')."
            ),
        )

    # Attach hedges to SEGMENT and/or LAPSE
    attached = _attach_hedges_to_predicates(doc)
    explicit_prob = _extract_explicit_prob(text_lower)

    # 5. Q6: Segment + Lapse filter (or pure Lapse filter across top segments)
    if lapse_ents:
        # Segment condition
        if seg is None:
            tau1, max_p1, only_top = 0.0, 1.0, True
            seg_desc = "their most probable segment"
        elif "SEGMENT" in attached:
            h_key, op1, thr1 = attached["SEGMENT"]
            if op1 == "<=":
                tau1, max_p1, only_top = 0.0, thr1, False
                seg_desc = f"P({seg}) ≤ {thr1:.2f} ('{h_key}')"
            else:
                tau1, max_p1, only_top = thr1, 1.0, False
                seg_desc = f"P({seg}) ≥ {thr1:.2f} ('{h_key}')"
        else:
            tau1, max_p1, only_top = 0.0, 1.0, True
            seg_desc = f"most probable segment = {seg}"

        # Lapse condition
        if "LAPSE" in attached:
            h_key2, op2, thr2 = attached["LAPSE"]
        elif explicit_prob is not None:
            op2, thr2 = explicit_prob
            h_key2 = "explicit"
        else:
            h_key2, (op2, thr2) = "probably", lexicon.lookup_hedge("probably")

        if op2 == "<=":
            tau2, max_p2 = 0.0, thr2
            lapse_desc = f"P(lapse) ≤ {thr2:.2f} ('{h_key2}')"
        else:
            tau2, max_p2 = thr2, 1.0
            lapse_desc = f"P(lapse) ≥ {thr2:.2f} ('{h_key2}')"

        thresholds_used = {"lapse": (op2, thr2)}
        if "SEGMENT" in attached:
            thresholds_used["segment"] = (attached["SEGMENT"][1], attached["SEGMENT"][2])

        return ParsedQuery(
            question=clean_q,
            is_supported=True,
            intent="segment_and_lapse",
            template_id="Q6",
            params={
                "method": method,
                "seg": seg,
                "tau1": tau1,
                "max_p1": max_p1,
                "only_top_segment": only_top,
                "tau2": tau2,
                "max_p2": max_p2,
                "country": country,
                "limit": 500,
            },
            thresholds_used=thresholds_used,
            interpretation=(
                f"Showing customers{country_clause} with {seg_desc} and {lapse_desc} "
                f"(method = '{method}')."
            ),
        )

    # 6. Q1: Confident members of a segment
    if seg is not None:
        if "SEGMENT" in attached:
            h_key, op, thr = attached["SEGMENT"]
            if op == "<=":
                tau, max_p, only_top = 0.0, thr, False
                cond_desc = f"P({seg}) ≤ {thr:.2f} ('{h_key}')"
            else:
                tau, max_p, only_top = thr, 1.0, False
                cond_desc = f"P({seg}) ≥ {thr:.2f} ('{h_key}')"
            thresholds_used = {"segment": (op, thr), "hedge": h_key}
        elif explicit_prob is not None:
            op, thr = explicit_prob
            if op == "<=":
                tau, max_p, only_top = 0.0, thr, False
                cond_desc = f"P({seg}) ≤ {thr:.2f}"
            else:
                tau, max_p, only_top = thr, 1.0, False
                cond_desc = f"P({seg}) ≥ {thr:.2f}"
            thresholds_used = {"segment": (op, thr)}
        else:
            # No hedge word -> most probable segment (hard label), CLAUDE.md section 7.9
            tau, max_p, only_top = 0.0, 1.0, True
            cond_desc = f"most probable segment = {seg} (no hedge word)"
            thresholds_used = {"segment": ("top_segment", 1.0)}

        return ParsedQuery(
            question=clean_q,
            is_supported=True,
            intent="confident_members",
            template_id="Q1",
            params={
                "method": method,
                "seg": seg,
                "tau": tau,
                "max_p": max_p,
                "only_top_segment": only_top,
                "country": country,
                "limit": 500,
            },
            thresholds_used=thresholds_used,
            interpretation=(
                f"Showing customers{country_clause} with {cond_desc} (method = '{method}')."
            ),
        )

    return _refuse(clean_q, "no supported segment, boundary, expected metric or lapse intent found")
