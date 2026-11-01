"""مسار الفرز الظاهري — إنشاء جولات غير متزامنة وجلب النتائج والتقارير.

POST /api/v1/screening/runs      → 202 + روابط المتابعة (طابور داخلي)
GET  /api/v1/screening/runs/{id} → حالة المهمة + النتيجة عند الاكتمال
GET  /api/v1/screening/runs/{id}/report?lang=ar → تقرير Markdown جاهز
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Response

from pharma_sdl.api.deps import app_settings, job_store
from pharma_sdl.api.schemas import RunAcceptedOut, RunStatusOut, ScreeningCreate
from pharma_sdl.curation.loader import load_ligands_csv
from pharma_sdl.engines.registry import get_engine
from pharma_sdl.models import ScreeningResult
from pharma_sdl.reporting.report import build_markdown
from pharma_sdl.screening.runner import run_screening
from pharma_sdl.targets.registry import get_target

router = APIRouter(prefix="/screening", tags=["screening"])


def _resolve_ligands(create: ScreeningCreate):
    settings = app_settings()
    if create.ligands:
        return create.ligands
    return load_ligands_csv(settings.data_dir / "demo_ligands.csv")


@router.post("/runs", response_model=RunAcceptedOut, status_code=202)
def create_run(create: ScreeningCreate) -> RunAcceptedOut:
    settings = app_settings()
    get_target(create.target_id)  # فشل سريع وصريح قبل قبول المهمة
    get_engine(create.engine)  # وكذلك المحرك — لا مهمة تُقبل بأمر مستحيل
    ligands = _resolve_ligands(create)
    if len(ligands) > settings.max_ligands_per_run:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "too_many_ligands",
                "message_ar": f"عدد الليغاندات {len(ligands)} يتجاوز سقف الطلب "
                f"({settings.max_ligands_per_run})",
                "message_en": f"{len(ligands)} ligands exceed the request cap "
                f"({settings.max_ligands_per_run})",
            },
        )
    store = job_store()
    job = store.submit(
        "screening",
        run_screening,
        create.target_id,
        ligands,
        create.engine,
        create.top_n,
        create.reject_pains,
    )
    return RunAcceptedOut(
        job_id=job.id,
        status=job.status,
        run_url=f"/api/v1/screening/runs/{job.id}",
        report_url=f"/api/v1/screening/runs/{job.id}/report",
    )


def _load_result(run_id: str) -> ScreeningResult:
    job = job_store().get(run_id)
    if job is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "run_not_found",
                "message_ar": f"لا توجد جولة بالمعرّف {run_id} (تُحذف النتائج بعد ساعة)",
                "message_en": f"No run with id {run_id} (results expire after an hour)",
            },
        )
    if job.status == "failed":
        raise HTTPException(
            status_code=500,
            detail={"code": "run_failed", "message_ar": job.error, "message_en": job.error},
        )
    result = job_store().result_of(run_id)
    if job.status != "done" or result is None:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "run_in_progress",
                "message_ar": f"الجولة {run_id} لا تزال {job.status} — أعد المحاولة بعد لحظات",
                "message_en": f"Run {run_id} is still {job.status} — retry shortly",
            },
        )
    return result


@router.get("/runs/{run_id}", response_model=RunStatusOut)
def run_status(run_id: str) -> RunStatusOut:
    job = job_store().get(run_id)
    if job is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "run_not_found",
                "message_ar": f"لا توجد جولة بالمعرّف {run_id}",
                "message_en": f"No run with id {run_id}",
            },
        )
    result: ScreeningResult | None = None
    if job.status == "done":
        raw = job_store().result_of(run_id)
        if isinstance(raw, ScreeningResult):
            result = raw
    return RunStatusOut(
        job_id=job.id, kind=job.kind, status=job.status, error=job.error, result=result
    )


@router.get("/runs/{run_id}/report")
def run_report(
    run_id: str,
    lang: str = Query("ar", pattern="^(ar|en)$"),
) -> Response:
    result = _load_result(run_id)
    markdown = build_markdown(result, lang=lang)
    return Response(
        content=markdown,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'inline; filename="screening-{run_id}.md"'},
    )
