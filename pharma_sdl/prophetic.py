"""مكتبة الطب النبوي — منتجات طبيعية موثقة كخط اكتشاف مُختبَر (P5).

المبدأ الحاكم (ADR-0010): فصل صارم بين ثلاث طبقات لا تُخلط أبداً:

    1) التوثيق التراثي   — حديث/آية بدرجته الفعلية المتخَرَّجة (متفق عليه/صحيح/
                           قرآن) وقيمته التوثيقية-الثقافية. التوثيق لا يُنتج
                           درجة ولا يُعد دليلاً على فعالية.
    2) الدليل الحديث      — طبقة أدلة مخبرية/قبل سريرية/سريرية بمرجع منشور
                           لكل مادة، بلا تضخيم.
    3) المخرج الحاسوبي    — تنبؤات نموذج الإنتاج على مكونات المكتبة داخل خط
                           الدرجات المعلن (predicted_potency) وبحالة
                           UNVALIDATED حصراً — بوابة P1 بشرية.

صحوة منهجية معلنة: الأحاديث المؤسِّسة للمواد الثلاث درجتها «متفق عليه»
(البخاري + مسلم) — وهي أقوى درجات المسند بعد المتواتر، وليست متواترة
تقنياً؛ نُوثّق الدرجة الفعلية لا الشائعة.

البناء:
    - 17 مركباً بجزيئات معلنة (SMILES + CID + صيغة) جُلبت من PubChem
      (PUG REST) وتُدقَّق في الاختبارات عبر RDKit: كل جزيء يُحلَّل وصيغته
      الجزيئية المحسوبة تطابق الصيغة الموثقة حرفياً.
    - إجرائان (حجامة/كي) بلا جزيء — لا يُفرَزان حاسوبياً؛ يُوثَّقان بصدق
      مع حدود دليلهما الحديث.
    - المكونات البوليمرية (بيتا جلوكان الشعير) خارج نطاق التحال الجزيئي
      وتُذكر في ملاحظات المصادر لا في المكتبة الجزيئية.
"""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field
from sklearn.ensemble import RandomForestRegressor

from pharma_sdl.active_learning import featurize
from pharma_sdl.experiments.registry import (
    ExperimentRecord,
    code_version,
    dataset_fingerprint,
)

# ─────────────────────────────────────────────────────────────
# التوثيق التراثي — تخريج دقيق (تدقيق 2026-11-02)
# ─────────────────────────────────────────────────────────────

HADITH_GRADES: tuple[str, ...] = ("متفق عليه", "صحيح", "قرآن")
"""الدرجات المسموح دخولها للمكتبة — لا حديث ضعيف ولا غير متخَرَّج."""


class HadithDoc(BaseModel):
    """توثيق تراثي واحد بدرجته الفعلية ومرجعه وراويه."""

    text_ar: str
    grade: str  # عنصر HADITH_GRADES حصراً
    reference: str  # «البخاري 5687 + مسلم 2213»
    narrator: str

    def model_post_init(self, __context: object, /) -> None:
        if self.grade not in HADITH_GRADES:
            raise ValueError(
                f"درجة حديث غير مقبولة: {self.grade} — المسموح: {', '.join(HADITH_GRADES)}"
            )


# مواد المكتبة الثلاث — كل مادة بأقوى توثيق متخَرَّج لها
HONEY_HADITH = HadithDoc(
    text_ar=(
        "«الشفاء في ثلاثة: شرطة محجم، أو شربة عسل، أو كية نار، وأنا أنهى أمتي "
        "عن الكي» — والعسل ذُكر في القرآن: «يخرج من بطونها شراب مختلف ألوانه "
        "فيه شفاء للناس»."
    ),
    grade="متفق عليه",
    reference="البخاري 5680 (ابن عباس)؛ والآية: النحل 69",
    narrator="عبد الله بن عباس",
)

BLACK_SEED_HADITH = HadithDoc(
    text_ar=(
        "«إن هذه الحبة السوداء شفاء من كل داء إلا من السام» — قيل: وما السام؟ "
        "قال: الموت."
    ),
    grade="متفق عليه",
    reference="البخاري 5687 و5688 + مسلم 2213",
    narrator="عائشة أم المؤمنين",
)

BARLEY_HADITH = HadithDoc(
    text_ar=(
        "«إن التلبينة تجمّ فؤاد المريض وتذهب ببعض الحزن» — والتلبينة دقيق "
        "الشعير المخلوق في الحليب."
    ),
    grade="متفق عليه",
    reference="البخاري 5417 + مسلم 2216",
    narrator="عائشة أم المؤمنين",
)

CUPPING_HADITH = HadithDoc(
    text_ar="«خير ما تداويتم به الحجامة» — وفي لفظ: الحجامة والقسط البحري.",
    grade="متفق عليه",
    reference="البخاري 5696 + مسلم 1577",
    narrator="عائشة أم المؤمنين",
)

# ─────────────────────────────────────────────────────────────
# الدليل الحديث — طبقات أدلة بمرجع منشور لكل مادة
# ─────────────────────────────────────────────────────────────

EVIDENCE_TIERS: tuple[str, ...] = (
    "T0_traditional",
    "T1_invitro",
    "T2_preclinical",
    "T3_clinical",
)

TIER_LABELS: dict[str, str] = {
    "T0_traditional": "توثيق تراثي فقط",
    "T1_invitro": "مخبري (in-vitro)",
    "T2_preclinical": "قبل سريري (حيواني/مخبري موسع)",
    "T3_clinical": "سريري (تجارب بشرية)",
}


class NaturalCompound(BaseModel):
    """مركب طبيعي واحد بجزيئه المعلن وتوثيقه المزدوج (تراثي + حديث)."""

    name_ar: str
    name_en: str
    smiles: str
    formula: str  # تُدقَّق ضد CalcMolFormula في الاختبارات
    molecular_weight: float
    pubchem_cid: int
    source: str  # العسل | حبة البركة | الشعير
    source_hadith: HadithDoc
    evidence_tier: str  # عنصر EVIDENCE_TIERS
    evidence_note: str  # مرجع منشور واحد على الأقل
    hadith: HadithDoc | None = None  # توثيق خاص بالمركب إن وُجد


# صيغPubChem الموثقة (جُلبت بتاريخ 2026-11-02 عبر PUG REST ودُقّقت)
COMPOUNDS: tuple[NaturalCompound, ...] = (
    # ── العسل ──
    NaturalCompound(
        name_ar="ميثيل جليوكسال",
        name_en="methylglyoxal",
        smiles="CC(=O)C=O",
        formula="C3H4O2",
        molecular_weight=72.06,
        pubchem_cid=880,
        source="العسل",
        source_hadith=HONEY_HADITH,
        evidence_tier="T1_invitro",
        evidence_note=(
            "المكوّن الحامل للنشاط البكتيري القاتل في عسل المانوكا — مرتبط "
            "بمؤشر UMF: Johnston et al. 2018, AIMS Microbiology 4(4):655 "
            "(PMC6613335)؛ والمرتبة السريرية للعسل الطبي في الجروح: Nolan "
            "2020, Antibiotics 9(11):766."
        ),
    ),
    NaturalCompound(
        name_ar="أبيجينين",
        name_en="apigenin",
        smiles="C1=CC(=CC=C1C2=CC(=O)C3=C(C=C(C=C3O2)O)O)O",
        formula="C15H10O5",
        molecular_weight=270.24,
        pubchem_cid=5280443,
        source="العسل",
        source_hadith=HONEY_HADITH,
        evidence_tier="T1_invitro",
        evidence_note="فلافون شائع في العسل — أدلة مخبرية مضادة للالتهاب دون تجارب سريرية حاسمة.",
    ),
    NaturalCompound(
        name_ar="كريسين",
        name_en="chrysin",
        smiles="C1=CC=C(C=C1)C2=CC(=O)C3=C(C=C(C=C3O2)O)O",
        formula="C15H10O4",
        molecular_weight=254.24,
        pubchem_cid=5281607,
        source="العسل",
        source_hadith=HONEY_HADITH,
        evidence_tier="T1_invitro",
        evidence_note="فلافون من البروبوليس والعسل — أدلة مخبرية أساسية.",
    ),
    NaturalCompound(
        name_ar="جالانجين",
        name_en="galangin",
        smiles="C1=CC=C(C=C1)C2=C(C(=O)C3=C(C=C(C=C3O2)O)O)O",
        formula="C15H10O5",
        molecular_weight=270.24,
        pubchem_cid=5281616,
        source="العسل",
        source_hadith=HONEY_HADITH,
        evidence_tier="T1_invitro",
        evidence_note="فلافونول من البروبوليس — نشاط مخبري مضاد ميكروبي موثق.",
    ),
    NaturalCompound(
        name_ar="بينوسمبرين",
        name_en="pinocembrin",
        smiles="O=C1CC(c2ccccc2)Oc2cc(O)cc(O)c12",  # 5,7-dihydroxyflavanone
        formula="C15H12O4",
        molecular_weight=256.25,
        pubchem_cid=68071,
        source="العسل",
        source_hadith=HONEY_HADITH,
        evidence_tier="T1_invitro",
        evidence_note="فلافانون رئيسي في البروبوليس — أدلة مخبرية.",
    ),
    NaturalCompound(
        name_ar="حمض الكافيين",
        name_en="caffeic acid",
        smiles="OC(=O)/C=C/c1ccc(O)c(O)c1",
        formula="C9H8O4",
        molecular_weight=180.16,
        pubchem_cid=689043,
        source="العسل",
        source_hadith=HONEY_HADITH,
        evidence_tier="T1_invitro",
        evidence_note="حمض فينولي شائع في العسائل — نشاط مخبري مضاد أكسدة.",
    ),
    NaturalCompound(
        name_ar="إستر الكافيين الفينيثيلي (CAPE)",
        name_en="caffeic acid phenethyl ester",
        smiles="O=C(OCCc1ccccc1)/C=C/c1ccc(O)c(O)c1",
        formula="C17H16O4",
        molecular_weight=284.31,
        pubchem_cid=5281787,
        source="العسل",
        source_hadith=HONEY_HADITH,
        evidence_tier="T1_invitro",
        evidence_note="مكوّن بروبوليس رئيسي — مثبط NF-κB مخبري موسوع دون تجارب سريرية حاسمة.",
    ),
    NaturalCompound(
        name_ar="كيرسيتين",
        name_en="quercetin",
        smiles="O=c1c(O)c(-c2ccc(O)c(O)c2)oc2cc(O)cc(O)c12",
        formula="C15H10O7",
        molecular_weight=302.23,
        pubchem_cid=5280343,
        source="العسل",
        source_hadith=HONEY_HADITH,
        evidence_tier="T1_invitro",
        evidence_note="فلافونول واسع التواجد في العسائل — أدلة مخبرية وفيرة وحيوية منخفضة.",
    ),
    NaturalCompound(
        name_ar="كامبفيرول",
        name_en="kaempferol",
        smiles="O=c1c(O)c(-c2ccc(O)cc2)oc2cc(O)cc(O)c12",
        formula="C15H10O6",
        molecular_weight=286.24,
        pubchem_cid=5280863,
        source="العسل",
        source_hadith=HONEY_HADITH,
        evidence_tier="T1_invitro",
        evidence_note="فلافونول من العسل والبروبوليس — أدلة مخبرية.",
    ),
    # ── حبة البركة ──
    NaturalCompound(
        name_ar="ثيموكينون",
        name_en="thymoquinone",
        smiles="CC(C)C1=CC(=O)C(C)=CC1=O",
        formula="C10H12O2",
        molecular_weight=164.2,
        pubchem_cid=10281,
        source="حبة البركة",
        source_hadith=BLACK_SEED_HADITH,
        evidence_tier="T2_preclinical",
        evidence_note=(
            "المركّب المحوري لزيت حبة البركة: أدلة قبل سريرية واسعة وتجارب "
            "سريرية أولية صغيرة (سكري/ربو/التهاب مفاصل) — Tavakkoli et al. "
            "2017, J Pharmacopuncture 20(3):179 (PMC5633670)؛ مراجعة شاملة: "
            "Int J Mol Sci 2024, 25(24):13410 (PMC11677364)."
        ),
    ),
    NaturalCompound(
        name_ar="ثيموهيدروكينون",
        name_en="thymohydroquinone",
        smiles="CC(C)c1cc(C)cc(O)c1O",
        formula="C10H14O2",
        molecular_weight=166.22,
        pubchem_cid=95779,
        source="حبة البركة",
        source_hadith=BLACK_SEED_HADITH,
        evidence_tier="T1_invitro",
        evidence_note="الشكل المختزل للثيموكينون في الزيت — أدلة مخبرية.",
    ),
    NaturalCompound(
        name_ar="ثيمول",
        name_en="thymol",
        smiles="CC(C)c1ccc(C)cc1O",
        formula="C10H14O",
        molecular_weight=150.22,
        pubchem_cid=6989,
        source="حبة البركة",
        source_hadith=BLACK_SEED_HADITH,
        evidence_tier="T1_invitro",
        evidence_note="مونوتربين فينولي من الزيت العطري — مضاد ميكروبي مخبري معروف.",
    ),
    NaturalCompound(
        name_ar="كارفاكرول",
        name_en="carvacrol",
        smiles="Cc1ccc(C(C)C)c(O)c1",
        formula="C10H14O",
        molecular_weight=150.22,
        pubchem_cid=10364,
        source="حبة البركة",
        source_hadith=BLACK_SEED_HADITH,
        evidence_tier="T1_invitro",
        evidence_note="متزامر الثيمول في الزيت — نشاط مخبري مضاد ميكروبي.",
    ),
    NaturalCompound(
        name_ar="بارا-سيمين",
        name_en="p-cymene",
        smiles="Cc1ccc(C(C)C)cc1",
        formula="C10H14",
        molecular_weight=134.22,
        pubchem_cid=7463,
        source="حبة البركة",
        source_hadith=BLACK_SEED_HADITH,
        evidence_tier="T1_invitro",
        evidence_note="مونوتربين عطري رئيسي في زيت البذور — أدلة مخبرية.",
    ),
    NaturalCompound(
        name_ar="أنيثول (متحوّل)",
        name_en="trans-anethole",
        smiles="C/C=C/c1ccc(OC)cc1",
        formula="C10H12O",
        molecular_weight=148.2,
        pubchem_cid=637563,
        source="حبة البركة",
        source_hadith=BLACK_SEED_HADITH,
        evidence_tier="T1_invitro",
        evidence_note="مكوّن عطري في الزيت — أدلة مخبرية أساسية.",
    ),
    # ── الشعير ──
    NaturalCompound(
        name_ar="حمض الفيروليك",
        name_en="ferulic acid",
        smiles="COc1cc(/C=C/C(=O)O)ccc1O",
        formula="C10H10O4",
        molecular_weight=194.18,
        pubchem_cid=445858,
        source="الشعير",
        source_hadith=BARLEY_HADITH,
        evidence_tier="T1_invitro",
        evidence_note="أهم حمض فينولي في نخالة الشعير — أدلة مخبرية مضادة أكسدة.",
    ),
    NaturalCompound(
        name_ar="حمض بارا-الكوماريك",
        name_en="p-coumaric acid",
        smiles="O=C(O)/C=C/c1ccc(O)cc1",
        formula="C9H8O3",
        molecular_weight=164.16,
        pubchem_cid=637542,
        source="الشعير",
        source_hadith=BARLEY_HADITH,
        evidence_tier="T1_invitro",
        evidence_note="حمض فينولي في حبة الشعير — أدلة مخبرية.",
    ),
)

# ─────────────────────────────────────────────────────────────
# الإجراءات العلاجية — بلا جزيء، لا دخول لها في المسار الحاسوبي
# ─────────────────────────────────────────────────────────────


class PropheticProcedure(BaseModel):
    """إجراء علاجي نبوي — يُوثَّق بصدق ولا يُفرَز حاسوبياً أبداً."""

    name_ar: str
    name_en: str
    hadith: HadithDoc
    evidence_tier: str
    evidence_note: str
    computational_note: str = (
        "إجراء علاجي لا جزيء له — خارج المسار الحاسوبي بنيوياً."
    )


PROCEDURES: tuple[PropheticProcedure, ...] = (
    PropheticProcedure(
        name_ar="الحجامة (شرطة المحجم)",
        name_en="wet cupping",
        hadith=CUPPING_HADITH,
        evidence_tier="T2_preclinical",
        evidence_note=(
            "مراجعات منهجية للحجامة الرطبة (آلام الجانب/الظهر) تعطي إشارات "
            "إيجابية بجودة دراسات متفاوتة — ليست أدلة حاسمة، ولا يُستخرج منها "
            "مكوّن جزيئي."
        ),
    ),
    PropheticProcedure(
        name_ar="الكاي",
        name_en="cauterization",
        hadith=CUPPING_HADITH.model_copy(
            update={
                "text_ar": (
                    "«الشفاء في ثلاثة: شرطة محجم، أو شربة عسل، أو كية نار، "
                    "وأنا أنهى أمتي عن الكي» — الذكر مقرون بنهي النبي ﷺ عنه."
                )
            }
        ),
        evidence_tier="T0_traditional",
        evidence_note=(
            "توثيق تراثي مقرون بنهٍ صريح في الحديث ذاته؛ لا دليل سريري حديث "
            "يرجّح استخدامه العلاجي — يُوثَّق تاريخياً فقط."
        ),
    ),
)

SOURCE_NOTES: dict[str, str] = {
    "الشعير": (
        "بيتا جلوكان الشعير بوليمر خارج نطاق التحال الجزيئي (لا جزيء واحداً "
        "يمثله) — ودليله السريري لخفض الكوليسترول أقوى دليل في المكتبة كلها "
        "ادعاء صحي منشور لدى FDA (21 CFR 101.81) — فيُوثَّق هنا دون تمثيل "
        "جزيئي، ولا يُحاكَم حاسوبياً."
    ),
}


# ─────────────────────────────────────────────────────────────
# الصدق بنيوياً — إخلاءات المكتبة
# ─────────────────────────────────────────────────────────────

DISCLAIMER_AR = (
    "تنبيه علمي/طبي/شرعي: ذكر المادة في القرآن أو السنة توثيقٌ تراثي ثقافي "
    "ثمين، وهو ليس دليلاً على فعالية سريرية ولا إجازة لعلاج ذاتي — الدليل "
    "العلمي طبقة منفصلة تُقاس بمعايير الطب الحديث، وكل مخرج حاسوبي هنا "
    "UNVALIDATED داخل خط درجة مستقل لا يُقارن أبداً بدرجات الالتحام أو "
    "القياسات المخبرية. لا تُستخدم هذه المكتبة بديلاً عن استشارة مختص."
)

DISCLAIMER_EN = (
    "Scientific/medical notice: a mention in the Quran or the Sunnah is a "
    "precious historical/cultural documentation, not clinical-efficacy "
    "evidence nor a licence for self-treatment — the modern-evidence layer is "
    "separate and measured by contemporary medical standards, and every "
    "computational output here stays UNVALIDATED inside a declared score lane "
    "never compared with docking scores or assay measurements. This library "
    "is no substitute for professional medical advice."
)


def library_summary() -> dict:
    """ملخص المكتبة بأعداد صادقة + الإخلاءات — كما هي في الـAPI والتقارير."""
    by_source: dict[str, int] = {}
    by_tier: dict[str, int] = {}
    for c in COMPOUNDS:
        by_source[c.source] = by_source.get(c.source, 0) + 1
        by_tier[c.evidence_tier] = by_tier.get(c.evidence_tier, 0) + 1
    return {
        "n_compounds": len(COMPOUNDS),
        "n_procedures": len(PROCEDURES),
        "by_source": by_source,
        "by_evidence_tier": by_tier,
        "hadith_grades": sorted({c.source_hadith.grade for c in COMPOUNDS}),
        "disclaimer_ar": DISCLAIMER_AR,
        "disclaimer_en": DISCLAIMER_EN,
        "source_notes": SOURCE_NOTES,
    }


# ─────────────────────────────────────────────────────────────
# الفرز الحاسوبي — نموذج الإنتاج نفسه، خط predicted_potency حصراً
# ─────────────────────────────────────────────────────────────

DATASET_CSV = Path(__file__).resolve().parent.parent / "data" / "mpro_sample.csv"
TARGET_ID = "CHEMBL4523582"  # MPRO — الهدف الإنتاجي الوحيد المُدرَّب


class ScreenRow(BaseModel):
    """صف فرز واحد — تنبؤ في مساره المعلن وحالته المعلنة."""

    name_ar: str
    name_en: str
    smiles: str
    source: str
    pubchem_cid: int
    predicted_pic50: float  # خط predicted_potency حصراً
    tree_std: float  # إشارة ترتيب (تدقيق P0) — ليست فترة ثقة
    lane: str = "predicted_potency"
    validation_state: str = "UNVALIDATED"


class ScreenReport(BaseModel):
    """تقرير فرز المكتبة — حتمي بالبذرة، قابل للتسلسل JSON."""

    target_id: str
    lane: str = "predicted_potency"
    dataset: str
    dataset_fingerprint: str
    n_dataset: int
    n_compounds: int
    n_estimators: int
    seed: int
    rows: list[ScreenRow] = Field(default_factory=list)
    rank_signal_note_ar: str = (
        "tree_std إشارة ترتيب (انحراف أشجار RF) مرتبطة بالخطأ إرتباطاً رتبياً "
        "موثقاً في تدقيق P0 — وليست فترة ثقة ولا وعد تغطية."
    )
    rank_signal_note_en: str = (
        "tree_std is a ranking signal (RF tree dispersion) with documented "
        "rank correlation to error (P0 audit) — not a confidence interval."
    )
    disclaimer_ar: str = DISCLAIMER_AR
    disclaimer_en: str = DISCLAIMER_EN
    runtime_seconds: float = 0.0


def _display_path(p: Path) -> str:
    try:
        return str(p.resolve().relative_to(Path(__file__).resolve().parent.parent))
    except ValueError:
        return str(p)


def run_library_screen(
    dataset_csv: str | Path | None = None,
    *,
    n_estimators: int = 300,
    seed: int = 0,
    registry: object | None = None,
) -> ScreenReport:
    """تدريب نموذج الإنتاج على بيانات MPRO ثم فرز مكتبة الطب النبوي.

    الالتزامات:
        - التمثيل نفسه (active_learning.featurize — تطابق core.ml_potency
          مُختبر تقاطعياً منذ P4).
        - التنبؤ أحادي الخيط بعد الملاءمة المتوازية — الحتمية عقد (درس ADR-0009).
        - كل صف UNVALIDATED في خط predicted_potency — لا درجة docking هنا.
    """
    if n_estimators < 10:
        raise ValueError("n_estimators must be >= 10")
    csv_path = Path(dataset_csv) if dataset_csv else DATASET_CSV
    t0 = time.perf_counter()

    df = pd.read_csv(csv_path)
    df = df.dropna(subset=["smiles", "pchembl_value"]).reset_index(drop=True)
    ds_smiles = df["smiles"].astype(str).tolist()
    ds_y = df["pchembl_value"].to_numpy(dtype=float)
    X_ds, ds_idx = featurize(ds_smiles)
    y_ds = ds_y[ds_idx]
    data_fp = dataset_fingerprint(csv_path)

    model = RandomForestRegressor(
        n_estimators=n_estimators, random_state=seed, n_jobs=-1
    )
    model.fit(X_ds, y_ds)
    model.n_jobs = 1  # الحتمية — درس ADR-0009

    lib_smiles = [c.smiles for c in COMPOUNDS]
    X_lib, lib_idx = featurize(lib_smiles)
    preds = model.predict(X_lib)  # التنبؤ المتوسط — أحادي الخيط بدرس ADR-0009
    tree_std_val = np.stack(
        [est.predict(X_lib) for est in model.estimators_]
    ).std(axis=0)  # إشارة ترتيب — ليست فترة ثقة

    order = np.argsort(-preds, kind="stable")
    rows: list[ScreenRow] = []
    for i_local in order:
        c = COMPOUNDS[lib_idx[i_local]]
        rows.append(
            ScreenRow(
                name_ar=c.name_ar,
                name_en=c.name_en,
                smiles=c.smiles,
                source=c.source,
                pubchem_cid=c.pubchem_cid,
                predicted_pic50=round(float(preds[i_local]), 3),
                tree_std=round(float(tree_std_val[i_local]), 4),
            )
        )

    report = ScreenReport(
        target_id=TARGET_ID,
        dataset=_display_path(csv_path),
        dataset_fingerprint=data_fp,
        n_dataset=len(ds_idx),
        n_compounds=len(rows),
        n_estimators=n_estimators,
        seed=seed,
        rows=rows,
        runtime_seconds=round(time.perf_counter() - t0, 1),
    )

    if registry is not None:
        record = registry.begin(
            ExperimentRecord(
                kind="natural_products_screen",
                hypothesis_ar=(
                    "مكونات مكتبة الطب النبوي لها تنبؤات فعالية على MPRO "
                    "تستحق الأولوية التجريبية؟"
                ),
                hypothesis_en=(
                    "Do Prophetic-library constituents yield MPRO potency "
                    "predictions worth experimental triage?"
                ),
                question=(
                    f"ما ترتيب {len(rows)} مركباً من المكتبة النبوية على نموذج "
                    f"الإنتاج ({n_estimators} شجرة، بذرة {seed})؟"
                ),
                target_id=TARGET_ID,
                engine_used="sklearn-rf",
                method="prophetic_library_screen",
                data_version=data_fp,
                code_version=code_version(),
                parameters={
                    "n_compounds": len(rows),
                    "n_estimators": n_estimators,
                    "seed": seed,
                    "lane": "predicted_potency",
                    "oracle": "none_model_prediction_only",
                },
            )
        )
        registry.complete(
            record.experiment_id,
            counts={"compounds_screened": len(rows)},
            top_hits=[
                {"name_en": r.name_en, "predicted_pic50": r.predicted_pic50}
                for r in rows[:5]
            ],
            elapsed_seconds=report.runtime_seconds,
            engine_used="sklearn-rf",
            method="prophetic_library_screen",
            lesson=(
                "فرز مكتبة الطب النبوي على نموذج MPRO الإنتاجي — تنبؤات "
                "UNVALIDATED في خط predicted_potency؛ التوثيق التراثي لا "
                "يُنتج درجات."
            ),
        )

    return report


__all__ = [
    "COMPOUNDS",
    "EVIDENCE_TIERS",
    "HADITH_GRADES",
    "PROCEDURES",
    "SOURCE_NOTES",
    "TIER_LABELS",
    "PropheticProcedure",
    "ScreenReport",
    "ScreenRow",
    "library_summary",
    "run_library_screen",
]
