"""اختبارات مقارنة النماذج — RandomForest مقابل GradientBoosting (P2-1)."""
from __future__ import annotations

import pandas as pd
import pytest

from core.ml_compare import ModelReport, compare_models


@pytest.fixture(scope="module")
def reports():
    """أعداد صغيرة (طيّات/أشجار أقل) لسرعة الاختبار — حتمية بثابت 42."""
    return compare_models(folds=3, n_estimators=60, seed=42)


def test_reports_are_dataclass_with_full_fields(reports):
    for r in reports:
        assert isinstance(r, ModelReport)
        assert r.name and r.name_ar
        assert r.n_folds == 3
        assert r.n_samples > 20


def test_two_models_compared(reports):
    assert {r.name for r in reports} == {"RandomForest", "GradientBoosting"}


def test_metrics_within_valid_ranges(reports):
    for r in reports:
        assert -1.0 <= r.r2 <= 1.0
        assert r.rmse >= 0.0
        assert r.mae >= 0.0
        assert r.fit_seconds >= 0.0


def test_deterministic_given_same_seed():
    """نفس البذرة → نفس المقاييس (fit_seconds وحده متغير بطبيعته)."""
    a = compare_models(folds=3, n_estimators=60, seed=42)
    b = compare_models(folds=3, n_estimators=60, seed=42)
    for ra, rb in zip(a, b):
        assert (ra.r2, ra.rmse, ra.mae) == (rb.r2, rb.rmse, rb.mae)


def test_insufficient_data_raises(tmp_path):
    p = tmp_path / "tiny.csv"
    pd.DataFrame(
        {
            "smiles": ["CCO"] * 5,
            "pchembl_value": [5.0, 6.0, 5.5, 4.8, 6.2],
        }
    ).to_csv(p, index=False)
    with pytest.raises(ValueError, match="غير كافية"):
        compare_models(path=p, folds=3, n_estimators=10)
