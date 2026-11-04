"""عميل ADMET-AI v2 — 41 نقطة نهاية ADMET بنماذج Chemprop متعددة المهام.

المرجع (خطوة التحقق 2026-11-04، كما تقتضي docs/INTEGRATION-ROADMAP.md:
«لا تبنِ إنتاجاً قبل خطوة تحقق واحدة»):

- ADMET-AI v2.0.1 (Harvard/AP-BSL، swansonk14/admet_ai) — رخصة MIT للكود.
  مُدرَّب على بيانات ADMET من Therapeutics Data Commons بمجموعة من 5 طيّات
  لنموذجين متعددي المهام (تصنيف + انحدار) — النماذج مضمّنة في الحزمة نفسها
  (‏~13MB) فلا حاجة لشبكة عند أول استخدام، والاستدلال CPU كافٍ.
- عقد المخرجات الموثَّق من كود الحزمة (admet_ai/admet_model.py):
  predict(smiles=...) يُرجع dict لجزيء واحد أو DataFrame لأكثر من جزيء،
  أعمدته: 41 مهمة ML (31 تصنيف [0..1] + 10 انحدار بوحداتها الرسمية)
  + 3 إنذارات بنيوية قاعدية (PAINS/BRENK/NIH) + 8 وصفات فيزيوكيميائية
  + عمود مئين مقابل الأدوية المعتمدة في DrugBank لكل ما سبق
  (‏"<task>_drugbank_approved_percentile").
- القياس الحي في بيئة المشروع موثّق ومجمَّد في
  docs/audit/model-admet-ai-p13-results.json (لوحة أدوية مرجعية).

المبدأ الحاكم (نمط ersilia_client): الحزمة الاختيارية غائبة أو فشل
الاستدلال لا يرمي استثناءً للواجهة — تُرجَع قائمة فارغة مع تلميح تثبيت،
والأحكام على القيم إرشادية تعليمية بلا ادعاء سريري أو تنظيمي.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# كتالوج المهام الـ41 — الأسماء الإنجليزية الرسمية من admet.csv
# (admet_ai/resources/data/admet.csv) والوحدات كما سجّلتها الحزمة.
# ─────────────────────────────────────────────────────────────

KIND_CLASSIFICATION = "classification"
KIND_REGRESSION = "regression"
KIND_ALERT = "structural_alert"
KIND_PHYSCHEM = "physchem"


@dataclass(frozen=True)
class AdmetAITask:
    """بطاقة نقطة نهاية ADMET-AI موثّقة — للتبويب ولتفسير المخرجات."""

    task_id: str  # اسم العمود في مخرجات ADMET-AI حرفياً
    name_ar: str
    name_en: str
    unit_ar: str
    unit_en: str
    kind: str  # classification | regression | structural_alert | physchem
    low_good: bool | None  # None = معلوماتية (الاتجاه يعتمد على السياق)
    family_ar: str  # العائلة الوظيفية (سمية/امتصاص/استقلاب/…)
    family_en: str


_CLASSIFICATION_TASKS: tuple[AdmetAITask, ...] = (
    AdmetAITask("AMES", "المطفرات (اختبار أمز)", "Mutagenicity (Ames test)", "احتمال [0..1]", "probability [0..1]", KIND_CLASSIFICATION, True, "سمية جينية", "Genetic toxicity"),
    AdmetAITask("BBB_Martins", "نفاذية الحاجز الدماغي", "Blood-Brain Barrier Penetration", "احتمال [0..1]", "probability [0..1]", KIND_CLASSIFICATION, None, "نقل", "Distribution"),
    AdmetAITask("Bioavailability_Ma", "التوافر الحيوي الفموي (F ≥ 30%)", "Oral Bioavailability (F ≥ 30%)", "احتمال [0..1]", "probability [0..1]", KIND_CLASSIFICATION, False, "امتصاص", "Absorption"),
    AdmetAITask("CYP1A2_Veith", "تثبيط CYP1A2", "CYP1A2 Inhibition", "احتمال [0..1]", "probability [0..1]", KIND_CLASSIFICATION, True, "استقلاب", "Metabolism"),
    AdmetAITask("CYP2C19_Veith", "تثبيط CYP2C19", "CYP2C19 Inhibition", "احتمال [0..1]", "probability [0..1]", KIND_CLASSIFICATION, True, "استقلاب", "Metabolism"),
    AdmetAITask("CYP2C9_Veith", "تثبيط CYP2C9", "CYP2C9 Inhibition", "احتمال [0..1]", "probability [0..1]", KIND_CLASSIFICATION, True, "استقلاب", "Metabolism"),
    AdmetAITask("CYP2D6_Veith", "تثبيط CYP2D6", "CYP2D6 Inhibition", "احتمال [0..1]", "probability [0..1]", KIND_CLASSIFICATION, True, "استقلاب", "Metabolism"),
    AdmetAITask("CYP3A4_Veith", "تثبيط CYP3A4", "CYP3A4 Inhibition", "احتمال [0..1]", "probability [0..1]", KIND_CLASSIFICATION, True, "استقلاب", "Metabolism"),
    AdmetAITask("CYP2C9_Substrate_CarbonMangels", "ركيزة CYP2C9", "CYP2C9 Substrate", "احتمال [0..1]", "probability [0..1]", KIND_CLASSIFICATION, None, "استقلاب", "Metabolism"),
    AdmetAITask("CYP2D6_Substrate_CarbonMangels", "ركيزة CYP2D6", "CYP2D6 Substrate", "احتمال [0..1]", "probability [0..1]", KIND_CLASSIFICATION, None, "استقلاب", "Metabolism"),
    AdmetAITask("CYP3A4_Substrate_CarbonMangels", "ركيزة CYP3A4", "CYP3A4 Substrate", "احتمال [0..1]", "probability [0..1]", KIND_CLASSIFICATION, None, "استقلاب", "Metabolism"),
    AdmetAITask("Carcinogens_Lagunin", "السرطنة", "Carcinogenicity", "احتمال [0..1]", "probability [0..1]", KIND_CLASSIFICATION, True, "سمية", "Toxicity"),
    AdmetAITask("ClinTox", "السمية السريرية (سحب/فشل تجارب)", "Clinical Toxicity (withdrawn/failed trials)", "احتمال [0..1]", "probability [0..1]", KIND_CLASSIFICATION, True, "سمية", "Toxicity"),
    AdmetAITask("DILI", "إصابة الكبد الدوائية", "Drug-Induced Liver Injury", "احتمال [0..1]", "probability [0..1]", KIND_CLASSIFICATION, True, "سمية", "Toxicity"),
    AdmetAITask("HIA_Hou", "الامتصاص المعوي البشري", "Human Intestinal Absorption", "احتمال [0..1]", "probability [0..1]", KIND_CLASSIFICATION, False, "امتصاص", "Absorption"),
    AdmetAITask("PAMPA_NCATS", "نفاذية PAMPA", "PAMPA Permeability", "احتمال [0..1]", "probability [0..1]", KIND_CLASSIFICATION, False, "امتصاص", "Absorption"),
    AdmetAITask("Pgp_Broccatelli", "تثبيط مضخة P-glycoprotein", "P-glycoprotein Inhibition", "احتمال [0..1]", "probability [0..1]", KIND_CLASSIFICATION, None, "نقل", "Distribution"),
    AdmetAITask("hERG", "حجب قناة hERG (سمية قلبية)", "hERG Blocking (cardiotoxicity)", "احتمال [0..1]", "probability [0..1]", KIND_CLASSIFICATION, True, "سمية", "Toxicity"),
    AdmetAITask("Skin_Reaction", "التحسس الجلدي", "Skin Reaction (sensitization)", "احتمال [0..1]", "probability [0..1]", KIND_CLASSIFICATION, True, "سمية", "Toxicity"),
    AdmetAITask("NR-AR", "مستقبل الأندروجين (طول كامل)", "Androgen Receptor (full length)", "احتمال [0..1]", "probability [0..1]", KIND_CLASSIFICATION, True, "نشاط نووي", "Nuclear receptor"),
    AdmetAITask("NR-AR-LBD", "مجال ربط الأندروجين (LBD)", "Androgen Receptor (ligand-binding domain)", "احتمال [0..1]", "probability [0..1]", KIND_CLASSIFICATION, True, "نشاط نووي", "Nuclear receptor"),
    AdmetAITask("NR-AhR", "مستقبل أريل هيدروكربون AhR", "Aryl Hydrocarbon Receptor", "احتمال [0..1]", "probability [0..1]", KIND_CLASSIFICATION, True, "نشاط نووي", "Nuclear receptor"),
    AdmetAITask("NR-Aromatase", "تثبيط الأروماتاز", "Aromatase inhibition", "احتمال [0..1]", "probability [0..1]", KIND_CLASSIFICATION, True, "نشاط نووي", "Nuclear receptor"),
    AdmetAITask("NR-ER", "مستقبل الإستروجين (طول كامل)", "Estrogen Receptor (full length)", "احتمال [0..1]", "probability [0..1]", KIND_CLASSIFICATION, True, "نشاط نووي", "Nuclear receptor"),
    AdmetAITask("NR-ER-LBD", "مجال ربط الإستروجين (LBD)", "Estrogen Receptor (ligand-binding domain)", "احتمال [0..1]", "probability [0..1]", KIND_CLASSIFICATION, True, "نشاط نووي", "Nuclear receptor"),
    AdmetAITask("NR-PPAR-gamma", "مستقبل PPAR-gamma", "PPAR-gamma", "احتمال [0..1]", "probability [0..1]", KIND_CLASSIFICATION, True, "نشاط نووي", "Nuclear receptor"),
    AdmetAITask("SR-ARE", "مسار الاستجابة المضادة للأكسدة ARE", "Antioxidant Response Element (ARE)", "احتمال [0..1]", "probability [0..1]", KIND_CLASSIFICATION, True, "مسارات إجهاد", "Stress response"),
    AdmetAITask("SR-ATAD5", "إصابة الـDNA (ATAD5)", "DNA damage (ATAD5)", "احتمال [0..1]", "probability [0..1]", KIND_CLASSIFICATION, True, "مسارات إجهاد", "Stress response"),
    AdmetAITask("SR-HSE", "مسار صدمة الحرارة HSE", "Heat Shock Response Element", "احتمال [0..1]", "probability [0..1]", KIND_CLASSIFICATION, True, "مسارات إجهاد", "Stress response"),
    AdmetAITask("SR-MMP", "اختلال غشاء الميتوكوندريا", "Mitochondrial Membrane Potential", "احتمال [0..1]", "probability [0..1]", KIND_CLASSIFICATION, True, "مسارات إجهاد", "Stress response"),
    AdmetAITask("SR-p53", "مسار ورم p53", "Tumor protein p53 pathway", "احتمال [0..1]", "probability [0..1]", KIND_CLASSIFICATION, True, "مسارات إجهاد", "Stress response"),
)

_REGRESSION_TASKS: tuple[AdmetAITask, ...] = (
    AdmetAITask("Caco2_Wang", "نفاذية Caco-2 الخلوية", "Caco-2 cell permeability", "log(10^-6 cm/s)", "log(10^-6 cm/s)", KIND_REGRESSION, False, "امتصاص", "Absorption"),
    AdmetAITask("Clearance_Hepatocyte_AZ", "التصفية الخلوية الكبدية", "Hepatocyte clearance", "µL/min/10^6 خلية", "µL/min/10^6 cells", KIND_REGRESSION, True, "تصفية", "Clearance"),
    AdmetAITask("Clearance_Microsome_AZ", "التصفية المجهرية", "Microsomal clearance", "µL/min/mg", "µL/min/mg", KIND_REGRESSION, True, "تصفية", "Clearance"),
    AdmetAITask("Half_Life_Obach", "عمر النصف (نموذج Obach)", "Half-life (Obach model)", "ساعة", "hr", KIND_REGRESSION, None, "توزّع", "Distribution"),
    AdmetAITask("HydrationFreeEnergy_FreeSolv", "طاقة الإماهة الحرة", "Hydration Free Energy", "kcal/mol", "kcal/mol", KIND_REGRESSION, None, "فيزيائي", "Physical"),
    AdmetAITask("LD50_Zhu", "السمية الحادة LD50", "Acute Toxicity LD50", "log(1/(mol/kg))", "log(1/(mol/kg))", KIND_REGRESSION, True, "سمية", "Toxicity"),
    AdmetAITask("Lipophilicity_AstraZeneca", "الليبوفيلية المقاسة (AstraZeneca)", "Measured Lipophilicity (AstraZeneca)", "نسبة لوغاريتمية logD", "log-ratio", KIND_REGRESSION, None, "فيزيائي", "Physical"),
    AdmetAITask("PPBR_AZ", "ارتباط بروتينات البلازما", "Plasma Protein Binding Rate", "%", "%", KIND_REGRESSION, None, "توزّع", "Distribution"),
    AdmetAITask("Solubility_AqSolDB", "الذوبانية المائية", "Aqueous Solubility", "log(mol/L)", "log(mol/L)", KIND_REGRESSION, False, "امتصاص", "Absorption"),
    AdmetAITask("VDss_Lombardo", "حجم التوزيع عند الثبات", "Volume of Distribution at Steady State", "L/kg", "L/kg", KIND_REGRESSION, None, "توزّع", "Distribution"),
)

_ALERT_TASKS: tuple[AdmetAITask, ...] = (
    AdmetAITask("PAINS_alert", "إنذار PAINS (مجمّعات كاذبة)", "PAINS Alert (frequent hitters)", "عدد", "count", KIND_ALERT, True, "إنذارات بنيوية", "Structural alerts"),
    AdmetAITask("BRENK_alert", "إنذار BRENK (هياكل غير مرغوبة)", "BRENK Alert (undesired substructures)", "عدد", "count", KIND_ALERT, True, "إنذارات بنيوية", "Structural alerts"),
    AdmetAITask("NIH_alert", "إنذار NIH (هياكل مزعجة)", "NIH Alert (nuisance structures)", "عدد", "count", KIND_ALERT, True, "إنذارات بنيوية", "Structural alerts"),
)

# 8 وصفات فيزيوكيميائية يحسبها ADMET-AI داخلياً (RDKit) — معلوماتية دائماً
_PHYSCHEM_TASKS: tuple[AdmetAITask, ...] = tuple(
    AdmetAITask(
        task_id=tid,
        name_ar=name_ar,
        name_en=name_en,
        unit_ar=unit_ar,
        unit_en=unit_en,
        kind=KIND_PHYSCHEM,
        low_good=None,
        family_ar="فيزيوكيميائي",
        family_en="Physicochemical",
    )
    for tid, name_ar, name_en, unit_ar, unit_en in (
        ("molecular_weight", "الوزن الجزيئي", "Molecular weight", "g/mol", "g/mol"),
        ("logP", "لوغاريتم التقسيم logP", "Partition coefficient logP", "بلا وحدة", "dimensionless"),
        ("hydrogen_bond_acceptors", "مستقبلات الروابط الهيدروجينية", "H-bond acceptors", "عدد", "count"),
        ("hydrogen_bond_donors", "مانحات الروابط الهيدروجينية", "H-bond donors", "عدد", "count"),
        ("Lipinski", "مخالفات قاعدة ليبنسكي", "Lipinski rule violations", "عدد", "count"),
        ("QED", "كثافة الدوائية التقديرية QED", "Quantitative Estimate of Drug-likeness", "0..1", "0..1"),
        ("stereo_centers", "مراكز فراغية", "Stereo centers", "عدد", "count"),
        ("tpsa", "المساحة السطحية القطبية TPSA", "Topological Polar Surface Area", "Å²", "Å²"),
    )
)

# السجل الكامل بالترتيب: تصنيف ← انحدار ← إنذارات ← فيزيوكيمياء
TASKS: dict[str, AdmetAITask] = {
    t.task_id: t
    for t in (*_CLASSIFICATION_TASKS, *_REGRESSION_TASKS, *_ALERT_TASKS, *_PHYSCHEM_TASKS)
}

# مهام ML الخزانة الـ41 فقط (بلا إنذارات قاعدية ولا وصفات)
ML_TASKS: tuple[str, ...] = tuple(
    t.task_id for t in (*_CLASSIFICATION_TASKS, *_REGRESSION_TASKS)
)
N_ML_TASKS = len(ML_TASKS)  # 41

# أعمدة المئين مقابل الأدوية المعتمدة في DrugBank — لاحقة ثابتة
PERCENTILE_SUFFIX = "_drugbank_approved_percentile"


def percentile_task_id(task_id: str) -> str:
    """معرّف عمود المئين الموافق لنقطة النهاية (يوجد لكل الأعمدة)."""
    return f"{task_id}{PERCENTILE_SUFFIX}"


# ─────────────────────────────────────────────────────────────
# التوفر والتحميل الكسول — الحزمة اختيارية، الغياب ليس خطأ
# ─────────────────────────────────────────────────────────────

_model = None  # singleton كاسول
_import_ok: bool | None = None  # None = لم يُفحص بعد (فصل التوفر عن التحميل)


def is_available() -> bool:
    """هل يمكن استيراد ADMET-AI في هذه البيئة؟ (فحص كسول يُخزَّن)."""
    global _import_ok
    if _import_ok is None:
        try:
            import admet_ai  # noqa: F401

            _import_ok = True
        except Exception:  # noqa: BLE001 — أي فشل استيراد (torch/chemprop/…) = غير متاح
            _import_ok = False
    return _import_ok


def get_model():
    """تحميل النموذج مرة واحدة — يُرجع None إن كانت الحزمة غير متاحة."""
    global _model
    if _model is not None:
        return _model
    if not is_available():
        return None
    from admet_ai import ADMETModel

    _model = ADMETModel()
    return _model


def reset_model() -> None:
    """إعادة ضبط الكاسول — للاختبارات فقط."""
    global _model, _import_ok
    _model = None
    _import_ok = None


# ─────────────────────────────────────────────────────────────
# صف النتيجة الموحّد
# ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class AdmetAIResult:
    """نتيجة تنبؤ جزيء واحد عبر ADMET-AI — قيم خام + مئينات DrugBank.

    values     : {task_id: قيمة} لكل الأعمدة غير المئينية (41 مهمة + 3 إنذارات + 8 وصفات)
    percentiles: {task_id: مئين} مقابل الأدوية المعتمدة في DrugBank (بلا اللاحقة)
    """

    smiles: str
    values: dict[str, float] = field(default_factory=dict)
    percentiles: dict[str, float] = field(default_factory=dict)

    def get(self, task_id: str) -> float | None:
        """قيمة نقطة نهاية بالمعرّف — None إن غابت (نقص صادق لا تزييف)."""
        v = self.values.get(task_id)
        return float(v) if v is not None else None

    def get_percentile(self, task_id: str) -> float | None:
        """المئين المقابل — None إن غاب."""
        v = self.percentiles.get(task_id)
        return float(v) if v is not None else None


def _to_float(x) -> float | None:
    """تحويل متساهل (pandas/numpy → float) — كل الفاشل → None."""
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    if f != f:  # NaN
        return None
    return f


def _parse_row(smiles: str, row: dict) -> AdmetAIResult:
    """صف من DataFrame الحزمة → AdmetAIResult (يحتمل الأعمدة الناقصة)."""
    values: dict[str, float] = {}
    percentiles: dict[str, float] = {}
    for key, raw in row.items():
        f = _to_float(raw)
        if f is None:
            continue
        if key.endswith(PERCENTILE_SUFFIX):
            percentiles[key[: -len(PERCENTILE_SUFFIX)]] = f
        else:
            values[key] = f
    return AdmetAIResult(smiles=smiles, values=values, percentiles=percentiles)


# ─────────────────────────────────────────────────────────────
# التنبؤ — النمط المعتمد: [] عند أي فشل (لا تنهار الواجهة)
# ─────────────────────────────────────────────────────────────

def predict_admet_ai_batch(smiles_list: list[str]) -> list[AdmetAIResult]:
    """تنبؤ دُفعة عبر ADMET-AI المحلي — نجاح جزئي مقبول، فشل كلي → [].

    - الجزيئات غير القابلة للتحليل تُرجِعها الحزمة عمود valid=False وتُستبعد.
    - أي استثناء (الحزمة غائبة/نفاد ذاكرة/…) → قائمة فارغة بلا استثناء.
    """
    clean = [s.strip() for s in smiles_list if s and s.strip()]
    if not clean:
        return []
    try:
        model = get_model()
        if model is None:
            return []
        df = model.predict(smiles=clean)
        # جزيء واحد قد يُرجَع dict — نوحّده دائماً كقاموس لكل جزيء
        if isinstance(df, dict):
            df_rows = [df]
        else:
            df_rows = df.to_dict(orient="records")
    except Exception:  # noqa: BLE001 — عقد الواجهة: لا استثناءات للعرض
        logger.warning("ADMET-AI prediction failed", exc_info=True)
        return []
    results: list[AdmetAIResult] = []
    valid_col = "valid"
    for smi, row in zip(clean, df_rows):
        # عمود valid المنطقي (إن وُجد) لا يُحتسب قيمة
        if valid_col in row and row[valid_col] in (False, 0, "False"):
            continue
        row = {k: v for k, v in row.items() if k != valid_col}
        results.append(_parse_row(smi, row))
    return results


# ─────────────────────────────────────────────────────────────
# الأحكام التعليمية على نقاط النهاية الرائدة — عتبات إرشادية موثّقة
# (ليست عتبات تنظيمية) — وتتّسق مع عتبات hERG في ersilia_client
# ─────────────────────────────────────────────────────────────

HERG_LOW, HERG_HIGH = 0.1, 0.3  # توحيد مع عميل Ersilia (0.1/0.3)
TOX_LOW, TOX_HIGH = 0.1, 0.3  # سمية عامة (AMES/DILI/ClinTox/سرطنة…)
ABS_GOOD, ABS_BAD = 0.7, 0.3  # امتصاص/توافر (فوق 0.7 جيد، تحت 0.3 ضعيف)


def verdict(task_id: str, value: float, lang: str = "ar") -> str:
    """حكم تعليمي قصير على قيمة نقطة نهاية — بلا ادعاء سريري.

    يغطي نقاط النهاية الرائدة؛ ما عداها يُرجع "—" (عرض القيمة + المئين
    هو العرض الصادق بدل أحكام مصطنعة).
    """
    ar = lang == "ar"
    t = TASKS.get(task_id)
    if t is None:
        return "—" if ar else "—"

    if t.kind == KIND_CLASSIFICATION:
        if task_id == "hERG":
            if value < HERG_LOW:
                return "خطر منخفض" if ar else "Low risk"
            if value <= HERG_HIGH:
                return "منطقة رمادية — مراقبة" if ar else "Grey zone — monitor"
            return "خطر مرتفع — فحوص QT" if ar else "High risk — QT follow-up"
        if task_id in {"AMES", "DILI", "ClinTox", "Carcinogens_Lagunin", "Skin_Reaction"}:
            if value < TOX_LOW:
                return "خطر منخفض" if ar else "Low risk"
            if value <= TOX_HIGH:
                return "منطقة رمادية — مراقبة" if ar else "Grey zone — monitor"
            return "خطر مرتفع" if ar else "High risk"
        if task_id in {"Bioavailability_Ma", "HIA_Hou", "PAMPA_NCATS"}:
            if value >= ABS_GOOD:
                return "جيد" if ar else "Good"
            if value >= ABS_BAD:
                return "متوسط" if ar else "Moderate"
            return "ضعيف" if ar else "Poor"
        if task_id == "BBB_Martins":
            if value >= ABS_GOOD:
                return "يتجاوز الحاجز على الأرجح" if ar else "Likely crosses BBB"
            if value < ABS_BAD:
                return "لا يتجاوز غالباً" if ar else "Unlikely to cross"
            return "منطقة رمادية" if ar else "Grey zone"
        return "—" if ar else "—"

    if t.kind == KIND_ALERT:
        return "بلا إنذار" if value == 0 else (f"⚠️ {int(value)} إنذار" if ar else f"⚠️ {int(value)} alert(s)")

    if t.kind == KIND_REGRESSION and task_id == "Solubility_AqSolDB":
        # توحيد مع عتبات SolTranNet في ersilia_client (mol/L لوغاريتمي)
        if value > -2.0:
            return "ذوبان جيد" if ar else "Good solubility"
        if value >= -4.0:
            return "ذوبان متوسط" if ar else "Moderate solubility"
        return "ذوبان ضعيف — عقبة تطوير" if ar else "Poor solubility — development risk"

    return "—" if ar else "—"


# ─────────────────────────────────────────────────────────────
# تلميح التثبيت + وضع الدرس — نمط SERVER_HINT/LESSON في ersilia_client
# ─────────────────────────────────────────────────────────────

INSTALL_HINT_AR = (
    "لتشغيل ADMET-AI محلياً (بيئة مستقلة عن التطبيق):\n"
    "```bash\n"
    "pip install torch --index-url https://download.pytorch.org/whl/cpu\n"
    "pip install admet-ai\n```"
    "\nالنماذج مضمّنة في الحزمة (~13MB) — لا شبكة ولا GPU مطلوبان، "
    "والاستدلال على CPU. حجم الذاكرة المقترح ≥ 4GB."
)
INSTALL_HINT_EN = (
    "To run ADMET-AI locally (independent from this app):\n"
    "```bash\n"
    "pip install torch --index-url https://download.pytorch.org/whl/cpu\n"
    "pip install admet-ai\n```"
    "\nModels ship inside the package (~13MB) — no network or GPU needed; "
    "CPU inference suffices. Recommended RAM ≥ 4GB."
)

ADMET_AI_LESSON: dict[str, str] = {
    "ar": (
        "**ADMET-AI** (هارفارد، رخصة MIT) يوسّع مركز ADMET من نموذجين إلى "
        "**{n} نقطة نهاية** بتعلّم آلي: مجموعة من 5 طيّات لنموذجَين متعددَي "
        "المهام مُدرَّبَين على بيانات Therapeutics Data Commons. العائلات: "
        "**الامتصاص** (Caco-2، HIA، الذوبانية، التوافر الحيوي)، **الاستقلاب** "
        "(تثبيط وركيزة CYP الأربعة الكبرى)، **التوزّع** (الحاجز الدماغي، "
        "ارتباط البلازما، حجم التوزيع، P-gp)، **التصفية** الكبدية والمجهرية، "
        "و**السمية**: القلبية hERG، الكبدية DILI، السرطنة، المطفرات AMES، "
        "السمية السريرية، والتحسس الجلدي، إضافة إلى مستقبلات نووية ومسارات "
        "إجهاد خلوي (Tox21). لكل قيمة يُعرض **المئين مقابل الأدوية المعتمدة "
        "في DrugBank** — كيف يقف جزيؤك بين أدوية حقيقية. القاعدة كما دائماً: "
        "**الفيزياء تُظهر قدرة الربط، وADMET يُظهر هل سيصل الدواء إلى هدفه "
        "وسلِماً** — والأحكام هنا إرشادية تعليمية لا تنظيمية."
    ),
    "en": (
        "**ADMET-AI** (Harvard, MIT license) expands the ADMET hub from two "
        "models to **{n} endpoints** via ML: a 5-fold ensemble of two "
        "multitask Chemprop models trained on Therapeutics Data Commons "
        "data. Families: **absorption** (Caco-2, HIA, solubility, "
        "bioavailability), **metabolism** (inhibition & substrates of the "
        "four major CYPs), **distribution** (BBB, plasma protein binding, "
        "volume of distribution, P-gp), **clearance** (hepatocyte & "
        "microsomal), and **toxicity**: cardiac hERG, DILI, carcinogenicity, "
        "AMES mutagenicity, clinical toxicity, skin sensitization — plus "
        "nuclear receptors and Tox21 stress-response pathways. Every value "
        "ships with its **percentile vs approved DrugBank drugs** — where "
        "your molecule stands among real drugs. Same rule as always: "
        "**physics shows binding; ADMET shows whether the drug reaches its "
        "target safely** — verdicts here are educational, not regulatory."
    ),
}

DISCLAIMER_AR = (
    "⚠️ محتوى تعليمي فقط — تنبؤات ADMET-AI البحثية بحدود تعميم معروفة؛ "
    "المئينات مقابل أدوية DrugBank المعتمدة للسياق لا للحكم. ليست توصية "
    "علاجية أو قراراً تنظيمياً."
)
DISCLAIMER_EN = (
    "⚠️ Educational content only — ADMET-AI research predictions with known "
    "generalization limits; DrugBank percentiles give context, not judgment. "
    "Never clinical or regulatory advice."
)
