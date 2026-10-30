# Progress

## Phase 0: Scaffold (done)

**What was done**
- Created the repo layout, `.gitignore`, `requirements.txt`, `src/config.py`, `src/db.py`, `data/download.py`, `pytest.ini` and `tests/test_setup.py`.
- `requirements.txt` pins the exact versions pip installed into a fresh Python 3.12.10 venv.
- `data/download.py` checked the UCI URL `https://archive.ics.uci.edu/static/public/502/online+retail+ii.zip` (HTTP 200). It downloaded the zip (45,622,418 bytes) and extracted `online_retail_II.xlsx` (45,622,278 bytes).
- `pytest`: 2 passed. One test checks that the snapshot windows are ordered and the other checks that the app connection refuses writes.

**Changes to the spec (agreed with the user)**
- Python version changed from 3.11 to **3.12** (CLAUDE.md section 4). The machine only had 3.10, so the user installed 3.12.10.
- `clean_sales` keeps rows without a `customer_id`, flagged with `has_customer = false`, so revenue totals stay complete. Every customer-level table filters on `customer_id IS NOT NULL` (CLAUDE.md section 6 reworded so the spec no longer contradicts itself).
- Added `src/eda.py` for the Phase 1 exploratory figures (CLAUDE.md section 5).

**Open items**
- `docs/architecture.png` is missing. The architecture diagram was not found on this machine.
- The spaCy model `en_core_web_sm` is not installed yet. It will be pinned by wheel URL in Phase 7 (CLAUDE.md section 7.11).
- `src/pipeline.py` is added in Phase 1, when there is a first phase to run.
