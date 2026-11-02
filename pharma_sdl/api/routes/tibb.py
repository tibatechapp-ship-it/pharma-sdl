"""مكتبة الطب النبوي كخدمة — حزمتا P5+P6 عبر الـAPI.

GET  /api/v1/tibb/library         → المكتبة كاملة: مركبات + إجراءات + توثيق مزدوج
GET  /api/v1/tibb/targets         → الأهداف المُدرّبة (Mpro + AChE + EGFR) — P6
POST /api/v1/tibb/screen          → 202 مهمة دائمة: فرز المكتبة على هدف مُدرّب
                                    (جسم اختياري {"target_id": …} — الافتراضي Mpro)
GET  /api/v1/tibb/screen/{job_id} → حالة الفرز والتقرير عند الاكتمال

الصدق بنيوياً:
- المكتبة للقراءة حصراً — لا إضافة من المستخدم في الخادم؛ المحتوى مُدقَّق
  في الاختبارات (SMILES وصيغ ودِرَجات أحاديث) وتتغير بمراجعة مُوثَّقة فقط.
- الفرز على نموذج الإنتاج المُدرّب على هدف من TARGETS حصراً — هدف غير
  مُدرّب ← 422 برسالة ثنائية اللغة؛ وحد MIN_DATASET_ROWS مفروض في النواة.
- خط predicted_potency حصراً، وكل صف UNVALIDATED، ولا درجة تحاليم هنا إطلاقاً.
- الإجراءات (حجامة/كي) تظهر في المكتبة للتوثيق ولا تدخل الفرز بنيوياً.
- وضع العرض: سقف أشجار أقل معلن هنا — مفروض في مسار التنفيذ.
"""

from __future__ import annotations

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException

from pharma_sdl.api.auth import Role, require_role
from pharma_sdl.api.deps import app_settings, experiment_registry, job_store
from pharma_sdl.api.schemas import (
    LibraryOut,
    ScreenRequest,
    ScreenRunOut,
    TibbScreenReportOut,
    TibbTargetOut,
    TibbTargetsOut,
)
from pharma_sdl.prophetic import (
    COMPOUNDS,
    DISCLAIMER_AR,
    DISCLAIMER_EN,
    PROCEDURES,
    SOURCE_NOTES,
    TARGETS,
    TIER_LABELS,
    library_summary,
    run_library_screen,
)

router = APIRouter(prefix="/tibb", tags=["tibb-nabawi"])

# سقف وضع العرض — المكتبة صغيرة أصلاً (17 مركباً) فالسقف على الأشجار
_DEMO_SCREEN_CAPS = {"n_estimators": 60}

_NOTE_AR = (
    "فرز مكتبة الطب النبوي على نموذج إنتاج مُدرَّب: خط predicted_potency "
    "حصراً، كل صف UNVALIDATED، والتوثيق التراثي (بدرجته المتخَرَّجة) لا "
    "يُنتج درجات ولا يُعد دليلاً على فعالية."
)
_NOTE_EN = (
    "Prophetic-medicine library screen against a trained production model: "
    "predicted_potency lane only, every row UNVALIDATED; the graded heritage "
    "documentation yields no scores and is no efficacy evidence."
)

_TARGETS_NOTE_AR = (
    "الأهداف المُدرَّبة في المنصة — كلها تُفرز بنفس الكود والمسار نفسه "
    "(predicted_potency / UNVALIDATED)؛ الهدف الجديد = بيانات مُخرَّجة + مواصفة."
)
_TARGETS_NOTE_EN = (
    "Trained targets of the platform — all screened by the same code and lane "
    "(predicted_potency / UNVALIDATED); a new target = curated data + one spec."
)


def _target_out(tid: str) -> TibbTargetOut:
    """مواصفة هدف واحدة كصف API — مع حجم بياناتها الفعلي."""
    spec = TARGETS[tid]
    n = len(pd.read_csv(spec.dataset_path))
    return TibbTargetOut(
        target_id=spec.target_id,
        name_ar=spec.name_ar,
        name_en=spec.name_en,
        dataset=f"data/{spec.dataset}",
        n_dataset=n,
        description_ar=spec.description_ar,
        description_en=spec.description_en,
    )


@router.get(
    "/library",
    response_model=LibraryOut,
    dependencies=[Depends(require_role(Role.VIEWER))],
)
def get_library() -> LibraryOut:
    """المكتبة كاملة — 17 مركباً + إجرائان بتوثيقهما المزدوج المُدقَّق."""
    s = library_summary()
    return LibraryOut(
        compounds=s["n_compounds"],
        procedures=s["n_procedures"],
        by_source=s["by_source"],
        by_evidence_tier=s["by_evidence_tier"],
        hadith_grades=s["hadith_grades"],
        items=[
            {
                "name_ar": c.name_ar,
                "name_en": c.name_en,
                "smiles": c.smiles,
                "formula": c.formula,
                "molecular_weight": c.molecular_weight,
                "pubchem_cid": c.pubchem_cid,
                "source": c.source,
                "evidence_tier": c.evidence_tier,
                "evidence_tier_label": TIER_LABELS[c.evidence_tier],
                "evidence_note": c.evidence_note,
                "hadith": c.source_hadith.model_dump(),
            }
            for c in COMPOUNDS
        ],
        procedure_items=[p.model_dump() for p in PROCEDURES],
        source_notes=SOURCE_NOTES,
        disclaimer_ar=s["disclaimer_ar"],
        disclaimer_en=s["disclaimer_en"],
    )


@router.get(
    "/targets",
    response_model=TibbTargetsOut,
    dependencies=[Depends(require_role(Role.VIEWER))],
)
def get_targets() -> TibbTargetsOut:
    """الأهداف المُدرَّبة — بنفس قواعد التخريج وحجم Mpro المرجعي."""
    return TibbTargetsOut(
        targets=[_target_out(t) for t in sorted(TARGETS)],
        note_ar=_TARGETS_NOTE_AR,
        note_en=_TARGETS_NOTE_EN,
    )


@router.post(
    "/screen",
    response_model=ScreenRunOut,
    status_code=202,
    dependencies=[Depends(require_role(Role.SCIENTIST))],
)
def create_screen(req: ScreenRequest | None = None) -> ScreenRunOut:
    """إطلاق فرز المكتبة كمهمة دائمة — على الهدف المطلوب أو Mpro الافتراضي."""
    requested = req.target_id if req else None
    if requested is not None and requested not in TARGETS:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "tibb_target_not_trained",
                "message_ar": (
                    f"هدف غير مُدرَّب: {requested} — المُدرَّب: "
                    f"{', '.join(sorted(TARGETS))}"
                ),
                "message_en": (
                    f"Target not trained: {requested} — trained: "
                    f"{', '.join(sorted(TARGETS))}"
                ),
            },
        )
    spec = TARGETS[requested] if requested else TARGETS["CHEMBL4523582"]
    settings = app_settings()
    n_estimators = 300
    if settings.demo_mode:
        n_estimators = min(n_estimators, _DEMO_SCREEN_CAPS["n_estimators"])
    registry = experiment_registry()

    def _job() -> dict:
        report = run_library_screen(
            target_id=spec.target_id,
            n_estimators=n_estimators,
            seed=0,
            registry=registry,
        )
        return {"report": report.model_dump(mode="json")}

    job = job_store().submit("tibb_screen", _job)
    return ScreenRunOut(
        job_id=job.id,
        kind=job.kind,
        status=job.status,
        note_ar=f"{spec.name_ar}: {_NOTE_AR} {DISCLAIMER_AR}",
        note_en=f"{spec.name_en}: {_NOTE_EN} {DISCLAIMER_EN}",
    )


@router.get(
    "/screen/{job_id}",
    response_model=ScreenRunOut,
    dependencies=[Depends(require_role(Role.VIEWER))],
)
def screen_status(job_id: str) -> ScreenRunOut:
    """حالة الفرز — وعند الاكتمال: التقرير كاملاً كما حُسب لحظة الإنجاز."""
    store = job_store()
    job = store.get(job_id)
    if job is None or job.kind != "tibb_screen":
        raise HTTPException(
            status_code=404,
            detail={
                "code": "tibb_screen_not_found",
                "message_ar": f"لا يوجد فرز للمكتبة النبوية بالمعرّف {job_id}",
                "message_en": f"No Prophetic-library screen with id {job_id}",
            },
        )
    out = ScreenRunOut(
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
            out.report = TibbScreenReportOut.model_validate(result["report"])
    return out


__all__ = ["router"]
