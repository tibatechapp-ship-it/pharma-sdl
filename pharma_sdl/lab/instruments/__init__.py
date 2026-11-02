"""طبقة سواقة الأجهزة الميدانية — التصدير العام + مصنع بلا تراجع صامت."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pharma_sdl.lab.instruments.base import (
    MIN_APPROVAL_TOKEN_LENGTH,
    InstrumentDriver,
    InstrumentReading,
    InstrumentStatus,
    reading_to_payload,
)
from pharma_sdl.lab.instruments.fret_reader import FRETReaderDriver

if TYPE_CHECKING:  # pragma: no cover — استيراد نمطي لتجنّب دورة الاستيراد
    from pharma_sdl.config import Settings

__all__ = [
    "MIN_APPROVAL_TOKEN_LENGTH",
    "FRETReaderDriver",
    "InstrumentDriver",
    "InstrumentReading",
    "InstrumentStatus",
    "make_instrument_driver",
    "reading_to_payload",
]


def make_instrument_driver(settings: Settings | None = None) -> FRETReaderDriver | None:
    """مصنع السواقة الميدانية: مضيف مضبوط ⇒ سواقة؛ وإلا `None` صريح.

    بخلاف مصنع المختبر (`make_lab_client`) الذي يعيد المحاكاة التوثيقية
    حين لا بوابة، طبقة الأجهزة أداة ميدانية: **غياب التهيئة يعني لا
    جهاز** — وادعاء وجود جهاز بالصمت أشد خطورة من عدم وجوده، لأن كل
    قراءة تخرج منه ستُظن فيزيائية.

    المضيف نفسه قد يشير إلى محاكي SCPI (`tools/fret_simulator.py`) —
    والحكمة عن طبيعة الجهاز تأتي من القراءة نفسها (`simulated`) لا من
    التخمين.
    """
    if settings is None:
        from pharma_sdl.config import get_settings

        settings = get_settings()
    if not settings.instrument_host:
        return None
    return FRETReaderDriver(
        host=settings.instrument_host,
        port=settings.instrument_port,
        timeout_seconds=settings.instrument_timeout_s,
        simulated=settings.instrument_simulated,
    )
