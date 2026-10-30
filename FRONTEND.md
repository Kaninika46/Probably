# FRONTEND.md: replace Streamlit with a designed web app

**Goal:** replace the Streamlit app with a polished, presentation-grade web app that runs on **http://localhost:8000** from one command (`run_app.bat`).

The visual bar is a modern analytics product, not a notebook demo. **All analysis stays in Python.** The front-end only displays what the API returns, so the viva stays about the three course topics.

This file overrides every Streamlit mention in `CLAUDE.md` (sections 2, 4, 5, 7.11 and the phase table). Update `CLAUDE.md`, the README and the explainers to match.

## 0. Before starting

1. Run `node --version`. Node **20 or newer** is required. If it's missing or too old, stop and tell the user to run `winget install OpenJS.NodeJS.LTS`, then restart the terminal.
2. Make sure the morning-review fixes are finished: one consistent revenue number, K = 5 marked PROVISIONAL, a Brier skill score in the lapse results, and the UTF-8 test. If any are missing, do them first.
3. `CLAUDE.md` rules still apply:
   - no invented numbers;
   - no placeholders;
   - code a student can explain;
   - tests must pass;
   - commit after each step.
4. **The front-end never hard-codes a number.** Every figure comes from the API, which reads `app/app.duckdb` (read-only) and `reports/tables/`.

## 1. Stack (approved; these dependencies may be added)

| Layer | Choice |
|---|---|
| API | **FastAPI** + **uvicorn** in `api/`. Reuses `src/nl/engine.py`, `src/prob_queries.py` and the templates. Opens `app/app.duckdb` with `read_only=True` |
| Front-end | **React + TypeScript + Vite** in `web/` |
| Styling | **Tailwind CSS**, with the design tokens below as CSS variables in `web/src/styles/tokens.css` |
| Charts | **Recharts**, or plain SVG/canvas where Recharts is limiting (the 4k-point map may use canvas) |
| Icons | **lucide-react** |
| Fonts | Self-hosted via `@fontsource` (works offline): **Bricolage Grotesque** (headings), **Figtree** (UI and body), **JetBrains Mono** (SQL and code). If a package name differs, use the closest official `@fontsource` package |
| Serving | In production, FastAPI serves the built `web/dist` at `/`, so the whole app is **one port: 8000**. During development, Vite proxies `/api` to 8000 |

Add `fastapi` and `uvicorn` to `requirements.txt`, pinned. Once the new app passes every check in section 7, remove `streamlit`, `app/streamlit_app.py` and its test.

## 2. API (`api/main.py`, `api/schemas.py`): read-only

All responses are typed with Pydantic, and errors return friendly messages.

| Endpoint | Returns |
|---|---|
| `GET /api/health` | `{"status": "ok"}` |
| `GET /api/meta` | dataset name, licence, snapshot date, customer count, segment list with colours, hedge lexicon, headline (from the gate decision) |
| `POST /api/ask` `{question, overrides?: {tau?, tau2?, method?}}` | `status` (ok / refused), `interpretation`, `tokens` (text, label, start, end), `thresholds` (word → value), `template_id`, `sql`, `params`, `columns`, `rows`, `row_count`, `summary` (matched, expected_count, expected_revenue when relevant) |
| `GET /api/segments?method=gmm` | per segment: name, hard count, expected size, median R/F/M, tree rule, histogram of max-p |
| `GET /api/segments/map?method=gmm` | one point per customer: id, recency_days, monetary, frequency, segment, max_p |
| `GET /api/customers/{id}` | features, membership for both methods across all segments, p_lapse_90d, tree rule path |
| `GET /api/lapse` | S2 metrics (Brier, Brier skill score, ROC-AUC, log loss, ECE), reliability bins, baseline comparison, top 20 high-monetary customers with the highest p_lapse |
| `GET /api/quality` | cleaning funnel, BIC grid, bootstrap ARI distribution, per-segment Jaccard, tree fidelity, NL dev metrics, test-set status |

The default membership method is **`gmm`** (provisional; record it in `docs/DECISIONS.md`). The UI lets the user switch to `bootstrap`, which is presented as the stability check.

## 3. Design direction: "colour only means data"

**The idea:** a calm, monochrome interface where colour is reserved for data. Segments have colours, lapse risk has a red ramp, and everything else is ink on paper. Uncertainty is shown, never hidden: faded marks mean "less sure".

**Light theme is the default**, because projectors wash out dark UIs. Dark mode comes through a toggle and the OS setting.

### Tokens (put them in `tokens.css`; never use raw hex values in components)

| Token | Light | Dark |
|---|---|---|
| `--bg` | `#F7F8FA` | `#0E1116` |
| `--surface` | `#FFFFFF` | `#151A21` |
| `--surface-2` | `#F0F2F5` | `#1C222B` |
| `--ink` | `#12161C` | `#ECEFF3` |
| `--ink-2` | `#3A4250` | `#C9CFD8` |
| `--muted` | `#6B7380` | `#9AA3AF` |
| `--line` | `#E2E5EA` | `#2A313B` |
| `--focus` | `#12161C` | `#ECEFF3` |

**Segment colours** (Okabe–Ito, colour-blind safe), in light / dark:

| Segment | Light | Dark |
|---|---|---|
| Champions | `#009E73` | `#2BC48F` |
| Loyal | `#0072B2` | `#4FA3E0` |
| New | `#CC79A7` | `#E59AC4` |
| At-Risk | `#E69F00` | `#F2B33D` |
| Hibernating | `#7A7F87` | `#A3A9B1` |

Map segment names from `/api/meta` and never assume the order.

**Lapse-risk ramp** (sequential red), from p = 0 to p = 1: `#FDE8E7` → `#F7B4AE` → `#F04438` → `#C0261B` → `#7A1A12`. Use a lighter version in dark mode.

**Primary buttons** are solid ink: `--ink` background with `--bg` text.

### Typography

| Use | Font and size |
|---|---|
| Display | Bricolage Grotesque, 600, 40/44 |
| H1 | Bricolage Grotesque, 28/34 |
| H2 | Bricolage Grotesque, 20/26 |
| Body | Figtree, 15/24 |
| Small | Figtree, 13/18 |
| SQL and code | JetBrains Mono, 13/20 |

- Every number uses `font-variant-numeric: tabular-nums`.
- Uppercase labels: 11px, letter-spacing 0.08em.

### Shape and spacing

- 4px base grid; card padding 20–24; gaps 16/24.
- Radius: 12 for cards, 8 for inputs, full for pills.
- Cards have a 1px `--line` border and at most a hairline shadow (`0 1px 2px rgba(16,24,40,.06)`). No gradients, no glassmorphism, and no coloured accent bars on cards.
- Motion: 150–200ms ease-out for fades and bar growth. Everything respects `prefers-reduced-motion`.

### Signature components (build these with care; they make the app memorable)

1. **ProbabilityBar.** A thin track with a fill up to p in the segment colour (or lapse red), a vertical tick at the active threshold, and the value in mono (e.g. `0.81`). Use it everywhere a probability appears.
2. **ParseStrip.** The user's question re-rendered with each recognised span marked:
   - segment: underline in the segment colour;
   - country: dotted underline;
   - hedge word: an inline pill such as `probably → P ≥ 0.66`;
   - numbers and comparisons: a subtle highlight.

   Hovering shows the label. This is the visible proof of the NLP topic.
3. **Uncertainty map.** A scatter of all customers: x = days since last purchase (reversed, so recent is on the right), y = monetary on a log scale. Colour = segment; opacity = confidence (max p, mapped 0.25 to 1).
   - Caption: "Faded dots are customers between segments."
   - Includes a method toggle (gmm / bootstrap), a hover tooltip, and click-to-open the customer drawer.
4. **Threshold control.** For each hedge word in the answer, a compact slider from 0.05 to 0.99 with labelled ticks at 0.33, 0.66, 0.90 and 0.95 (the IPCC and Kent anchors). Changing it re-runs the query, debounced to 300ms.
5. **Customer drawer.** A right-side sheet showing:
   - customer id and country;
   - R/F/M facts;
   - a 100% stacked bar of segment membership, one row for gmm and one for bootstrap;
   - a lapse gauge (ProbabilityBar in red);
   - the decision-tree rule path written in plain words.

## 4. Pages (left sidebar navigation, 240px; content max-width 1200px)

The top bar shows the product name **Probably**, the subtitle "Customer intelligence with honest confidence", a dataset badge ("UCI Online Retail II · snapshot 10 Dec 2011 · N customers", with N from the API) and the theme toggle. The footer status reads "Read-only · app.duckdb".

1. **Overview** (`/`):
   - a headline that follows the gate decision. With lapse risk as the headline: "When we say a customer is 70% likely to lapse, about that share really do." This is backed by a mini reliability chart and the Brier skill score from the API;
   - a large Ask bar that goes to the Ask page;
   - a segment summary strip: five chips with hard count vs expected size;
   - three stat tiles: customers, segments, lapse calibration error.
2. **Ask** (`/ask`). The heart of the app.
   - A command-bar input, 56px tall. Enter submits; `/` focuses it.
   - Six example chips, one per template, including "Which German customers are probably Champions but likely to lapse?"
   - Each answer shows, in this order:
     - the interpretation sentence (large);
     - the ParseStrip;
     - threshold controls;
     - summary tiles (matched; expected count vs hard count; expected revenue when relevant);
     - a results table with inline ProbabilityBars (sortable; clicking a row opens the drawer);
     - a small chart where it helps (for example the distribution of p in the result);
     - a collapsible SQL panel with syntax highlighting, a parameters table and a copy button.
   - Out-of-scope questions get a friendly refusal card with three clickable suggestions.
   - Keep the last 5 questions as a history list in the sidebar section.
3. **Segments** (`/segments`): the uncertainty map (full width); five segment cards (name, colour, hard vs expected count, median R/F/M, tree rule, max-p mini histogram); and a bar chart of hard vs expected size per segment.
4. **Lapse risk** (`/lapse`): metric tiles (Brier, skill score, ROC-AUC, ECE), the reliability diagram (predicted vs observed with the diagonal and a count bar underneath), the model vs baselines comparison, and a "high value, likely to lapse" table.
5. **Model quality** (`/quality`): the cleaning funnel as stepped horizontal bars, the BIC chart by K and covariance type, the bootstrap ARI histogram, per-segment Jaccard bars with the 0.75 reference line, and NL dev metrics. The test set is shown honestly as "Test set: waiting for questions written by someone else".
6. **About** (`/about`): `docs/architecture.png`, the S1–S3 snapshot timeline, how each part maps to Topics 3, 1 and 2, limitations, and the dataset licence and citation.

Every chart gets a one-line takeaway title stating what it shows, axis labels with units, tooltips, and an `aria-label`. Use loading skeletons, not spinners. Empty and error states explain what happened and what to do.

## 5. Quality bar

- **Accessibility:** WCAG AA contrast in both themes, full keyboard navigation, visible focus rings, `aria-live` for new answers.
- **Responsive:** looks right at 1440×900 and 1280×800 (projector), and is still usable at 768px.
- **Performance:** API responses under 300ms locally; the map stays smooth with every customer drawn.
- **Code organisation:** `web/src/{pages,components,charts,lib,styles}`. Each component file has a short top comment saying what it shows and which API field it uses.

## 6. Run scripts

`run_app.bat` (repo root):
```
@echo off
cd /d %~dp0
if not exist web\dist\index.html (
  pushd web
  call npm ci
  call npm run build
  popd
)
call .venv\Scripts\activate.bat
start "" http://localhost:8000
uvicorn api.main:app --port 8000
```
Also add `run_dev.bat`, which starts uvicorn with `--reload` and `npm run dev` in two windows, and document both in the README.

## 7. Verification (all must pass before removing Streamlit)

1. `pytest` passes, including the new `tests/test_api.py` (FastAPI TestClient):
   - every endpoint returns 200;
   - `/api/ask` handles a "probably" question, an "almost certainly" question, an out-of-scope question and an injection string (`'; DROP TABLE customers; --` must never reach SQL);
   - the database connection refuses writes.
2. `npm run build` succeeds with zero TypeScript errors.
3. Start uvicorn **in the background**. Check that `curl -s http://localhost:8000/api/health` returns ok and that `curl -s http://localhost:8000/` returns the HTML page. Then stop the server.
4. If you have a browser or screenshot tool, open every page at 1440×900 in light and dark. Look for overflow, overlapping elements, clipped text and low contrast, and fix them. Save the final screenshots to `docs/screenshots/` and use them in the README. If you have no browser tool, say so in the report.
5. Update the README (screenshots, how to run), `CLAUDE.md`, `docs/PROGRESS.md`, `docs/DECISIONS.md`, and `docs/explainers/phase-10.md`. The explainer covers how the browser talks to the API, why the API is read-only, and why all logic lives in Python, with 5 viva questions.
6. Commit after each step, then write `docs/FRONTEND_REPORT.md`: what was built, how to run it, screenshots, known issues and test results.
