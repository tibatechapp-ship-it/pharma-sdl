"""مخططات الطلب/الاستجابة لواجهة الـAPI — عقد مفتوح عبر OpenAPI."""

from __future__ import annotations

from pydantic import BaseModel, Field

from pharma_sdl.models import AssayResult, LigandInput, ScreeningResult
from pharma_sdl.validation.gate import ValidationState


# ── عام ──
class HealthOut(BaseModel):
    status: str = "ok"
    version: str
    engines_available: list[str]
    auth_mode: str = "open"  # open | enforced — لا وضع مصادقة خفي (P2)
    demo_mode: bool = False  # وضع العرض العام المحدود صادق ومعلن (P2)


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


# ── الاعتماد العلمي (P2) ──
class ValidationTransitionIn(BaseModel):
    """طلب ترقية بشرية صريح — التوقيع (actor) إلزامي، والمرفقات بحسب الحالة."""

    to: ValidationState
    reason: str = Field(min_length=1, description="سبب موثق — الترقية بلا مبرر تُرفض")
    actor: str = Field(min_length=1, description="من يوقّع: اسم/بريد المُجيز البشري")
    checks: list[str] = Field(default_factory=list)
    assay_ref: str | None = Field(
        None, description="إلزامي للترقية إلى EXPERIMENTALLY_SUPPORTED"
    )
    protocol: str | None = Field(
        None, description="إلزامي للترقية إلى INDEPENDENTLY_REPRODUCED"
    )
    independent_lab: str | None = Field(
        None, description="إلزامي للترقية إلى INDEPENDENTLY_REPRODUCED"
    )


class ValidationRevokeIn(BaseModel):
    """تخفيض صريح موثق — يُحى أبداً من تاريخ البطاقة."""

    reason: str = Field(min_length=1)
    actor: str = Field(min_length=1)
