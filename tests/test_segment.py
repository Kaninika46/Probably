"""Phase 3 segmentation tests (CLAUDE.md section 7.4).

Verifies S3 preprocessing (99th percentile cap -> log1p -> StandardScaler),
the K-Means and GMM grids, and the candidate segment profile invariants.
"""

import numpy as np
import pandas as pd
import pytest

from src import config, db, segment

if not (config.TABLES_DIR / "gmm_grid.csv").exists():
    pytest.skip("Run `python -m src.pipeline --phase 3` first", allow_module_level=True)


def test_preprocess_s3_rfm_standardizes_to_zero_mean_unit_std():
    con = db.connect_app(config.DB_PATH)
    s3_df = segment.load_s3_features(con)
    con.close()

    x_scaled, caps_df = segment.preprocess_s3_rfm(s3_df)
    assert x_scaled.shape == (len(s3_df), 3)
    assert np.allclose(x_scaled.mean(axis=0), 0.0, atol=1e-6)
    assert np.allclose(x_scaled.std(axis=0), 1.0, atol=1e-6)
    assert set(caps_df["feature"]) == {"recency_days", "frequency", "monetary"}


def test_kmeans_grid_covers_k2_to_k8():
    km_df = pd.read_csv(config.TABLES_DIR / "kmeans_grid.csv")
    assert list(km_df["k"]) == list(config.K_RANGE)
    assert (km_df["silhouette"].between(-1.0, 1.0)).all()
    assert (km_df["davies_bouldin"] > 0).all()
    assert (km_df["calinski_harabasz"] > 0).all()


def test_gmm_grid_covers_all_28_combinations():
    gmm_df = pd.read_csv(config.TABLES_DIR / "gmm_grid.csv")
    assert len(gmm_df) == len(config.K_RANGE) * len(config.GMM_COVARIANCE_TYPES)
    assert set(gmm_df["covariance_type"]) == set(config.GMM_COVARIANCE_TYPES)
    assert set(gmm_df["k"]) == set(config.K_RANGE)


def test_proposed_profiles_sum_to_s3_customers_and_are_stable():
    con = db.connect_app(config.DB_PATH)
    n_s3 = con.execute("SELECT COUNT(*) FROM customer_features WHERE snapshot = 'S3'").fetchone()[0]
    con.close()

    for fname, expected_k in [
        ("segment_profiles_spherical_k5.csv", 5),
        ("segment_profiles_spherical_k4.csv", 4),
    ]:
        prof = pd.read_csv(config.TABLES_DIR / fname)
        assert len(prof) == expected_k
        assert int(prof["n_customers"].sum()) == n_s3
        assert prof["proposed_segment"].nunique() == expected_k
        assert (prof["jaccard_mean"] >= config.JACCARD_STABLE).all()
