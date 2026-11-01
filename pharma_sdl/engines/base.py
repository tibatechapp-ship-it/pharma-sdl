"""عقود محركات التسجيل — كل المحركات تلتزم بواجهة واحدة.

المبدأ (خطة v1.1 — API-First): طبقة الفرز لا تعرف شيئاً عن Vina أو Boltz-2،
تعرف فقط «محركاً يعيد kcal/mol لجزيء مقابل هدف». إضافة محرك جديد =
كلاس واحد + سطر تسجيل — بلا لمس خط الفرز.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from pharma_sdl.targets.models import Target


@dataclass(frozen=True)
class EngineScore:
    """درجة واحدة لجزيء واحد — مع الطريقة بصراحة كاملة."""

    kcal: float
    method: str
    engine: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EngineStatus:
    """حالة محرك في السجل — تُعرض في الـAPI والـCLI كما هي."""

    name: str
    label: str
    kind: str  # "simulation" | "docking" | "affinity"
    available: bool
    note_ar: str = ""
    note_en: str = ""


class DockingEngine(Protocol):
    """العقد الأدنى لكل محرك تسجيل/تقارب."""

    name: str
    label: str
    kind: str

    def available(self) -> bool:
        """هل المحرك جاهز فعلاً في هذه البيئة؟ (لا افتراضات — فحص حقيقي)"""
        ...

    def score(self, smiles: str, target: Target) -> EngineScore:
        """درجة ارتباط (kcal/mol) — الأكثر سالبية أقوى."""
        ...
