"""بوابة الاعتماد العلمي — أربع حالات، ترقية صريحة بشرية فقط.

المبدأ (تدقيق P0 + قرار v1.1): نتيجة ما لا تنتقل إلى حالة أعلى تلقائياً
مهما نجح البرنامج أو ارتفعت الدرجة. الترقية قرار موثق بسببٍ ومُجيزٍ،
خطوة واحدة صعوداً، وبمرفقات إلزامية للحالتين العليا:

    UNVALIDATED                نتيجة أولية لم تُتحقق علميًا (حالة كل مخرج جديد)
    COMPUTATIONALLY_VALIDATED  اجتازت فحوصًا حسابية محددة معلنة
    EXPERIMENTALLY_SUPPORTED   تدعمها نتائج تجريبية موثقة (مرجع فحص إلزامي)
    INDEPENDENTLY_REPRODUCED   أعاد فريق مستقل إنتاجها (بروتوكول + مختبر مستقل)

كل بطاقة تحمل تاريخها الكامل (history) — لا محو ولا تخفيض صامت:
التخفيض `revoke` صريح موثق كذلك. هذه الوحدة pydantic فقط بلا تبعيات أخرى.
"""

from pharma_sdl.validation.gate import (
    ValidationCard,
    ValidationState,
    card_summary,
    default_card,
    promote,
    revoke,
)

__all__ = [
    "ValidationCard",
    "ValidationState",
    "card_summary",
    "default_card",
    "promote",
    "revoke",
]
