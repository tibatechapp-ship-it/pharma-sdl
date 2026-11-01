"""مسار الحلقة المغلقة كخدمة — الفلسفة تصبح نقطة نهاية (P3).

POST /api/v1/loop/runs       → 202 مهمة دائمة: ثلاث جولات (خط أساس ← استكشاف ← توظيف)
GET  /api/v1/loop/runs/{id}  → حالة المهمة، وعند الاكتمال الجولات الثلاث متسلسلة

الصدق بنيوياً:
- كل جولة تُكتب في سجل المنصة نفسه (sqlite أو postgres وفق الإعدادات) —
  الذاكرة واحدة، وسلسلة الأسلاف تُقرأ من مسار التجارب نفسه.
- كل النتائج تبقى UNVALIDATED — لا ترقية آلية أبداً (بوابة P1 بشرية حصراً).
- وضع العرض: المحرك مقفول على القائمة المسموحة، وسقف top_n مفروض في مسار
  التنفيذ لا في الوثائق فقط — عدالة الحساب المشترك كما في P2.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from pharma_sdl.api.auth import Role, require_role
from pharma_sdl.api.demo import demo_caps, demo_engine_allowed
from pharma_sdl.api.deps import app_settings, experiment_registry, job_store
from pharma_sdl.api.schemas import LoopCreate, LoopRunOut
from pharma_sdl.engines.registry import get_engine
from pharma_sdl.experiments.registry import ExperimentRecord
from pharma_sdl.loop.closed_loop import run_closed_loop
from pharma_sdl.targets.registry import get_target

router = APIRouter(prefix="/loop", tags=["loop"])

_NOTE_AR = (
    "ثلاث جولات متسلسلة بالأسلاف — كل النتائج UNVALIDATED حتى ترقية بشرية موثقة "
    "عبر بوابة الاعتماد، والمحرك وطريقة كل نتيجة معلنان في السجل."
)
_NOTE_EN = (
    "Three chained rounds — every result stays UNVALIDATED until a documented human "
    "promotion via the validation gate; engine and method are recorded per result."
)


@router.post(
    "/runs",
    response_model=LoopRunOut,
    status_code=202,
    dependencies=[Depends(require_role(Role.SCIENTIST))],
)
def create_loop_run(create: LoopCreate) -> LoopRunOut:
    """إطلاق حلقة مغلقة كمهمة دائمة — تُكتب جولاتها في سجل المنصة نفسه."""
    settings = app_settings()
    get_target(create.target_id)  # فشل سريع وصريح قبل قبول المهمة
    engine_name = create.engine or settings.default_engine
    get_engine(engine_name)  # لا مهمة تُقبل بأمر مستحيل
    if not demo_engine_allowed(create.engine):
        raise HTTPException(
            status_code=422,
            detail={
                "code": "engine_not_allowed_demo",
                "message_ar": f"المحرك {engine_name} غير متاح في وضع العرض العام — "
                f"المسموح: {settings.demo_allowed_engines}",
                "message_en": f"Engine {engine_name} is not available in public demo mode — "
                f"allowed: {settings.demo_allowed_engines}",
            },
        )
    # السقف مفروض في مسار التنفيذ: وضع العرض يفرض سقفه الأدنى — العدالة قبل الكرم.
    top_cap = demo_caps()[1] if settings.demo_mode else settings.default_top_n
    top_n = min(create.top_n, top_cap)

    registry = experiment_registry()

    def _job() -> dict:
        records = run_closed_loop(
            target_id=create.target_id,
            top_n=top_n,
            engine_name=engine_name,
            registry=registry,
        )
        return {
            "experiments": [r.model_dump(mode="json") for r in records],
            "round_count": len(records),
            "target_id": create.target_id,
            "engine": engine_name,
        }

    job = job_store().submit("closed_loop", _job)
    return LoopRunOut(
        job_id=job.id,
        kind=job.kind,
        status=job.status,
        note_ar=_NOTE_AR,
        note_en=_NOTE_EN,
    )


@router.get(
    "/runs/{job_id}",
    response_model=LoopRunOut,
    dependencies=[Depends(require_role(Role.VIEWER))],
)
def loop_status(job_id: str) -> LoopRunOut:
    """حالة الحلقة — وعند الاكتمال: الجولات الثلاث كما كُتبت في السجل الدائم."""
    store = job_store()
    job = store.get(job_id)
    if job is None or job.kind != "closed_loop":
        raise HTTPException(
            status_code=404,
            detail={
                "code": "loop_run_not_found",
                "message_ar": f"لا توجد حلقة بالمعرّف {job_id}",
                "message_en": f"No closed-loop run with id {job_id}",
            },
        )
    out = LoopRunOut(job_id=job.id, kind=job.kind, status=job.status, error=job.error)
    if job.status == "done":
        result = store.result_of(job_id) or {}
        out.rounds = [ExperimentRecord.model_validate(r) for r in result.get("experiments", [])]
        out.round_count = len(out.rounds)
        out.note_ar = _NOTE_AR
        out.note_en = _NOTE_EN
    return out


__all__ = ["router"]
