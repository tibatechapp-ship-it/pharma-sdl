"""المقاييس التشغيلية — عدّادات صادقة من الذاكرة الحية (P3).

GET /api/v1/metrics → ما في المنصة فعلاً: تجارب بحسب الحالة وحالة الاعتماد،
مهام بحسب الحالة، الخلفية الحية (sqlite | postgres)، والمحركات المتاحة.
لا تقديرات ولا تجميل — الأرقام تُقرأ من المخازن لحظة الطلب.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from pharma_sdl import __version__
from pharma_sdl.api.auth import Role, auth_mode_label, require_role
from pharma_sdl.api.deps import app_settings, experiment_registry, job_store
from pharma_sdl.api.schemas import MetricsOut
from pharma_sdl.engines.registry import list_engines

router = APIRouter(prefix="/metrics", tags=["meta"])


@router.get("", response_model=MetricsOut, dependencies=[Depends(require_role(Role.VIEWER))])
def metrics() -> MetricsOut:
    """حجم الذاكرة العلمية والحالة التشغيلية — لحظة الطلب بلا كاش."""
    settings = app_settings()
    registry = experiment_registry()
    store = job_store()
    return MetricsOut(
        version=__version__,
        registry_backend=settings.store_backend,
        experiments_by_status=registry.stats(),
        experiments_by_validation_state=registry.validation_stats(),
        jobs_by_status=store.stats(),
        engines_available=[e.name for e in list_engines() if e.available],
        auth_mode=auth_mode_label(),
        demo_mode=settings.demo_mode,
    )


__all__ = ["router"]
