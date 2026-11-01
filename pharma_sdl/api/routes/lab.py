"""مسار المختبر — فحص FRET (محاكى الآن عبر SimulatedFretLab)."""

from __future__ import annotations

from fastapi import APIRouter

from pharma_sdl.api.schemas import AssayCreate, AssayOut
from pharma_sdl.lab.interface import AssayRequest
from pharma_sdl.lab.simulation import SimulatedFretLab

router = APIRouter(prefix="/lab", tags=["lab"])


@router.post("/assays", response_model=AssayOut)
def create_assay(create: AssayCreate) -> AssayOut:
    lab = SimulatedFretLab()
    result = lab.run_assay(
        AssayRequest(smiles=create.smiles, dg_kcal=create.dg_kcal)
    )
    return AssayOut(**result.model_dump())
