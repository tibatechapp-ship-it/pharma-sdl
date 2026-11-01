"""أخطاء المنصة — تسلسل واحد واضح تترجمه طبقة الـAPI إلى رموز HTTP صادقة."""

from __future__ import annotations


class PlatformError(Exception):
    """أساس كل أخطاء المنصة — رسالة عربية + رمز HTTP."""

    http_status = 500
    code = "platform_error"

    def __init__(self, message_ar: str, message_en: str | None = None) -> None:
        super().__init__(message_ar)
        self.message_ar = message_ar
        self.message_en = message_en or message_ar


class ValidationError(PlatformError):
    """إدخال غير صالح من المستدعي."""

    http_status = 422
    code = "validation_error"


class NotFoundError(PlatformError):
    """العنصر المطلوب غير موجود (هدف، جولة، مهمة...)."""

    http_status = 404
    code = "not_found"


class EngineUnavailableError(PlatformError):
    """المحرك المطلوب غير مركَّب/غير مهيأ في هذه البيئة."""

    http_status = 409
    code = "engine_unavailable"


class ScreeningError(PlatformError):
    """فشل داخلي أثناء تنفيذ جولة فرز."""

    http_status = 500
    code = "screening_error"
