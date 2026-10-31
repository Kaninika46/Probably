# Project Decisions & Checkpoint Status (`docs/DECISIONS.md`)

This document records every human-checkpoint decision in *Probably High-Value?* and distinguishes **confirmed** decisions from **provisional** defaults so the viva examination can inspect each choice transparently.

---

## 1. Phase 1: Revenue Accounting & Non-Product Stock Codes (CONFIRMED)

- **Excluded stock codes (Rule 5):** 21 non-product codes are excluded in `sql/02_clean_views.sql` (`POST`, `DOT`, `C2`, `M`, `m`, `ADJUST`, `ADJUST2`, `B`, `BANK CHARGES`, `AMAZONFEE`, `D`, `TEST001`, `TEST002`, `S`, and `gift_0001_10` … `gift_0001_80`).
  - Samples (`S`) are accounting adjustments rather than product sales.
  - Gift vouchers (`gift_0001_*`) are a payment instrument; counting both the purchase of a voucher and the products later bought with it would double-count revenue.
- **Single consistent set of revenue figures (`reports/tables/raw_totals.csv`, `cleaning_funnel.csv`, `clean_sales_summary.csv`, `snapshot_summary.csv`):**
  - **Raw net revenue (`1,067,371` rows in `raw_transactions`):** `£19,287,250.57` (includes negative cancellation and adjustment lines).
  - **Clean product sales revenue (`1,003,357` rows in `clean_sales` after Rules 1–5):** `£19,643,861.64`.
  - **Clean product sales revenue with a known `customer_id` (`776,596` rows after Rule 6):** `£17,068,582.74` (the `226,761` guest-checkout rows without a `customer_id` account for `£2,575,278.90`).
  - **Snapshot `S3` 9-month customer revenue (`3,961` customers active in `2011-03-10` to `2011-12-09`):** `£7,004,392.65`.

---

## 2. Phase 3 Checkpoint: Segmentation Model & Segment Names (PROVISIONAL)

- **Status:** **PROVISIONAL** (`CHOSEN_K = 5`, `CHOSEN_GMM_COV = "spherical"` in `src/config.py`).
- **Why `diag` and `full` were rejected:** Because `frequency` is a discrete integer (`1,480` of `3,961` S3 customers have `frequency = 1` and `781` have `frequency = 2`), `diag` and `full` covariance matrices collapse components onto zero-variance integer planes (`reports/tables/gmm_diag_degeneracy.csv`), producing artificial likelihood spikes and low silhouette (`0.10–0.18`).
- **Why `spherical, K = 5` is the provisional choice:** Among non-degenerate models (`spherical` and `tied`), `spherical, K = 5` achieves `BIC = 23,604.24`, `AIC = 23,453.42`, silhouette `0.3106`, bootstrap ARI median `0.8674` (IQR `0.0977`), and per-segment mean Jaccard $\ge 0.8449$ across all 5 segments (`Champions` `0.8669`, `Loyal` `0.8775`, `At-Risk` `0.8449`, `New` `0.8758`, `Hibernating` `0.9009`), while separating wholesale `Champions` (`258` customers, median spend `£5,455.26`, median recency `5.0` days) from regular `Loyal` buyers (`1,105` customers, median spend `£1,579.14`, median recency `17.0` days).
- **Preserved alternatives:** `reports/tables/segment_profiles_spherical_k4.csv` and `reports/tables/segment_profiles_tied_k4.csv` remain exported so switching `CHOSEN_K` to `4` requires changing only `src/config.py`.

---

## 3. Phase 4 Gate Checkpoint: Default Membership Method & Headline (PROVISIONAL)

- **Status:** **PROVISIONAL** (`DEFAULT_METHOD = "gmm"` in `src/config.py` and `/api/*`).
- **Gate findings (`reports/tables/gate.csv`):**
  - Under **`method = 'gmm'`** (Gaussian mixture posteriors), **`12.50%`** of S3 customers (`495` of `3,961`) sit on a segment boundary (`max p < 0.60`), with mean normalised entropy `0.2526`.
  - Under **`method = 'bootstrap'`** ($B = 100$ resample co-assignment probabilities), **`3.84%`** of S3 customers (`152` of `3,961`) have `max p < 0.60`, with mean normalised entropy `0.1041`, confirming high cluster stability across resamples.
- **Provisional gate decision:**
  1. **Default membership method in API & UI:** `gmm` is used as the default in the web app (`GET /api/segments?method=gmm`, `GET /api/segments/map?method=gmm`) because its `12.50%` boundary share displays genuine continuous cluster-boundary uncertainty, while `bootstrap` is exposed via a one-click UI toggle as the stability check.
  2. **Overview headline:** The Overview page leads with **calibrated 90-day lapse risk** (*"When we say a customer is 70% likely to lapse, about that share really do"*, backed by S2 Brier score `0.2034`, Brier skill score `0.1672`, ROC-AUC `0.7390`, and 10-bin ECE `0.0343`), paired with segment membership confidence in `Q6`.


---

## 4. Phase 10: Frontend Architecture Migration (FastAPI + React/TS/Tailwind) (CONFIRMED)

- **Status:** **CONFIRMED** (`FRONTEND.md` implemented, Streamlit removed).
- **Motivation:** The initial Streamlit prototype (`app/streamlit_app.py`) re-executed script code on widget clicks, mixed presentation with query execution, lacked custom canvas rendering for large customer scatter plots, and could not strictly enforce design token isolation ("colour only means data").
- **Adopted Architecture:**
  1. **Read-only FastAPI Backend (`api/main.py`, `api/schemas.py`):**
     - Typed Pydantic v2 schemas for all responses.
     - Storage-level read-only connection to `app/app.duckdb` (`read_only=True`).
     - Zero string interpolation: natural language queries map exclusively through parameterised templates `Q1`–`Q6` with strict allow-list validation.
     - Serves static assets and production SPA bundle from `web/dist` on `http://localhost:8000`.
  2. **Production React + TypeScript Web Application (`web/`):**
     - UI built with Vite, Tailwind CSS, Lucide icons, Recharts, and self-hosted `@fontsource` typography (`Bricolage Grotesque`, `Figtree`, `JetBrains Mono`).
     - Strict token-driven styling via CSS custom properties in `tokens.css`; zero raw `#...` hex literals in component source code.
     - Okabe–Ito categorical segment palette and 4-step sequential red ramp for 90-day lapse risk.
     - Custom HTML5 `<canvas>` Uncertainty Map rendering all 3,961 S3 customers with uncertainty halos at 60fps, hit-testing, and slide-over customer detail drawer.
  3. **Streamlit Decommissioning:**
     - Removed `streamlit==1.66.1` and `altair==6.3.0` from `requirements.txt`.
     - Deleted `app/streamlit_app.py` and `tests/test_app.py`.
     - Consolidated all test assertions into `tests/test_api.py` and `tests/test_setup.py`.
