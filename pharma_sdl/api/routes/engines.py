"""مسار المحركات — حالة كل محرك بصدق كامل."""

from __future__ import annotations

from fastapi import APIRouter

from pharma_sdl.api.schemas import EngineOut
from pharma_sdl.engines.registry import list_engines

router = APIRouter(prefix="/engines", tags=["engines"])


@router.get("", response_model=list[EngineOut])
def engines() -> list[EngineOut]:
    return [
        EngineOut(
            name=e.name,
            label=e.label,
            kind=e.kind,
            available=e.available,
            note_ar=e.note_ar,
            note_en=e.note_en,
        )
        for e in list_engines()
    ]
