"""اختبار محاذاة البروتوكول المجمَّد مع الإنتاج المعتمد — درس انزياح 2026-11.

الثغرة المعالجة: ترقية/تعديل نموذج الإنتاج (مثل P11: بصمة تكرارات +
max_features=0.3) لم يُقابَل في scripts/evaluate_generalization.py، فبقيت
بطاقات النماذج توثّق تكويناً قديماً رغم ادعاء «نفس مواصفات الإنتاج» —
ووُجد الانحراف متأخراً بمقارنة الأرقام (0.436 مقابل 0.440). هذا الاختبار
يجعل أي انزياح مستقبلي بين الطرفين يفشل فوراً لا بعد أسابيع.
"""
from __future__ import annotations

import inspect

import numpy as np
import pytest

from core import ml_potency
from scripts.evaluate_generalization import (
    COUNT_BASED,
    PROD_MAX_FEATURES,
    fit_rf,
)


def _production_train_source() -> str:
    return inspect.getsource(ml_potency.train_default_model)


def test_protocol_count_based_matches_production():
    """بروتوكول التقييم يستخدم بصمة التكرارات كالإنتاج المعتمد (P11)."""
    assert COUNT_BASED is True
    assert "count_based=True" in _production_train_source()


def test_protocol_max_features_matches_production():
    """عتبة max_features في البروتوكول تساوي المعتمد في الإنتاج حرفياً."""
    prod_src = _production_train_source()
    assert "max_features=0.3" in prod_src
    assert PROD_MAX_FEATURES == 0.3


def test_fit_rf_carries_production_max_features():
    """fit_rf يمرّر max_features المعتمد فعلاً إلى sklearn — لا ادعاء نصي."""
    rng = np.random.default_rng(0)
    X = (rng.random((40, 16)) > 0.5).astype(float)
    y = X.sum(axis=1) + rng.normal(scale=0.1, size=40)
    model = fit_rf(X, y, seed=0, n_estimators=10)
    assert model.max_features == pytest.approx(PROD_MAX_FEATURES)
