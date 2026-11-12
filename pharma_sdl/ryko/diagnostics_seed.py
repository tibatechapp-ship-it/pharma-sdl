"""مرحلة 2 — بذرة التشخيص البايزي (docs/ryko/RYKO-MASTER-PLAN.md §4).

حدود صادقة مُعلنة: Ryko **لا يشخّص ولا يوصي** — يحسب احتمالات ما بعد
الاختبار من مدخلات المستخدم (حساسية/نوعية/انتشار) رياضياً حتمياً.
خريطة الأمراض والعلامات = P21 (قاعدة معرفة مُدقَّقة المصدر، لاحقاً).

المصادر: Bayes؛ Fagan 1975 (نوموغرام الاحتمال بعد الاختبار)؛ Cohen 1960 (kappa).
"""

from __future__ import annotations

import math

from .errors import RykoInputError


def _unit(name: str, value: float) -> float:
    """حاكم احتمالات: العدد يجب أن يكون في [0, 1]."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        raise RykoInputError(
            f"المدخل «{name}» يجب أن يكون رقماً.",
            f"Input '{name}' must be a number.",
        ) from None
    if not (0.0 <= v <= 1.0):
        raise RykoInputError(
            f"المدخل «{name}» احتمال — يجب أن يكون بين 0 و1 (وصل: {value}).",
            f"Input '{name}' is a probability — must be within 0–1 (got: {value}).",
        )
    return v


def ppv_npv(sensitivity: float, specificity: float, prevalence: float):
    """PPV/NPV من (حساسية، نوعية، انتشار) — بذرة المرحلة الثانية.

    الذهبية: Se=Sp=0.9، π=0.1 ⇒ PPV=0.5 · NPV≈0.9878.
    """
    se = _unit("sensitivity", sensitivity)
    sp = _unit("specificity", specificity)
    prev = _unit("prevalence", prevalence)
    denom = se * prev + (1.0 - sp) * (1.0 - prev)
    if denom == 0.0:
        raise RykoInputError(
            "المقام صفر (Se=Sp=0 أو انتشار حدي) — PPV غير معرّف.",
            "Zero denominator (Se=Sp=0 or degenerate prevalence) — PPV undefined.",
        )
    ppv = se * prev / denom
    npv_denom = (1.0 - se) * prev + sp * (1.0 - prev)
    npv = sp * (1.0 - prev) / npv_denom if npv_denom > 0 else 0.0
    return ppv, {"npv": npv, "sensitivity": se, "specificity": sp, "prevalence": prev}


def likelihood_ratios(sensitivity: float, specificity: float):
    """LR⁺ = Se/(1−Sp) · LR⁻ = (1−Se)/Sp — أرجحية الاختبار."""
    se = _unit("sensitivity", sensitivity)
    sp = _unit("specificity", specificity)
    if sp >= 1.0:
        raise RykoInputError(
            "النوعية = 1 ⇒ LR⁺ غير معرّف (القسمة على صفر) — استخدم قيمة أقل من 1.",
            "Specificity = 1 makes LR⁺ undefined (division by zero) — use < 1.",
        )
    if se >= 1.0:
        raise RykoInputError(
            "الحساسية = 1 ⇒ LR⁻ = 0 بالتعريف، لكن الشرط المعلن يمنع الحد.",
            "Sensitivity = 1 forces LR⁻ = 0 by definition — boundary rejected by policy.",
        )
    lr_pos = se / (1.0 - sp)
    lr_neg = (1.0 - se) / sp
    return lr_pos, {"lr_minus": lr_neg, "sensitivity": se, "specificity": sp}


def post_test_probability(pre_test_prob: float, likelihood_ratio: float):
    """الاحتمال بعد الاختبار: odds × LR — نوموغرام Fagan حتمياً.

    pre_test_prob في [0,1]؛ likelihood_ratio > 0.
    """
    p = _unit("pre_test_prob", pre_test_prob)
    lr = float(likelihood_ratio)
    if not (0.0 < lr < math.inf):
        raise RykoInputError(
            f"نسبة الأرجحية يجب أن تكون رقماً موجباً منتهياً (وصل: {likelihood_ratio}).",
            f"Likelihood ratio must be a finite positive number (got: {likelihood_ratio}).",
        )
    if p in (0.0, 1.0):
        # الحدود المعلنة: احتمال مطلق مسبقاً لا يتغير بأي اختبار — نرفض لا نتجاهل
        raise RykoInputError(
            "الاحتمال المسبق 0 أو 1 حدّي — لا يعبره اختبار؛ أدخل قيمة داخل (0,1).",
            "Pre-test probability 0 or 1 is a boundary no test crosses — use (0,1).",
        )
    pre_odds = p / (1.0 - p)
    post_odds = pre_odds * lr
    post = post_odds / (1.0 + post_odds)
    return post, {"pre_odds": pre_odds, "post_odds": post_odds, "lr": lr}


def kappa(a: float, b: float, c: float, d: float):
    """اتساق كوهين من جدول 2×2 (a متفق موجب، b/c خلاف، d متفق سالب).

    κ = (Po − Pe)/(1 − Pe)؛ Po = (a+d)/n، Pe = متوقع بالصدفة.
    """
    vals = [a, b, c, d]
    for name, v in zip(("a", "b", "c", "d"), vals):
        _nn(name, v)
    n = a + b + c + d
    if n <= 0:
        raise RykoInputError(
            "الجدول فارغ — kappa غير معرّف.",
            "Empty table — kappa undefined.",
        )
    po = (a + d) / n
    pe = ((a + b) * (a + c) + (c + d) * (b + d)) / (n * n)
    if pe >= 1.0:
        raise RykoInputError(
            "الاتساق المتوقع بالصدفة ≥ 1 — جدول حدّي؛ kappa غير معرّف.",
            "Expected-by-chance agreement ≥ 1 — degenerate table; kappa undefined.",
        )
    return (po - pe) / (1.0 - pe), {"po": po, "pe": pe, "n": n}


def _nn(name: str, value: float) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        raise RykoInputError(
            f"المدخل «{name}» يجب أن يكون رقماً.",
            f"Input '{name}' must be a number.",
        ) from None
    if not math.isfinite(v) or v < 0:
        raise RykoInputError(
            f"المدخل «{name}» يجب أن يكون غير سالب (وصل: {value}).",
            f"Input '{name}' must be non-negative (got: {value}).",
        )
    return v
