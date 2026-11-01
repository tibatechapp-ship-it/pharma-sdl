"""مخططات الطلب/الاستجابة لواجهة الـAPI — عقد مفتوح عبر OpenAPI."""

from __future__ import annotations

from pydantic import BaseModel, Field

from pharma_sdl.models import AssayResult, LigandInput, ScreeningResult


# ── عام ──
class HealthOut(BaseModel):
    status: str = "ok"
    version: str
    engines_available: list[str]


class VersionOut(BaseModel):
    name: str
    version: str
    api: str
    docs: str


class EngineOut(BaseModel):
    name: str
    label: str
    kind: str
    available: bool
    note_ar: str = ""
    note_en: str = ""


class PolicyOut(BaseModel):
    non_covalent_only: bool
    reason_ar: str
    reason_en: str


class TargetOut(BaseModel):
    id: str
    pdb_id: str
    name_ar: str
    name_en: str
    center: list[float]
    box_size: list[float]
    policy: PolicyOut
    self_dock_reference_kcal: float | None = None
    co_crystal_name: str = ""


# ── الفرز ──
class ScreeningCreate(BaseModel):
    """طلب جولة فرز — بلا ليغاندات = وضع العرض (مجموعة demo_ligands)."""

    target_id: str = "7VH8_A"
    engine: str | None = Field(
        None, description="simulation | vina | boltz2 — الإعداد الافتراضي: simulation"
    )
    top_n: int = Field(10, ge=1, le=100)
    reject_pains: bool = False
    ligands: list[LigandInput] | None = Field(
        None, description="اتركه فارغاً لاستخدام مجموعة العرض data/demo_ligands.csv"
    )


class RunAcceptedOut(BaseModel):
    job_id: str
    status: str
    run_url: str
    report_url: str


class RunStatusOut(BaseModel):
    job_id: str
    kind: str
    status: str
    error: str | None = None
    result: ScreeningResult | None = None


# ── المختبر ──
class AssayCreate(BaseModel):
    smiles: str
    dg_kcal: float = Field(..., description="ΔG من جولة الفرز — يُشتق منه IC50 عبر Cheng-Prusoff")


class AssayOut(AssayResult):
    pass
