# References

Every methodological choice in *Probably High-Value?* is grounded in the published literature below. References are grouped by the pipeline component they support.

> [!NOTE] Citation Verification & Audit Record
> * **Verified against publisher record / DOI:**
>   - Chen (2019): UCI ML Repository (DOI: 10.24432/C5CG6D)
>   - Chen, Sain, & Guo (2012): Palgrave Macmillan / Springer (DOI: 10.1057/dbm.2012.17)
>   - Fayyad, Piatetsky-Shapiro, & Smyth (1996): AAAI AI Magazine
>   - Pedregosa et al. (2011): Journal of Machine Learning Research (JMLR)
>   - Scikit-learn Documentation: Official GMM / Model Selection specification
>   - Dalvi & Suciu (2007): VLDB Journal / Springer (DOI: 10.1007/s00778-007-0064-2)
>   - Suciu, Olteanu, Ré, & Koch (2011): Morgan & Claypool / Springer Nature (DOI: 10.2200/S00362ED1V01Y201105DTM017)
>   - Van den Broeck & Suciu (2017): Now Publishers (DOI: 10.1561/1900000052)
>   - Koch (2009): Springer (*Managing and Mining Uncertain Data*, Ch. 6, pp. 149–180)
>   - Huang, Antova, Koch, & Olteanu (2009): ACM SIGMOD 2009 (pp. 1071–1074, DOI: 10.1145/1559845.1559981)
>   - Mastrandrea et al. (2010): IPCC AR5 Guidance Note on Treatment of Uncertainties
>   - Kent (1964): Studies in Intelligence Vol. 8, No. 4 (CIA Historical Review Program)
>   - Yu et al. (2018): ACL Anthology (EMNLP 2018, Spider dataset)
>   - Li et al. (2023): NeurIPS 2023 (BIRD benchmark)
>   - Dasgupta, Frost, Moshkovitz, & Rashtchian (2020): PMLR (ICML 2020)
>   - Hennig (2007): Elsevier CSDA (DOI: 10.1016/j.csda.2006.11.025)
>   - Fader, Hardie, & Lee (2005): INFORMS Marketing Science (DOI: 10.1287/mksc.1040.0098)
> * **Not verified / Corrected:**
>   - The previously listed entry `"Antova, L., Koch, C., & Olteanu, D. (2009). MayBMS: A system for managing large probabilistic databases"` was audited, determined to be non-existent in publication databases, and replaced with the two genuine peer-reviewed MayBMS publications: Koch (2009, Springer) and Huang, Antova, Koch, & Olteanu (2009, ACM SIGMOD).

---

## 1. Dataset

- **Chen, D. [Daqing Chen] (2019).** *Online Retail II* [Dataset]. UCI Machine Learning Repository. DOI: [10.24432/C5CG6D](https://doi.org/10.24432/C5CG6D). URL: https://archive.ics.uci.edu/dataset/502/online+retail+ii (Licensed under CC BY 4.0).
  - Companion study on the same retailer: **Chen, D., Sain, S. L., & Guo, K. (2012).** Data mining for the online retail industry: A case study of RFM model-based customer segmentation using data mining. *Journal of Database Marketing & Customer Strategy Management*, 19(3), 197–208. DOI: [10.1057/dbm.2012.17](https://doi.org/10.1057/dbm.2012.17).
  - **How we use it:** Raw transactions from both sheets (`Year 2009-2010` and `Year 2010-2011`, totalling 1,067,371 rows across 2009-12-01 to 2011-12-09) are ingested unchanged into `raw_transactions` in `data/retail.duckdb` and cleaned through a logged six-step SQL funnel (`sql/02_clean_views.sql`).

---

## 2. Knowledge Discovery in Databases (KDD)

- **Fayyad, U., Piatetsky-Shapiro, G., & Smyth, P. (1996).** From data mining to knowledge discovery in databases. *AI Magazine*, 17(3), 37–54.
  - **How we use it:** Structures our end-to-end offline pipeline (`src/pipeline.py`) into explicit KDD stages: Selection & Cleaning (`sql/02_clean_views.sql`), Transformation & Temporal Feature Engineering (`sql/03_features.sql`), Data Mining (`src/segment.py`, `src/membership.py`, `src/lapse.py`), and Interpretation & Evaluation (`src/rules.py`, `src/evaluate.py`).

---

## 3. Gaussian Mixture Models & Model Selection

- **Pedregosa, F., Varoquaux, G., Gramfort, A., Michel, V., Thirion, B., Grisel, O., Blondel, M., Prettenhofer, P., Weiss, R., Dubourg, V., Vanderplas, J., Passos, A., Cournapeau, D., Brucher, M., Perrot, M., & Duchesnay, É. (2011).** Scikit-learn: Machine learning in Python. *Journal of Machine Learning Research*, 12, 2825–2830.
- **Scikit-learn Documentation.** *Gaussian Mixture Models (`sklearn.mixture.GaussianMixture`) and Gaussian Mixture Model Selection (BIC/AIC example)*. URL: https://scikit-learn.org/stable/modules/mixture.html
  - **How we use it:** Implements our K-Means (`K = 2..8`), Gaussian Mixture Model grid (`K = 2..8` across `{spherical, tied, diag, full}` covariance structures with `n_init=10`), and Platt-scaled (`CalibratedClassifierCV(method='sigmoid', cv=5)`) logistic regression lapse classifier. We combine BIC/AIC curves with silhouette scores and cluster degeneracy checks to select `spherical, K = 5` on S3 (`src/segment.py`).

---

## 4. Probabilistic Databases (BID Tables, Tuple-Independent Tables & Possible Worlds)

- **Dalvi, N., & Suciu, D. (2007).** Efficient query evaluation on probabilistic databases. *The VLDB Journal*, 16(4), 523–544.
- **Suciu, D., Olteanu, D., Ré, C., & Koch, C. (2011).** *Probabilistic Databases*. Synthesis Lectures on Data Management, Morgan & Claypool Publishers.
- **Van den Broeck, G., & Suciu, D. (2017).** Query processing on probabilistic data: A survey. *Foundations and Trends in Databases*, 7(3–4), 197–341. DOI: [10.1561/1900000052](https://doi.org/10.1561/1900000052).
- **Koch, C. (2009).** MayBMS: A System for Managing Large Uncertain and Probabilistic Databases. Chapter 6 in C. Aggarwal (Ed.), *Managing and Mining Uncertain Data*. Springer.
- **Huang, J., Antova, L., Koch, C., & Olteanu, D. (2009).** MayBMS: a probabilistic database management system. *SIGMOD 2009*, pp. 1071–1074. (and the MayBMS Manual on `repair key` block-independent-disjoint tables and `conf()` confidence aggregation).
  - **How we use it:** Defines our database schema in `sql/01_schema.sql`:
    - `segment_membership` is a **Block-Independent-Disjoint (BID)** relation where each `(customer_id, snapshot, method)` block forms a mutually exclusive probability distribution over the 5 segments ($\sum p = 1.0$, analogous to `repair key` in MayBMS).
    - `lapse_risk` is a **tuple-independent** probabilistic table storing each customer's calibrated 90-day lapse probability `p_lapse_90d`.
    - Templates Q1–Q6 (`sql/templates/`) evaluate exact confidence selection, normalised Shannon entropy, linearity-of-expectation segment sizes and revenues, top-$k$ ranking, and joint filtering without falsely multiplying dependent probabilities.
    - `src/worlds.py` implements a 10,000-world Monte Carlo possible-worlds sampler to verify Q3 expected sizes and variances numerically.

---

## 5. Verbal Probability Scales & Hedge Lexicon

- **Mastrandrea, M. D., Field, C. B., Stocker, T. F., Edenhofer, O., Ebi, K. L., Frame, D. J., Held, H., Kriegler, E., Mach, K. J., Matschoss, P. R., Plattner, G.-K., Yohe, G. W., & Zwiers, F. W. (2010).** *Guidance Note for Lead Authors of the IPCC Fifth Assessment Report on Consistent Treatment of Uncertainties*. Intergovernmental Panel on Climate Change (IPCC).
- **Kent, S. (1964).** Words of estimative probability. *Studies in Intelligence*, Vol. 8, No. 4. Central Intelligence Agency.
  - **How we use it:** Grounds our natural-language hedge lexicon (`src/nl/lexicon.py`) in published probability scales rather than arbitrary cutoffs:
    - `possibly`, `might` $\rightarrow P \ge 0.33$ (IPCC "about as likely as not" starts at 33%)
    - `probably`, `likely` $\rightarrow P \ge 0.66$ (IPCC "likely" 66–100%; Kent "probable" 63–87%)
    - `very likely`, `highly likely` $\rightarrow P \ge 0.90$ (IPCC "very likely" 90–100%)
    - `almost certainly`, `definitely` $\rightarrow P \ge 0.95$ (Kent "almost certain" $93\% \pm 6\%$)
    - `unlikely` $\rightarrow P \le 0.33$ (IPCC "unlikely" 0–33%)

---

## 6. Natural-Language to SQL Evaluation

- **Yu, T., Zhang, R., Yang, K., Yasunaga, M., Wang, D., Li, Z., Ma, J., Li, I., Yao, Q., Roman, S., Zhang, Z., & Radev, D. (2018).** Spider: A large-scale human-labeled dataset for complex and cross-domain semantic parsing and text-to-SQL task. In *Proceedings of the 2018 Conference on Empirical Methods in Natural Language Processing (EMNLP)*.
- **Li, J., Hui, B., Qu, G., Yang, J., Li, B., Li, B., Wang, B., Qin, B., Geng, R., Huo, N., Zhou, X., Ma, C., Li, G., Chang, K. C.-C., Huang, F., Cheng, R., & Li, Y. (2023).** Can LLM already serve as a database interface? A BIg bench for large-scale database grounded text-to-SQLs (BIRD). In *Advances in Neural Information Processing Systems (NeurIPS)*.
  - **How we use it:** Following Spider and BIRD, `src/evaluate.py` evaluates our NL interface using **execution accuracy** (comparing actual query result sets against gold SQL, order-insensitive unless the gold SQL contains a top-level `ORDER BY`) rather than brittle string matching, alongside template match rate, out-of-scope rejection rate, and hedge-threshold accuracy.

---

## 7. Explainable Clustering with Decision Trees

- **Dasgupta, S., Frost, N., Moshkovitz, M., & Rashtchian, C. (2020).** Explainable k-means and k-medians clustering. In *Proceedings of the 37th International Conference on Machine Learning (ICML)*.
  - **How we use it:** Motivates fitting a shallow axis-aligned decision-tree surrogate (`DecisionTreeClassifier(max_depth=4)` in original RFM units, `src/rules.py`) to translate our log-transformed, standardised spherical GMM segments into human-readable threshold rules (`reports/tables/tree_rules.md`), while explicitly reporting the 30% held-out fidelity (`86.80%` across 16 leaves) so users know the tree is an interpretable approximation of the curved cluster boundaries.

---

## 8. Clusterwise Bootstrap Stability

- **Hennig, C. (2007).** Cluster-wise assessment of cluster stability. *Computational Statistics & Data Analysis*, 52(1), 258–271.
  - **How we use it:** Guides our $B = 100$ nonparametric bootstrap co-assignment procedure (`src/membership.py`). On each resample of the 3,961 S3 customers, we refit the `spherical, K = 5` GMM, align cluster labels to the reference solution via the Hungarian algorithm (`scipy.optimize.linear_sum_assignment`), and measure per-segment Jaccard similarity across all 100 resamples. Using Hennig's stability bands ($\ge 0.75$ stable, $0.60\text{--}0.75$ doubtful, $< 0.60$ unstable), all five S3 segments are verified as stable (`At-Risk` = `0.8449`, `Champions` = `0.8669`, `New` = `0.8758`, `Loyal` = `0.8775`, `Hibernating` = `0.9009`).

---

## 9. Non-Contractual Customer Base Analysis (Alternative Not Used)

- **Fader, P. S., Hardie, B. G. S., & Lee, K. L. (2005).** "Counting your customers" the easy way: An alternative to the Pareto/NBD model. *Marketing Science*, 24(2), 275–284.
  - **Why it is mentioned:** In non-contractual retail settings like UCI Online Retail II, customers do not formally cancel an account, which is why we strictly model **90-day lapse** (no purchase in the next 90 days) rather than permanent "churn". The Beta-Geometric / Negative Binomial Distribution (BG/NBD) model of Fader, Hardie & Lee (2005) is the classic continuous-time parametric buy-till-you-die alternative that models transaction timing via Poisson purchase rates and geometric dropout after each transaction. We chose a supervised, Platt-calibrated logistic regression on temporal SQL snapshots (`S1` train, `S2` held-out test, `S3` score) instead of BG/NBD so we can directly include `monetary`, `tenure_days`, and `avg_basket` features alongside recency and frequency, evaluate 10-bin calibration error on a strictly held-out 90-day window (`S2`), and store the resulting 90-day lapse probability as a tuple-independent probabilistic attribute (`lapse_risk.p_lapse_90d`).
