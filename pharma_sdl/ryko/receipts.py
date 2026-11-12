"""إيصالات Ryko القابلة للتحقق — مفهوم مُنتقا من ZYKO (docs/ryko/RYKO-MASTER-PLAN.md §2).

الإيصال ليس وثيقة تُدَّعى، بل **قرار يُحسب**: كل عملية تعيد قيمة + معادلة +
مصدر + افتراضات، والبصمة SHA-256 تُشتق من الحقول حصراً (بلا طوابع زمنية
ولا عشوائية) — فإعادة الحساب دون اتصال ممكنة دائماً، وأي تلاعب حرفيّ
يُكتشف (`verify_stored`).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

_DIGEST_ROUNDS = 10  # تقريب عشري مُثبَّت داخل البصمة (حتمية بالبايت)


def _canonical(value: float) -> float:
    return round(float(value), _DIGEST_ROUNDS)


@dataclass(frozen=True)
class RykoReceipt:
    """إيصال نتيجة علمية — قابلة للتحقق دون اتصال."""

    module: str
    op: str
    inputs: dict
    value: float | str
    unit: str
    formula: str
    source: str
    assumptions: tuple[str, ...] = ()
    extra: dict = field(default_factory=dict)

    def to_payload(self) -> dict:
        """حمولة الإيصال القياسية — الحقول نفسها التي تُحتسب منها البصمة."""
        value = self.value
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            value = _canonical(value)
        return {
            "module": self.module,
            "op": self.op,
            "inputs": self.inputs,
            "value": value,
            "unit": self.unit,
            "formula": self.formula,
            "source": self.source,
            "assumptions": list(self.assumptions),
            "extra": self.extra,
        }

    @property
    def digest(self) -> str:
        """بصمة SHA-256 للحمولة الكانونية (مفاتيح مرتّبة، صفر عشوائية)."""
        return self.digest_of(self.to_payload())

    @staticmethod
    def digest_of(payload: dict) -> str:
        """بصمة حمولة — الدالة المرجعية الوحيدة (تُستخدم للإنتاج والتحقق معاً)."""
        canonical = json.dumps(
            payload,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict:
        """الشكل المخزَّن/المنشور: الحقول + البصمة."""
        return {**self.to_payload(), "digest": self.digest}

    @classmethod
    def verify_stored(cls, stored: dict) -> bool:
        """إعادة الحساب دون اتصال: بصمة الإيصال المخزَّن تُشتق مجدداً وتُقارن.

        أي تعديل حرفيّ في الحقول (القيمة، المعادلة، المصدر، المدخلات…)
        يجعل التحقق يفشل — هذا عقد حتمية بالبايت.
        """
        if "digest" not in stored:
            return False
        fields = {k: v for k, v in stored.items() if k != "digest"}
        expected = cls.digest_of(fields)
        # مقارنة زمنية-ثابتة على سلاسل hex — سلامة جماعية لا سرية
        import hmac

        return hmac.compare_digest(expected, str(stored["digest"]))
