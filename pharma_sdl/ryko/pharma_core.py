"""U5 — الفارماكولوجيا: Hill، مؤشر الأمان، Cheng-Prusoff، قواعد معرفة معلنة (§3 U5).

قاعدتا المعرفة (CYP وDDD) **ثابتتان ومُعلنتا المصدر ومحدودتان عمداً** — لا
تخمين ولا اكتمال زائف: ما ليس في القاعدة يُرفض صادقاً برسالة واضحة.
المصادر: Hill 1910؛ Goutelle 2008؛ Cheng & Prusoff 1973؛ FDA Guidance 2020
(أمثلة إنزيمات معيارية)؛ WHO ATC/DDD Index 2024.
"""

from __future__ import annotations

import math

from .errors import RykoInputError, RykoUnknownOpError


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


# ── Hill / Emax ──


def hill_effect(conc: float, emax: float, ec50: float, hill_coeff: float = 1.0):
    """E = Emax·Cʰ/(EC50ʰ+Cʰ) — الأثر عند تركيز.

    الذهبي: C=EC50 ⇒ E=Emax/2 مهما كان h.
    """
    c = _nn_guard("conc", conc)
    em = _finite("emax", emax)
    ec = _pos("ec50", ec50)
    h = _pos("hill_coeff", hill_coeff)
    e = em * (c**h) / (ec**h + c**h)
    return e, {"conc": c, "emax": em, "ec50": ec, "h": h, "fraction_of_emax": e / em if em else 0.0}


def ec50_from_effect(effect: float, emax: float, conc: float, hill_coeff: float = 1.0):
    """العكس الحتمي: EC50 من (أثر، Emax، تركيز) — يتطلب 0<effect<Emax."""
    e = _nn_guard("effect", effect)
    em = _pos("emax", emax)
    c = _pos("conc", conc)
    h = _pos("hill_coeff", hill_coeff)
    if e >= em:
        raise RykoInputError(
            f"الأثر {e} ≥ Emax {em} — لا يحدد EC50؛ أدخل أثراً أشد من صفر وأقل من Emax.",
            f"Effect {e} ≥ Emax {em} — cannot determine EC50; need 0 < effect < Emax.",
        )
    ec50 = c * ((em / e) - 1.0) ** (1.0 / h)
    return ec50, {"effect": e, "emax": em, "conc": c, "h": h}


def therapeutic_index(td50: float, ed50: float):
    """TI = TD50/ED50 — مؤشر العلاجية."""
    t, e = _pos("td50", td50), _pos("ed50", ed50)
    return t / e, {"td50": t, "ed50": e}


def certain_safety_factor(td1: float, ed99: float):
    """CSF = TD₁/ED₉₉ — عامل الأمان المؤكد (أصرم من TI)."""
    t, e = _pos("td1", td1), _pos("ed99", ed99)
    return t / e, {"td1": t, "ed99": e}


def cheng_prusoff_ki(ic50: float, ligand_nm: float, kd_nm: float):
    """Ki = IC50/(1+[L]/Kd) — تصحيح Cheng-Prusoff للتراكيز المطلقة (nM)."""
    ic = _pos("ic50", ic50)
    l = _pos("ligand_nm", ligand_nm)
    kd = _pos("kd_nm", kd_nm)
    ki = ic / (1.0 + l / kd)
    return ki, {"ic50": ic, "ligand_nm": l, "kd_nm": kd, "correction": 1.0 + l / kd}


# ── قاعدة معرفة CYP (ثابتة، معلنة المصدر، محدودة عمداً) ──
# أمثلة إنزيمات معيارية من FDA Guidance (2020): Clinical Drug Interaction Studies.
_CYP_KB: dict[str, dict[str, str]] = {
    "ketoconazole": {"cyp3a4": "strong_inhibitor"},
    "clarithromycin": {"cyp3a4": "strong_inhibitor"},
    "rifampin": {"cyp3a4": "strong_inducer"},
    "carbamazepine": {"cyp3a4": "inducer"},
    "midazolam": {"cyp3a4": "probe_substrate"},
    "omeprazole": {"cyp2c19": "inhibitor"},
    "clopidogrel": {"cyp2c19": "prodrug_substrate"},
    "fluoxetine": {"cyp2d6": "inhibitor"},
    "paroxetine": {"cyp2d6": "inhibitor"},
    "quinidine": {"cyp2d6": "inhibitor"},
    "warfarin": {"cyp2c9": "substrate"},
    "losartan": {"cyp2c9": "substrate"},
    "amoxicillin": {"cyp": "no_major_cyp"},
    "metformin": {"cyp": "no_major_cyp"},
}


def cyp_lookup(drug: str):
    """دور الدواء في إنزيمات CYP — من القاعدة الثابتة المعلنة فقط.

    ما ليس في القاعدة يُرفض صادقاً (لا استنتاج ولا اكتمال زائف).
    """
    if not isinstance(drug, str) or not drug.strip():
        raise RykoInputError(
            "اسم الدواء مطلوب.",
            "Drug name required.",
        )
    key = drug.strip().lower()
    entry = _CYP_KB.get(key)
    if entry is None:
        raise RykoUnknownOpError(
            f"«{drug}» ليس في قاعدة CYP المعلنة ({len(_CYP_KB)} إدخالاً) — "
            "لا نستنتج ولا نخمّن؛ وسّع القاعدة بمصدر معلن إن لزم.",
            f"'{drug}' is not in the declared CYP knowledge base ({len(_CYP_KB)} entries) — "
            "no guessing; extend it with a declared source if needed.",
        )
    return key, {"roles": entry, "kb_size": len(_CYP_KB)}


# ── قاعدة معرفة DDD (WHO ATC/DDD Index 2024 — الجرعة اليومية المحددة، الفموية) ──
_DDD_KB: dict[str, dict[str, str]] = {
    "amoxicillin": {"ddd": "1 g", "atc": "J01CA04", "route": "O"},
    "paracetamol": {"ddd": "3 g", "atc": "N02BE01", "route": "O"},
    "ibuprofen": {"ddd": "1.2 g", "atc": "M01AE01", "route": "O"},
    "metformin": {"ddd": "2 g", "atc": "A10BA02", "route": "O"},
    "atorvastatin": {"ddd": "20 mg", "atc": "C10AA05", "route": "O"},
    "omeprazole": {"ddd": "20 mg", "atc": "A02BC01", "route": "O"},
    "amlodipine": {"ddd": "5 mg", "atc": "C08CA01", "route": "O"},
    "warfarin": {"ddd": "5 mg", "atc": "B01AA03", "route": "O"},
}


def ddd_lookup(drug: str):
    """الجرعة اليومية المحددة (DDD) من قاعدة WHO المعلنة فقط."""
    if not isinstance(drug, str) or not drug.strip():
        raise RykoInputError(
            "اسم الدواء مطلوب.",
            "Drug name required.",
        )
    key = drug.strip().lower()
    entry = _DDD_KB.get(key)
    if entry is None:
        raise RykoUnknownOpError(
            f"«{drug}» ليس في قاعدة DDD المعلنة ({len(_DDD_KB)} إدخالاً، WHO 2024) — "
            "راجع فهرس WHO مباشرة أو وسّع القاعدة بمصدر معلن.",
            f"'{drug}' is not in the declared DDD knowledge base ({len(_DDD_KB)} entries, "
            "WHO 2024) — consult the WHO index directly or extend with a declared source.",
        )
    return key, {**entry, "source": "WHO ATC/DDD Index 2024"}


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


def _nn_guard(name: str, value: float) -> float:
    v = _finite(name, value)
    if v < 0:
        raise RykoInputError(
            f"المدخل «{name}» يجب أن يكون غير سالب (وصل: {value}).",
            f"Input '{name}' must be non-negative (got: {value}).",
        )
    return v
