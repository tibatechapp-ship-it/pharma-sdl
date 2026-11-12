"""U1 — الرياضيات والحساب الدوائي (docs/ryko/RYKO-MASTER-PLAN.md §3 U1).

كل دالة تعيد `(القيمة, قيم_فرعية)` وترفض المدخل خارج النطاق برفض مُعلَّل
ثنائي اللغة — لا صمت ولا رقم مُختلق.
المصادر المعلنة: Rowland & Tozer (2011)؛ Gabrielsson & Weiner (2007).
"""

from __future__ import annotations

import math

from .errors import RykoInputError

# ── وحدات الكتلة والحجم (SI) ──
_MASS = {"kg": 1e6, "g": 1e3, "mg": 1.0, "ug": 1e-3, "mcg": 1e-3, "ng": 1e-6}
_VOLUME = {"L": 1.0, "mL": 1e-3, "uL": 1e-6}


def _pos(name: str, value: float, unit_hint: str = "") -> float:
    """حاكم ما قبل الحساب: قيمة موجبة إلزامية."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        raise RykoInputError(
            f"المدخل «{name}» يجب أن يكون رقماً.",
            f"Input '{name}' must be a number.",
        ) from None
    if not math.isfinite(v) or v <= 0:
        raise RykoInputError(
            f"المدخل «{name}» يجب أن يكون رقماً موجباً {unit_hint}(وصل: {value}).",
            f"Input '{name}' must be a positive number {unit_hint}(got: {value}).",
        )
    return v


def _nn(name: str, value: float) -> float:
    """حاكم: قيمة غير سالبة (≥ 0)."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        raise RykoInputError(
            f"المدخل «{name}» يجب أن يكون رقماً.",
            f"Input '{name}' must be a number.",
        ) from None
    if not math.isfinite(v) or v < 0:
        raise RykoInputError(
            f"المدخل «{name}» يجب أن يكون رقماً غير سالب (وصل: {value}).",
            f"Input '{name}' must be a non-negative number (got: {value}).",
        )
    return v


# ── U1: الوحدات ──


def convert(value: float, from_unit: str, to_unit: str, molar_mass: float | None = None):
    """تحويل وحدات: كتلة وحجم داخلياً، وكتلة↔مول عبر الكتلة المولية."""
    fu, tu = str(from_unit).lower().strip(), str(to_unit).lower().strip()
    if fu in _MASS and tu in _MASS:
        out = _pos("value", value) * _MASS[fu] / _MASS[tu]
        return out, {"family": "mass"}
    if fu in _VOLUME and tu in _VOLUME:
        out = _pos("value", value) * _VOLUME[fu] / _VOLUME[tu]
        return out, {"family": "volume"}
    if fu in _MASS and tu in {"mol", "mmol", "umol"}:
        mm = _pos("molar_mass_g_per_mol", molar_mass)
        grams = _pos("value", value) * _MASS[fu] / 1e3
        to_mol = {"mol": 1.0, "mmol": 1e3, "umol": 1e6}[tu]
        out = grams / mm * to_mol
        return out, {"family": "mass→moles", "molar_mass_g_per_mol": mm}
    if fu in {"mol", "mmol", "umol"} and tu in _MASS:
        mm = _pos("molar_mass_g_per_mol", molar_mass)
        from_mol = {"mol": 1.0, "mmol": 1e-3, "umol": 1e-6}[fu]
        mols = _pos("value", value) * from_mol
        out = mols * mm * 1e3 / _MASS[tu]
        return out, {"family": "moles→mass", "molar_mass_g_per_mol": mm}
    raise RykoInputError(
        f"تحويل غير مدعوم: {from_unit} ← {to_unit} (العائلات يجب أن تتطابق أو "
        "تستخدم الكتلة المولية).",
        f"Unsupported conversion: {from_unit} → {to_unit} (families must match "
        "or use molar_mass).",
    )


# ── U1: الحركية الدوائية (PK) ──


def auc_trapz(times, concs, log_tail: bool = False):
    """المساحة تحت المنحنى — قاعدة الشريط (خطية؛ ذيل لوغاريتمي اختياري).

    times: أزمنة متزايدة (ساعات)؛ concs: تراكيز (وحدة موحدة).
    log_tail: الشريط الأخير لوغاريتمي C₁·Δt/ln(C₁/C₂) — صالح فقط C₁>C₂>0.
    """
    t = [float(x) for x in times]
    c = [float(x) for x in concs]
    if len(t) != len(c) or len(t) < 2:
        raise RykoInputError(
            "يلزم نقاطان متطابقتان على الأقل (زمن وتركيز).",
            "Need at least two matched (time, concentration) points.",
        )
    for i in range(1, len(t)):
        if not (t[i] > t[i - 1]):
            raise RykoInputError(
                "الأزمنة يجب أن تكون متزايدة بدقة.",
                "Times must be strictly increasing.",
            )
    for x in c:
        _nn("conc", x)
    auc = 0.0
    for i in range(1, len(t)):
        dt = t[i] - t[i - 1]
        if log_tail and i == len(t) - 1 and c[i] > 0 and c[i - 1] > 0 and c[i] < c[i - 1]:
            auc += c[i - 1] * dt / math.log(c[i - 1] / c[i])
        else:
            auc += (c[i - 1] + c[i]) / 2 * dt
    return auc, {"segments": len(t) - 1, "log_tail": bool(log_tail)}


def half_life(ke: float):
    """t½ = ln(2)/kₑ — من ثابت الإطراح (1/ساعة) إلى العمر النصفي (ساعة)."""
    k = _pos("ke", ke)
    return math.log(2.0) / k, {"ke_per_h": k}


def ke_from_half_life(t_half_h: float):
    """kₑ = ln(2)/t½ — العكس الحتمي."""
    th = _pos("t_half_h", t_half_h)
    return math.log(2.0) / th, {"t_half_h": th}


def clearance(dose_mg: float, auc: float):
    """CL = Dose/AUC — الوضوح الجسمي (لتر/ساعة إذا Dose mg وAUC mg·h/L)."""
    d, a = _pos("dose_mg", dose_mg), _pos("auc", auc)
    return d / a, {"dose_mg": d, "auc": a}


def volume_distribution(cl_l_h: float, ke: float):
    """Vd = CL/kₑ — حجم التوزيع الظاهري (لتر)."""
    cl, k = _pos("cl_l_h", cl_l_h), _pos("ke", ke)
    return cl / k, {"cl_l_h": cl, "ke_per_h": k}


def bioavailability(auc_po: float, auc_iv: float, dose_po: float, dose_iv: float):
    """F = (AUCpo/AUCiv)×(Doseiv/Dosepo) — التوافر الحيوي المطلق (0–1)."""
    ap, ai = _pos("auc_po", auc_po), _pos("auc_iv", auc_iv)
    dp, di = _pos("dose_po", dose_po), _pos("dose_iv", dose_iv)
    f = (ap / ai) * (di / dp)
    if f > 1.0:
        raise RykoInputError(
            f"F المحسوب {f:.4f} > 1 — مستحيل فيزيولوجياً؛ راجع المدخلات.",
            f"Computed F {f:.4f} > 1 — physiologically impossible; check inputs.",
        )
    return f, {"auc_ratio": ap / ai, "dose_ratio": di / dp}


# ── U1: الإحصاء الوصفي ──


def ci95_mean(values):
    """فترة ثقة 95% للمتوسط: x̄ ± t(0.975, n−1)·s/√n (scipy.stats t)."""
    from scipy import stats as st

    xs = [float(x) for x in values]
    n = len(xs)
    if n < 2:
        raise RykoInputError(
            "يلزم قيمتان على الأقل لفترة الثقة.",
            "Need at least two values for a CI.",
        )
    mean = sum(xs) / n
    var = sum((x - mean) ** 2 for x in xs) / (n - 1)
    sd = math.sqrt(var)
    tcrit = float(st.t.ppf(0.975, n - 1))
    half = tcrit * sd / math.sqrt(n)
    return mean, {
        "ci95_lower": mean - half,
        "ci95_upper": mean + half,
        "sd": sd,
        "n": n,
        "t_critical": tcrit,
    }


def pic50_to_ic50(pic50: float):
    """IC50[nM] = 10^(9−pIC50) — التعريف القياسي لمقياس pIC50 (P20).

    الذهبي: pIC50 = 7.0 ⇒ IC50 = 100 nM.
    """
    v = float(pic50)
    if not math.isfinite(v) or not (2.0 <= v <= 13.0):
        raise RykoInputError(
            f"pIC50 يجب أن يكون بين 2 و13 (وصل: {pic50}) — خارج هذا المدى "
            "القيمة ليست فعالية قابلة للقياس تجريبياً.",
            f"pIC50 must be within [2, 13] (got: {pic50}) — outside this range "
            "the value is not a measurable potency.",
        )
    ic50_nm = 10.0 ** (9.0 - v)
    return ic50_nm, {"ic50_um": ic50_nm / 1e3, "ic50_m": ic50_nm / 1e9}


def linear_fit(xs, ys):
    """انحدار خطي بأقل مربعات (إغلاقي): ميل، تقاطع، R²."""
    x, y = [float(v) for v in xs], [float(v) for v in ys]
    if len(x) != len(y) or len(x) < 2:
        raise RykoInputError(
            "يلزم زوجان متطابقان على الأقل.",
            "Need at least two matched pairs.",
        )
    n = len(x)
    mx, my = sum(x) / n, sum(y) / n
    sxy = sum((x[i] - mx) * (y[i] - my) for i in range(n))
    sxx = sum((v - mx) ** 2 for v in x)
    if sxx == 0:
        raise RykoInputError(
            "تباين المدخل الأفقي صفر — لا يمكن ملاءمة ميل.",
            "Zero variance in x — cannot fit a slope.",
        )
    slope = sxy / sxx
    intercept = my - slope * mx
    syy = sum((v - my) ** 2 for v in y)
    r2 = (sxy**2) / (sxx * syy) if syy > 0 else 1.0
    return slope, {"intercept": intercept, "r_squared": r2, "n": n}
