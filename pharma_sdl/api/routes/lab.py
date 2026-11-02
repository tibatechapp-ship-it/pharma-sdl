"""مسار المختبر — نفس الواجهة فوق أي خلفية (P8): محاكاة افتراضياً، LIMS حين يُضبط.

الصدق التشغيلي: `GET /lab/backend` يعلن أي خلفية تعمل الآن فعلاً — لا
خمّاس. `POST /lab/batches` هو الشكل الطبيعي للفيزياء الحقيقية:
تقديم ← تذكرة ← استطلاع حتى حالة نهائية (ADR-0013).

ملاحظة صدق صريحة: مع المحاكاة تُحفظ حالة الدفعات في ذاكرة العملية
(مثيل واحد لكل إعدادات) — كافية للعرض والاختبار؛ أما الحالة الإنتاجية
فهي عند البوابة الحقيقية نفسها، فلا يعتمد الاستطلاع على ذاكرة المنصة.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from pharma_sdl.api.auth import Role, require_role
from pharma_sdl.api.schemas import (
    AssayCreate,
    AssayOut,
    LabBackendOut,
    LabBatchCreate,
    LabBatchOut,
    LabBatchPollOut,
)
from pharma_sdl.config import get_settings
from pharma_sdl.lab import make_lab_client
from pharma_sdl.lab.interface import AssayRequest
from pharma_sdl.lab.lims import HttpLimsLab
from pharma_sdl.lab.simulation import SimulatedFretLab

router = APIRouter(prefix="/lab", tags=["lab"])

#: مثيل واحد لكل إعدادات معروفة — حفظ حالة الدفعات بين الطلبات لا يضيع.
_lab_pair: tuple[object, SimulatedFretLab | HttpLimsLab] | None = None


def _get_lab() -> SimulatedFretLab | HttpLimsLab:
    global _lab_pair
    settings = get_settings()
    if _lab_pair is None or _lab_pair[0] is not settings:
        _lab_pair = (settings, make_lab_client(settings))
    return _lab_pair[1]


def _lims_configured() -> bool:
    return bool(get_settings().lims_url)


@router.get(
    "/backend",
    response_model=LabBackendOut,
    dependencies=[Depends(require_role(Role.VIEWER))],
)
def lab_backend() -> LabBackendOut:
    lab = _get_lab()
    if _lims_configured():
        note_ar = (
            "الخلفية الحالية بوابة LIMS حقيقية عبر عقد REST (ADR-0013) — "
            "نتائجها simulated=false وتبقى UNVALIDATED حتى ترقية بشرية موثقة."
        )
        note_en = (
            "Active backend is a real LIMS gateway over the REST contract (ADR-0013) — "
            "results carry simulated=false and stay UNVALIDATED until documented human promotion."
        )
    else:
        note_ar = (
            "الخلفية الحالية محاكاة FRET برمجية — لا قياس فيزيائياً هنا؛ "
            "ضبط PHARMA_SDL_LIMS_URL يبدّل نفس الواجهة إلى بوابة حقيقية."
        )
        note_en = (
            "Active backend is the simulated FRET lab — nothing physical here; "
            "set PHARMA_SDL_LIMS_URL to switch this same interface to a real gateway."
        )
    return LabBackendOut(
        adapter=lab.name,
        simulated=not _lims_configured(),
        lims_configured=_lims_configured(),
        note_ar=note_ar,
        note_en=note_en,
    )


@router.post(
    "/batches",
    response_model=LabBatchOut,
    status_code=202,
    dependencies=[Depends(require_role(Role.SCIENTIST))],
)
def create_batch(create: LabBatchCreate) -> LabBatchOut:
    lab = _get_lab()
    ticket = lab.submit_batch(
        [AssayRequest(smiles=a.smiles, dg_kcal=a.dg_kcal) for a in create.assays],
        idempotency_key=create.idempotency_key,
    )
    return LabBatchOut(
        batch_id=ticket.batch_id,
        adapter=ticket.adapter,
        n_assays=ticket.n_assays,
        status=ticket.status,
        simulated=not _lims_configured(),
    )


@router.get(
    "/batches/{batch_id}",
    response_model=LabBatchPollOut,
    dependencies=[Depends(require_role(Role.VIEWER))],
)
def poll_batch(batch_id: str) -> LabBatchPollOut:
    lab = _get_lab()
    poll = lab.poll_batch(batch_id)
    return LabBatchPollOut(
        batch_id=poll.batch_id,
        adapter=poll.adapter,
        status=poll.status,
        results=[AssayOut(**r.model_dump()) for r in poll.results] if poll.results else None,
        error_ar=poll.error_ar,
        error_en=poll.error_en,
    )


@router.post(
    "/assays", response_model=AssayOut, dependencies=[Depends(require_role(Role.SCIENTIST))]
)
def create_assay(create: AssayCreate) -> AssayOut:
    """فحص فردي متزامن — التوافق التاريخي حرفياً؛ الخلفية عبر المصنع نفسه."""
    lab = _get_lab()
    result = lab.run_assay(AssayRequest(smiles=create.smiles, dg_kcal=create.dg_kcal))
    return AssayOut(**result.model_dump())
