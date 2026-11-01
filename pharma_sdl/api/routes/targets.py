"""مسار الأهداف — السجل وسياساته (Mpro غير تساهمي حصراً)."""

from __future__ import annotations

from fastapi import APIRouter

from pharma_sdl.api.schemas import PolicyOut, TargetOut
from pharma_sdl.targets.registry import list_targets

router = APIRouter(prefix="/targets", tags=["targets"])


@router.get("", response_model=list[TargetOut])
def targets() -> list[TargetOut]:
    return [
        TargetOut(
            id=t.id,
            pdb_id=t.pdb_id,
            name_ar=t.name_ar,
            name_en=t.name_en,
            center=list(t.center),
            box_size=list(t.box_size),
            policy=PolicyOut(
                non_covalent_only=t.policy.non_covalent_only,
                reason_ar=t.policy.reason_ar,
                reason_en=t.policy.reason_en,
            ),
            self_dock_reference_kcal=t.self_dock_reference_kcal,
            co_crystal_name=t.co_crystal_name,
        )
        for t in list_targets()
    ]
