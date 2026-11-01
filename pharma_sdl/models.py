"""نماذج البيانات المشتركة (Pydantic v2) — عقد واحد تلتزم به كل الطبقات.

من الـAPI إلى الـCLI إلى الاختبارات: نفس النماذج، لا نسخ متوازية.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from pharma_sdl.scores import DISCLAIMER_AR, DISCLAIMER_EN


def utcnow_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


# ─────────────────────────────────────────────────────────────
# التنقية (Curation)
# ─────────────────────────────────────────────────────────────

class LigandInput(BaseModel):
    """ليغاند خام قبل التنقية — أقل وصف مقبول: SMILES."""

    name: str | None = None
    smiles: str
    source: str | None = None


class CuratedLigand(BaseModel):
    """ليغاند ناجٍ من خط التنقية مع وصله الكيميائي الكامل."""

    input_id: str
    name: str | None = None
    input_smiles: str
    canonical_smiles: str
    inchikey: str | None = None
    mol_weight: float
    clogp: float
    tpsa: float
    hbd: int
    hba: int
    rotatable_bonds: int
    heavy_atoms: int
    sa_score: float | None = None
    pains_alerts: list[str] = Field(default_factory=list)
    warhead_alerts: list[str] = Field(default_factory=list)
    lipinski_flags: list[str] = Field(default_factory=list)
    veber_flags: list[str] = Field(default_factory=list)


class Rejection(BaseModel):
    """رفض مسبَّب — كل رفض يحمل السبب بلغتين (شفافية كاملة)."""

    input_id: str
    name: str | None = None
    smiles: str
    stage: Literal["validate", "dedupe", "covalent_gate", "pains"]
    reason_ar: str
    reason_en: str


class CurationReport(BaseModel):
    """تقرير جولة تنقية: الناجون + المرفوضون + العدّادات."""

    kept: list[CuratedLigand] = Field(default_factory=list)
    rejected: list[Rejection] = Field(default_factory=list)
    duplicates_removed: int = 0
    counts: dict[str, int] = Field(default_factory=dict)


# ─────────────────────────────────────────────────────────────
# الفرز الظاهري (Screening)
# ─────────────────────────────────────────────────────────────

class ScoredHit(BaseModel):
    """مرشح مُرتَّب — درجة kcal/mol الأكثر سالبية أقوى."""

    rank: int
    input_id: str
    name: str | None = None
    canonical_smiles: str
    inchikey: str | None = None
    docking_kcal: float
    method: str
    mol_weight: float
    clogp: float
    tpsa: float
    pains_alerts: list[str] = Field(default_factory=list)
    warhead_alerts: list[str] = Field(default_factory=list)
    lipinski_flags: list[str] = Field(default_factory=list)


class ScreeningResult(BaseModel):
    """نتيجة جولة فرز كاملة — قابلة للتسلسل JSON مباشرة."""

    run_id: str
    target_id: str
    target_label_ar: str
    target_label_en: str
    engine_requested: str
    engine_used: str
    fallback_note: str | None = None
    created_at: str = Field(default_factory=utcnow_iso)
    counts: dict[str, int] = Field(default_factory=dict)
    hits: list[ScoredHit] = Field(default_factory=list)
    rejected: list[Rejection] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    elapsed_seconds: float = 0.0
    # عقد الصدق (تدقيق P0): كل استجابة فرز تحمل التحذير العلمي/الطبي معها —
    # التحذير يسافر مع البيانات وليس في التوثيق فقط.
    disclaimer_ar: str = DISCLAIMER_AR
    disclaimer_en: str = DISCLAIMER_EN

    def top(self, n: int) -> list[ScoredHit]:
        return self.hits[:n]


# ─────────────────────────────────────────────────────────────
# المختبر (Lab)
# ─────────────────────────────────────────────────────────────

class AssayResult(BaseModel):
    """نتيجة فحص مخبري — الحقل simulated صادق دائماً عن طبيعة النتيجة."""

    smiles: str
    assay: str
    simulated: bool = True
    ic50_um: float | None = None
    pic50: float | None = None
    dg_kcal_input: float | None = None
    notes_ar: str = ""
    notes_en: str = ""


# ─────────────────────────────────────────────────────────────
# المهام (Jobs)
# ─────────────────────────────────────────────────────────────

class JobInfo(BaseModel):
    """حالة مهمة في الطابور الداخلي."""

    id: str
    kind: str
    status: Literal["pending", "running", "done", "failed"] = "pending"
    created_at: str = Field(default_factory=utcnow_iso)
    started_at: str | None = None
    finished_at: str | None = None
    error: str | None = None
    detail: dict[str, Any] = Field(default_factory=dict)
