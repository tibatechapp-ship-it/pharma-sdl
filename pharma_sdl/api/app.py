"""بوابة الـAPI — FastAPI بوصف عربي/إنجليزي وأخطاء موحّدة.

التشغيل:
    uvicorn pharma_sdl.api.app:create_app --factory --port 8000
أو:
    pharma-sdl serve --port 8000
التوثيق التفاعلي: /docs (Swagger) — OpenAPI كامل للتكامل الخارجي.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from pharma_sdl import __version__
from pharma_sdl.api.deps import app_settings
from pharma_sdl.api.routes import engines, health, lab, screening, targets
from pharma_sdl.engines.registry import list_engines
from pharma_sdl.errors import PlatformError

_DESCRIPTION = f"""**Pharma SDL — منصة اكتشاف الأدوية API-First** (v{__version__})

خط تشغيلي كامل: **تنقية** ← **فرز ظاهري** ← **إجماع** ← **مختبر** ← **تقرير**،
بمحركات قابلة للتبديل وسياسات أهداف صريحة (Mpro 7VH8 غير تساهمي حصراً).

* `GET /api/v1/targets` — الأهداف الجاهزة وسياساتها
* `POST /api/v1/screening/runs` — جولة فرز (202 غير متزامنة)
* `GET /api/v1/screening/runs/{{id}}/report` — تقرير Markdown ثنائي اللغة
* `POST /api/v1/lab/assays` — فحص FRET (محاكى — simulated=true دائماً حتى الدمج الحقيقي)

المحرك الافتراضي `simulation` حتمي ومتاح دائماً — الوصول لـ`vina` يتطلب
vina/meeko المحليين، ولـ`boltz2` بوابة `PHARMA_SDL_BOLTZ2_ENDPOINT`.
"""


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = app_settings()
    available = [e.name for e in list_engines() if e.available]
    print(f"[pharma_sdl] v{__version__} — engines available: {available}")
    _ = settings
    yield


def create_app() -> FastAPI:
    """مصنع التطبيق — يعيد نسخة جديدة كاملة (صديقة للاختبارات والتشغيل المتعدد)."""
    settings = app_settings()
    app = FastAPI(
        title="Pharma SDL Platform API",
        version=__version__,
        description=_DESCRIPTION,
        lifespan=_lifespan,
    )
    origins = ["*"] if settings.cors_origins == "*" else settings.cors_origins.split(",")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(PlatformError)
    async def platform_error_handler(_: Request, exc: PlatformError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.http_status,
            content={
                "code": exc.code,
                "message_ar": exc.message_ar,
                "message_en": exc.message_en,
            },
        )

    app.include_router(health.router, prefix="/api/v1")
    app.include_router(engines.router, prefix="/api/v1")
    app.include_router(targets.router, prefix="/api/v1")
    app.include_router(screening.router, prefix="/api/v1")
    app.include_router(lab.router, prefix="/api/v1")

    @app.get("/", tags=["meta"])
    def root() -> dict[str, Any]:
        return {
            "name": "Pharma SDL Platform",
            "version": __version__,
            "docs": "/docs",
            "api": "/api/v1",
            "note_ar": "بوابة المنصة التشغيلية — ابدأ من /docs",
            "note_en": "Platform gateway — start at /docs",
        }

    return app
