"""اختبارات بطاقات النماذج — كلها offline على بيانات صناعية سريعة.

العقود التي تُختبر: فترات الثقة حتمية بالبذرة وتحتوي النقطة، والمعايرة
تُطابق القطر على بيانات مثالية، وعتبة AD تُفصل الإقليم البعيد فعلاً.
"""
import json

import numpy as np
import pytest
from sklearn.ensemble import RandomForestRegressor

from core.model_cards import (
    ApplicabilityDomain,
    applicability_report,
    bootstrap_metric,
    build_model_card,
    calibration_bins,
    fit_applicability_domain,
    metrics_with_ci,
    nn_tanimoto_similarity,
    uncertainty_calibration,
)

RNG = np.random.default_rng(7)


def _regression_data(n=300, noise=0.3, seed=1):
    """انحدار خطي صناعي نظيف — y = x·w + ضوضاء."""
    rng = np.random.default_rng(seed)
    X = rng.normal(size=(n, 8))
    y = X @ np.linspace(1, -1, 8) + rng.normal(scale=noise, size=n)
    return X, y


# ── فترات الثقة ──────────────────────────────────────────────


def test_bootstrap_metric_deterministic_and_brackets_point():
    _, y = _regression_data()
    pred = y + RNG.normal(scale=0.5, size=len(y))
    a = bootstrap_metric(y, pred, metric="r2", n_boot=200, seed=42)
    b = bootstrap_metric(y, pred, metric="r2", n_boot=200, seed=42)
    assert a == b  # البذرة تحفظ إعادة الإنتاج
    assert a["ci95"][0] <= a["point"] <= a["ci95"][1]
    assert a["n"] == len(y) and a["seed"] == 42


def test_metrics_with_ci_three_metrics():
    _, y = _regression_data()
    pred = y + 0.2
    block = metrics_with_ci(y, pred, n_boot=100)
    assert set(block) == {"r2", "mae", "rmse"}
    for m in block.values():
        assert m["ci95"][0] <= m["point"] <= m["ci95"][1]


def test_bootstrap_requires_two_points():
    with pytest.raises(ValueError, match="نقطتين"):
        bootstrap_metric([1.0], [1.0])


# ── المعايرة ─────────────────────────────────────────────────


def test_calibration_bins_perfect_model_aligns_with_diagonal():
    """نموذج مثالي (pred=y): متوسط الملاحظة يقارب متوسط التنبؤ في كل صندوق."""
    _, y = _regression_data(n=800, noise=0.05)
    bins = calibration_bins(y, y, n_bins=8)
    assert sum(b["n"] for b in bins) == 800
    for b in bins:
        assert b["low"] <= b["pred_mean"] <= b["high"]
        assert abs(b["obs_mean"] - b["pred_mean"]) < 0.25  # القطر


def test_calibration_bins_skip_empty_bins():
    y = np.array([1.0, 1.1, 9.0, 9.2, 5.0])  # فجوة في الوسط
    bins = calibration_bins(y, y, n_bins=10)
    assert sum(b["n"] for b in bins) == 5
    lows = [b["low"] for b in bins]
    assert lows == sorted(lows)  # الحواف تصاعدية


def test_calibration_constant_predictions_single_bin():
    bins = calibration_bins(np.array([1.0, 2.0, 3.0]), np.array([2.0, 2.0, 2.0]))
    assert len(bins) == 1 and bins[0]["n"] == 3


# ── نطاق قابلية التطبيق ──────────────────────────────────────


def test_nn_tanimoto_identical_and_disjoint():
    a = np.array([[1, 1, 0, 0]], dtype=float)
    b = np.array([[1, 1, 0, 0], [0, 0, 1, 1]], dtype=float)
    sims = nn_tanimoto_similarity(a, b)
    assert sims[0] == pytest.approx(1.0)  # مطابق تام
    disjoint = np.array([[0, 0, 1, 1]], dtype=float)
    assert nn_tanimoto_similarity(disjoint, a)[0] == pytest.approx(0.0)


def test_fit_ad_threshold_train_self_inside():
    """مئين 5 من التشابه الذاتي: ≈95% من التدريب داخل نطاقه — تعريفياً.

    ملاحظة العقد: is_inside مخصصة لجزيئات جديدة — إعادة تسجيل التدريب
    نفسه بها تُقيّم كل نقطة مع نفسها (تشابه 1.0) والإحصاء الصادق للتدريب
    هو train_inside_frac المحسوب بإقصاء النفس.
    """
    rng = np.random.default_rng(3)
    X = (rng.random((60, 32)) > 0.6).astype(float)
    ad = fit_applicability_domain(X)
    assert isinstance(ad, ApplicabilityDomain)
    assert 0.0 <= ad.threshold <= 1.0
    assert ad.train_inside_frac == pytest.approx(0.95, abs=0.05)
    # نقاط جديدة من نفس التوزيع: غالبيتها العظمى داخل النطاق
    fresh = (rng.random((30, 32)) > 0.6).astype(float)
    assert ad.is_inside(fresh).mean() >= 0.8


def test_fit_ad_requires_two_points():
    with pytest.raises(ValueError, match="نقطتين"):
        fit_applicability_domain(np.ones((1, 4)))


def test_applicability_report_far_region_degrades():
    """جزيئات «غريبة» (إقليم بعيد بصماتها) تُعلَّم خارج النطاق — الفصل يعمل."""
    rng = np.random.default_rng(5)
    X_tr = (rng.random((150, 40)) > 0.7).astype(float)
    y_tr = X_tr.sum(axis=1) + rng.normal(scale=0.1, size=150)
    inside_te = (rng.random((40, 40)) > 0.7).astype(float)
    # إقليم بعيد: بتات مضغوطة في النصف الآخر — قليل التداخل مع التدريب
    far_te = np.zeros((20, 40))
    far_te[:, :5] = 1.0
    X_te = np.vstack([inside_te, far_te])
    y_te = np.concatenate([inside_te.sum(axis=1), far_te.sum(axis=1)]) + 0.0
    model = RandomForestRegressor(n_estimators=20, random_state=0).fit(X_tr, y_tr)
    pred = model.predict(X_te)
    ad = fit_applicability_domain(X_tr)
    rep = applicability_report(ad, X_te, y_te, pred)
    assert rep["inside"]["n"] > rep["outside"]["n"] > 0
    assert rep["outside"]["mae"] is not None  # المقاييس خارج النطاق تُعلَن لا تُحذف
    assert "note_ar" in rep


# ── البطاقة الكاملة ──────────────────────────────────────────


def _train_tiny_rf():
    X, y = _regression_data(n=220, seed=11)
    idx = np.arange(len(y))
    tr, te = idx[:180], idx[180:]
    model = RandomForestRegressor(n_estimators=25, random_state=42).fit(X[tr], y[tr])
    preds = np.stack([est.predict(X[te]) for est in model.estimators_])
    return X, tr, te, y, model.predict(X[te]), preds.std(axis=0)


def test_build_model_card_shape_and_json_roundtrip():
    X, tr, te, y, pred, tstd = _train_tiny_rf()
    card = build_model_card(
        y_true=y[te], y_pred=pred, train_X=X[tr], test_X=X[te],
        provenance={"data": "synthetic", "model": "RF(25)", "seed": 42},
        tree_std=tstd,
    )
    assert set(card) == {
        "provenance", "n_test", "metrics", "calibration_bins",
        "applicability_domain", "uncertainty_calibration",
    }
    assert card["provenance"]["data"] == "synthetic"
    assert card["n_test"] == len(te)
    # البطاقة تُسلسَل JSON فعلاً — عقد docs/audit
    payload = json.dumps(card, ensure_ascii=False)
    assert "applicability_domain" in payload


def test_uncertainty_calibration_structure():
    rng = np.random.default_rng(2)
    y = rng.normal(size=200)
    pred = y + rng.normal(scale=0.3, size=200)
    tstd = rng.random(200)
    block = uncertainty_calibration(y, pred, tstd)
    assert -1.0 <= block["spearman_rho_abserror_vs_treestd"] <= 1.0
    assert block["p_value"] >= 0.0


# ── الصيغة المعمَّمة: توافق الثنائية حرفياً + صحة التكرارات ─────────


def test_generalized_tanimoto_binary_matches_classic_formula():
    """على المتجهات الثنائية: Σmin/Σmax ≡ c/(a+b−c) — التوافق الكامل."""
    from core.model_cards import generalized_tanimoto

    q = np.array([[1, 1, 0, 0]], dtype=float)
    r = np.array([[1, 0, 1, 0], [1, 1, 0, 0], [0, 0, 1, 1]], dtype=float)
    sims = generalized_tanimoto(q, r)
    classic = np.array([[
        1 / (2 + 2 - 1),      # c/(a+b−c) يدوياً
        2 / (2 + 2 - 2),
        0.0,
    ]])
    assert np.allclose(sims, classic, atol=1e-9)


def test_generalized_tanimoto_counts_min_over_max():
    """على متجهات العدّ: T = Σmin(a,b)/Σmax(a,b) — لا تضخيم كالصيغة الثنائية."""
    from core.model_cards import generalized_tanimoto

    a = np.array([[3, 1, 0, 0]], dtype=float)   # مجموع 4
    b = np.array([[1, 1, 0, 0], [3, 0, 0, 0]], dtype=float)
    sims = generalized_tanimoto(a, b)
    # Σmin=2 Σmax=4 → 0.5 ; Σmin=3 Σmax=4 → 0.75
    assert np.allclose(sims, [[0.5, 0.75]], atol=1e-9)


def test_generalized_tanimoto_zero_row_safe():
    """صف أصفار كامل → تشابه 0 بلا انهيار قسمة."""
    from core.model_cards import generalized_tanimoto

    a = np.array([[0, 0, 0, 0]], dtype=float)
    b = np.array([[1, 1, 0, 0]], dtype=float)
    assert generalized_tanimoto(a, b)[0, 0] == pytest.approx(0.0, abs=1e-9)
