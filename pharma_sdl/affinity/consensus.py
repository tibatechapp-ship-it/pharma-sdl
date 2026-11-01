"""جسور الإجماع العلاجي — مقارنة عالم الفيزياء بعالم القياسات.

يعيد استخدام جسر Cheng-Prusoff المُتحقق منه في core.docking:
    ΔG ≈ −(RT·ln10)·pIC50 ≈ −1.364 × pIC50  kcal/mol (298 K)
حيث «الاتفاق التقريبي ممتاز، والاختلاف الكبير درس يُعلَّم ولا يُخفى».
"""

from __future__ import annotations

from typing import Any

from core.docking import pic50_to_dg_kcal  # re-export — جسر واحد لا اثنان

__all__ = ["consensus_row", "pic50_to_dg_kcal"]


def consensus_row(vina_kcal: float | None, pic50: float | None) -> dict[str, Any]:
    """صف إجماع موحّد مع حكم صريح على الاتفاق.

    |الفجوة| ≤ 2 kcal/mol → متسق · ≤ 4 → مقبول بانتظار · أعلى → مراجعة بشرية.
    """
    row: dict[str, Any] = {
        "vina_kcal": None if vina_kcal is None else round(float(vina_kcal), 2),
        "dg_from_pic50": None if pic50 is None else round(pic50_to_dg_kcal(pic50), 2),
        "gap": None,
        "verdict_ar": "بيانات ناقصة — لا حكم",
        "verdict_en": "insufficient data — no verdict",
    }
    if vina_kcal is None or pic50 is None:
        return row
    gap = round(float(vina_kcal) - pic50_to_dg_kcal(pic50), 2)
    row["gap"] = gap
    abs_gap = abs(gap)
    if abs_gap <= 2.0:
        row["verdict_ar"], row["verdict_en"] = "متسق", "consistent"
    elif abs_gap <= 4.0:
        row["verdict_ar"], row["verdict_en"] = "مقبول بانتظار القياس", "acceptable, await assay"
    else:
        row["verdict_ar"], row["verdict_en"] = "مراجعة بشرية مطلوبة", "human review required"
    return row
