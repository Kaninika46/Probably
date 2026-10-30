"""Database connections.

There are two kinds of connection on purpose:

* The pipeline connection can write, because the pipeline builds the tables.
* The app connection is opened with read_only=True, so even if a bug in the
  NL engine produced a bad query, DuckDB itself would refuse to change data.
"""

from pathlib import Path

import duckdb

from src import config


def connect_pipeline(db_path: Path = config.DB_PATH) -> duckdb.DuckDBPyConnection:
    """Open the main database for reading and writing (used by the pipeline)."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(db_path))


def connect_app(db_path: Path = config.APP_DB_PATH) -> duckdb.DuckDBPyConnection:
    """Open the app database read-only, so the app can never modify it."""
    return duckdb.connect(str(db_path), read_only=True)


def run_sql_file(con: duckdb.DuckDBPyConnection, sql_path: Path) -> None:
    """Run every statement in a .sql file.

    We keep SQL in .sql files rather than Python strings so it can be read and
    tested on its own, and so the viva can point at one file per step.
    """
    sql_text = sql_path.read_text(encoding="utf-8")
    con.execute(sql_text)
