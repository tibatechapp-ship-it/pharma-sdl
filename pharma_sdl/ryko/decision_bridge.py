"""جسر Ryko إلى سلسلة القرار — P20 (docs/ryko/RYKO-MASTER-PLAN.md §خارطة الطريق).

سلسلة القرار في المنصة (core/three_tier): الطبقة 1 (ML) تفرز الآلاف، الطبقة 2
(Vina) تصفي المئات، الطبقة 3 (Boltz-2) تسعّر العشرات. قراءات هذه الطبقات أرقام
خام — والجسر هنا يحوّل كل قراءة إلى **إيصالات Ryko قابلة للتحقق دون اتصال**:
IC50 من pIC50، وKd من ΔG، وKi بتصحيح Cheng-Prusoff، والأثر (Hill) عند تركيز
القرار (مثلاً C90 في capstone).

الجسر لا يحسب شيئاً بنفسه: كل رقم يخرج عبر عملية معلنة في المحرك
(`get_engine().compute`) — فالإيصال يحمل معادلة ومصدراً وافتراضات وبصمة
SHA-256 تُتحقق بـ `RykoReceipt.verify_stored`. القراءة الفاشلة أو الغائبة
تعيد قائمة فارغة — غياب صادق، لا إيصال مُختلق.
"""

from __future__ import annotations

from .receipts import RykoReceipt


def _engine():
    from . import get_engine

    return get_engine()


def receipts_for_reading(
    reading: dict | None,
    temp_c: float = 25.0,
    ligand_nm: float | None = None,
    kd_nm: float | None = None,
) -> list[RykoReceipt]:
    """قراءة three_tier → إيصالات قابلة للتحقق (IC50، Ki، Kd).

    reading: قراءة طبقة من core/three_tier (dict بحالة «ok») أو dict يدوي
    يحمل pic50 و/أو dg_kcal. القراءة الفاشلة/الغائبة ⇒ [] بلا استثناء.

    - pic50 ⇒ إيصال `math.pic50_to_ic50` (IC50 nM).
    - pic50 + [L] + Kd ⇒ إيصال `pharma.cheng_prusoff_ki` (Ki nM).
    - dg_kcal ⇒ إيصال `physics.kd_from_dg` (Kd µM عند temp_c).
    """
    if not reading or reading.get("status") != "ok":
        return []
    eng = _engine()
    out: list[RykoReceipt] = []
    pic50 = reading.get("pic50")
    if pic50 is not None:
        ic50_receipt = eng.compute("math", "pic50_to_ic50", pic50=float(pic50))
        out.append(ic50_receipt)
        if ligand_nm is not None and kd_nm is not None:
            out.append(eng.compute(
                "pharma",
                "cheng_prusoff_ki",
                ic50=float(ic50_receipt.value),
                ligand_nm=float(ligand_nm),
                kd_nm=float(kd_nm),
            ))
    dg = reading.get("dg_kcal")
    if dg is not None:
        out.append(eng.compute(
            "physics", "kd_from_dg", dg_kcal=float(dg), temp_c=float(temp_c),
        ))
    return out


def receipts_for_candidate(
    pic50: float,
    conc_nm: float,
    hill_coeff: float = 1.0,
) -> list[RykoReceipt]:
    """إيصالات مرشح في سلسلة القرار: فعالية ← تركيز ← أثر Hill عند التركيز.

    conc_nm: تركيز القرار (مثلاً C90 من core/capstone.c90_nm). الإيصال الثاني
    يُظهر الأثر الفعلي عند هذا التركيز فتصبح نسبة الاحتلال معلنة ومتحققة،
    لا ادعاء: عند conc = C90 يكون الأثر ≈ 0.90 حرفياً.
    """
    eng = _engine()
    ic50_receipt = eng.compute("math", "pic50_to_ic50", pic50=float(pic50))
    hill_receipt = eng.compute(
        "pharma",
        "hill_effect",
        conc=float(conc_nm),
        emax=1.0,
        ec50=float(ic50_receipt.value),
        hill_coeff=float(hill_coeff),
    )
    return [ic50_receipt, hill_receipt]


def stored(receipts: list[RykoReceipt]) -> list[dict]:
    """الشكل المخزَّن/المنشور (الحقول + البصمة) — للسجل والتقارير."""
    return [r.to_dict() for r in receipts]
