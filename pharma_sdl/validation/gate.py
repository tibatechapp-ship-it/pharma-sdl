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

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from pharma_sdl.errors import ValidationError


class ValidationState(str, Enum):
    """حالات الاعتماد العلمي الأربع — ترتيبها رقماً صارماً."""

    UNVALIDATED = "UNVALIDATED"
    COMPUTATIONALLY_VALIDATED = "COMPUTATIONALLY_VALIDATED"
    EXPERIMENTALLY_SUPPORTED = "EXPERIMENTALLY_SUPPORTED"
    INDEPENDENTLY_REPRODUCED = "INDEPENDENTLY_REPRODUCED"

    @property
    def rank(self) -> int:
        return _RANK[self]

    @property
    def label_ar(self) -> str:
        return _LABELS_AR[self]

    @property
    def label_en(self) -> str:
        return _LABELS_EN[self]


_RANK: dict[ValidationState, int] = {
    ValidationState.UNVALIDATED: 0,
    ValidationState.COMPUTATIONALLY_VALIDATED: 1,
    ValidationState.EXPERIMENTALLY_SUPPORTED: 2,
    ValidationState.INDEPENDENTLY_REPRODUCED: 3,
}

_LABELS_AR = {
    ValidationState.UNVALIDATED: "نتيجة أولية غير متحققة علمياً",
    ValidationState.COMPUTATIONALLY_VALIDATED: "متحقق حسابياً (فحوص محددة)",
    ValidationState.EXPERIMENTALLY_SUPPORTED: "مدعوم بأدلة تجريبية موثقة",
    ValidationState.INDEPENDENTLY_REPRODUCED: "مُعاد إنتاجه مستقلاً وفق بروتوكول",
}
_LABELS_EN = {
    ValidationState.UNVALIDATED: "Preliminary, not scientifically validated",
    ValidationState.COMPUTATIONALLY_VALIDATED: "Computationally validated (declared checks)",
    ValidationState.EXPERIMENTALLY_SUPPORTED: "Supported by documented experimental evidence",
    ValidationState.INDEPENDENTLY_REPRODUCED: "Independently reproduced per protocol",
}


class ValidationCard(BaseModel):
    """بطاقة اعتماد نتيجة — من يتكلم هذه الأرقام وماذا يجوز استنتاجه."""

    state: ValidationState = ValidationState.UNVALIDATED
    subject: str  # ماذا تُعتمد: "screening_run:<id>" أو "ligand:<inchikey>"
    result_id: str | None = None
    engine: str | None = None
    method: str | None = None
    data_version: str | None = None  # بصمة المدخلات (sha256 مقتطع)
    code_version: str | None = None  # git commit القصير
    checks: list[str] = Field(default_factory=list)  # ماذا فُحص فعلاً
    limits: str | None = None  # حدود الاستنتاج الصريحة
    reproducible_command: str | None = None
    actor: str = "system"  # من نفّذ آخر انتقال
    reason: str | None = None  # سبب آخر انتقال
    updated_at: str | None = None
    history: list[dict[str, str]] = Field(default_factory=list)


def default_card(
    subject: str,
    result_id: str | None = None,
    engine: str | None = None,
    method: str | None = None,
    data_version: str | None = None,
    code_version: str | None = None,
    limits: str | None = None,
    reproducible_command: str | None = None,
) -> ValidationCard:
    """بطاقة جديدة — كل مخرج يبدأ UNVALIDATED بلا استثناء (لا استنتاج تلقائي)."""
    return ValidationCard(
        state=ValidationState.UNVALIDATED,
        subject=subject,
        result_id=result_id,
        engine=engine,
        method=method,
        data_version=data_version,
        code_version=code_version,
        limits=limits,
        reproducible_command=reproducible_command,
        checks=[],
    )


def promote(
    card: ValidationCard,
    to: ValidationState,
    reason: str,
    actor: str,
    *,
    checks: list[str] | None = None,
    assay_ref: str | None = None,
    protocol: str | None = None,
    independent_lab: str | None = None,
) -> ValidationCard:
    """ترقية خطوة واحدة صعوداً — صريحة، موثقة، وبشروط إلزامية للحالات العليا.

    - لا قفزات: rank(to) يجب أن يساوي rank(الحالي) + 1.
    - reason إلزامي غير فارغ — الترقية بلا سبب ليست ترقية.
    - EXPERIMENTALLY_SUPPORTED يتطلب مرجع فحص تجريبي موثق (assay_ref).
    - INDEPENDENTLY_REPRODUCED يتطلب بروتوكولاً + جهة مستقلة.
    """
    if not reason or not reason.strip():
        raise ValidationError(
            "الترقية تتطلب سبباً موثقاً — لا انتقال بلا مبرر",
            "Promotion requires a documented reason — no unexplained transition",
        )
    if to.rank != card.state.rank + 1:
        raise ValidationError(
            f"انتقال غير مشروع: {card.state.value} → {to.value} — "
            "الترقية خطوة واحدة صعوداً فقط، ولا ترقية تلقائية أبداً",
            f"Illegal transition {card.state.value} → {to.value}: "
            "single upward step only, never automatic",
        )
    if to is ValidationState.EXPERIMENTALLY_SUPPORTED and not (assay_ref and assay_ref.strip()):
        raise ValidationError(
            "الحالة التجريبية تتطلب مرجع فحص موثقاً (assay_ref)",
            "EXPERIMENTALLY_SUPPORTED requires a documented assay reference",
        )
    if to is ValidationState.INDEPENDENTLY_REPRODUCED and not (
        protocol and protocol.strip() and independent_lab and independent_lab.strip()
    ):
        raise ValidationError(
            "إعادة الإنتاج المستقلة تتطلب بروتوكولاً موثقاً وجهة مستقلة",
            "INDEPENDENTLY_REPRODUCED requires a protocol and an independent lab",
        )

    from pharma_sdl.models import utcnow_iso  # استيراد موضعي — كسر الدوران

    new_checks = list(card.checks) + (checks or [])
    entry = {
        "from": card.state.value,
        "to": to.value,
        "actor": actor,
        "reason": reason.strip(),
        "at": utcnow_iso(),
    }
    if assay_ref:
        entry["assay_ref"] = assay_ref.strip()
    if protocol:
        entry["protocol"] = protocol.strip()
    if independent_lab:
        entry["independent_lab"] = independent_lab.strip()
    return card.model_copy(
        update={
            "state": to,
            "actor": actor,
            "reason": reason.strip(),
            "updated_at": entry["at"],
            "checks": new_checks,
            "history": card.history + [entry],
        }
    )


def revoke(card: ValidationCard, reason: str, actor: str) -> ValidationCard:
    """تخفيض صريح إلى UNVALIDATED — يوثَّق ولا يُحى أبداً (اكتشاف خطأ مثلاً)."""
    if not reason or not reason.strip():
        raise ValidationError(
            "التخفيض يتطلب سبباً موثقاً", "Revocation requires a documented reason"
        )
    from pharma_sdl.models import utcnow_iso

    entry = {
        "from": card.state.value,
        "to": ValidationState.UNVALIDATED.value,
        "actor": actor,
        "reason": reason.strip(),
        "at": utcnow_iso(),
    }
    return card.model_copy(
        update={
            "state": ValidationState.UNVALIDATED,
            "actor": actor,
            "reason": reason.strip(),
            "updated_at": entry["at"],
            "history": card.history + [entry],
        }
    )


def card_summary(card: ValidationCard, lang: str = "ar") -> str:
    """سطر حالة جاهز للتقارير والواجهة — الحالة + حدودها."""
    if lang == "en":
        label = card.state.label_en
        limits = card.limits or "See the model evaluation report for validity bounds."
        return f"**{label}** — {limits}"
    label = card.state.label_ar
    limits = card.limits or "انظر تقرير التقييم المستقل لحدود الصلاحية."
    return f"**{label}** — {limits}"


__all__ = [
    "ValidationCard",
    "ValidationState",
    "card_summary",
    "default_card",
    "promote",
    "revoke",
]
