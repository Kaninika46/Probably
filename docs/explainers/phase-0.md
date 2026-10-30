# Phase 0 explained: setting up the project

## What we did, in plain words

Before touching any data we built the skeleton of the project:

- **A fixed Python version and fixed library versions.** `requirements.txt` lists the exact version of each library (for example `duckdb==2.0.0`, `scikit-learn==1.9.1`). Anyone who installs from it gets the same code we used, so they get the same results.
- **One file for every setting.** `src/config.py` holds every path, snapshot date, threshold and random seed. If an examiner asks "where is the 90-day lapse window set?", the answer is one line in one file.
- **Two kinds of database connection.** `src/db.py` has a normal connection for the pipeline, which builds tables, and a `read_only=True` connection for the app. The read-only one is a safety net: even a buggy query from the app can't change the data.
- **A download script that refuses to fake data.** `data/download.py` downloads the official UCI zip. If that fails it stops and explains how to download the file by hand.
- **Raw data stays out of git.** `.gitignore` excludes `data/raw/` and database files.

## Results

- The UCI URL responded with HTTP 200. The zip was 45,622,418 bytes and the extracted workbook `online_retail_II.xlsx` was 45,622,278 bytes.
- `pytest`: 2 tests passed.

## Likely viva questions

**1. Why did you pin exact library versions?**
Libraries change their defaults between versions. For example, pandas 3 changed how strings are stored. Pinning versions means a fresh install behaves exactly like ours. Our pins come from what pip actually installed into a clean Python 3.12.10 venv.

**2. Why is the app's database connection read-only?**
The app builds SQL from what users type. User text only fills typed parameters, never raw SQL. On top of that, opening the file with `read_only=True` means DuckDB rejects any INSERT, UPDATE or DROP. `tests/test_setup.py::test_app_connection_is_read_only` proves this: it tries an INSERT and checks that an error is raised.

**3. Why put all settings in `config.py`?**
So that there is a single source of truth. If the snapshot dates were scattered across files, changing one and forgetting another would silently break the leakage guarantees. `tests/test_setup.py` also checks that every feature window ends before its snapshot date.

**4. Why is raw data not committed to git?**
It is 45 MB, it belongs to UCI under CC BY 4.0, and anyone can download it again with `python data/download.py`. Our rule is that raw data is never edited, so there is nothing of ours in it to version.

**5. Why Python 3.12 when the spec first said 3.11?**
The machine had only 3.10, so we installed 3.12.10, which every library on our list supports. We updated CLAUDE.md and recorded the change in `docs/PROGRESS.md` so the spec and the code agree.
