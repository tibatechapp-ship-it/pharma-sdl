"""المقارنة ثلاثية الطبقات لتسعير القرابة — P14 (خطة التطوير §الربع الثاني، P14).

السؤال المحوري: كم يكلّف ربط هذا الجزيء بالمستقبل من منظور ثلاث طبقات
تسعير مختلفة الجهد والثقة — ومتى نثق بأي طبقة ولماذا؟

- الطبقة 1 (سريعة): نموذجنا التعلمي v0.12.0 (بصمة Morgan بالتكرارات +
  RandomForest، max_features=0.3) → pIC50 ± CI95 في أجزاء من الثانية،
  وثقتها الخارجية موثقة في P12 (16/18 على Solubility) — للاستخدام
  الترتيبي داخل سلالة كيميائية متقاربة، لا للقيم المطلقة خارجها.
- الطبقة 2 (فيزيائية): AutoDock Vina على المستقبل الجاهز 7VH8 → ΔG
  (kcal/mol) تُحوَّل إلى pIC50 عبر جسر Cheng-Prusoff العكسي (ΔG =
  −1.3644·pIC50) — درجات تعليمية تُبالغ/تُقلّل مقارنة بالتجربة، ومرجع
  إعادة الربط الذاتي للمستقبل −8.28 kcal/mol موثق في receptors.json.
- الطبقة 3 (المرجعية): Boltz-2 co-folding برأس تقارب مدرَّب على
  FEP+/CASP16 — تعمل على Colab GPU فقط عبر دفتر Lab08، وتصل محلياً
  كبيان مجمّد يستهلكه core/clients/boltz2_client.py.

الوحدة عمداً بلا استيراد من الواجهة التطبيقية — تُستخدم من السكربت
المجمّد ومن الاختبارات ومن أي مصرف لاحق في القمع.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from rdkit import Chem, RDLogger

from core.clients.boltz2_client import Boltz2Client
from core.docking import RT_KCAL, dock_ligand, load_receptors
from core.ml_potency import PotencyModel

RDLogger.DisableLog("rdApp.*")

LN10_RT = RT_KCAL * 2.302585092994046  # RT·ln10 = 1.3644 kcal/mol عند 298K

# حدود الاتفاق في فضاء pIC50 — معلنة لا مخمّنة
AGREE_LOG = 1.0        # |ΔpIC50| ≤ 1 → اتفاق كمّي
AGREE_LOOSE = 2.0      # ≤ 2 → اتفاق تقريبي؛ ما فوقه تعارض يُفصَّل

TIER_ML = 1
TIER_VINA = 2
TIER_BOLTZ2 = 3


# ─────────────────────────────────────────────────────────────
# قراءات الطبقات
# ─────────────────────────────────────────────────────────────

def ml_reading(model: PotencyModel, smiles: str) -> dict[str, Any]:
    """الطبقة 1 — pIC50 ± CI95 من النموذج الافتراضي المعتمد."""
    pred = model.predict(smiles)
    return {
        "tier": TIER_ML,
        "engine": "rf-morgan-counts (v0.12.0 config)",
        "status": "ok",
        "pic50": float(pred["pic50"]),
        "ci95": pred["ci95"],
        "pic50_std": float(pred["pic50_std"]),
        "ic50_nm": float(pred["ic50_nm"]),
        "unit": "pIC50",
    }


def vina_reading(
    smiles: str,
    receptor_id: str = "7VH8_A",
    exhaustiveness: int = 8,
    random_seed: int = 42,
) -> dict[str, Any]:
    """الطبقة 2 — أفضل بوز Vina → ΔG → pIC50 عبر الجسر العكسي الموثق.

    pIC50 = −ΔG / (RT·ln10) — معكوس جسر Cheng-Prusoff في core/docking.py.
    بذرة ثابتة (42) افتراضياً حتى يكون التجميد المنشور قابلاً للتكرار حرفياً.
    """
    receptors = load_receptors()
    rec = next((r for r in receptors if r.id == receptor_id), None)
    if rec is None:
        raise ValueError(f"مستقبل غير معروف: {receptor_id}")
    result = dock_ligand(smiles, rec, exhaustiveness=exhaustiveness, random_seed=random_seed)
    best_dg = result.best
    if best_dg is None:
        return {"tier": TIER_VINA, "engine": "vina", "status": "unavailable_no_poses"}
    pic50 = -float(best_dg) / LN10_RT
    return {
        "tier": TIER_VINA,
        "engine": f"vina (7VH8_A, exhaustiveness=8, seed={random_seed})",
        "status": "ok",
        "dg_kcal": round(float(best_dg), 2),
        "pic50": round(pic50, 2),
        "n_poses": len(result.scores),
        "unit": "pIC50 (جسر Cheng-Prusoff من ΔG)",
        "self_dock_reference_kcal": rec.self_dock_best_kcal,
    }


def boltz2_reading(client: Boltz2Client | None, smiles: str) -> dict[str, Any] | None:
    """الطبقة 3 — قراءة من بيان Boltz-2 المجمد، أو None بحالة صادقة.

    لا بيان → حالة غياب موثقة على مستوى اللوحة (بلا قيمة مختلقة).
    بيان موجود وجزيء غائب → حالة «ليس في البيان» لهذا الجزيء.
    """
    if client is None:
        return None
    reading = client.reading_for(smiles)
    if reading is None:
        return {
            "tier": TIER_BOLTZ2,
            "engine": "boltz-2",
            "status": "not_in_manifest",
            "unit": "log10(IC50[μM])",
        }
    # تسوية مفردة الحالة إلى مفردات اللوحة (العميل يقول available، اللوحة تقول ok)
    if reading.get("status") == "available":
        reading["status"] = "ok"
    return reading


def boltz2_unavailable_placeholder() -> dict[str, Any]:
    """حالة غياب الطبقة الثالثة على مستوى اللوحة — صادقة ومعلنة."""
    return {
        "tier": TIER_BOLTZ2,
        "engine": "boltz-2",
        "status": "unavailable_offline",
        "note": "الطبقة الثالثة تعمل على Colab GPU فقط — شغّل labs/lab08_boltz2_co_folding.ipynb ثم أعد سكربت التجميد",
        "unit": "log10(IC50[μM])",
    }


# ─────────────────────────────────────────────────────────────
# الاتفاق والدروس
# ─────────────────────────────────────────────────────────────

def agreement_label(a: float | None, b: float | None) -> str:
    """تصنيف الاتفاق بين قراءتين على مقياس pIC50 الموحّد."""
    if a is None or b is None:
        return "غير قابل للحسم — إحدى الطبقتين غائبة"
    delta = abs(a - b)
    if delta <= AGREE_LOG:
        return "اتفاق كمّي (|ΔpIC50| ≤ 1)"
    if delta <= AGREE_LOOSE:
        return "اتفاق تقريبي (1 < |ΔpIC50| ≤ 2)"
    return "تعارض (|ΔpIC50| > 2)"


def nearest_anchor_gap(anchor: float | None, readings: list[dict[str, Any]]) -> dict[str, Any]:
    """أي طبقة أقرب إلى المرجع التجريبي — وأكبر فجوة لكل طبقة."""
    if anchor is None:
        return {"verdict": "بلا مرجع تجريبي في هذه اللوحة", "gaps": {}}
    gaps: dict[str, float] = {}
    for r in readings:
        if r is None or r.get("status") != "ok" or "pic50" not in r:
            continue
        gaps[str(r["tier"])] = round(abs(float(r["pic50"]) - anchor), 2)
    if not gaps:
        return {"verdict": "لا قراءات صالحة للمقارنة بالمرجع", "gaps": {}}
    best_tier = min(gaps, key=lambda k: gaps[k])
    return {"closest_tier": int(best_tier), "gaps": gaps}


def trust_lesson() -> dict[str, str]:
    """الدرس العربي: متى نثق بأي طبقة — قواعد معلنة لا ذوق شخصي."""
    return {
        "tier1_ml": (
            "ثِق بالطبقة السريعة لـ**ترتيب** آلاف المرشحين داخل سلالة كيميائية "
            "قريبة من تدريبها (Mpro هنا) — ولا تثق بقيمها المطلقة خارج سلالتها: "
            "قياس P12 الخارجي (16/18 على Solubility) وثّق أن سقف فئة "
            "«بصمة+RF» يُكشف فقط على مرجع لا نملكه."
        ),
        "tier2_vina": (
            "ثِق بـVina لـ**موضع الربط** وطاقة خشنة سريعة، مع انحياز معلوم: "
            "درجاته تعليمية وتتأثر بامتلاء الصندوق — لذلك نحمل مرجع إعادة "
            "الربط الذاتي (−8.28 kcal/mol لـ7VH8) وحده مقياساً لصحة الصندوق."
        ),
        "tier3_boltz2": (
            "ثِق بـBoltz-2 للحكم **المرجعي** على عشرات المرشحين التي نجاها "
            "الطبقتان الأوليان: رأس تقاربه مدرَّب على بيانات فيزيائية (FEP+/"
            "CASP16) ويعطي بنية + قرابة معاً في ~20 ثانية GPU — لكنه غالي "
            "البنية (GPU) ولا يعمل بلا شبكة، وبياناته إنجليزية المصدر دائماً."
        ),
        "funnel_rule": (
            "قاعدة القمع: الطبقة 1 تفرز الآلاف ← الطبقة 2 تصفي المئات ← "
            "الطبقة 3 تُسعّر العشرات ← التجربة الحقيقية تحكم. كل طبقة رخيصة "
            "نسبياً تسبق أغلى منها، ولا طبقة تتجاوز حكمها لأعلى منها."
        ),
        "disagreement_rule": (
            "عند التعارض (|ΔpIC50| > 2): لا تصوّت طبقات — الأقرب للمرجع "
            "التجريبي يكسب في هذه اللوحة، والتعارض بحد ذاته نتيجة تُنشر "
            "وتُحلّل (غالباً: مرونة المستقبل مفقودة في الطبقتين 1 و2)."
        ),
    }


# ─────────────────────────────────────────────────────────────
# لوحة المقارنة الكاملة
# ─────────────────────────────────────────────────────────────

@dataclass
class TierPanelEntry:
    """صف لوحة لجزيء واحد — كل الطبقات + المرجع + الأحكام."""

    smiles: str
    name_ar: str
    name_en: str
    anchor: dict[str, Any] | None = None
    readings: dict[str, Any] = field(default_factory=dict)
    out_of_sample: bool = True
    nearest_train_tanimoto: float | None = None


def build_panel(
    entries: list[TierPanelEntry],
    model: PotencyModel,
    boltz_client: Boltz2Client | None,
    receptor_id: str = "7VH8_A",
    exhaustiveness: int = 8,
    dock_fn: Callable[[str, str, int], dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """بناء صفوف اللوحة كاملة — dock_fn قابل للحقن في الاختبارات."""
    rows: list[dict[str, Any]] = []
    for entry in entries:
        canon = Chem.MolToSmiles(Chem.MolFromSmiles(entry.smiles))
        ml = ml_reading(model, entry.smiles)
        if dock_fn is not None:
            vina = dock_fn(entry.smiles, receptor_id, exhaustiveness)
        else:
            vina = vina_reading(entry.smiles, receptor_id, exhaustiveness)
        boltz = boltz2_reading(boltz_client, canon) if boltz_client is not None else None

        anchor_pic50 = entry.anchor.get("pic50") if entry.anchor else None
        pairwise = {}
        for tier_key, reading in (("ml", ml), ("vina", vina), ("boltz2", boltz)):
            if reading and reading.get("status") == "ok" and "pic50" in reading:
                pairwise[tier_key] = agreement_label(float(reading["pic50"]), anchor_pic50)

        rows.append({
            "smiles": canon,
            "name_ar": entry.name_ar,
            "name_en": entry.name_en,
            "anchor": entry.anchor,
            "out_of_sample": entry.out_of_sample,
            "nearest_train_tanimoto": entry.nearest_train_tanimoto,
            "tier1_ml": ml,
            "tier2_vina": vina,
            "tier3_boltz2": boltz if boltz is not None else boltz2_unavailable_placeholder(),
            "agreement_vs_anchor": pairwise,
            "closest_to_anchor": nearest_anchor_gap(anchor_pic50, [ml, vina, boltz]),
        })
    return rows
