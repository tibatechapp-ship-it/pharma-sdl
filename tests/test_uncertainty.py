"""اختبارات المعاير conformal — ضمان التغطية يُقاس لا يُدَّعى (P4)."""

from __future__ import annotations

import numpy as np
import pytest
from sklearn.ensemble import RandomForestRegressor

from pharma_sdl.uncertainty import ConformalCalibrator


def _synthetic_regression(n: int = 500, noise: float = 0.8, seed: int = 7):
    """y = f(x) + ضجيج ثابت التباين — تغطية conformal قابلة للتحقق نظرياً."""
    rng = np.random.default_rng(seed)
    X = rng.uniform(0, 1, size=(n, 4))
    y = (
        2.0 * X[:, 0]
        - 1.5 * X[:, 1]
        + 0.5 * np.sin(6.0 * X[:, 2])
        + rng.normal(0.0, noise, size=n)
    )
    return X, y


def test_coverage_matches_nominal_on_synthetic():
    X, y = _synthetic_regression(n=500, noise=0.8, seed=7)
    idx = np.arange(len(y))
    rng = np.random.default_rng(0)
    perm = rng.permutation(len(y))
    tr, cal, te = idx[perm[:250]], idx[perm[250:350]], idx[perm[350:]]
    model = RandomForestRegressor(n_estimators=80, random_state=0, n_jobs=1)
    model.fit(X[tr], y[tr])
    calib = ConformalCalibrator(model.predict(X[cal]), y[cal], alpha=0.10)
    coverage = calib.coverage(model.predict(X[te]), y[te])
    # تغطية فعلية قريبة من الاسمية 0.90 — والانحراف المسموح معلن في الاختبار
    assert 0.83 <= coverage <= 0.97
    assert calib.finite_sample_guarantee is True
    assert calib.nominal_coverage == pytest.approx(0.90)


def test_interval_is_symmetric_and_deterministic():
    rng = np.random.default_rng(3)
    calib = ConformalCalibrator(
        rng.normal(0, 1, 200), rng.normal(0, 1, 200), alpha=0.10
    )
    lo, hi = calib.interval(5.0)
    assert hi - lo == pytest.approx(2 * calib.q)
    assert (lo + hi) / 2 == pytest.approx(5.0)
    lo2, hi2 = calib.interval(5.0)
    assert (lo, hi) == (lo2, hi2)


def test_smaller_alpha_yields_wider_interval():
    residuals = np.abs(np.random.default_rng(11).normal(0, 1, 300))
    preds = np.zeros(300)
    trues = preds + residuals * np.sign(np.random.default_rng(12).normal(size=300))
    narrow = ConformalCalibrator(preds, trues, alpha=0.20)
    wide = ConformalCalibrator(preds, trues, alpha=0.05)
    assert wide.q > narrow.q


def test_rejects_bad_alpha_and_short_calibration():
    rng = np.random.default_rng(1)
    preds = rng.normal(size=50)
    with pytest.raises(ValueError):
        ConformalCalibrator(preds, preds, alpha=0.0)
    with pytest.raises(ValueError):
        ConformalCalibrator(preds[:1], preds[:1], alpha=0.1)


def test_summary_reports_honest_fields():
    rng = np.random.default_rng(5)
    calib = ConformalCalibrator(rng.normal(size=100), rng.normal(size=100), alpha=0.2)
    s = calib.summary()
    assert s["method"] == "split_conformal_absolute_residual"
    assert s["n_calib"] == 100
    assert s["nominal_coverage"] == pytest.approx(0.8)
    assert s["finite_sample_guarantee"] is True
