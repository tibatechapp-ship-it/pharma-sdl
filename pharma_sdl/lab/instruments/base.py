"""طبقة الأجهزة — المقبس الذي يُوصَل فيه السلك الفيزيائي (P10).

P8/P9 أوصلا عقد REST حتى نقطة الرفع في البوابة المرجعية («هنا تُوصَل
الأجهزة» — ADR-0013/0014)؛ هذه الوحدة تبني ما خلفها في جهة الميدان:
بروتوكول موحّد لأي جهاز قياس (حقيقي أو محاكى) وقراءة موقّعة تحمل
هويتها الكاملة.

المبدأ الحاكم: **«الوكيل يبني المقبس، والإنسان يوصّل السلك»**:

- كل قراءة تحمل `simulated` صادقاً + الرقم التسلسلي + بصمة المعايرة
  + رمز الموافقة — قراءة بلا هوية ليست دليلاً علمياً.
- القراءة المحاكاة تحصل تلقائياً على رمز تتبع `SIMULATED-…`؛ القراءة
  الحقيقية تتطلب رمز موافقة بشرياً (≥ 16 حرفاً) وإلا `SafetyViolation`.
- الجسر `reading_to_payload` **لا يشتق IC50 من نسبة FRET واحدة أبداً** —
  القيمة المقاسة تأتي من تحليل منحنى الجرعة البشري وتُمرَّر صراحة؛
  والصف الناتج يحمل `simulated` من القراءة نفسها، فبيانات المحاكي
  لا تمرّ عبر بوابة حقيقية متسللةً كفيزياء.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Protocol, runtime_checkable

from pharma_sdl.errors import ValidationError

#: الحد الأدنى لطول رمز الموافقة البشرية على قياس حقيقي.
MIN_APPROVAL_TOKEN_LENGTH = 16


class InstrumentStatus(str, Enum):
    """حالة الجهاز اللحظية كما يفصح عنها بروتوكوله."""

    IDLE = "idle"
    BUSY = "busy"
    ERROR = "error"
    CALIBRATING = "calibrating"
    OFFLINE = "offline"


@dataclass(frozen=True)
class InstrumentReading:
    """قراءة خام موقّعة من جهاز قياس — هويتها الكاملة جزء من الدليل.

    هذه ليست `AssayResult`: القراءة الخام تقف خلف نقطة رفع البوابة،
    ولا تتحول إلى نتيجة منصة إلا عبر `reading_to_payload` بقيم مقاسة
    يمررها التحليل البشري صراحة.

    Raises:
        ValidationError: على هوية ناقصة أو قيم غير منتهية أو رمز موافقة
            غير ملائم (القياس الحقيقي يتطلب رمزاً ≥ 16 حرفاً).
    """

    experiment_id: str
    compound_id: str
    target_id: str
    instrument_serial: str
    timestamp: datetime
    raw_value: float
    standard_error: float
    control_positive: float | None
    control_negative: float | None
    calibration_curve_hash: str
    operator_id: str
    approval_token: str
    protocol_name: str = ""
    unit: str = "fret_ratio"
    simulated: bool = True

    def __post_init__(self) -> None:
        if not self.experiment_id.strip() or not self.compound_id.strip():
            raise ValidationError(
                "القراءة بلا معرّف تجربة أو مركب — قراءة بلا هوية ليست دليلاً",
                "Reading without experiment/compound id is not evidence",
            )
        if not self.instrument_serial.strip():
            raise ValidationError(
                "القراءة بلا رقم تسلسلي للجهاز",
                "Reading without instrument serial number",
            )
        for name, value in (
            ("raw_value", self.raw_value),
            ("standard_error", self.standard_error),
            ("control_positive", self.control_positive),
            ("control_negative", self.control_negative),
        ):
            if value is not None and not math.isfinite(float(value)):
                raise ValidationError(
                    f"القيمة {name} غير منتهية — لا تُقبل قراءة غير منتهية",
                    f"{name} is not finite — non-finite readings are rejected",
                )
        if not self.approval_token:
            raise ValidationError(
                "كل قراءة تحتاج رمز تتبع/موافقة — حتى المحاكاة توثَّق",
                "Every reading requires a tracking/approval token",
            )
        if not self.simulated and len(self.approval_token) < MIN_APPROVAL_TOKEN_LENGTH:
            raise ValidationError(
                "القراءة الحقيقية تتطلب رمز موافقة بشرياً "
                f"(≥ {MIN_APPROVAL_TOKEN_LENGTH} حرفاً)",
                "Real readings require a human approval token "
                f"(≥ {MIN_APPROVAL_TOKEN_LENGTH} chars)",
            )

    def verify_against_controls(self) -> bool:
        """هل القراءة ضمن نطاق الضابطين؟ (غياب الضوابط ⇒ False)."""
        if self.control_positive is None or self.control_negative is None:
            return False
        low = min(float(self.control_positive), float(self.control_negative))
        high = max(float(self.control_positive), float(self.control_negative))
        return low <= float(self.raw_value) <= high

    def content_hash(self) -> str:
        """بصمة SHA-256 لهوية القراءة وقياسها — لكشف أي عبث لاحق."""
        payload = "|".join(
            (
                self.experiment_id,
                self.compound_id,
                self.target_id,
                self.instrument_serial,
                self.protocol_name,
                self.timestamp.isoformat(),
                f"{self.raw_value!r}",
                self.unit,
                f"{self.standard_error!r}",
                self.calibration_curve_hash,
                self.operator_id,
                self.approval_token,
                str(self.simulated),
            )
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict:
        """تمثيل JSONي كامل — لأرشيف الجلسة الميدانية وسجلات التدقيق."""
        return {
            "experiment_id": self.experiment_id,
            "compound_id": self.compound_id,
            "target_id": self.target_id,
            "protocol_name": self.protocol_name,
            "instrument_serial": self.instrument_serial,
            "timestamp": self.timestamp.isoformat(),
            "raw_value": self.raw_value,
            "unit": self.unit,
            "standard_error": self.standard_error,
            "control_positive": self.control_positive,
            "control_negative": self.control_negative,
            "calibration_curve_hash": self.calibration_curve_hash,
            "operator_id": self.operator_id,
            "approval_token": self.approval_token,
            "simulated": self.simulated,
            "content_hash": self.content_hash(),
        }


@runtime_checkable
class InstrumentDriver(Protocol):
    """عقد أي جهاز قياس — محاكى الآن، حقيقي غداً، نفس الواجهة حرفياً.

    ما فوق السواقة لا يعرف إن كان الجهاز حقيقياً؛ يقرأ `is_simulated`
    و`InstrumentReading.simulated` ويتصرف بصدق تبعاً لهما.
    """

    @property
    def serial_number(self) -> str:
        """الرقم التسلسلي للجهاز — يدخل في كل قراءة."""
        ...

    @property
    def is_simulated(self) -> bool:
        """هل هذه سواقة محاكي؟ (الجهاز الحقيقي قرار بشري موثق)."""
        ...

    def connect(self) -> None:
        """فتح الاتصال والتحقق من هوية الجهاز."""
        ...

    def disconnect(self) -> None:
        """إغلاق الاتصال وتنظيف الحالة."""
        ...

    def get_status(self) -> InstrumentStatus:
        """حالة الجهاز اللحظية."""
        ...

    def calibrate(self, standards: list[float]) -> str:
        """تشغيل معايرة بمعايير معلومة — يعيد بصمة منحنى المعايرة."""
        ...

    def run_assay(
        self,
        compound_id: str,
        target_id: str,
        protocol_name: str,
        approval_token: str,
    ) -> InstrumentReading:
        """تنفيذ قياس واحد وإعادة قراءة موقّعة."""
        ...


def reading_to_payload(reading: InstrumentReading, *, smiles: str, ic50_um: float) -> dict:
    """الجسر الصادق من قراءة ميدانية إلى صف نتائج ترفعه البوابة.

    القيمتان `smiles` و`ic50_um` **مدخلات بشرية إلزامية**: الأولى من
    خريطة الصفيحة، والثانية من ملاءمة منحنى الجرعة-الاستجابة للقراءات.
    الكود لا يشتق IC50 من نسبة FRET واحدة — فذلك تخمين يرتدي زي قياس.

    `simulated` في الصف يأتي من القراءة نفسها: قراءة محاكي تبقى
    `simulated=True` وسيرفضها عميل بوابة حقيقية (عقد ADR-0013) —
    بيانات التدريب لا تعبر إلى مسار الفيزياء متسللةً.

    Raises:
        ValidationError: على smiles فارغ أو ic50_um غير موجب منتهٍ.
    """
    if not isinstance(smiles, str) or not smiles.strip():
        raise ValidationError(
            "الجسر يتطلب smiles صالحاً من خريطة الصفيحة — لا تخمين",
            "reading_to_payload requires a valid smiles from the plate map",
        )
    if isinstance(ic50_um, bool) or not isinstance(ic50_um, (int, float)):
        raise ValidationError(
            "الجسر يتطلب ic50_um مقاسة من ملاءمة المنحنى — مرر القيمة لا تخمينها",
            "reading_to_payload requires a curve-fitted ic50_um — pass it, never guess",
        )
    ic50 = float(ic50_um)
    if not math.isfinite(ic50) or ic50 <= 0:
        raise ValidationError(
            "ic50_um يجب أن تكون موجبة منتهية — القيم غير الفيزيائية تُرفض هنا",
            "ic50_um must be finite-positive — non-physical values are rejected here",
        )
    pic50 = round(-math.log10(ic50 * 1e-6), 2)
    return {
        "smiles": smiles.strip(),
        "ic50_um": ic50,
        "pic50": pic50,
        "simulated": bool(reading.simulated),
    }


__all__ = [
    "MIN_APPROVAL_TOKEN_LENGTH",
    "InstrumentDriver",
    "InstrumentReading",
    "InstrumentStatus",
    "reading_to_payload",
]
