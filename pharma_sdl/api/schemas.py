"""مخططات الطلب/الاستجابة لواجهة الـAPI — عقد مفتوح عبر OpenAPI."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from pharma_sdl.campaign import CampaignReport
from pharma_sdl.experiments.registry import ExperimentRecord
from pharma_sdl.models import AssayResult, LigandInput, ScreeningResult
from pharma_sdl.prophetic import ScreenReport as TibbScreenReportOut
from pharma_sdl.validation.gate import ValidationState


# ── عام ──
class HealthOut(BaseModel):
    status: str = "ok"
    version: str
    engines_available: list[str]
    auth_mode: str = "open"  # open | enforced — لا وضع مصادقة خفي (P2)
    demo_mode: bool = False  # وضع العرض العام المحدود صادق ومعلن (P2)
    store_backend: str = "sqlite"  # sqlite | postgres — الخلفية معلنة لا خفية (P3)


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


# ── الحلقة كخدمة (P3) ──
class LoopCreate(BaseModel):
    """طلب حلقة مغلقة — ثلاث جولات (خط أساس ← استكشاف ← توظيف) في مهمة دائمة."""

    target_id: str = "7VH8_A"
    engine: str | None = Field(None, description="الافتراضي: simulation — حتمي ومتاح دائماً")
    top_n: int = Field(5, ge=1, le=25, description="أفضل المرشحين لكل جولة")


class LoopRunOut(BaseModel):
    """حالة حلقة مغلقة — الجولات الثلاث متسلسلة بالأسلاف، كلها UNVALIDATED."""

    job_id: str
    kind: str = "closed_loop"
    status: str
    error: str | None = None
    rounds: list[ExperimentRecord] | None = None  # None حتى اكتمال المهمة
    round_count: int = 0
    note_ar: str = ""
    note_en: str = ""


# ── حملات التعلم النشط (P4) ──
class CampaignCreate(BaseModel):
    """طلب حملة تعلم نشط — N جولات يُحدَّث فيها النموذج من نتائجه."""

    strategy: Literal["random", "greedy", "uncertainty", "ucb"] = "uncertainty"
    rounds: int = Field(6, ge=2, le=15, description="جولات التعلم — كل جولة ملاءمة جديدة")
    batch_size: int = Field(8, ge=1, le=24, description="حجم الدفعة المختارة كل جولة")
    initial_labeled: int = Field(40, ge=20, le=200, description="البذرة المُعنونة الابتدائية")
    n_estimators: int = Field(300, ge=20, le=300, description="عدد أشجار RF")
    kappa: float = Field(1.0, gt=0.0, le=5.0, description="معامل الاستكشاف في ucb")


class CampaignRunOut(BaseModel):
    """حالة حملة تعلم — وعند الاكتمال التقرير الكامل بمنحنى التعلم."""

    job_id: str
    kind: str = "learning_campaign"
    status: str
    error: str | None = None
    report: CampaignReport | None = None  # None حتى اكتمال المهمة
    note_ar: str = ""
    note_en: str = ""


# ── مكتبة الطب النبوي (P5) ──
class LibraryOut(BaseModel):
    """المكتبة النبوية كاملة — مركبات مُدقَّقة + إجراءات + توثيق مزدوج."""

    compounds: int
    procedures: int
    by_source: dict[str, int]
    by_evidence_tier: dict[str, int]
    hadith_grades: list[str]
    items: list[dict]  # المركبات: SMILES/صيغة/CID/مصدر/طبقة دليل/توثيق تراثي
    procedure_items: list[dict]  # الإجراءات: بلا جزيء — توثيق فقط
    source_notes: dict[str, str]
    disclaimer_ar: str
    disclaimer_en: str


class TibbTargetOut(BaseModel):
    """هدف تِبّي مُدرّب واحد — معرفه واسمه وبياناته وقصة اختياره (P6).

    الاسم مُسبَّق بـ Tibb تمييزاً له عن TargetOut (أهداف الـDocking بمعرفات
    PDB) — التصادم كشفه الاختبار التكاملي وأعيدت التسمية لا الدمج.
    """

    target_id: str
    name_ar: str
    name_en: str
    dataset: str
    n_dataset: int
    description_ar: str
    description_en: str


class TibbTargetsOut(BaseModel):
    """سجل الأهداف التِبّية المُدرّبة — كلها تُفرز بنفس الكود والمسار نفسه."""

    targets: list[TibbTargetOut]
    note_ar: str
    note_en: str


class ScreenRequest(BaseModel):
    """طلب فرز اختياري الجسم — target_id من TARGETS أو غيابه (Mpro)."""

    target_id: str | None = None


class ScreenRunOut(BaseModel):
    """حالة فرز المكتبة — وعند الاكتمال التقرير الكامل."""

    job_id: str
    kind: str = "tibb_screen"
    status: str
    error: str | None = None
    report: TibbScreenReportOut | None = None  # None حتى اكتمال المهمة
    note_ar: str = ""
    note_en: str = ""


# ── المقاييس التشغيلية (P3) ──
class MetricsOut(BaseModel):
    """عدّادات صادقة من الذاكرة الحية — لا تقديرات ولا تجميل."""

    version: str
    registry_backend: str
    experiments_by_status: dict[str, int]
    experiments_by_validation_state: dict[str, int]
    jobs_by_status: dict[str, int]
    engines_available: list[str]
    auth_mode: str
    demo_mode: bool
