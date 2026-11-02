"""واجهة المختبر — FRET محاكى الآن، وجسر LIMS حقيقي (P8) بنفس العقود.

المصنع `make_lab_client` هو نقطة التبديل الوحيدة: رابط LIMS مضبوط ⇒
الجسر الحقيقي؛ وإلا ⇒ المحاكاة. لا مسار ثالث، ولا عودة صامتة إلى
المحاكاة بعد ضبط البوابة — فذلك تلفيق نتائج (ADR-0013).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pharma_sdl.lab.batch import (
    BATCH_STATUSES,
    TERMINAL_BATCH_STATUSES,
    BatchPoll,
    BatchTicket,
    LabBatchClient,
)
from pharma_sdl.lab.interface import AssayRequest, LabClient
from pharma_sdl.lab.lims import HttpLimsLab, LimsSettings
from pharma_sdl.lab.outbox import BatchOutbox
from pharma_sdl.lab.simulation import SimulatedFretLab

if TYPE_CHECKING:  # pragma: no cover — استيراد نمطي لتجنّب دورة الاستيراد
    from pharma_sdl.config import Settings

__all__ = [
    "BATCH_STATUSES",
    "TERMINAL_BATCH_STATUSES",
    "AssayRequest",
    "BatchOutbox",
    "BatchPoll",
    "BatchTicket",
    "HttpLimsLab",
    "LabBatchClient",
    "LabClient",
    "LimsSettings",
    "SimulatedFretLab",
    "make_lab_client",
]


def make_lab_client(settings: Settings | None = None) -> SimulatedFretLab | HttpLimsLab:
    """مصنع المختبر: بوابة مضبوطة ⇒ `HttpLimsLab`؛ وإلا ⇒ `SimulatedFretLab`.

    الاتجاه الوحيد المسموح للتراجع هو من الحقيقي إلى الفشل الصريح
    (`LabError`) — العودة الصامتة إلى المحاكاة بعد ضبط البوابة تلفيق
    نتائج مخبرية وممنوعة بنيوياً.
    """
    if settings is None:
        from pharma_sdl.config import get_settings

        settings = get_settings()
    if settings.lims_url:
        outbox = BatchOutbox(settings.lims_outbox) if settings.lims_outbox else None
        return HttpLimsLab(
            LimsSettings(
                base_url=settings.lims_url,
                token=settings.lims_token,
                timeout_s=settings.lims_timeout_s,
                poll_interval_s=settings.lims_poll_interval_s,
                max_polls=settings.lims_max_polls,
            ),
            outbox=outbox,
        )
    return SimulatedFretLab()
