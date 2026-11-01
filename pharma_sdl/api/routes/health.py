"""مسارات الصحة والإصدار."""

from __future__ import annotations

from fastapi import APIRouter

from pharma_sdl import __version__
from pharma_sdl.api.schemas import HealthOut, VersionOut
from pharma_sdl.engines.registry import list_engines

router = APIRouter(tags=["meta"])


@router.get("/health", response_model=HealthOut)
def health() -> HealthOut:
    return HealthOut(
        status="ok",
        version=__version__,
        engines_available=[e.name for e in list_engines() if e.available],
    )


@router.get("/version", response_model=VersionOut)
def version() -> VersionOut:
    return VersionOut(
        name="Pharma SDL Platform",
        version=__version__,
        api="v1",
        docs="/docs",
    )
