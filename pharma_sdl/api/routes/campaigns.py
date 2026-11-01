"""حملات التعلم النشط كخدمة — حزمة Q4 عبر الـAPI (P4).

POST /api/v1/loop/campaigns       → 202 مهمة دائمة: حملة تعلم N جولات
GET  /api/v1/loop/campaigns/{id}  → حالة المهمة، وعند الاكتمال التقرير كاملاً

الصدق بنيوياً:
- الحملة تُكتب جولاتها في سجل المنصة نفسه (sqlite أو postgres وفق الإعدادات)
  بسلسلة أسلاف — ذاكرة الحلقة واحدة لا نسختان.
- مجموعة البيانات ثابتة (data/mpro_sample.csv المجمَّعة مع المنصة) — لا مسارات
  من المستخدم في الخادم، ولا بيانات خارجية بلا توثيق.
- وضع العرض: سقوف حسابية أدنى معلنة هنا (جولات/دفعة/أشجار) — عدالة الحساب
  المشترك كما في P2/P3، مفروضة في مسار التنفيذ لا في الوثائق فقط.
- كل النتائج UNVALIDATED والأوراكل in-silico معلن في كل تقرير.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from pharma_sdl.api.auth import Role, require_role
from pharma_sdl.api.deps import app_settings, experiment_registry, job_store
from pharma_sdl.api.schemas import CampaignCreate, CampaignRunOut
from pharma_sdl.campaign import (
    DISCLAIMER_AR,
    DISCLAIMER_EN,
    CampaignReport,
    run_campaign,
)

router = APIRouter(prefix="/loop", tags=["learning"])

# سقوف وضع العرض — أقل من حدود النموذج الصغيرة؛ حساب مشترك عادل لا كرم بالغائب
_DEMO_CAMPAIGN_CAPS = {
    "rounds": 3,
    "batch_size": 8,
    "initial_labeled": 60,
    "n_estimators": 60,
}

_NOTE_AR = (
    "حملة تعلم نشط: النموذج يُحدَّث من نتائج كل جولة، والأوراكل يكشف قياسات "
    "pChEMBL من مجموعة البيانات (in-silico). كل النتائج UNVALIDATED، "
    "والقياس الصادق على اختبار scaffold ثابت لا تلمسه الاختيارات."
)
_NOTE_EN = (
    "Active-learning campaign: the model updates from every round's results, and "
    "the in-silico oracle reveals dataset pChEMBL values. All results stay "
    "UNVALIDATED; honest metrics are measured on a fixed scaffold holdout the "
    "selection never touches."
)


def _apply_demo_caps(create: CampaignCreate) -> CampaignCreate:
    """سقوف وضع العرض مفروضة في مسار التنفيذ — لا اعتماد على انضباط المستدعِ."""
    settings = app_settings()
    if not settings.demo_mode:
        return create
    return CampaignCreate(
        strategy=create.strategy,
        rounds=min(create.rounds, _DEMO_CAMPAIGN_CAPS["rounds"]),
        batch_size=min(create.batch_size, _DEMO_CAMPAIGN_CAPS["batch_size"]),
        initial_labeled=min(
            create.initial_labeled, _DEMO_CAMPAIGN_CAPS["initial_labeled"]
        ),
        n_estimators=min(create.n_estimators, _DEMO_CAMPAIGN_CAPS["n_estimators"]),
        kappa=create.kappa,
    )


@router.post(
    "/campaigns",
    response_model=CampaignRunOut,
    status_code=202,
    dependencies=[Depends(require_role(Role.SCIENTIST))],
)
def create_campaign(create: CampaignCreate) -> CampaignRunOut:
    """إطلاق حملة تعلم نشط كمهمة دائمة — جولاتها في سجل المنصة نفسه."""
    create = _apply_demo_caps(create)
    registry = experiment_registry()

    def _job() -> dict:
        report = run_campaign(
            strategy=create.strategy,
            seed=0,
            initial_labeled=create.initial_labeled,
            batch_size=create.batch_size,
            rounds=create.rounds,
            n_estimators=create.n_estimators,
            kappa=create.kappa,
            registry=registry,
        )
        return {"report": report.model_dump(mode="json")}

    job = job_store().submit("learning_campaign", _job)
    return CampaignRunOut(
        job_id=job.id,
        kind=job.kind,
        status=job.status,
        note_ar=_NOTE_AR,
        note_en=_NOTE_EN,
    )


@router.get(
    "/campaigns/{job_id}",
    response_model=CampaignRunOut,
    dependencies=[Depends(require_role(Role.VIEWER))],
)
def campaign_status(job_id: str) -> CampaignRunOut:
    """حالة الحملة — وعند الاكتمال: التقرير الكامل كما حُسب لحظة الإنجاز."""
    store = job_store()
    job = store.get(job_id)
    if job is None or job.kind != "learning_campaign":
        raise HTTPException(
            status_code=404,
            detail={
                "code": "campaign_not_found",
                "message_ar": f"لا توجد حملة تعلم بالمعرّف {job_id}",
                "message_en": f"No learning campaign with id {job_id}",
            },
        )
    out = CampaignRunOut(
        job_id=job.id,
        kind=job.kind,
        status=job.status,
        error=job.error,
        note_ar=_NOTE_AR,
        note_en=_NOTE_EN,
    )
    if job.status == "done":
        result = store.result_of(job_id) or {}
        if result.get("report"):
            out.report = CampaignReport.model_validate(result["report"])
            out.note_ar = f"{_NOTE_AR} {DISCLAIMER_AR}"
            out.note_en = f"{_NOTE_EN} {DISCLAIMER_EN}"
    return out


__all__ = ["router"]
