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


class UnauthorizedError(PlatformError):
    """لا هوية أو هوية غير معروفة — المصادقة مفعلة والمفتاح مفقود/مرفوض (P2)."""

    http_status = 401
    code = "unauthorized"


class ForbiddenError(PlatformError):
    """هوية معروفة لكن دورها أدنى مما تتطلبه العملية — RBAC (P2)."""

    http_status = 403
    code = "forbidden"


class RateLimitError(PlatformError):
    """تجاوز حد المعدل في وضع العرض العام — عدالة الحساب المشترك (P2)."""

    http_status = 429
    code = "rate_limited"


class StoreUnavailableError(PlatformError):
    """خلفية التخزين الحية غير قابلة للوصول (P3) — فشل صريح لا ادعاء تشغيل."""

    http_status = 503
    code = "store_unavailable"


class LabError(PlatformError):
    """فشل جسر المختبر (P8) — شبكة أو بوابة LIMS أو مهلة استطلاع.

    الصدق بنيوياً: عند ضبط بوابة حقيقية فإن فشلها فشل صريح — لا عودة
    صامتة إلى المحاكاة، فذلك تلفيق نتائج مخبرية لم تقع أصلاً.
    """

    http_status = 502
    code = "lab_error"


class LimsContractError(LabError):
    """خرق عقد بوابة المختبر (ADR-0013) — استجابة لا تطابق العقد المعلن.

    انضباط عقود ChEMBL نفسه مطبق على الفيزياء: كل الخروق تُجمع في رفض
    واحد، والدفعة تُرفض كاملة لا تُقبل جزئياً بلا سؤال.
    """

    http_status = 502
    code = "lims_contract_violation"
