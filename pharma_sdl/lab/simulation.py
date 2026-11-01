"""مختبر FRET محاكى — يؤكد واجهة المختبر قبل وصول الشريك الحقيقي.

التحويل معكوس جسر Cheng-Prusoff: pIC50 ≈ −ΔG/1.364، ثم IC50 = 10^(−pIC50) μM،
مع ضوضاء لوغاريتمية طبيعية موقّعة (hash) تحاكي تفاوت القياس المخبري.

⚠️ كل نتيجة تخرج بعلامة simulated=True وبيان صريح — صفر التباس مع قياس حقيقي.
"""

from __future__ import annotations

import hashlib
import math

from pharma_sdl.lab.interface import AssayRequest
from pharma_sdl.models import AssayResult

_DG_PER_PIC50 = 1.3644  # kcal/mol لكل وحدة pIC50 (298 K)


def _seeded_noise(smiles: str, sigma: float = 0.15) -> float:
    """ضوضاء ضربية حتمية (lognormal مبسطة) من hash الجزيء."""
    digest = hashlib.sha256(f"fret::{smiles}".encode()).digest()
    unit = int.from_bytes(digest[:8], "big") / 0xFFFFFFFFFFFFFFFF
    # تحويل uniform(0,1] إلى ضوضاء لوغاريتمية موقّعة حول 1.0
    z = math.sqrt(12.0) * (unit - 0.5)  # uniform → تقريب طبيعي [-1.73, 1.73]
    return math.exp(sigma * z)


class SimulatedFretLab:
    """فحص FRET افتراضي — للعرض والاختبار وتدريب سير العمل قبل الدمج."""

    name = "simulated-fret"

    def run_assay(self, request: AssayRequest) -> AssayResult:
        if request.dg_kcal is None:
            return AssayResult(
                smiles=request.smiles,
                assay=self.name,
                simulated=True,
                notes_ar="بلا طاقة مدخلة — لا يمكن اشتقاق IC50؛ مرّر dg_kcal من جولة الفرز.",
                notes_en="No input ΔG — cannot derive IC50; pass dg_kcal from a screening run.",
            )
        pic50 = (-float(request.dg_kcal) / _DG_PER_PIC50) * _seeded_noise(request.smiles)
        ic50_um = 10 ** (-pic50) * 1e6
        return AssayResult(
            smiles=request.smiles,
            assay=self.name,
            simulated=True,
            ic50_um=round(ic50_um, 3),
            pic50=round(pic50, 2),
            dg_kcal_input=round(float(request.dg_kcal), 2),
            notes_ar="نتيجة محاكاة FRET — ليست قياساً مخبرياً؛ للعرض والتدريب فقط.",
            notes_en="Simulated FRET result — not a wet-lab measurement; demo/training only.",
        )
