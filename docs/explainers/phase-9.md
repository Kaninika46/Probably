# Phase 9 Explainer: Automated Report Tables, References & Viva Synthesis

## Plain-Language Overview

Phase 9 ties together the entire *Probably High-Value?* project so every number in the documentation is directly traceable to code run on the UCI Online Retail II dataset (`1,067,371` raw rows) and every methodological choice is backed by a verified academic citation.

### 1. Why `src/report_tables.py` Generates the README Tables Automatically
In many student projects, numbers in `README.md` drift out of sync with the actual code outputs or get rounded by hand. To enforce Rule 1 of `CLAUDE.md` (*never invent, estimate, or round up numbers*), `src/report_tables.py` reads the seven core CSV files in `reports/tables/`:
1. `cleaning_funnel.csv` (6-step SQL cleaning funnel from `1,067,371` raw rows to `776,596` customer-identified clean sale rows)
2. `snapshot_summary.csv` (`S1 = 3,256`, `S2 = 3,247`, `S3 = 3,961` customers; base 90-day lapse rates `S1 = 41.40%`, `S2 = 42.38%`)
3. `segment_profiles_spherical_k5.csv` and `tree_fidelity.csv` (`Champions`, `Loyal`, `At-Risk`, `New`, `Hibernating` profiles, bootstrap ARI median `0.8674`, per-segment Jaccard `0.8449`–`0.9009`, and depth-4 decision-tree surrogate with `86.80%` held-out test fidelity across `16` leaves)
4. `gate.csv` (`gmm` boundary share `12.50%` / `495` customers vs `bootstrap` boundary share `3.84%` / `152` customers)
5. `kmeans_vs_expected_sizes.csv` (hard counts vs probabilistic expected sizes $\sum p_i$ and independent standard deviations $\sqrt{\sum p_i(1-p_i)}$)
6. `lapse_s2_eval.csv` (held-out `S2` evaluation: `logistic_calibrated` Brier `0.2034`, ROC-AUC `0.7390`, log loss `0.5870`, 10-bin ECE `0.0343`)
7. `nl_summary.csv` (26-question dev benchmark: `100.0%` execution accuracy, template match, out-of-scope rejection, and hedge-threshold accuracy)

It writes these seven tables to `reports/tables/readme_results.md` and injects them directly between `<!-- BEGIN AUTO-GENERATED RESULTS -->` and `<!-- END AUTO-GENERATED RESULTS -->` in `README.md`.

### 2. Verified Literature (`docs/references.md`)
`docs/references.md` documents the nine foundational references behind our system:
- **Dataset:** Daqing Chen (2019), *Online Retail II*, DOI `10.24432/C5CG6D` (CC BY 4.0), and Chen, Sain & Guo (2012).
- **KDD Process:** Fayyad, Piatetsky-Shapiro & Smyth (1996).
- **Gaussian Mixture Models & BIC Selection:** Pedregosa et al. (2011) and the scikit-learn GMM/BIC documentation.
- **Probabilistic Databases:** Dalvi & Suciu (2007), Suciu et al. (2011), Van den Broeck & Suciu (2017), and the MayBMS manual (`repair key` for BID tables and `conf()` for confidence queries).
- **Verbal Probability Scales:** IPCC AR5 Uncertainty Guidance Note (Mastrandrea et al., 2010) and Sherman Kent (1964), *Words of Estimative Probability*.
- **Text-to-SQL Evaluation:** Spider (Yu et al., 2018) and BIRD (Li et al., 2023) for execution accuracy.
- **Explainable Clustering:** Dasgupta, Frost, Moshkovitz & Rashtchian (ICML 2020) for axis-aligned decision-tree explanations of clusters.
- **Clusterwise Bootstrap Stability:** Hennig (2007) for Jaccard stability bands ($\ge 0.75$ stable).
- **Buy-Till-You-Die Alternative:** Fader, Hardie & Lee (2005) BG/NBD model, explained as the classic continuous-time non-contractual alternative not used here.

---

## 5 Likely Viva Questions & Answers

### Q1. How do the three course topics (Topic 3 KDD, Topic 1 Probabilistic Databases, Topic 2 NLP for Databases) connect in your architecture?
**Answer:**
1. **Topic 3 (Data Mining & KDD)** cleans `1,067,371` raw transactions down to `776,596` customer-level clean sale rows, builds leak-free RFM snapshots (`S1`, `S2`, `S3`), fits a `spherical, K=5` Gaussian Mixture Model and a $B=100$ bootstrap ensemble on `S3` (`3,961` customers), and trains a Platt-calibrated 90-day lapse classifier on `S1` (`3,256` customers, verified once on `S2 = 3,247` customers with Brier score `0.2034` and ROC-AUC `0.7390`).
2. **Topic 1 (Probabilistic Databases)** stores those mining outputs not as flat hard labels, but as formal uncertain relations: a **Block-Independent-Disjoint (BID)** table `segment_membership` (`39,610` rows where each `(customer_id, snapshot, method)` block sums to `1.0`) and a **tuple-independent** table `lapse_risk` (`3,961` rows with `p_lapse_90d`).
3. **Topic 2 (NLP for Database Interaction)** parses plain-English questions with `spaCy` and maps verbal hedges like *"probably"* ($\ge 0.66$) and *"almost certainly"* ($\ge 0.95$) from the IPCC AR5 and Sherman Kent scales into typed parameters for SQL templates `Q1`–`Q6` against read-only `app/app.duckdb`.

### Q2. Why did you mention the BG/NBD model (Fader, Hardie & Lee, 2005) in `docs/references.md` if you used calibrated logistic regression for lapse risk?
**Answer:**
In non-contractual retail (where customers do not have a subscription to cancel), Fader, Hardie & Lee's (2005) BG/NBD model is the classic continuous-time parametric benchmark that models purchase frequency as a Poisson process and permanent dropout after any purchase as a geometric coin flip, using only `(recency, frequency, T)`. We chose supervised Platt-calibrated logistic regression across temporal SQL snapshots (`S1` $\rightarrow$ `S2` $\rightarrow$ `S3`) for three project-specific reasons:
1. It predicts a clean, bounded **90-day lapse event** (`purchased_next_90d = 0`) that can be directly verified on the held-out `S2` outcome window (`2011-09-10` to `2011-12-09`, base lapse rate `42.38%`).
2. Unlike standard BG/NBD, it incorporates `monetary` and `avg_basket` alongside recency, frequency, and tenure.
3. Its 10-bin calibration can be audited directly via Expected Calibration Error (`ECE = 0.0343` on `S2`) before storing `p_lapse_90d` in the tuple-independent `lapse_risk` table.

### Q3. How does your project guarantee that no numbers in `README.md` were invented or hand-edited?
**Answer:**
Every empirical table in `README.md` sits inside `<!-- BEGIN AUTO-GENERATED RESULTS -->` and `<!-- END AUTO-GENERATED RESULTS -->` markers and is written programmatically by `src/report_tables.py` (Phase 9 of `src/pipeline.py`). In addition, `tests/test_phase9.py` re-runs `build_all_tables_md()` during `pytest` and asserts that the text inside `README.md` matches the live output of `reports/tables/*.csv` byte-for-byte, and scans the repository to verify that no placeholder strings exist anywhere.

### Q4. According to Dasgupta et al. (ICML 2020), why is a depth-4 decision tree only an approximation of your GMM clusters?
**Answer:**
Our `spherical, K=5` Gaussian Mixture Model partitions customers using spherical Gaussian densities in **log-transformed (`log1p`), standardised (`StandardScaler`)** RFM space, which creates smooth, curved boundaries when mapped back to original pounds and days. By contrast, a shallow decision tree (`DecisionTreeClassifier(max_depth=4)` with `16` leaves) only makes axis-aligned rectangular cuts (`recency_days <= 44.5`, `frequency <= 3.5`, `monetary <= 1057.33`). As Dasgupta et al. (2020) show, bounding the tree depth makes the clusters human-explainable at a small fidelity cost: on our 30% held-out test split of `S3` (`1,189` customers), the depth-4 tree agrees with the GMM hard label on `86.80%` of customers (`89.72%` on train), with nearly all disagreements occurring among the `12.50%` boundary customers (`max p < 0.60`).

### Q5. If an examiner clones this repository on a fresh machine, how do they reproduce the entire database, all tables, all figures, and the app from scratch?
**Answer:**
1. Create a Python 3.12 virtual environment and run `pip install -r requirements.txt`.
2. Run `python data/download.py` to fetch the UCI Online Retail II workbook into `data/raw/online_retail_II.xlsx`.
3. Run `python -m src.pipeline --all`, which executes Phases 1, 2, 3, 4, 5, 6, 7, and 9 deterministically (`random_state = 42` in `src/config.py`), rebuilding `data/retail.duckdb`, `app/app.duckdb`, all CSVs in `reports/tables/`, all PNGs in `reports/figures/`, and the results section of `README.md`.
4. Run `pytest -v` to verify all cleaning, zero-leakage, BID probability, template, NL security, read-only, and documentation tests.
5. Launch `streamlit run app/streamlit_app.py` to explore the interactive 4-tab application.
