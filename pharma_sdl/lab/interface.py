"""واجهة المختبر الذاتي — مقبس موحّد لأي فحص (FRET اليوم، خلافه غداً).

خطة v1.1: دفعات FRET تأكيدية في Q3/Q4 عبر شريك مختبري. هذا الملف هو
نقطة الدمج: أدوات المنصة تُنتج مرشحين، والمختبر يؤكدهم — عبر Protocol واحد
يُنفَّذ محلياً (محاكاة) أو لاحقاً بخدمة LIMS حقيقية بلا تغيير في الأعلى.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from pharma_sdl.models import AssayResult


@dataclass(frozen=True)
class AssayRequest:
    """طلب فحص: جزيء + الطاقة المفترضة من خط الفرز (للاستخدام في التحويل)."""

    smiles: str
    dg_kcal: float | None = None
    compound_name: str | None = None


class LabClient(Protocol):
    """عقد أي مختبر — محاكى الآن، حقيقي لاحقاً، نفس الواجهة."""

    name: str

    def run_assay(self, request: AssayRequest) -> AssayResult:
        """تنفيذ الفحص وإعادة نتيجة موقّعة (simulated=True للنتائج غير الحقيقية)."""
        ...
