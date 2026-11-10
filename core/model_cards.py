"""بطاقات النماذج — التحقق الخارجي الصادق لكل نموذج تنبؤي داخلي.

المبدأ (v0.18 — مركز التحقق الخارجي): رقم بلا فترته لا يُقتبس، ونموذج
بلا حدود يُعلَن عنه لا يُؤتمن. كل بطاقة نموذج هنا تجيب عن ثلاثة أسئلة:

    1. كم دقيق؟        — المقاييس مع فترات ثقة bootstrap 95% (نقطة + مجال)
    2. هل مداه موثوق؟  — معايرة تنبؤ/ملاحظة: هل القيم المتوقعة تعني ما تقول؟
    3. أين يعمم؟       — نطاق قابلية التطبيق AD: داخل المنطقة المعروفة
                         مقابل خارجها — والمقاييس تُفصل بينهما بصدق

هذا امتداد للبروتوكول المجمَّد في scripts/evaluate_generalization.py
(نفس التقسيمات وبذورها — يُستورد من السكربت لا يُعاد بناؤه)؛ الجديد هنا
هو البعدان 2 و3 اللذان لم ينشرا من قبل، وهما وجه «معالجة الضعف»:
النموذج الذي ينشر حدوده يُؤتمن أكثر من نموذج يخفيها.

كل الدوال numpy/scipy خالصة — بلا RDKit وبلا شبكة، وقابلة للاختبار
offline على بيانات صناعية. المخرجات dict جاهزة للـJSON بأسلوب docs/audit.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy import stats
from scipy.spatial.distance import cdist
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

BOOTSTRAP_N = 1000
CI_LEVEL = 0.95
AD_PERCENTILE = 5.0  # عتبة AD = المئين 5 من تشابه أقرب جار داخل التدريب


# ─────────────────────────────────────────────────────────────
# 1) المقاييس مع فترات الثقة
# ─────────────────────────────────────────────────────────────

def _metric_value(y_true: np.ndarray, y_pred: np.ndarray, metric: str) -> float:
    if metric == "r2":
        return float(r2_score(y_true, y_pred))
    if metric == "mae":
        return float(mean_absolute_error(y_true, y_pred))
    return float(np.sqrt(mean_squared_error(y_true, y_pred)))


def bootstrap_metric(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    metric: str = "r2",
    n_boot: int = BOOTSTRAP_N,
    ci: float = CI_LEVEL,
    seed: int = 42,
) -> dict:
    """نقطة المقياس + فاصل ثقة بإعادة المعاينة على الاختبار (نمط البروتوكول المجمَّد).

    المقياس r2 لأخذ العينات مع الجزء قد ينتج قيماً متطرفة قصوى — المئينات
    متينة تجاهها. البذرة محفوظة في المخرجات لكي يُعاد الإنتاج حرفياً.
    """
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    n = len(y_true)
    if n < 2:
        raise ValueError("فاصل ثقة يحتاج نقطتين على الأقل")
    rng = np.random.default_rng(seed)
    vals: list[float] = []
    for _ in range(n_boot):
        idx = rng.integers(0, n, n)
        vals.append(_metric_value(y_true[idx], y_pred[idx], metric))
    alpha = (1 - ci) / 2 * 100
    lo, hi = np.percentile(vals, [alpha, 100 - alpha])
    return {
        "point": round(_metric_value(y_true, y_pred, metric), 3),
        "ci95": [round(float(lo), 3), round(float(hi), 3)],
        "n": int(n),
        "n_boot": int(n_boot),
        "seed": int(seed),
    }


def metrics_with_ci(
    y_true: np.ndarray, y_pred: np.ndarray, seed: int = 42, n_boot: int = BOOTSTRAP_N
) -> dict:
    """المقاييس الثلاثة (r2/mae/rmse) كلٌّ بفترته — جوهر البطاقة."""
    return {
        m: bootstrap_metric(y_true, y_pred, metric=m, seed=seed, n_boot=n_boot)
        for m in ("r2", "mae", "rmse")
    }


# ─────────────────────────────────────────────────────────────
# 2) معايرة تنبؤ/ملاحظة
# ─────────────────────────────────────────────────────────────

def calibration_bins(
    y_true: np.ndarray, y_pred: np.ndarray, n_bins: int = 10
) -> list[dict]:
    """جداول موثوقية الانحدار: صناديق متساوية العرض على مدى المتنبَّأ،
    ومتوسط الملاحظة داخل كل صندوق — البطاقة السليمة تقارب القطر (obs≈pred).

    الصندوق الفارغ لا يُختلق — نقص صادق لا تزييف.
    """
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    lo, hi = float(y_pred.min()), float(y_pred.max())
    if hi <= lo:  # تنبؤ شبه ثابت — صندوق واحد يكفي ولا معنى للتقسيم
        return [{
            "low": round(lo, 3), "high": round(hi, 3), "n": len(y_pred),
            "pred_mean": round(float(y_pred.mean()), 3),
            "obs_mean": round(float(y_true.mean()), 3),
        }]
    edges = np.linspace(lo, hi, n_bins + 1)
    out: list[dict] = []
    for i in range(n_bins):
        mask = (y_pred >= edges[i]) & (
            y_pred < edges[i + 1] if i < n_bins - 1 else y_pred <= edges[i + 1]
        )
        if not mask.any():
            continue
        out.append({
            "low": round(float(edges[i]), 3),
            "high": round(float(edges[i + 1]), 3),
            "n": int(mask.sum()),
            "pred_mean": round(float(y_pred[mask].mean()), 3),
            "obs_mean": round(float(y_true[mask].mean()), 3),
            "bin_mae": round(float(np.mean(np.abs(y_true[mask] - y_pred[mask]))), 3),
        })
    return out


# ─────────────────────────────────────────────────────────────
# 3) نطاق قابلية التطبيق — أعلى تشابه تانيروتو مقابل التدريب
# ─────────────────────────────────────────────────────────────

def generalized_tanimoto(A: np.ndarray, B: np.ndarray) -> np.ndarray:
    """تشابه تانيروتو المعمَّم لمتجهات العدّ: Σmin(a,b)/Σmax(a,b).

    بصمة الإنتاج المعتمد (P11) تكرارات لا ثنائية — والصيغة الكلاسيكية
    c/(a+b−c) تفترض ثنائية وتضخّم التشابه عند تعدّد الإصابة. الصيغة
    المعمَّمة تتفكك للكلاسيكية حرفياً على المتجهات الثنائية (Σmin=c،
    Σmax=a+b−c) — التوافق الكامل مع البروتوكول المنشور محفوظ.
    """
    A = np.asarray(A, dtype=float)
    B = np.asarray(B, dtype=float)
    if A.ndim == 1:
        A = A.reshape(1, -1)
    if B.ndim == 1:
        B = B.reshape(1, -1)
    sums_a = A.sum(axis=1)[:, None]
    sums_b = B.sum(axis=1)[None, :]
    l1 = cdist(A, B, "cityblock")
    smin = (sums_a + sums_b - l1) / 2.0
    smax = (sums_a + sums_b + l1) / 2.0
    return smin / (smax + 1e-12)  # صف أصفار كامل → تشابه 0 لا انهيار


def nn_tanimoto_similarity(query: np.ndarray, ref: np.ndarray) -> np.ndarray:
    """أعلى تشابه تانيروتو لكل صف query مقابل صفوف ref.

    الصيغة المعمَّمة Σmin/Σmax (المطلوبة لبصمات التكرارات المعتمدة في
    الإنتاج) — وتعطي للثنائية أرقام صيغة البروتوكول c/(a+b−c) حرفياً.
    """
    if ref.shape[0] == 0:
        return np.zeros(np.atleast_2d(query).shape[0])
    sims = generalized_tanimoto(query, ref)
    return sims.max(axis=1)


@dataclass
class ApplicabilityDomain:
    """عتبة AD مستنبطة من التدريب ذاته — بلا فرض خارجي.

    العتبة = المئين 5 (الافتراضي) من توزيع تشابه أقرب جار داخل التدريب
    (كل جزيء مقابل بقية التدريب بإقصاء نفسه). نقطة اختبار «داخل النطاق»
    إن بلغ تشابهها مع أقرب جزيء تدريب العتبة — أي أنها ليست غريبة
    عن الإقليم الكيميائي الذي تدرّب النموذج عليه.
    """

    train_X: np.ndarray
    threshold: float
    percentile: float
    train_nn_sim: np.ndarray = field(default_factory=lambda: np.empty(0))

    @property
    def train_inside_frac(self) -> float:
        return float(np.mean(self.train_nn_sim >= self.threshold))

    def nn_similarity(self, query: np.ndarray) -> np.ndarray:
        """أعلى تشابه لكل نقطة استعلام مقابل التدريب المحفوظ."""
        return nn_tanimoto_similarity(np.asarray(query, dtype=float), self.train_X)

    def is_inside(self, query: np.ndarray) -> np.ndarray:
        """قناع داخل/خارج النطاق لكل نقطة استعلام."""
        return self.nn_similarity(query) >= self.threshold


def fit_applicability_domain(
    train_X: np.ndarray, percentile: float = AD_PERCENTILE
) -> ApplicabilityDomain:
    """استنباط عتبة AD من التشابه الذاتي للتدريب (إقصاء النفس قبل max)."""
    X = np.asarray(train_X, dtype=float)
    n = X.shape[0]
    if n < 2:
        raise ValueError("نطاق قابلية التطبيق يحتاج تدريباً من نقطتين على الأقل")
    sims = generalized_tanimoto(X, X)
    np.fill_diagonal(sims, -np.inf)  # إقصاء النفس — أقرب «آخر» جار
    train_nn = sims.max(axis=1)
    threshold = float(np.percentile(train_nn, percentile))
    return ApplicabilityDomain(
        train_X=X, threshold=threshold, percentile=percentile, train_nn_sim=train_nn
    )


def applicability_report(
    ad: ApplicabilityDomain,
    test_X: np.ndarray,
    y_true: np.ndarray,
    y_pred: np.ndarray,
) -> dict:
    """تفصيل الأداء داخل النطاق وخارجه — العدل يتطلب إظهار الاثنين معاً.

    الخلاصة الحاسمة: إن كانت المقاييس داخل AD جيدة وتنهار خارجه، فهذه
    ليست عيباً يُخفى بل حد يُعلَن — أداة تشرح «متى لا تثق بي».
    """
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    sims = ad.nn_similarity(test_X)
    inside = sims >= ad.threshold
    out: dict = {
        "method": "max Tanimoto vs train — threshold = train self-NN p5",
        "similarity": "generalized Tanimoto Σmin/Σmax (count fingerprints؛ الثنائية = c/(a+b−c) حرفياً)",
        "percentile": ad.percentile,
        "threshold": round(ad.threshold, 3),
        "train_inside_frac": round(ad.train_inside_frac, 3),
        "n_test": len(y_true),
        "inside": {"n": int(inside.sum()), "frac": round(float(inside.mean()), 3)},
        "outside": {"n": int((~inside).sum()), "frac": round(float((~inside).mean()), 3)},
    }
    for name, mask in (("inside", inside), ("outside", ~inside)):
        if mask.sum() >= 2:
            out[name]["r2"] = round(float(r2_score(y_true[mask], y_pred[mask])), 3)
            out[name]["mae"] = round(float(mean_absolute_error(y_true[mask], y_pred[mask])), 3)
        else:
            out[name]["r2"] = None
            out[name]["mae"] = None
    out["note_ar"] = (
        "داخل النطاق = الجزيء قريب كيميائياً من التدريب (تشابهه مع أقرب جار "
        "تدريب بلغ العتبة). النموذج يُستشهد به داخل النطاق؛ خارجه تنبيه "
        "استقراء لا حكم."
    )
    return out


# ─────────────────────────────────────────────────────────────
# تركيب البطاقة الكاملة
# ─────────────────────────────────────────────────────────────

def uncertainty_calibration(y_true: np.ndarray, y_pred: np.ndarray, tree_std: np.ndarray) -> dict:
    """هل فترة الثقة من تباين الأشجار تحمل معلومة؟ (ارتباط |الخطأ| بالانحراف)

    نفس مقياس البروتوكول المجمَّد — تُدمج هنا لِأكمل البطاقة من مصدر واحد.
    """
    rho = stats.spearmanr(np.abs(np.asarray(y_true) - np.asarray(y_pred)), tree_std)
    return {
        "spearman_rho_abserror_vs_treestd": round(float(rho.statistic), 3),
        "p_value": float(f"{rho.pvalue:.2e}"),
    }


def build_model_card(
    *,
    y_true: np.ndarray,
    y_pred: np.ndarray,
    train_X: np.ndarray,
    test_X: np.ndarray,
    provenance: dict,
    tree_std: np.ndarray | None = None,
    ad_percentile: float = AD_PERCENTILE,
    seed: int = 42,
) -> dict:
    """بطاقة نموذج كاملة JSON-جاهزة: مقاييس بفترات + معايرة + نطاق قابلية تطبيق.

    provenance يوثّق المصدر حرفياً (البيانات، التمثيل، النموذج، التقسيم،
    بذوره، نسخة sklearn) — البطاقة بلا نسب لا تُستشهد.
    """
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    card: dict = {
        "provenance": dict(provenance),
        "n_test": len(y_true),
        "metrics": metrics_with_ci(y_true, y_pred, seed=seed),
        "calibration_bins": calibration_bins(y_true, y_pred),
        "applicability_domain": applicability_report(
            fit_applicability_domain(train_X, ad_percentile), test_X, y_true, y_pred
        ),
    }
    if tree_std is not None:
        card["uncertainty_calibration"] = uncertainty_calibration(y_true, y_pred, tree_std)
    return card
