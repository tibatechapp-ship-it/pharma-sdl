"""U4 — الصيدلانيات: انحلال، BCS، جرعات (docs/ryko/RYKO-MASTER-PLAN.md §3 U4).

المصادر المعلنة: Higuchi 1961/1963؛ Korsmeyer & Peppas 1983؛
Löbenberg & Amidon 2000 (BCS)؛ Cockcroft & Gault 1976؛ Rowland & Tozer 2011.
"""

from __future__ import annotations

import math

from .errors import RykoInputError


def _pos(name: str, value: float) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        raise RykoInputError(
            f"المدخل «{name}» يجب أن يكون رقماً.",
            f"Input '{name}' must be a number.",
        ) from None
    if not math.isfinite(v) or v <= 0:
        raise RykoInputError(
            f"المدخل «{name}» يجب أن يكون رقماً موجباً (وصل: {value}).",
            f"Input '{name}' must be a positive number (got: {value}).",
        )
    return v


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


def _fit_xy(xs, ys):
    x, y = [float(v) for v in xs], [float(v) for v in ys]
    if len(x) != len(y) or len(x) < 2:
        raise RykoInputError(
            "يلزم زوجان متطابقان على الأقل (زمن وقيمة).",
            "Need at least two matched (time, value) pairs.",
        )
    n = len(x)
    mx, my = sum(x) / n, sum(y) / n
    sxy = sum((x[i] - mx) * (y[i] - my) for i in range(n))
    sxx = sum((v - mx) ** 2 for v in x)
    if sxx <= 0:
        raise RykoInputError(
            "الأزمنة متطابقة — لا يمكن ملاءمة ميل.",
            "Times are identical — cannot fit a slope.",
        )
    slope = sxy / sxx
    intercept = my - slope * mx
    syy = sum((v - my) ** 2 for v in y)
    r2 = (sxy**2) / (sxx * syy) if syy > 0 else 1.0
    return slope, intercept, r2


# ── نماذج الانحلال ──


def higuchi_k(times_h, amounts_released):
    """Q = k·√t — ثابت هيغوتشي من ميل الكمية المطلقة مقابل جذر الزمن.

    الملاءمة على كل النقاط المعطاة؛ الحكم على الخطية يترك لـR² المُعلن.
    """
    t = [_nn("time_h", v) for v in times_h]
    q = [_nn("amount_released", v) for v in amounts_released]
    root_t = [math.sqrt(v) for v in t]
    k, b, r2 = _fit_xy(root_t, q)
    return k, {"intercept": b, "r_squared": r2, "n": len(t)}


def korsmeyer_peppas(times_h, fraction_released):
    """Q = k·tⁿ — ميل ون Korsmeyer-Peppas عبر اللوغاريتمات.

    fraction_released أجزاء ≤ 1 (لا نسب مئوية). تفسير n: ≤0.45 انتشار فِك؛
    0.45<n≤0.89 أسطواني؛ n>0.89 كروي (الحد المعلن للأسطواني).
    """
    t = [_nn("time_h", v) for v in times_h]
    q = [_nn("fraction", v) for v in fraction_released]
    for v in q:
        if v > 1.0:
            raise RykoInputError(
                f"الجزء المطلق {v} > 1 — أدخل أجزاء (0–1) لا نسباً مئوية.",
                f"Fraction {v} > 1 — pass fractions (0–1), not percentages.",
            )
    log_t = [math.log(v) for v in t if v > 0]
    log_q = [math.log(v) for v in q if v > 0]
    if len(log_t) != len(log_q) or len(log_t) < 2:
        raise RykoInputError(
            "يلزم نقتان موجبتان على الأقل (اللوغاريتم غير معرّف للصفر).",
            "Need two positive points at least (log undefined at zero).",
        )
    n, b, r2 = _fit_xy(log_t, log_q)
    k = math.exp(b)
    interp = (
        "fickian" if n <= 0.45 else "anomalous_cylindrical" if n <= 0.89 else "case_ii_spherical"
    )
    return k, {"n": n, "r_squared": r2, "interpretation": interp}


def first_order_k(times_h, released_fraction):
    """Q(t)=Q∞(1−e^(−kt)) — k من الميل اللوغاريتمي للجزء المتبقي ln(1−Q)."""
    t = [_nn("time_h", v) for v in times_h]
    q = [_nn("fraction", v) for v in released_fraction]
    pairs = [(v, math.log(1.0 - w)) for v, w in zip(t, q) if 0.0 <= w < 1.0]
    if len(pairs) < 2:
        raise RykoInputError(
            "يلزم نقتان على الأقل بجزء متبقٍ موجب (0≤Q<1).",
            "Need two points with 0≤Q<1 (log of remaining is defined).",
        )
    xs = [p[0] for p in pairs]
    ys = [p[1] for p in pairs]
    slope, b, r2 = _fit_xy(xs, ys)
    if slope >= 0:
        raise RykoInputError(
            "الميل غير سالب — لا يتوافق مع انحلال من الرتبة الأولى؛ راجع البيانات.",
            "Non-negative slope — incompatible with first-order release; check data.",
        )
    return -slope, {"intercept": b, "r_squared": r2, "n": len(pairs)}


def zero_order_rate(times_h, amounts_released):
    """Q = Q₀ + k·t — معدل الجرعة الصفرية من الملاءمة الخطية المباشرة."""
    t = [_nn("time_h", v) for v in times_h]
    q = [_nn("amount_released", v) for v in amounts_released]
    k, b, r2 = _fit_xy(t, q)
    return k, {"intercept": b, "r_squared": r2, "n": len(t)}


# ── BCS ──


def dose_number(dose_mg: float, solubility_mg_ml: float, volume_ml: float = 250.0):
    """D₀ = الجرعة/(الذوبانية×الحجم) — الحجم الافتراضي 250mL (كوب ماء)."""
    d = _pos("dose_mg", dose_mg)
    cs = _pos("solubility_mg_ml", solubility_mg_ml)
    v = _pos("volume_ml", volume_ml)
    return d / (cs * v), {"dose_mg": d, "solubility_mg_ml": cs, "volume_ml": v}


def bcs_class(dose_number: float, permeability_high: bool):
    """خريطة BCS المعلنة: (D₀، نفاذية عالية؟) → I/II/III/IV.

    عالية/الد₀≤1 ⇒ I · عالية/الد₀>1 ⇒ II · منخفضة/الد₀≤1 ⇒ III · منخفضة/>1 ⇒ IV.
    المصدر: Löbenberg & Amidon 2000؛ حدود الد₀=1 الحرفية.
    """
    d0 = _nn("dose_number", dose_number)
    if not isinstance(permeability_high, bool):
        raise RykoInputError(
            "permeability_high يجب أن يكون منطقياً (صح/خطأ).",
            "permeability_high must be a boolean (true/false).",
        )
    if permeability_high:
        cls = "I" if d0 <= 1.0 else "II"
    else:
        cls = "III" if d0 <= 1.0 else "IV"
    return cls, {"dose_number": d0, "permeability_high": permeability_high}


def noyes_whitney_rate(diff_cm2_s: float, area_cm2: float, cs_minus_c_mg_ml: float, h_cm: float):
    """dC/dt = D·A·(Cs−C)/h — معدل الانحلال اللحظي (mg/s)."""
    d = _pos("diff_cm2_s", diff_cm2_s)
    a = _pos("area_cm2", area_cm2)
    dc = _nn("cs_minus_c_mg_ml", cs_minus_c_mg_ml)
    h = _pos("h_cm", h_cm)
    return d * a * dc / h, {"D": d, "A": a, "dC": dc, "h": h}


# ── الجرعات ──


def cockcroft_gault(age_y: float, weight_kg: float, scr_mg_dl: float, male: bool = True):
    """CrCl = ((140−العمر)×الوزن)/(72×SCr) ×(0.85 للإناث) — mL/min.

    الذهبي: ذكر 40س/70كغ/SCr=1.0 ⇒ 97.22 mL/min.
    """
    age = _pos("age_y", age_y)
    w = _pos("weight_kg", weight_kg)
    scr = _pos("scr_mg_dl", scr_mg_dl)
    if age >= 140:
        raise RykoInputError(
            f"العمر {age} ≥ 140 — خارج النطاق البشري المعقول.",
            f"Age {age} ≥ 140 — outside any plausible human range.",
        )
    crcl = ((140.0 - age) * w) / (72.0 * scr)
    if not male:
        crcl *= 0.85
    return crcl, {"age": age, "weight_kg": w, "scr_mg_dl": scr, "sex": "m" if male else "f"}


def loading_dose(vd_l: float, target_conc_mg_l: float, bioavailability_f: float = 1.0):
    """LD = Cp·Vd/F — جرعة التحميل (mg)."""
    vd = _pos("vd_l", vd_l)
    cp = _pos("target_conc_mg_l", target_conc_mg_l)
    f = _pos("bioavailability_f", bioavailability_f)
    if f > 1.0:
        raise RykoInputError(
            f"التوافر F {f} > 1 — مستحيل فيزيولوجياً.",
            f"Bioavailability F {f} > 1 — physiologically impossible.",
        )
    return cp * vd / f, {"vd_l": vd, "target_mg_l": cp, "F": f}


def maintenance_rate(cl_l_h: float, css_mg_l: float, bioavailability_f: float = 1.0):
    """معدل الجرعة = CL·Css/F — معدل الجرعة المستمرة (mg/h)."""
    cl = _pos("cl_l_h", cl_l_h)
    css = _pos("css_mg_l", css_mg_l)
    f = _pos("bioavailability_f", bioavailability_f)
    if f > 1.0:
        raise RykoInputError(
            f"التوافر F {f} > 1 — مستحيل فيزيولوجياً.",
            f"Bioavailability F {f} > 1 — physiologically impossible.",
        )
    return cl * css / f, {"cl_l_h": cl, "css_mg_l": css, "F": f}


def infusion_css(rate_mg_h: float, cl_l_h: float, ke: float | None = None):
    """Css = معدل التسريب/CL · زمن 95% ≈ 4.32×t½ (إن وُفر ke)."""
    r, cl = _pos("rate_mg_h", rate_mg_h), _pos("cl_l_h", cl_l_h)
    css = r / cl
    extra = {"rate_mg_h": r, "cl_l_h": cl}
    if ke is not None:
        k = _pos("ke", ke)
        extra["t95_h"] = 4.32 * math.log(2.0) / k
    return css, extra


def pediatric_dose(weight_kg: float, mg_per_kg: float):
    """جرعة الأطفال بالوزن = وزن×mg/kg — حساب تعليمي لا وصفة."""
    w = _pos("weight_kg", weight_kg)
    rate = _pos("mg_per_kg", mg_per_kg)
    if w > 250:
        raise RykoInputError(
            f"الوزن {w} كغ خارج النطاق المعقول (≤250).",
            f"Weight {w} kg outside plausible range (≤250).",
        )
    return w * rate, {"weight_kg": w, "mg_per_kg": rate}
