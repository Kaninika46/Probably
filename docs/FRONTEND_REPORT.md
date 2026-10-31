# Frontend Implementation Report: FastAPI + React Single-Page Application

Course project deliverable for **Data Management and AI Integration (ABAI2009L)**, Bennett University.  
This report documents the design, implementation, and verification of the web interface built to replace the initial Streamlit prototype in accordance with `FRONTEND.md`.

---

## 1. Executive Summary & Purpose

The purpose of this phase was to replace the initial Streamlit script with a production-grade, accessible, and fast web application running on `http://localhost:8000` from a single command (`run_app.bat`).

The web interface embodies the core principle **"colour only means data"**:
1. **Neutral chrome:** all layout surfaces, borders, text, and active states use neutral slate tones (`--bg`, `--surface`, `--ink`, `--line`), ensuring that color is never used as mere decoration.
2. **Okabe–Ito categorical palette:** customer segments are displayed exclusively with the five color-blind-safe Okabe–Ito hues. In light mode (the default) four of them are darkened slightly so each reaches at least 3:1 contrast on white and faded low-confidence dots stay visible on a projector (`Champions` `#00876A`, `Loyal` `#0072B2`, `New` `#B5608F`, `At-Risk` `#B07800`, `Hibernating` `#666B73`); dark mode keeps the lighter variants.
3. **Sequential red ramp:** 90-day lapse risk is represented using a distinct four-level monochromatic red scale (`--lapse-1` to `--lapse-4`), completely separated from categorical segment hues.
4. **Self-hosted offline typography:** `@fontsource/bricolage-grotesque` (editorial headings), `@fontsource/figtree` (interface copy), and `@fontsource/jetbrains-mono` (tabular figures and code).
5. **Decoupled architecture:** all data modeling, natural language parsing, and probabilistic SQL logic execute inside the Python backend (`src/`, `api/main.py`), while the React frontend (`web/`) serves purely as a responsive rendering layer.

---

## 2. System Architecture & API Design

### 2.1 Backend: Read-Only FastAPI Service (`api/`)

The backend is implemented in `api/main.py` using FastAPI and Pydantic v2 schemas (`api/schemas.py`). It enforces database security and query safety:
- **Storage-level read-only connection:** `get_readonly_con()` connects to `app/app.duckdb` with `duckdb.connect(str(APP_DB_PATH), read_only=True)`. Even if SQL injection were attempted, DuckDB's storage engine rejects write statements (`duckdb.InvalidInputException`).
- **Closed template execution:** user text never directly becomes SQL. The natural language engine (`src/nl/parser.py`) maps user input to one of six closed templates (`Q1`–`Q6`), and parameters are validated against strict Python allow-lists before being bound into parameterized DuckDB queries.
- **SPA static file serving:** when the React application is built into `web/dist`, FastAPI mounts the assets and serves `index.html` on client routes, allowing both the REST API and the frontend UI to operate on a single port (`8000`).

#### Core Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/health` | Health check confirming API status and read-only DuckDB reachability. |
| `GET` | `/api/meta` | System metadata: 3 headline revenue numbers, segment color mappings, hedge lexicon, and example questions. |
| `POST` | `/api/ask` | Natural language question execution: returns parsed tokens, threshold controls, summary metrics, result rows, and SQL. |
| `GET` | `/api/segments` | Segment profiles, hard vs expected counts, surrogate decision-tree rules, and max-p histograms. |
| `GET` | `/api/segments/map` | Full S3 customer scatter plot dataset (all 3,961 customers with RFM, top-2 segment posteriors, entropy, and lapse risk). |
| `GET` | `/api/customers/{id}` | Customer detail view: 5-segment probability vector, 9-month facts, recent invoice items, and surrogate tree path. |
| `GET` | `/api/lapse` | 90-day lapse evaluation metrics on held-out S2, 10-bin reliability diagram, baseline comparison, and top at-risk cohort. |
| `GET` | `/api/quality` | 6-step cleaning funnel, GMM BIC grid across K=2..8 and 4 covariance structures, bootstrap ARI histogram, and Jaccard bars. |
| `GET` | `/api/assets/architecture.png` | Serves the verified architecture diagram for the About page. |

---

## 3. Frontend Implementation & Five Signature Components

The frontend is a single-page application built with React 18, TypeScript, Vite, Tailwind CSS, Recharts, and Lucide icons.

### 3.1 Five Signature Components

1. **`ProbabilityBar` (`web/src/components/ProbabilityBar.tsx`):**
   - Renders a horizontal probability bar with rounded caps and smooth transitions.
   - Supports two variants: `segment` (filled with the Okabe–Ito segment color) and `lapse` (filled with the sequential red ramp via `lapseCssColor()`).
   - Includes an optional vertical reference tick indicating the active decision threshold (e.g., `0.66` for "probably" or `0.95` for "almost certainly").
2. **`ParseStrip` (`web/src/components/ParseStrip.tsx`):**
   - Displays the natural-language question broken into interactive token chips.
   - Highlights recognized countries (e.g., "Germany"), hedge words (e.g., "probably" $\to P \ge 0.66$), segment targets ("Champions"), and lapse predicates.
3. **`ThresholdControl` (`web/src/components/ThresholdControl.tsx`):**
   - Allows analysts to override probability thresholds interactively via sliders (`0.05` to `0.99`) and quick-select hedge buttons (*Possibly 0.33*, *Probably 0.66*, *Very likely 0.90*, *Almost certain 0.95*).
   - Uses a 150ms debounce to prevent query thrashing while maintaining responsive interaction.
   - Includes a persistent toggle between `gmm` posteriors (default, soft boundary uncertainty) and `bootstrap` co-assignment (resample stability).
4. **`UncertaintyMap` (`web/src/charts/UncertaintyMap.tsx`):**
   - An HTML5 `<canvas>` scatter plot rendering all 3,961 S3 customers by recency (x-axis, reversed) and monetary spend (y-axis, $\log_{10}$ scale).
   - Shaded by segment certainty: points with $\max_k p_{ik} < 0.65$ display a soft translucent halo proportional to boundary uncertainty ($1 - p_{i,1}$).
   - Includes viewport panning, zooming, boundary-only filtering, segment legend filtering, and sub-millisecond hover hit-testing.
   - Clicking any point instantly opens the customer in the slide-over drawer.
5. **`CustomerDrawer` (`web/src/components/CustomerDrawer.tsx`):**
   - Slide-over inspection drawer for an individual customer.
   - Shows 9-month RFM facts (recency, frequency, monetary spend, tenure, average basket size).
   - Side-by-side comparison of GMM posterior distribution vs bootstrap co-assignment distribution ($\sum p = 1.00$).
   - 90-day lapse risk gauge with the 0.66 IPCC "probably" reference line.
   - Surrogate decision-tree traversal path in readable English units.
   - Recent clean invoice items from `data/processed/transactions_clean.parquet`.

---

## 4. Web Application Pages

The application is structured into six pages accessible via the persistent sidebar navigation:

1. **Overview (`/`):**
   - **Headline finding:** leads with calibrated 90-day lapse risk (*"When we say a customer is 70% likely to lapse, about that share really do"*), one plain-English sentence with the held-out customer count from the API, and four metric pills (Brier skill score, Brier score, ROC-AUC, 10-bin ECE).
   - **Full-width reliability diagram** stacked below the headline: labelled axes, a "perfect calibration" diagonal label, dots sized by bin count (count on hover), and a caption computed from the bins that states how the highest non-empty bin compares with the diagonal and how many customers it holds.
   - **Command bar:** 56px input with 6 quick-launch example chips.
   - **Segment summary strip:** 5 cards showing share of customers, hard counts vs probabilistic expected sizes ($\sum p$) with standard deviations, and a hard-vs-Σp bar pair on a scale shared by all five cards, followed by a sentence (computed from the API) confirming the expected sizes sum to the customer count.
2. **Ask (`/ask`):**
   - Natural language query interface with `/` keyboard shortcut to focus.
   - Large human-readable interpretation sentence (e.g., *"Showing customers with P(Champions) ≥ 0.95 ('almost certainly') (method = 'gmm')*").
   - `ParseStrip` entity breakdown and `ThresholdControl` slider.
   - Summary metric tiles (`matched_rows`, `expected_count vs hard_count`, `expected_revenue_in_result`).
   - Sortable results table with inline `ProbabilityBar` indicators.
   - Companion distribution chart for the result set.
   - Collapsible SQL drawer displaying the parameterised query, bound parameters table, and copy button.
3. **Segments (`/segments`):**
   - Boundary share and mean normalised entropy as two stat tiles beside a `K = 5 · provisional` title pill.
   - Full-width interactive `UncertaintyMap` of all 3,961 customers, with recency on a reversed square-root scale and ±0.4-day seeded jitter.
   - Five segment profile cards in original units (median recency, frequency, monetary spend, surrogate tree rule, and 10-bin confidence mini-histogram).
   - Bar chart comparing K-Means hard counts, GMM hard counts, and probabilistic expected sizes.
4. **90-Day Lapse Risk (`/lapse`):**
   - Four metric tiles: S2 Brier score (`0.2034`), Brier skill score (`+16.72%` over base rate `42.38%`), S2 ROC-AUC (`0.7390`), and 10-bin ECE (`0.0343`).
   - 10-bin reliability diagram with diagonal reference line and customer count histogram underneath.
   - Model vs baselines comparison table (`logistic_calibrated`, `tree_depth4_calibrated`, `two_bin_recency_90d`).
   - Live high-value at-risk customer cohort table via `Q6`.
5. **Model Quality (`/quality`):**
   - Stepped horizontal bar chart of the 6-step SQL cleaning funnel (`1,067,371` raw rows down to `776,596` customer-identified clean sales rows).
   - GMM BIC selection grid across $K = 2\dots 8$ and all 4 covariance types (`spherical`, `tied`, `diag`, `full`), highlighting the degeneracy of `diag` and `full` on integer frequency.
   - Bootstrap ARI histogram across 100 resamples (median `0.8674`, IQR `0.0977`).
   - Hennig clusterwise Jaccard stability bars with the `0.75` reference line (all 5 segments $\ge 0.822$).
   - Natural language development evaluation table (100% execution accuracy on dev; test set honestly marked as waiting for external grader questions).
6. **About (`/about`):**
   - Full system architecture diagram (`docs/architecture.png`).
   - S1–S3 temporal snapshot timeline.
   - Course topic alignment table (Topics 3, 1, 2).
   - Methodological limitations and non-contractual assumptions.
   - Dataset licence and citation (UCI Online Retail II, CC BY 4.0).

---

## 5. How to Run the Application

The application requires **Python 3.12** and **Node.js**:

### Single-Command Production Mode

```powershell
.\run_app.bat
```
*What this script does:*
1. Checks if `web/dist/index.html` exists; if not, automatically runs `npm ci` and `npm run build` inside `web/`.
2. Activates the Python 3.12 virtual environment (`.venv`).
3. Launches the default browser to `http://localhost:8000`.
4. Starts `uvicorn api.main:app --port 8000` to serve both the API and the React SPA.

### Development Mode (Hot Reload)

```powershell
.\run_dev.bat
```
*What this script does:*
1. Starts the FastAPI backend with `--reload` on `http://127.0.0.1:8000` in a new window.
2. Starts the Vite frontend dev server with hot module replacement on `http://localhost:5173` in a new window.
3. Opens the browser to `http://localhost:5173`.

---

## 6. Screenshots & Visual Verification

All screenshots were captured at **1440×900** with headless Google Chrome driven over the DevTools protocol, waiting five real seconds per page so data loads and Recharts animations finish (Chrome's `--virtual-time-budget` flag leaves Recharts charts blank, which is why earlier Lapse and Segments screenshots showed empty plots). Each was inspected for overflow, clipped text, overlaps and contrast:

| Deliverable | File Path | Resolution | Description & Visual Verification |
|---|---|---|---|
| **Overview (Light)** | `docs/screenshots/overview_light.png` | 1440×900 | Headline finding, metric pills and the full-width S2 reliability diagram with its top-bin caption. |
| **Overview (Dark)** | `docs/screenshots/overview_dark.png` | 1440×900 | High-contrast dark theme verification; neutral slate card surfaces, readable tabular text. |
| **Ask (Light)** | `docs/screenshots/ask_light.png` | 1440×900 | Q1 query execution ("Which customers are almost certainly Champions?"), interpretation sentence, ParseStrip tokens, threshold slider, summary tiles (148 matched, 146.66 expected, £2,760,590 expected revenue), sortable table with ProbabilityBars. |
| **Ask (Dark)** | `docs/screenshots/ask_dark.png` | 1440×900 | Dark theme of the Ask page showing Q6 German customers query, dual threshold controls, and SQL panel. |
| **Segments (Light)** | `docs/screenshots/segments_light.png` | 1440×900 | HTML5 Canvas Uncertainty Map rendering all 3,961 customers with uncertainty halos, Okabe–Ito segment legend, 5 segment cards with mini-histograms. |
| **Segments (Dark)** | `docs/screenshots/segments_dark.png` | 1440×900 | Dark theme Uncertainty Map; bright categorical dots on dark canvas background. |
| **Lapse Risk (Light)** | `docs/screenshots/lapse_light.png` | 1440×900 | Metric tiles (Brier 0.2034, Skill Score +16.72%, ROC-AUC 0.7390, ECE 0.0343), 10-bin reliability diagram with count histogram. |
| **Lapse Risk (Dark)** | `docs/screenshots/lapse_dark.png` | 1440×900 | Dark theme of the lapse evaluation dashboard with sequential red line styling. |
| **Model Quality (Light)** | `docs/screenshots/quality_light.png` | 1440×900 | Stepped horizontal bar cleaning funnel, GMM BIC grid across 4 covariance types, bootstrap ARI histogram. |
| **Model Quality (Dark)** | `docs/screenshots/quality_dark.png` | 1440×900 | Dark theme of the model quality audit dashboard. |
| **About (Light)** | `docs/screenshots/about_light.png` | 1440×900 | Embedded system architecture diagram (`docs/architecture.png`), timeline, topics table, and limitations. |
| **About (Dark)** | `docs/screenshots/about_dark.png` | 1440×900 | Dark theme of the system architecture and documentation page. |
| **Customer Drawer** | `docs/screenshots/customer_drawer_light.png` | 1440×900 | Slide-over customer record (#14646) showing RFM stats, BID segment distribution, lapse risk gauge, and surrogate tree path. |

---

## 7. Verification Audit (`FRONTEND.md` Section 7 Checklist)

Every check specified in Section 7 of `FRONTEND.md` has been executed and verified:

| Check # | Requirement | Status | Evidence / Verification Method |
|---|---|---|---|
| **1** | `pytest` passes, including `tests/test_api.py` (FastAPI TestClient):<br>• Every endpoint returns 200.<br>• `/api/ask` handles "probably", "almost certainly", out-of-scope, and injection.<br>• Read-only connection refuses writes. | **PASS** | `tests/test_api.py` passed with 4 dedicated test functions in 4.28s. All 54 tests across the entire test suite pass cleanly (`pytest -v`). |
| **2** | `npm run build` succeeds with zero TypeScript errors. | **PASS** | `tsc -b && vite build` compiled 2,218 modules into `web/dist` in 5.69s with zero errors or warnings. |
| **3** | Background uvicorn health check: `curl -s http://localhost:8000/api/health` returns `{"status":"ok"}` and `curl -s http://localhost:8000/` returns the HTML page. | **PASS** | Verified via background task: `/api/health` returned HTTP 200 `{"status":"ok"}`; `/` returned HTTP 200 with `<div id="root"></div>` HTML bundle. |
| **4** | Headless browser screenshots at 1440×900 in light and dark modes inspected for overflow, overlapping elements, clipped text, and contrast. | **PASS** | Captured 13 PNG images into `docs/screenshots/` using headless Chrome; all inspected and verified. |
| **5** | Update documentation: `README.md`, `CLAUDE.md`, `docs/PROGRESS.md`, `docs/DECISIONS.md`, and `docs/explainers/phase-10.md`. | **PASS** | All documents updated, cross-referenced, and verified with zero forbidden placeholders. |
| **6** | Streamlit decommissioning: remove `streamlit` and `altair` from `requirements.txt`, remove `app/streamlit_app.py` and `tests/test_app.py`. | **PASS** | Packages removed from `requirements.txt`; files deleted via `git rm`; spaCy wheel pin test migrated into `tests/test_setup.py`. |

---

## 8. Known Issues, Limitations & Edge Cases Handled Honestly

1. **Zero-Placeholder Guarantee (Rule 2):**
   - Every number in the application is dynamically served from `app/app.duckdb` or pre-computed audit tables in `reports/tables/`. No hardcoded mock values, placeholder text ("TBD", "XX%"), or dummy cards exist.
2. **Evaluation Test Set Transparency (Rule 6):**
   - In accordance with viva guidelines, `eval/questions_test.csv` contains only the header row (`q_id,question,gold_sql,author`). The Quality page honestly displays this status: *"Test set: waiting for questions written by someone else (eval/questions_test.csv is currently header-only)"*.
3. **Country Demonym Aliasing:**
   - In queries such as *"Which German customers are probably Champions?"*, the adjective "German" is automatically mapped to the database country name "Germany" via `COUNTRY_ALIASES` in `src/nl/lexicon.py`.
4. **Boundary Edge Case Handling in Q6:**
   - When filtering on high joint thresholds (e.g. $P(\text{Champions}) \ge 0.66$ and $P(\text{lapse}) \ge 0.66$ in smaller countries like Germany where only 102 total customers exist), the query may match 0 customers. The UI displays an honest zero-state (`0 rows returned`, `£0 expected revenue`) rather than an error or fallback approximation.
5. **Surrogate Decision-Tree Approximations:**
   - The UI explicitly states on the Segments page and Customer Drawer that surrogate tree rules are interpretable approximations (86.80% test fidelity) of curved GMM boundaries in log-space.
