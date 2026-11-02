"""طبقة دفعات المختبر — الوحدة الطبيعية للفيزياء الحقيقية (P8).

المختبر الحقيقي لا يفحص جزيئاً واحداً متزامناً: يُقدَّم الطلب **دفعة**،
تُمنح **تذكرة**، ثم تُستطلع النتائج حتى حالة نهائية. هذا البروتوكول هو
الشكل الذي تتحدث به أي بوابة أجهزة أو LIMS — والمحاكاة تنفذه حرفياً
أيضاً، فما فوق المختبر لا يرى فرقاً سوى حقل `simulated` في النتائج.

(ADR-0013 — جسر الفيزياء: التكامل الفعلي ضبطُ تهيئة لا إعادة كتابة.)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from pharma_sdl.lab.interface import AssayRequest
from pharma_sdl.models import AssayResult

#: حالات الدفعة كما يعرفها العقد — المختبر مصدر الحقيقة لحالتها.
BATCH_STATUSES = ("pending", "running", "completed", "failed")

#: الحالات النهائية — بعدها لا استطلاع ولا تغيير.
TERMINAL_BATCH_STATUSES = ("completed", "failed")


@dataclass(frozen=True)
class BatchTicket:
    """تذكرة دفعة مقدَّمة — هويتها عند المختبر لا عند المنصة."""

    batch_id: str
    adapter: str
    n_assays: int
    status: str = "pending"


@dataclass(frozen=True)
class BatchPoll:
    """استطلاع واحد لحالة دفعة — النتائج تظهر حصراً عند اكتمال سليم."""

    batch_id: str
    adapter: str
    status: str
    results: tuple[AssayResult, ...] | None = None
    error_ar: str | None = None
    error_en: str | None = None


@runtime_checkable
class LabBatchClient(Protocol):
    """عقد المختبر بالدفعات — محاكى الآن، LIMS حقيقي غداً، نفس الواجهة.

    يمتد على `LabClient` التزامني (جزيء واحد) دون إلغائه: الأعلى يختار
    الشكل المناسب، والمحولان ينفذان الاثنين — لا استثناءات في الأعلى.
    """

    name: str

    def submit_batch(
        self, requests: list[AssayRequest], idempotency_key: str | None = None
    ) -> BatchTicket:
        """تقديم دفعة — إعادة التقديم بالمفتاح نفسه يجب ألا تُكرِّر العمل."""
        ...

    def poll_batch(self, batch_id: str) -> BatchPoll:
        """استطلاع حالة دفعة مقدَّمة — دفعة مجهولة خطأ صريح لا صمت."""
        ...
