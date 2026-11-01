"""فلاتر الأمان الدوائي — أول حاجز في المنصة قبل أي تسجيل.

1) بوابة الرؤوس التساهمية (Covalent Warheads): تُنفّذ سياسة الهدف.
   وفق الخطة v1.1: محركاتنا (Vina/Boltz-2) لا تمثّل الترابط التساهمي،
   لذلك هدف Mpro يُفرز غير تساهمي حصراً — أي رأس تساهمي يُرفض مسبَّباً.
2) تنبيهات PAINS عبر فهرس RDKit الرسمي (PAINS A/B/C).
3) قواعد Lipinski/Veber كأعلام معلوماتية (لا تُرفض بها الجزيئات — تُوثَّق).
4) SAscore (Ertl) إن توفّر الحزمة — وإلا None بلا تدّليع.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from rdkit import Chem
from rdkit.Chem import FilterCatalog

if TYPE_CHECKING:
    from pharma_sdl.chemistry.molecules import MoleculeRecord


# ─────────────────────────────────────────────────────────────
# الرؤوس التساهمية — SMARTS مرجعية (فئة hard = منع صريح، nitrile = سياسة الهدف)
# ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class WarheadRule:
    name: str
    smarts: str
    category: str  # "hard" أو "nitrile"
    label_ar: str
    label_en: str


COVALENT_WARHEADS: tuple[WarheadRule, ...] = (
    WarheadRule("acrylamide", "[NX3][CX3](=O)[CX3]=[CX3]", "hard",
                "أكريلاميد (مستقبل مايكل)", "acrylamide (Michael acceptor)"),
    WarheadRule("enone_michael", "[CX3]=[CX3][CX3](=O)", "hard",
                "إينون/مايكل عام", "enone / Michael acceptor"),
    WarheadRule("aldehyde", "[CX3H1](=O)[#6]", "hard",
                "ألدهيد", "aldehyde"),
    WarheadRule("chloroacetamide", "[NX3][CX3](=O)[CX4][Cl,Br,I]", "hard",
                "هالو أسيتاميد", "haloacetamide"),
    WarheadRule("alpha_haloketone", "[CX3](=O)[CX4][Cl,Br,I]", "hard",
                "ألفا-هالو كيتون", "alpha-haloketone"),
    WarheadRule("vinyl_sulfone", "[CX3]=[CX3][SX4](=O)(=O)", "hard",
                "فينيل سلفون", "vinyl sulfone"),
    WarheadRule("epoxide", "[CX4]1[CX4][OX2]1", "hard",
                "إيبوكسيد", "epoxide"),
    WarheadRule("aziridine", "[CX4]1[CX4][NX3]1", "hard",
                "أزيريدين", "aziridine"),
    WarheadRule("boronic_acid", "[BX3]", "hard",
                "حمض بوروني", "boronic acid/ester"),
    WarheadRule("sulfonyl_fluoride", "[SX4](=O)(=O)[F]", "hard",
                "سلفونيل فلوريد", "sulfonyl fluoride"),
    WarheadRule("nitrile", "C#N", "nitrile",
                "نيتريل (تساهمي عكوس)", "nitrile (reversible covalent)"),
)


def _compiled_rules() -> list[tuple[WarheadRule, object]]:
    out: list[tuple[WarheadRule, object]] = []
    for rule in COVALENT_WARHEADS:
        patt = Chem.MolFromSmarts(rule.smarts)
        if patt is not None:
            out.append((rule, patt))
    return out


_COMPILED = _compiled_rules()


def detect_warheads(mol: Chem.Mol) -> list[WarheadRule]:
    """قائمة الرؤوس التساهمية الموجودة في الجزيء (قد تكون فارغة)."""
    hits: list[WarheadRule] = []
    for rule, patt in _COMPILED:
        if mol.HasSubstructMatch(patt):
            hits.append(rule)
    return hits


def classify_warhead_risk(hits: list[WarheadRule]) -> str | None:
    """أسوأ تصنيف في قائمة الإصابات: hard ← nitrile ← None."""
    cats = {h.category for h in hits}
    if "hard" in cats:
        return "hard"
    if "nitrile" in cats:
        return "nitrile"
    return None


# ─────────────────────────────────────────────────────────────
# PAINS
# ─────────────────────────────────────────────────────────────

def _build_pains_catalog() -> FilterCatalog.FilterCatalog | None:
    try:
        params = FilterCatalog.FilterCatalogParams()
        params.AddCatalog(FilterCatalog.FilterCatalogParams.FilterCatalogs.PAINS_A)
        params.AddCatalog(FilterCatalog.FilterCatalogParams.FilterCatalogs.PAINS_B)
        params.AddCatalog(FilterCatalog.FilterCatalogParams.FilterCatalogs.PAINS_C)
        return FilterCatalog.FilterCatalog(params)
    except Exception:  # noqa: BLE001 — غياب الكتالوج لا يُسقط خط التنقية
        return None


_PAINS = _build_pains_catalog()


def pains_alerts(mol: Chem.Mol) -> list[str]:
    """أسماء تنبيهات PAINS المصطادة (فارغة = نظيف)."""
    if _PAINS is None:
        return []
    alerts: list[str] = []
    for entry in _PAINS.GetMatches(mol):
        desc = entry.GetDescription()
        if desc not in alerts:
            alerts.append(desc)
    return alerts


# ─────────────────────────────────────────────────────────────
# SAscore (Ertl) — اختياري إن توفّر في توزيعة RDKit
# ─────────────────────────────────────────────────────────────

def sa_score(mol: Chem.Mol) -> float | None:
    try:
        from rdkit.Contrib.SA_Score import scorer  # type: ignore[import-not-found]

        return round(float(scorer.calculateScore(mol)), 2)
    except Exception:  # noqa: BLE001 — العدم الصادق أفضل من رقم مختلق
        return None


# ─────────────────────────────────────────────────────────────
# Lipinski / Veber — أعلام توثيقية (لا رفض بها)
# ─────────────────────────────────────────────────────────────

def lipinski_flags(rec: MoleculeRecord) -> list[str]:
    flags: list[str] = []
    if rec.mol_weight > 500:
        flags.append("MW>500")
    if rec.clogp > 5:
        flags.append("LogP>5")
    if rec.hbd > 5:
        flags.append("HBD>5")
    if rec.hba > 10:
        flags.append("HBA>10")
    return flags


def veber_flags(rec: MoleculeRecord) -> list[str]:
    flags: list[str] = []
    if rec.rotatable_bonds > 10:
        flags.append("RotB>10")
    if rec.tpsa > 140:
        flags.append("TPSA>140")
    return flags
