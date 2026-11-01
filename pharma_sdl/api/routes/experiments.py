"""مسار التجارب والاعتماد — الذاكرة العلمية تصبح API-First (P2، تقييم #4/#5).

القراءة (viewer): قائمة التجارب، سجل كامل، سلسلة الأسلاف، بطاقة الاعتماد.
الترقية والتخفيض (admin حصراً): تمر عبر gate.promote/gate.revoke — نفس
العقد البشري الصارم: خطوة واحدة صعوداً، سبب ومُجيز موثقان، ومرفقات
إلزامية للحالتين العليا. **لا مسار API يرقّى آلياً أبداً** — والبطاقة
الكاملة تُحفظ في السجل فـ«لماذا رُقّيت؟» يُجاب منه.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from pharma_sdl.api.auth import Role, require_role
from pharma_sdl.api.deps import experiment_registry
from pharma_sdl.api.schemas import ValidationRevokeIn, ValidationTransitionIn
from pharma_sdl.experiments.registry import ExperimentRecord, ExperimentRegistry
from pharma_sdl.validation.gate import (
    ValidationCard,
    promote,
    revoke,
)

router = APIRouter(
    prefix="/experiments", tags=["experiments"], dependencies=[Depends(require_role(Role.VIEWER))]
)


def _load(registry: ExperimentRegistry, experiment_id: str) -> ExperimentRecord:
    record = registry.get(experiment_id)
    if record is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "experiment_not_found",
                "message_ar": f"لا توجد تجربة بالمعرّف {experiment_id}",
                "message_en": f"No experiment with id {experiment_id}",
            },
        )
    return record


@router.get("", response_model=list[ExperimentRecord])
def list_experiments(
    status: str | None = Query(None, pattern="^(running|completed|failed)$"),
    limit: int = Query(20, ge=1, le=100),
) -> list[ExperimentRecord]:
    """أحدث التجارب من السجل الدائم — فلترة اختيارية بالحالة."""
    return experiment_registry().latest(limit=limit, status=status)


@router.get("/{experiment_id}", response_model=ExperimentRecord)
def get_experiment(experiment_id: str) -> ExperimentRecord:
    """تجربة كاملة واحدة — فرضيتها وإعداداتها ونتائجها ودرسها."""
    return _load(experiment_registry(), experiment_id)


@router.get("/{experiment_id}/lineage", response_model=list[ExperimentRecord])
def experiment_lineage(experiment_id: str) -> list[ExperimentRecord]:
    """سلسلة الأسلاف من الجذر إلى هذه التجربة — ذاكرة الحلقة كما كُتبت."""
    registry = experiment_registry()
    _load(registry, experiment_id)
    return registry.lineage(experiment_id)


@router.get("/{experiment_id}/validation", response_model=ValidationCard)
def experiment_validation(experiment_id: str) -> ValidationCard:
    """بطاقة الاعتماد الحالية — الحالة والتاريخ والمرفقات إن وُجدت."""
    registry = experiment_registry()
    _load(registry, experiment_id)
    return registry.validation_card_of(experiment_id)


@router.post(
    "/{experiment_id}/validation/promote",
    response_model=ValidationCard,
    dependencies=[Depends(require_role(Role.ADMIN))],
)
def promote_validation(experiment_id: str, body: ValidationTransitionIn) -> ValidationCard:
    """ترقية بشرية صريحة خطوة واحدة — admin حصراً، سبب ومُجيز إلزاميان.

    أخطاء البوابة (قفزة غير مشروعة 422، سبب مفقود 422) تصل كما هي عبر
    معالج PlatformError العام — رسائلها عربية/إنجليزية موحّدة.
    """
    registry = experiment_registry()
    _load(registry, experiment_id)
    card = registry.validation_card_of(experiment_id)
    promoted = promote(
        card,
        to=body.to,
        reason=body.reason,
        actor=body.actor,
        checks=body.checks,
        assay_ref=body.assay_ref,
        protocol=body.protocol,
        independent_lab=body.independent_lab,
    )
    registry.save_validation_card(experiment_id, promoted)
    return promoted


@router.post(
    "/{experiment_id}/validation/revoke",
    response_model=ValidationCard,
    dependencies=[Depends(require_role(Role.ADMIN))],
)
def revoke_validation(experiment_id: str, body: ValidationRevokeIn) -> ValidationCard:
    """تخفيض صريح إلى UNVALIDATED — موثق بلا محو (اكتشاف خطأ مثلاً)."""
    registry = experiment_registry()
    _load(registry, experiment_id)
    card = registry.validation_card_of(experiment_id)
    revoked = revoke(card, reason=body.reason, actor=body.actor)
    registry.save_validation_card(experiment_id, revoked)
    return revoked


__all__ = ["router"]
