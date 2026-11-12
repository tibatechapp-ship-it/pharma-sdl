"""U2 — الفيزياء: ديناميكا حرارية وانتقال (docs/ryko/RYKO-MASTER-PLAN.md §3 U2).

ثوابت SI المعلنة، وحدات صريحة في كل دالة، وحاكم ما قبل الحساب على كل مدخل.
المصادر: Einstein (1905)؛ Fick (1855)؛ Arrhenius (1889)؛ van't Hoff.
"""

from __future__ import annotations

import math

from .errors import RykoInputError

# ثوابت فيزيائية — CODATA 2018 (SI)
R_J_PER_MOL_K = 8.314462618  # J/(mol·K)
K_B = 1.380649e-23  # J/K
KCAL_PER_J = 1.0 / 4184.0


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


def _kelvin(name: str, t_c: float) -> float:
    """حاكم حرارة: مئوية → كلفن، مع سقف فيزيائي (لا حرارة دون صفر مطلق)."""
    try:
        c = float(t_c)
    except (TypeError, ValueError):
        raise RykoInputError(
            f"المدخل «{name}» يجب أن يكون رقماً.",
            f"Input '{name}' must be a number.",
        ) from None
    k = c + 273.15
    if not math.isfinite(c) or k <= 0:
        raise RykoInputError(
            f"«{name}» أدنى من الصفر المطلق — مستحيل فيزيائياً (وصل: {t_c}°C).",
            f"'{name}' is below absolute zero — physically impossible (got: {t_c} °C).",
        )
    return k


# ── الديناميكا الحرارية للربط ──


def binding_dg(kd_um: float, temp_c: float = 25.0):
    """ΔG = RT·ln(Kd) — طاقة الربط (kcal/mol) من ثابت الانفصال Kd.

    kd_um بالميكرومولار؛ temp_c درجة حرارة مئوية (افتراض 25°C=298.15K).
    قاعدة تحقق ذهبية: Kd=1µM عند 25°C ⇒ ΔG≈−8.185 kcal/mol.
    """
    kd_m = _pos("kd_um", kd_um) * 1e-6
    T = _kelvin("temp_c", temp_c)
    dg_j = R_J_PER_MOL_K * T * math.log(kd_m)
    return dg_j * KCAL_PER_J, {
        "kd_M": kd_m,
        "T_K": T,
        "R_J_per_mol_K": R_J_PER_MOL_K,
    }


def kd_from_dg(dg_kcal: float, temp_c: float = 25.0):
    """العكس الحتمي: Kd (µM) من ΔG (kcal/mol)."""
    T = _kelvin("temp_c", temp_c)
    dg_j = _finite("dg_kcal", dg_kcal) * 4184.0
    kd_m = math.exp(dg_j / (R_J_PER_MOL_K * T))
    return kd_m / 1e-6, {"T_K": T, "dg_J_per_mol": dg_j}


def _finite(name: str, value: float) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        raise RykoInputError(
            f"المدخل «{name}» يجب أن يكون رقماً.",
            f"Input '{name}' must be a number.",
        ) from None
    if not math.isfinite(v):
        raise RykoInputError(
            f"المدخل «{name}» يجب أن يكون رقماً منتهياً.",
            f"Input '{name}' must be a finite number.",
        )
    return v


# ── الانتشار والانتقال ──


def stokes_einstein(radius_nm: float, viscosity_mpa_s: float = 1.0, temp_c: float = 25.0):
    """D = kT/(6πηr) — معامل انتشار جسيم كروي (m²/s) — Stokes-Einstein.

    radius_nm بالنانونمتر؛ viscosity_mpa_s بالملي·باسكال·ثانية (الماء ≈ 1 عند 20°C).
    """
    r = _pos("radius_nm", radius_nm) * 1e-9
    eta = _pos("viscosity_mpa_s", viscosity_mpa_s) * 1e-3
    T = _kelvin("temp_c", temp_c)
    d = K_B * T / (6.0 * math.pi * eta * r)
    return d, {"radius_m": r, "eta_Pa_s": eta, "T_K": T, "k_B": K_B}


def arrhenius_ratio(ea_j_per_mol: float, temp1_c: float, temp2_c: float):
    """k₂/k₁ = exp(−Ea/R × (1/T₂ − 1/T₁)) — نسبة معدلات بين حرارتين."""
    ea = _pos("ea_j_per_mol", ea_j_per_mol)
    T1, T2 = _kelvin("temp1_c", temp1_c), _kelvin("temp2_c", temp2_c)
    ratio = math.exp(-(ea / R_J_PER_MOL_K) * (1.0 / T2 - 1.0 / T1))
    return ratio, {"Ea_J_per_mol": ea, "T1_K": T1, "T2_K": T2}


def vant_hoff_ratio(dh_j_per_mol: float, temp1_c: float, temp2_c: float):
    """ln(K₂/K₁) = −ΔH/R × (1/T₂ − 1/T₁) — نسبة ثابت الاتزان بين حرارتين.

    dh_j_per_mol: أنثالبي التفاعل (إشارة معلنة: سالبة = طارد للحرارة).
    """
    dh = _finite("dh_j_per_mol", dh_j_per_mol)
    T1, T2 = _kelvin("temp1_c", temp1_c), _kelvin("temp2_c", temp2_c)
    ratio = math.exp(-(dh / R_J_PER_MOL_K) * (1.0 / T2 - 1.0 / T1))
    return ratio, {"dH_J_per_mol": dh, "T1_K": T1, "T2_K": T2}


def fick_flux(diff_m2_s: float, area_m2: float, delta_c_mol_m3: float, thickness_m: float):
    """J = D·A·ΔC/Δx — معدل الانتقال الغشائي (mol/s) — قانون فيك الأول."""
    d = _pos("diff_m2_s", diff_m2_s)
    a = _pos("area_m2", area_m2)
    dc = _nn_guard("delta_c_mol_m3", delta_c_mol_m3)
    dx = _pos("thickness_m", thickness_m)
    return d * a * dc / dx, {"D_m2_s": d, "A_m2": a, "dC_mol_m3": dc, "dx_m": dx}


def _nn_guard(name: str, value: float) -> float:
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
