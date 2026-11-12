"""مسارات Ryko — العقل العلمي (الكتالوج + الحساب بالإيصال).

نفس البوابة، نفس المصادقة وحد المعدل. كل ناتج إيصال قابلة للتحقق دون
اتصال (بصمة SHA-256 حتمية). رفض المدخل 422، وعملية غير معروفة 404 —
الرسالة ثنائية اللغة في الحالتي.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from pharma_sdl.api.schemas import RykoCatalogOut, RykoComputeIn, RykoReceiptOut
from pharma_sdl.ryko import get_engine
from pharma_sdl.ryko.errors import RykoInputError, RykoUnknownOpError

router = APIRouter(tags=["ryko"])


@router.get("/ryko/catalog", response_model=RykoCatalogOut)
def ryko_catalog() -> RykoCatalogOut:
    """الكتالوج المعلن — الواجهة العلمية قبل أي حساب."""
    engine = get_engine()
    stats = engine.stats()
    return RykoCatalogOut(
        version=stats["version"],
        modules=stats["modules"],
        operations=stats["operations"],
        catalog=engine.catalog(),
    )


@router.post("/ryko/compute", response_model=RykoReceiptOut)
def ryko_compute(body: RykoComputeIn) -> RykoReceiptOut:
    """حساب عملية — الناتج إيصال: قيمة + معادلة + مصدر + افتراضات + بصمة."""
    try:
        receipt = get_engine().compute(body.module, body.op, **body.inputs)
    except RykoInputError as exc:
        raise HTTPException(status_code=422, detail=exc.as_dict()) from exc
    except RykoUnknownOpError as exc:
        raise HTTPException(status_code=404, detail=exc.as_dict()) from exc
    return RykoReceiptOut(**receipt.to_dict())
