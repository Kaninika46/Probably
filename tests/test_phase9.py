"""Phase 9 tests: report_tables.py, README traceability, references.md, and zero placeholders."""

from __future__ import annotations

import json
import re

from src import config, report_tables


def test_report_tables_matches_readme():
    """Verify `reports/tables/readme_results.md` and `README.md` match live CSV tables."""
    out_path = report_tables.run()
    assert out_path.exists()

    expected_md = report_tables.build_all_tables_md().strip()
    file_md = out_path.read_text(encoding="utf-8").strip()
    assert file_md == expected_md

    readme_text = report_tables.README_PATH.read_text(encoding="utf-8")
    assert report_tables.BEGIN_MARKER in readme_text
    assert report_tables.END_MARKER in readme_text

    _, remainder = readme_text.split(report_tables.BEGIN_MARKER, maxsplit=1)
    embedded_md, _ = remainder.split(report_tables.END_MARKER, maxsplit=1)
    assert embedded_md.strip() == expected_md


def test_references_md_contains_all_required_citations():
    """Verify `docs/references.md` covers all 9 required citations from CLAUDE.md Section 11."""
    ref_path = config.PROJECT_ROOT / "docs" / "references.md"
    assert ref_path.exists()
    text = ref_path.read_text(encoding="utf-8")

    required_keywords = [
        "10.24432/C5CG6D",
        "Daqing Chen",
        "Fayyad",
        "Pedregosa",
        "GaussianMixture",
        "Dalvi",
        "Suciu",
        "MayBMS",
        "IPCC",
        "Kent",
        "Spider",
        "BIRD",
        "Dasgupta",
        "Hennig",
        "Fader",
        "BG/NBD",
    ]
    for kw in required_keywords:
        assert kw in text, f"Missing required citation keyword '{kw}' in docs/references.md"


def test_no_placeholders_in_deliverables():
    """Verify Rule 2: no placeholders ('TBD', '[insert]', 'TO CONFIRM', 'XX%') in deliverables."""
    placeholder_patterns = [
        re.compile(r"\bTBD\b"),
        re.compile(r"\[insert\]", re.IGNORECASE),
        re.compile(r"\bTO CONFIRM\b"),
        re.compile(r"\bXX%"),
    ]
    paths_to_check = [
        config.PROJECT_ROOT / "README.md",
        config.PROJECT_ROOT / "docs" / "PROGRESS.md",
        config.PROJECT_ROOT / "docs" / "references.md",
        config.PROJECT_ROOT / "docs" / "how_to_write_test_questions.md",
        config.TABLES_DIR / "readme_results.md",
        config.TABLES_DIR / "tree_rules.md",
    ]
    explainers_dir = config.PROJECT_ROOT / "docs" / "explainers"
    paths_to_check.extend(sorted(explainers_dir.glob("phase-*.md")))

    for path in paths_to_check:
        assert path.exists(), f"Expected deliverable {path} does not exist"
        content = path.read_text(encoding="utf-8")
        for pat in placeholder_patterns:
            match = pat.search(content)
            assert match is None, f"Found forbidden placeholder '{ pat.pattern }' in {path.name}"


def test_questions_test_csv_remains_header_only():
    """Verify Rule 6: `eval/questions_test.csv` has headers only."""
    test_csv = config.PROJECT_ROOT / "eval" / "questions_test.csv"
    assert test_csv.exists()
    lines = [line.strip() for line in test_csv.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert lines == ["q_id,question,gold_sql,author"]


def test_presentation_notebook_is_valid():
    """Verify `notebooks/presentation_walkthrough.ipynb` exists and is valid nbformat 4 JSON."""
    nb_path = config.PROJECT_ROOT / "notebooks" / "presentation_walkthrough.ipynb"
    assert nb_path.exists()
    nb_data = json.loads(nb_path.read_text(encoding="utf-8"))
    assert nb_data.get("nbformat") == 4
    assert len(nb_data.get("cells", [])) >= 5
