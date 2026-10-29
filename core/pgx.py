"""علم الصيدلة الجيني (PGx) — توصيات CPIC حية + احتياطي مدمج تعليمي.

المصدر الحي: api.cpicpgx.org (PostgREST، بيانات مفتوحة بلا مفتاح).
الاحتياطي المدمج: مختصر تعليمي منسّق من إرشادات CPIC (تُعرض دائماً مع تنبيه).
الهدف: تعليم كيف يغيّر الوراثي (diplotype) قرار الجرعة/الدواء — وليس الاستخدام السريري.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd
import requests

CPIC_BASE = "https://api.cpicpgx.org/v1/recommendation"
CPIC_TIMEOUT = 20

DISCLAIMER_AR = (
    "⚠️ محتوى تعليمي فقط — مبسّط من إرشادات CPIC المحدثة المستمرة. "
    "لا يُستخدم لأي قرار سريري؛ راجع cpicpgx.org والنصوص الرسمية."
)
DISCLAIMER_EN = (
    "⚠️ Educational content only — simplified from CPIC guidelines. "
    "Never for clinical decisions; consult cpicpgx.org."
)

CLASS_AR = {
    "strong": "قوي",
    "moderate": "متوسط",
    "optional": "اختياري",
    "informative": "للاطلاع",
}


# ─────────────────────────────────────────────────────────────
# تعريفات الجينات
# ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class GeneInfo:
    """بطاقة تعريف جين PGx للتبويب."""

    id: str
    title_ar: str
    title_en: str
    function_ar: str
    function_en: str
    substrates_ar: str
    diplotypes: dict[str, str] = field(default_factory=dict)  # diplotype → phenotype_en

    @property
    def phenotype_of(self) -> dict[str, str]:
        return self.diplotypes


GENES: dict[str, GeneInfo] = {
    "CYP2D6": GeneInfo(
        id="CYP2D6",
        title_ar="CYP2D6 — أيض الكودايين والتاموكسيفين والأتوموكسيتين",
        title_en="CYP2D6 — codeine, tamoxifen & atomoxetine metabolism",
        function_ar="أيض فموي واسع الانتشار؛ الكودايين يُفعَّل بواسطته إلى مورفين، "
        "والتاموكسيفين يُفعَّل إلى إندوكسيفين — النمط يقلب الفائدة والسمية معاً.",
        function_en="Widespread oral-phase metabolism; activates codeine to morphine "
        "and tamoxifen to endoxifen — phenotype flips both benefit and toxicity.",
        substrates_ar="كودايين · تاموكسيفين · أتوموكسيتين · أوكسيكودون",
        diplotypes={
            "*1/*1": "Normal Metabolizer",
            "*1/*1xN": "Ultrarapid Metabolizer",
            "*1/*4": "Intermediate Metabolizer",
            "*10/*10": "Intermediate Metabolizer",
            "*4/*4": "Poor Metabolizer",
        },
    ),
    "TPMT": GeneInfo(
        id="TPMT",
        title_ar="TPMT — أيض الثيوبورينات (أزاثيوبرين/6-MP)",
        title_en="TPMT — thiopurine metabolism (azathioprine/6-MP)",
        function_ar="ينظّف الخلية من نيوكليوتيدات الثيوغوانين؛ الانخفاض الوراثي يراكم "
        "السمية النقوية — من أشهر أمثلة الجرعة الموجَّهة وراثياً في الأدوية.",
        function_en="Detoxifies thioguanine nucleotides; inherited reduction accumulates "
        "myelotoxicity — the classic genotype-guided dosing example.",
        substrates_ar="أزاثيوبرين · 6-مركابتوبورين · ثيوغوانين",
        diplotypes={
            "*1/*1": "Normal Metabolizer",
            "*1/*4": "Intermediate Metabolizer",
            "*4/*4": "Poor Metabolizer",
        },
    ),
    "UGT1A1": GeneInfo(
        id="UGT1A1",
        title_ar="UGT1A1 — غلوكوروندة الإرينوتيكان وأتازانافير",
        title_en="UGT1A1 — irinotecan & atazanavir glucuronidation",
        function_ar="يُغلّي البيليروبين ومستقلبات الأدوية؛ التكرار TA7 (*28) يخفض "
        "التعبير — سمّية الإرينوتيكان المعوية وفرق بيليروبين الأتازانافير.",
        function_en="Glucuronidates bilirubin and drug metabolites; TA7 repeat (*28) "
        "lowers expression — irinotecan GI toxicity and atazanavir hyperbilirubinemia.",
        substrates_ar="إرينوتيكان · أتازانافير · بيليروبين",
        diplotypes={
            "*1/*1": "Normal Metabolizer",
            "*1/*28": "Intermediate Metabolizer",
            "*28/*28": "Poor Metabolizer",
        },
    ),
    "CYP2C19": GeneInfo(
        id="CYP2C19",
        title_ar="CYP2C19 — تفعيل الكلوبيغريل ومثبطات مضخة البروتون",
        title_en="CYP2C19 — clopidogrel activation & PPIs",
        function_ar="يفعّل البرودروغ الكلوبيغريل؛ فقد الوظيفة (*2) يعني جلطة محتملة رغم "
        "الالتزام — أشهر توصية «بدّل الدواء» في PGx.",
        function_en="Activates the prodrug clopidogrel; loss alleles (*2) mean possible "
        "thrombosis despite adherence — the classic \"switch drug\" PGx case.",
        substrates_ar="كلوبيغريل · أوميبرازول · إسكوميبرازول",
        diplotypes={
            "*1/*1": "Normal Metabolizer",
            "*1/*2": "Intermediate Metabolizer",
            "*17/*17": "Ultrarapid Metabolizer",
            "*2/*2": "Poor Metabolizer",
        },
    ),
    "CYP3A5": GeneInfo(
        id="CYP3A5",
        title_ar="CYP3A5 — تعبير المُعاضِد المناعي تاكروليموس",
        title_en="CYP3A5 — tacrolimus expresser status",
        function_ar="المُعاضِد المناعي تاكروليموس يُعايَر وفق TDM؛ المُعبِّرون (*1) "
        "يحتاجون جرعة بداية أعلى للوصول للنطاق العلاجي أسرع.",
        function_en="Tacrolimus is TDM-titrated; expressers (*1) need a higher starting "
        "dose to reach the therapeutic window sooner.",
        substrates_ar="تاكروليموس · سيروليموس",
        diplotypes={
            "*1/*1": "Normal (Expresser)",
            "*1/*3": "Intermediate (Expresser)",
            "*3/*3": "Poor (Non-expresser)",
        },
    ),
}

# ─────────────────────────────────────────────────────────────
# الاحتياطي المدمج (مختصر تعليمي منسّق من CPIC)
# ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class PgxRec:
    """توصية واحدة: جين + نمط + دواء + توصية + قوة الإرشاد."""

    gene: str
    diplotype: str
    phenotype_en: str
    drug: str
    drug_ar: str
    recommendation_ar: str
    recommendation_en: str
    classification: str  # strong | moderate | optional | informative
    guideline: str


FALLBACK_RECS: tuple[PgxRec, ...] = (
    # ── CYP2D6 (CPIC 2020) ──
    PgxRec("CYP2D6", "*1/*1", "Normal Metabolizer", "codeine", "كودايين",
           "الجرعة المعيارية حسب العمر مع مراقبة التسكين والسمية.",
           "Usual age-appropriate dose; monitor analgesia and toxicity.",
           "moderate", "CPIC 2020"),
    PgxRec("CYP2D6", "*1/*4", "Intermediate Metabolizer", "codeine", "كودايين",
           "جرعة معيارية بحذر؛ عند ضعف التسكين استخدم بديلاً (مورفين).",
           "Usual dose with caution; if analgesia is poor, use an alternative (morphine).",
           "moderate", "CPIC 2020"),
    PgxRec("CYP2D6", "*4/*4", "Poor Metabolizer", "codeine", "كودايين",
           "تجنّب الكودايين — تحويل ضعيف للمورفين يعني لا تسكين؛ استخدم بديلاً.",
           "Avoid codeine — poor morphine conversion means no analgesia; use alternative.",
           "strong", "CPIC 2020"),
    PgxRec("CYP2D6", "*1/*1xN", "Ultrarapid Metabolizer", "codeine", "كودايين",
           "تجنّب الكودايين — تحويل سريع لمورفين وخطر تسمم تنفسي.",
           "Avoid codeine — rapid morphine conversion with respiratory-toxicity risk.",
           "strong", "CPIC 2020"),
    PgxRec("CYP2D6", "*1/*1", "Normal Metabolizer", "tamoxifen", "تاموكسيفين",
           "ابدأ بالجرعة المعيارية (20 mg/يوم) مع تعزيز الالتزام والمتابعة.",
           "Start the recommended dose (20 mg/day) with adherence monitoring.",
           "moderate", "CPIC 2018"),
    PgxRec("CYP2D6", "*1/*4", "Intermediate Metabolizer", "tamoxifen", "تاموكسيفين",
           "جرعة معيارية؛ فكّر في بديل (مثبط أروماتاز) عند توفره وفق حالة المريضة.",
           "Standard dose; consider an alternative (aromatase inhibitor) when appropriate.",
           "optional", "CPIC 2018"),
    PgxRec("CYP2D6", "*4/*4", "Poor Metabolizer", "tamoxifen", "تاموكسيفين",
           "تجنّب الاعتماد على الجرعة المعيارية — استخدم علاجاً هرمونياً بديلاً.",
           "Do not rely on standard dosing — use alternative endocrine therapy.",
           "strong", "CPIC 2018"),
    PgxRec("CYP2D6", "*10/*10", "Intermediate Metabolizer", "codeine", "كودايين",
           "جرعة معيارية بحذر؛ النمط المنخفض (*10) يعامل كوسيط الأيض.",
           "Usual dose with caution; the decreased-function (*10) phenotype "
           "is treated as intermediate metabolism.",
           "moderate", "CPIC 2020"),
    PgxRec("CYP2D6", "*10/*10", "Intermediate Metabolizer", "tamoxifen", "تاموكسيفين",
           "جرعة معيارية مع مراقبة؛ فكّر في بديل عند الحاجة (شائع لدى شرق آسيا).",
           "Standard dose with monitoring; consider alternatives when needed "
           "(common in East Asian populations).",
           "optional", "CPIC 2018"),
    # ── TPMT (CPIC 2018) ──
    PgxRec("TPMT", "*1/*1", "Normal Metabolizer", "azathioprine", "أزاثيوبرين",
           "الجرعة المستهدفة المعيارية، ثم عاير بعد 2-4 أسابيع وفق تعداد الدم.",
           "Start standard target dose; titrate after 2-4 weeks per blood counts.",
           "moderate", "CPIC 2018"),
    PgxRec("TPMT", "*1/*4", "Intermediate Metabolizer", "azathioprine", "أزاثيوبرين",
           "ابدأ بنحو 50% من الجرعة المستهدفة وعرّج ببطء حسب تعداد الدم.",
           "Start at ~50% of target dose and titrate slowly per blood counts.",
           "strong", "CPIC 2018"),
    PgxRec("TPMT", "*4/*4", "Poor Metabolizer", "azathioprine", "أزاثيوبرين",
           "تجنّب؛ إن اضطُررت ابدأ بـ~10% مع مراقبة دموية أسبوعية وعرّج ببطء.",
           "Avoid; if used, start ~10% with weekly blood-count monitoring and slow titration.",
           "strong", "CPIC 2018"),
    # ── UGT1A1 (CPIC 2017) ──
    PgxRec("UGT1A1", "*1/*1", "Normal Metabolizer", "irinotecan", "إرينوتيكان",
           "الجرعة المعيارية حسب البروتوكول.",
           "Standard protocol dosing.",
           "informative", "CPIC 2017"),
    PgxRec("UGT1A1", "*1/*28", "Intermediate Metabolizer", "irinotecan", "إرينوتيكان",
           "فكّر في جرعة بداية أخفض وفق تقدير الطبيب المعالج.",
           "Consider a lower starting dose at the physician's discretion.",
           "optional", "CPIC 2017"),
    PgxRec("UGT1A1", "*28/*28", "Poor Metabolizer", "irinotecan", "إرينوتيكان",
           "اخفض جرعة البداية مستوى واحداً على الأقل في بروتوكول العلاج.",
           "Reduce the starting dose by at least one dose level.",
           "strong", "CPIC 2017"),
    PgxRec("UGT1A1", "*28/*28", "Poor Metabolizer", "atazanavir", "أتازانافير",
           "خطر فرق بيليروبين انعزالي — فكّر في بديل من مثبطات البروتييز.",
           "Risk of isolated hyperbilirubinemia — consider an alternative protease inhibitor.",
           "informative", "CPIC 2017"),
    # ── CYP2C19 (CPIC 2022) ──
    PgxRec("CYP2C19", "*1/*1", "Normal Metabolizer", "clopidogrel", "كلوبيغريل",
           "الجرعة المعيارية 75 mg/يوم.",
           "Standard 75 mg/day.",
           "moderate", "CPIC 2022"),
    PgxRec("CYP2C19", "*1/*2", "Intermediate Metabolizer", "clopidogrel", "كلوبيغريل",
           "يفضَّل تيكاغريلور أو براسوغريل عند عدم وجود مانع.",
           "Ticagrelor or prasugrel preferred when not contraindicated.",
           "moderate", "CPIC 2022"),
    PgxRec("CYP2C19", "*2/*2", "Poor Metabolizer", "clopidogrel", "كلوبيغريل",
           "استخدم بديلاً (تيكاغريلور/براسوغريل) — التفعيل ضعيف والخطر قلبي وعائي.",
           "Use an alternative (ticagrelor/prasugrel) — poor activation, CV risk.",
           "strong", "CPIC 2022"),
    PgxRec("CYP2C19", "*17/*17", "Ultrarapid Metabolizer", "clopidogrel", "كلوبيغريل",
           "الجرعة المعيارية؛ لا توصية حالياً بتعديلها.",
           "Standard dose; no dose change currently recommended.",
           "informative", "CPIC 2022"),
    # ── CYP3A5 (CPIC 2020) ──
    PgxRec("CYP3A5", "*1/*1", "Normal (Expresser)", "tacrolimus", "تاكروليموس",
           "ابدأ بـ1.5-2× الجرعة المعيارية مع مراقبة تركيز الدم (TDM).",
           "Start 1.5-2x the standard dose with TDM.",
           "strong", "CPIC 2020"),
    PgxRec("CYP3A5", "*1/*3", "Intermediate (Expresser)", "tacrolimus", "تاكروليموس",
           "الجرعة المعيارية مع TDM مكثف؛ قد تحتاج زيادة لاحقة.",
           "Standard dose with intensified TDM; may need later increases.",
           "moderate", "CPIC 2020"),
    PgxRec("CYP3A5", "*3/*3", "Poor (Non-expresser)", "tacrolimus", "تاكروليموس",
           "الجرعة المعيارية مع مراقبة تركيز الدم (TDM).",
           "Standard dose with TDM.",
           "moderate", "CPIC 2020"),
)

REC_COLUMNS = [
    "gene", "diplotype", "phenotype_en", "drug", "drug_ar",
    "recommendation_ar", "recommendation_en", "classification", "guideline",
]


def fallback_df(gene: str | None = None, diplotype: str | None = None) -> pd.DataFrame:
    """الاحتياطي المدمج كإطار بيانات (مع فلترة اختيارية)."""
    rows = [r.__dict__ for r in FALLBACK_RECS]
    df = pd.DataFrame(rows, columns=REC_COLUMNS)
    if gene:
        df = df[df["gene"] == gene]
    if diplotype:
        df = df[df["diplotype"] == diplotype]
    return df.reset_index(drop=True)


# ─────────────────────────────────────────────────────────────
# الجلب الحي من CPIC (بلا مفتاح، بلا استثناءات — يرجع [] عند الفشل)
# ─────────────────────────────────────────────────────────────

def fetch_cpic(gene: str) -> list[dict]:
    """سحب توصيات CPIC الحية لجين واحد — يعيد صفوفاً موحّدة أو [] عند أي فشل.

    شكل API: GET {CPIC_BASE}?gene=eq.{gene}&select=drugname,phenotypes,
    classification,recommendation,implication&limit=100
    """
    params = {
        "gene": f"eq.{gene}",
        "select": "drugname,phenotypes,classification,recommendation,implication",
        "limit": "100",
    }
    try:
        resp = requests.get(CPIC_BASE, params=params, timeout=CPIC_TIMEOUT)
        resp.raise_for_status()
        payload = resp.json()
    except Exception:  # noqa: BLE001 — الشبكة أو الشكل غير المتوقع → احتياطي
        return []

    out: list[dict] = []
    for row in payload if isinstance(payload, list) else []:
        phen = ""
        ph = row.get("phenotypes")
        if isinstance(ph, dict):
            for v in ph.values():
                if isinstance(v, dict) and v.get("phenotype"):
                    phen = str(v["phenotype"])
                    break
                if isinstance(v, str):
                    phen = v
                    break
        rec_text = row.get("recommendation") or ""
        if isinstance(rec_text, dict):
            rec_text = rec_text.get("text") or ""
        out.append({
            "gene": gene,
            "diplotype": "",
            "phenotype_en": phen,
            "drug": str(row.get("drugname") or ""),
            "drug_ar": "",
            "recommendation_ar": "",
            "recommendation_en": str(rec_text).strip(),
            "classification": str(row.get("classification") or "").lower(),
            "guideline": "CPIC حي (api.cpicpgx.org)",
        })
    return out


def recommendations_df(
    gene: str,
    diplotype: str,
    lang: str = "ar",
    live_rows: list[dict] | None = None,
) -> pd.DataFrame:
    """جدول التوصيات: حي إن توفّر ومطابق، وإلا الاحتياطي المدمج.

    المطابقة الحية: phenotype_en يبدأ بنفس فئة النمط (Normal/Intermediate/
    Poor/Ultrarapid/Expresser) — تفاوت صياغات CPIC مقبول بالاحتواء.
    """
    phenotype_en = GENES[gene].diplotypes.get(diplotype, "")
    tokens = [t for t in phenotype_en.split() if t in
              ("Normal", "Intermediate", "Poor", "Ultrarapid", "Non-expresser")]
    token = tokens[0] if tokens else phenotype_en.split()[0] if phenotype_en else ""

    src: pd.DataFrame
    if live_rows:
        live = pd.DataFrame(live_rows, columns=REC_COLUMNS)
        if token:
            live = live[live["phenotype_en"].str.contains(token, case=False, na=False)]
        if not live.empty:
            src = live.reset_index(drop=True)
        else:
            src = fallback_df(gene, diplotype)
    else:
        src = fallback_df(gene, diplotype)

    rec_col = "recommendation_ar" if lang == "ar" else "recommendation_en"
    drug_col = "drug_ar" if lang == "ar" else "drug"
    out = pd.DataFrame({
        "الدواء": src[drug_col].fillna(src["drug"]),
        "النمط": src["phenotype_en"],
        "التوصية": src[rec_col].fillna(src["recommendation_en"]),
        "القوة": src["classification"].map(lambda c: CLASS_AR.get(c, c or "—")),
        "المصدر": src["guideline"],
    })
    return out.reset_index(drop=True)
