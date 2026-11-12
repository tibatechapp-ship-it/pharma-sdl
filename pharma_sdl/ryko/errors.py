"""أخطاء Ryko — ثنائية اللغة (عربي/إنجليزي) ومُعلَّلة دائماً.

فلسفة المنصة: تدهور صادق — لا رقم مُختلق ولا صمت. كل رفض يحمل سببه
باللغتين، ويُترجم على API إلى 422/404 برسالة قابلة للعرض.
"""

from __future__ import annotations


class RykoError(Exception):
    """الأساس — خطأ Ryko ثنائي اللغة."""

    def __init__(self, ar: str, en: str) -> None:
        super().__init__(f"{ar} | {en}")
        self.ar = ar
        self.en = en

    def as_dict(self) -> dict[str, str]:
        return {"ar": self.ar, "en": self.en}


class RykoInputError(RykoError):
    """مدخل خارج النطاق أو غير صالح — يُترجم إلى 422."""


class RykoUnknownOpError(RykoError):
    """وحدة أو عملية غير معروفة — يُترجم إلى 404."""
