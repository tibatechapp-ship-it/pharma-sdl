"""محرك المحاكاة — Walking Skeleton (خطة v1.1، القرار D5).

درجات «حتمية شبه-فيزيائية» للتجارب والاختبارات وCI والعرض الحي بلا GPU:
  • hash(SMILES + target) → قيمة ثابتة 100% بين الجولات (نفس المدخل = نفس النتيجة).
  • المدى [-10.5, -5.2] kcal/mol — نطاق واقعي لدرجات الربط في جيوب بروتينية.

⚠️ الصدق أولاً: هذه ليست فيزياء — method="simulation" يظهر في كل نتيجة
وتقرير، لذلك لا يمكن أن تختلط نتائج المحاكاة بالحقيقية في أي عرض.
استبدلها بـ Vina/Boltz-2 عند توفرهما — الخط نفسه بلا تغيير.
"""

from __future__ import annotations

import hashlib

from pharma_sdl.engines.base import EngineScore
from pharma_sdl.targets.models import Target

_LO, _HI = -10.5, -5.2


def _deterministic_score(smiles: str, target_id: str) -> float:
    digest = hashlib.sha256(f"{smiles.strip()}::{target_id}".encode()).digest()
    unit = int.from_bytes(digest[:8], "big") / 0xFFFFFFFFFFFFFFFF
    return round(_LO + (_HI - _LO) * unit, 2)


class SimulationEngine:
    """محرك حتمي متاح دائماً — العمود الفقري للاختبارات والعرض الفوري."""

    name = "simulation"
    label = "محاكاة حتمية (Walking Skeleton)"
    kind = "simulation"

    def available(self) -> bool:
        return True

    def score(self, smiles: str, target: Target) -> EngineScore:
        return EngineScore(
            kcal=_deterministic_score(smiles, target.id),
            method="simulation",
            engine=self.name,
            details={
                "deterministic": True,
                "note_ar": "درجة محاكاة حتمية للتطوير — ليست فيزياء ولا تنبؤاً.",
                "note_en": "Deterministic dev score — not physics, not a prediction.",
            },
        )
