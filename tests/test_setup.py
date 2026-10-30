"""Phase 0 checks: the config is consistent and the read-only connection works."""

import duckdb
import pytest

from src import config, db


def test_snapshot_windows_are_ordered():
    """Feature window must end before S, and the outcome window must start at S."""
    for name, snap in config.SNAPSHOTS.items():
        assert snap["feature_start"] < snap["feature_end"] < snap["snapshot_date"], name
        if snap["outcome_start"] is not None:
            assert snap["outcome_start"] == snap["snapshot_date"], name
            assert snap["outcome_start"] < snap["outcome_end"], name


def test_app_connection_is_read_only(tmp_path):
    """A write through the read-only connection must raise an error."""
    db_file = tmp_path / "tiny.duckdb"
    # Build a tiny database with a normal connection first.
    writer = duckdb.connect(str(db_file))
    writer.execute("CREATE TABLE t (x INTEGER)")
    writer.close()

    reader = db.connect_app(db_file)
    with pytest.raises(duckdb.Error):
        reader.execute("INSERT INTO t VALUES (1)")
    reader.close()


def test_all_text_files_are_valid_utf8():
    """Every text deliverable and source file in the repo must decode as UTF-8 without U+FFFD."""
    text_exts = {".py", ".sql", ".md", ".csv", ".json", ".ipynb", ".txt", ".ini", ".bat"}
    skip_dirs = {".venv", ".git", ".pytest_cache", "node_modules", "dist"}
    for path in config.PROJECT_ROOT.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in text_exts:
            continue
        if any(part in skip_dirs for part in path.parts):
            continue
        content = path.read_text(encoding="utf-8")
        assert "\ufffd" not in content, f"Replacement character U+FFFD found in {path}"
