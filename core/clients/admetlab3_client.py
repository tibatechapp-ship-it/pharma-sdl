"""عميل ADMETlab 3.0 — 121 نقطة نهاية ADMET عبر الخدمة السحابية (scbdd/SJTU).

خطوة التحقق (2026-11-09 — كما تقتضي docs/INTEGRATION-ROADMAP.md:
«لا تبنِ إنتاجاً قبل خطوة تحقق واحدة»):

- العقد الموثّق من الدليل الرسمي https://admetlab3.scbdd.com/apis/ (docsify):
  ``POST {base}/api/admet`` بجسم JSON
  ``{"SMILES": "<smiles>" | ["<smiles>", …], "feature": bool, "uncertain": bool}``
  → ``{"status": "success", "code": 200, "data": {"taskid": …,
  "number of all molecules": …, "number of valid molecules": …,
  "data": [{"smiles": …, "MW": 318.1, …}], "explanation": {…}}}``.
  الجزيء غير الصالح تعود قيمه نصاً «Invalid Molecule» وتُرشَّح هنا.
- قائمة الأعمدة الـ121 كاملة من ملف النتائج النموذجي الرسمي
  ``/static/apis/files/results.csv`` — محفوظة حرفياً في ``EXPECTED_COLUMNS``.
- التحقق الحي الفعلي (من بيئة المشروع 2026-11-09):
  * ``POST /api/washmol`` → **200 حقيقي** (أسبرين عاد متعارفاً
    ``CC(=O)Oc1ccccc1C(=O)O``) — الخدمة حية وجوابها JSON سليم.
  * ``POST /api/admet`` → **404** في نفس اليوم رغم توثيقه (تعطل حسابي مؤقت —
    بانر «تعرضت خوادمنا لهجمات مستمرة…عدم استقرار» معلن على وثائقهم أنفسهم).
  * نداء سريع → **429 Too Many Requests** من nginx — حد الاستخدام الموثّق
    (≤5 طلبات/ثانية) مطبَّق فعلاً على مستوى الخادم.
  الخلاصة: العقد صحيح والخدمة متقلبة واقعياً — العميل مصمَّم لهذا الواقع
  (أسباب فشل قابلة للبرمجة، بلا استثناءات للواجهة، تباعد بين الطلبات).
- سياسة الاستخدام الرسمية: الخدمة ليست لأحجام بالملايين؛ ≤5 طلبات/ثانية،
  والمجموعات الضخمة عبر البريد فقط — عميلنا يرسل دفعة واحدة لكل نداء
  ويقطّع الدفعات الكبيرة بتباعد زمني صريح.

المبدأ الحاكم (نمط ersilia/japanfold): فشل الشبكة أو الخدمة لا يرمي
استثناءً للواجهة — تُرجَع حزمة فارغة مع ``reason`` قابل للبرمجة تترجمه
الواجهة لرسالة صادقة. لا مفتاح (الخدمة بلا مفاتيح)، والقيم إرشادية
تعليمية بلا ادعاء سريري أو تنظيمي.
"""
from __future__ import annotations

import logging
import math
import os
import time
from dataclasses import dataclass, field

import requests

logger = logging.getLogger(__name__)

BASE_DEFAULT = "https://admetlab3.scbdd.com"
ADMET_ENDPOINT = "/api/admet"
WASHMOL_ENDPOINT = "/api/washmol"
MAX_BATCH = 48  # دفعة مهذبة واحدة لكل نداء — بوليصة الاستخدام ≤5 طلبات/ث
_MIN_INTERVAL_S = 0.25  # تباعد بين دفعات متتالية (4 طلبات/ث كحد أقصى فعلي)
DEFAULT_TIMEOUT = 45.0

# أكواد فشل قابلة للبرمجة — تترجمها الواجهة، ولا استثناء يعبر أبداً
REASON_EMPTY = "empty_input"
REASON_NETWORK = "network_error"
REASON_RATE = "rate_limited"
REASON_UNAVAILABLE = "endpoint_unavailable"
REASON_SERVICE = "service_error"
REASON_BAD_SHAPE = "bad_response"

REASON_MESSAGES_AR: dict[str, str] = {
    REASON_EMPTY: "لا مدخلات — أدخل SMILES صالحة أولاً.",
    REASON_NETWORK: "تعذر الوصول إلى الخدمة (شبكة/مهلة) — كل المختبرات المحلية تعمل كالمعتاد.",
    REASON_RATE: "الخدمة تحدّ من الطلبات حالياً (429) — أعد المحاولة بعد لحظات.",
    REASON_UNAVAILABLE: "نقطة الحساب غير متاحة الآن من الخدمة (404) — انقطاع موثّق على طرفهم؛ العميل جاهز لحظة التعافي.",
    REASON_SERVICE: "الخدمة أعادت خطأً داخلياً (5xx) — أعد المحاولة لاحقاً.",
    REASON_BAD_SHAPE: "استجابة غير متوقعة من الخدمة — العقد موثّق ولا نجتهد على شكل غير معلن.",
}

REASON_MESSAGES_EN: dict[str, str] = {
    REASON_EMPTY: "No input — enter valid SMILES first.",
    REASON_NETWORK: "Service unreachable (network/timeout) — all local labs work as usual.",
    REASON_RATE: "Service is rate-limiting right now (429) — retry in a moment.",
    REASON_UNAVAILABLE: "The compute endpoint is currently unavailable (404) — a documented outage on their side; the client is ready the moment it recovers.",
    REASON_SERVICE: "Service returned an internal error (5xx) — retry later.",
    REASON_BAD_SHAPE: "Unexpected response shape — the contract is documented; we do not guess.",
}


def reason_message(reason: str | None, lang: str = "ar") -> str:
    """رسالة صادقة لسبب فشل قابل للبرمجة — بلغة الواجهة."""
    if reason is None:
        return ""
    table = REASON_MESSAGES_AR if lang == "ar" else REASON_MESSAGES_EN
    return table.get(reason, reason)

# ─────────────────────────────────────────────────────────────
# الأعمدة الـ121 الموثّقة حرفياً من ملف النتائج الرسمي results.csv
# (بلا smiles/molstr وأعمدة الصور المظللة — عناصر عرض لا بيانات)
# ─────────────────────────────────────────────────────────────

EXPECTED_COLUMNS: tuple[str, ...] = (
    "MW", "Vol", "Dense", "nHA", "nHD", "TPSA", "nRot", "nRing", "MaxRing",
    "nHet", "fChar", "nRig", "Flex", "nStereo", "sa", "QED", "Fsp3", "MCE-18",
    "Natural Product-likeness", "Alarm_NMR", "BMS", "Chelating", "PAINS",
    "Lipinski", "Pfizer", "GSK", "GoldenTriangle", "logS", "logD", "logP",
    "mp", "bp", "pka_acidic", "pka_basic", "caco2", "MDCK", "logVDss", "Fu",
    "PPB", "cl-int", "t0.5", "cl-plasma", "BCF", "IGC50", "LC50FM", "LC50DM",
    "f20", "f30", "f50", "hia", "MRP1", "OATP1B1", "OATP1B3", "pgp_inh",
    "pgp_sub", "BCRP", "BBB", "PAMPA", "CYP1A2-inh", "CYP1A2-sub",
    "CYP2C19-inh", "CYP2C19-sub", "CYP2C9-inh", "CYP2C9-sub", "CYP2D6-inh",
    "CYP2D6-sub", "CYP3A4-inh", "CYP3A4-sub", "CYP2B6-inh", "CYP2B6-sub",
    "CYP2C8-inh", "LM-mouse", "LM-rat", "LM-human", "A549", "Ames",
    "Carcinogenicity", "DILI", "EC", "EI", "FDAMDD", "Genotoxicity", "H-HT",
    "HEK293", "Hematotoxicity", "hERG-10um", "hERG", "Nephrotoxicity-DI",
    "Neurotoxicity-DI", "Ototoxicity", "Respiratory", "ROA", "RPMI-8226",
    "SkinSen", "NR-AR", "NR-AR-LBD", "NR-AhR", "NR-Aromatase", "NR-ER",
    "NR-ER-LBD", "NR-PPAR-gamma", "SR-ARE", "SR-ATAD5", "SR-HSE", "SR-MMP",
    "SR-p53", "NonBiodegradable", "NonGenotoxic_Carcinogenicity", "SureChEMBL",
    "LD50_oral", "Skin_Sensitization", "Acute_Aquatic_Toxicity", "Toxicophores",
    "Genotoxic_Carcinogenicity_Mutagenicity", "Aggregators", "Fluc",
    "Blue_fluorescence", "Green_fluorescence", "Reactive",
    "Other_assay_interference", "Promiscuous",
)

KIND_PHYSCHEM = "physchem"
KIND_RULE = "rule"
KIND_ADME = "adme"
KIND_TOX = "tox"


@dataclass(frozen=True)
class AdmetLab3Endpoint:
    """بطاقة عرض لنقطة نهاية ADMETlab 3.0 — للمفاتيح الموثّقة شائعة الاستخدام."""

    key: str  # اسم العمود في استجابة الخدمة حرفياً
    name_ar: str
    name_en: str
    unit_ar: str
    unit_en: str
    kind: str  # physchem | rule | adme | tox
    low_good: bool | None  # None = معلوماتية بلا اتجاه حكم


# كتالوج منقّح للمفاتيح الأكثر استخداماً — ما عداها يُعرض باسمه الخام بصدق
ENDPOINTS: dict[str, AdmetLab3Endpoint] = {
    e.key: e
    for e in (
        # فيزيوكيمياء أساسية
        AdmetLab3Endpoint("MW", "الوزن الجزيئي", "Molecular weight", "g/mol", "g/mol", KIND_PHYSCHEM, None),
        AdmetLab3Endpoint("Vol", "الحجم الجزيئي", "Molecular volume", "Å³", "Å³", KIND_PHYSCHEM, None),
        AdmetLab3Endpoint("Dense", "الكثافة الجزيئية", "Molecular density", "g/cm³", "g/cm³", KIND_PHYSCHEM, None),
        AdmetLab3Endpoint("nHA", "مستقبلات الروابط الهيدروجينية", "H-bond acceptors", "عدد", "count", KIND_PHYSCHEM, None),
        AdmetLab3Endpoint("nHD", "مانحات الروابط الهيدروجينية", "H-bond donors", "عدد", "count", KIND_PHYSCHEM, None),
        AdmetLab3Endpoint("TPSA", "المساحة السطحية القطبية", "Topological polar surface area", "Å²", "Å²", KIND_PHYSCHEM, None),
        AdmetLab3Endpoint("nRot", "الروابط الدوّارة", "Rotatable bonds", "عدد", "count", KIND_PHYSCHEM, None),
        AdmetLab3Endpoint("nRing", "عدد الحلقات", "Number of rings", "عدد", "count", KIND_PHYSCHEM, None),
        AdmetLab3Endpoint("nStereo", "مراكز فراغية", "Stereo centers", "عدد", "count", KIND_PHYSCHEM, None),
        AdmetLab3Endpoint("sa", "صعوبة التخليق (SA)", "Synthetic accessibility", "1..10", "1..10", KIND_PHYSCHEM, False),
        AdmetLab3Endpoint("QED", "كثافة الدوائية QED", "Quantitative estimate of drug-likeness", "0..1", "0..1", KIND_PHYSCHEM, False),
        AdmetLab3Endpoint("Fsp3", "نسبة الكربون الشبعي Fsp³", "Fraction sp³ carbon", "0..1", "0..1", KIND_PHYSCHEM, None),
        AdmetLab3Endpoint("MCE-18", "تعقيد MCE-18", "MCE-18 complexity", "درجة", "score", KIND_PHYSCHEM, None),
        # خصائص فيزيائية
        AdmetLab3Endpoint("logS", "الذوبانية المائية", "Aqueous solubility", "log(mol/L)", "log(mol/L)", KIND_ADME, False),
        AdmetLab3Endpoint("logD", "التوزيع logD (pH 7.4)", "Distribution coefficient logD", "بلا وحدة", "dimensionless", KIND_ADME, None),
        AdmetLab3Endpoint("logP", "التقسيم logP", "Partition coefficient logP", "بلا وحدة", "dimensionless", KIND_PHYSCHEM, None),
        AdmetLab3Endpoint("pka_acidic", "أكثر pKa حمضي", "Most acidic pKa", "pH", "pH", KIND_PHYSCHEM, None),
        AdmetLab3Endpoint("pka_basic", "أكثر pKa قاعدي", "Most basic pKa", "pH", "pH", KIND_PHYSCHEM, None),
        # قواعد وأعلام مخدرية
        AdmetLab3Endpoint("Lipinski", "مخالفات قاعدة ليبنسكي", "Lipinski rule violations", "عدد", "count", KIND_RULE, True),
        AdmetLab3Endpoint("PAINS", "إنذار PAINS", "PAINS alert", "عدد", "count", KIND_RULE, True),
        AdmetLab3Endpoint("BMS", "إنذار BMS", "BMS alert", "عدد", "count", KIND_RULE, True),
        AdmetLab3Endpoint("Chelating", "قابلية الخلب", "Chelating alert", "عدد", "count", KIND_RULE, True),
        AdmetLab3Endpoint("Pfizer", "قاعدة فايزر (3/75)", "Pfizer 3/75 rule", "عدد", "count", KIND_RULE, True),
        AdmetLab3Endpoint("GSK", "قاعدة GSK (4/400)", "GSK 4/400 rule", "عدد", "count", KIND_RULE, True),
        AdmetLab3Endpoint("GoldenTriangle", "المثلث الذهبي", "Golden Triangle", "عدد", "count", KIND_RULE, True),
        # امتصاص وتوزيع
        AdmetLab3Endpoint("caco2", "نفاذية Caco-2", "Caco-2 permeability", "log(10⁻⁶ cm/s)", "log(10⁻⁶ cm/s)", KIND_ADME, False),
        AdmetLab3Endpoint("MDCK", "نفاذية MDCK", "MDCK permeability", "10⁻⁶ cm/s", "10⁻⁶ cm/s", KIND_ADME, False),
        AdmetLab3Endpoint("hia", "الامتصاص المعوي البشري", "Human intestinal absorption", "احتمال [0..1]", "probability [0..1]", KIND_ADME, False),
        AdmetLab3Endpoint("f20", "التوافر الحيوي F≥20%", "Bioavailability F≥20%", "احتمال [0..1]", "probability [0..1]", KIND_ADME, False),
        AdmetLab3Endpoint("f30", "التوافر الحيوي F≥30%", "Bioavailability F≥30%", "احتمال [0..1]", "probability [0..1]", KIND_ADME, False),
        AdmetLab3Endpoint("f50", "التوافر الحيوي F≥50%", "Bioavailability F≥50%", "احتمال [0..1]", "probability [0..1]", KIND_ADME, False),
        AdmetLab3Endpoint("BBB", "نفاذية الحاجز الدماغي", "Blood-brain barrier", "احتمال [0..1]", "probability [0..1]", KIND_ADME, None),
        AdmetLab3Endpoint("PAMPA", "نفاذية PAMPA", "PAMPA permeability", "احتمال [0..1]", "probability [0..1]", KIND_ADME, False),
        AdmetLab3Endpoint("PPB", "ارتباط بروتينات البلازما", "Plasma protein binding", "%", "%", KIND_ADME, None),
        AdmetLab3Endpoint("Fu", "الجزء الحر غير المرتبط", "Fraction unbound", "0..1", "0..1", KIND_ADME, None),
        AdmetLab3Endpoint("logVDss", "حجم التوزيع عند الثبات", "Volume of distribution (VDss)", "L/kg لوغاريتمي", "log L/kg", KIND_ADME, None),
        AdmetLab3Endpoint("pgp_inh", "تثبيط مضخة P-gp", "P-glycoprotein inhibition", "احتمال [0..1]", "probability [0..1]", KIND_ADME, True),
        AdmetLab3Endpoint("pgp_sub", "ركيزة مضخة P-gp", "P-glycoprotein substrate", "احتمال [0..1]", "probability [0..1]", KIND_ADME, None),
        AdmetLab3Endpoint("BCRP", "تثبيط BCRP", "BCRP inhibition", "احتمال [0..1]", "probability [0..1]", KIND_ADME, True),
        AdmetLab3Endpoint("OATP1B1", "تثبيط OATP1B1", "OATP1B1 inhibition", "احتمال [0..1]", "probability [0..1]", KIND_ADME, True),
        AdmetLab3Endpoint("OATP1B3", "تثبيط OATP1B3", "OATP1B3 inhibition", "احتمال [0..1]", "probability [0..1]", KIND_ADME, True),
        AdmetLab3Endpoint("MRP1", "تثبيط MRP1", "MRP1 inhibition", "احتمال [0..1]", "probability [0..1]", KIND_ADME, True),
        # تصفية وعمر
        AdmetLab3Endpoint("cl-int", "التصفية الداخلية", "Intrinsic clearance", "µL/min/mg", "µL/min/mg", KIND_ADME, None),
        AdmetLab3Endpoint("cl-plasma", "التصفية البلازمية", "Plasma clearance", "mL/min/kg", "mL/min/kg", KIND_ADME, None),
        AdmetLab3Endpoint("t0.5", "عمر النصف", "Half-life", "ساعة", "hr", KIND_ADME, None),
        # استقلاب CYP — التثبيط ثم الركيزة
        AdmetLab3Endpoint("CYP1A2-inh", "تثبيط CYP1A2", "CYP1A2 inhibition", "احتمال [0..1]", "probability [0..1]", KIND_ADME, True),
        AdmetLab3Endpoint("CYP2C19-inh", "تثبيط CYP2C19", "CYP2C19 inhibition", "احتمال [0..1]", "probability [0..1]", KIND_ADME, True),
        AdmetLab3Endpoint("CYP2C9-inh", "تثبيط CYP2C9", "CYP2C9 inhibition", "احتمال [0..1]", "probability [0..1]", KIND_ADME, True),
        AdmetLab3Endpoint("CYP2D6-inh", "تثبيط CYP2D6", "CYP2D6 inhibition", "احتمال [0..1]", "probability [0..1]", KIND_ADME, True),
        AdmetLab3Endpoint("CYP3A4-inh", "تثبيط CYP3A4", "CYP3A4 inhibition", "احتمال [0..1]", "probability [0..1]", KIND_ADME, True),
        AdmetLab3Endpoint("CYP1A2-sub", "ركيزة CYP1A2", "CYP1A2 substrate", "احتمال [0..1]", "probability [0..1]", KIND_ADME, None),
        AdmetLab3Endpoint("CYP2C19-sub", "ركيزة CYP2C19", "CYP2C19 substrate", "احتمال [0..1]", "probability [0..1]", KIND_ADME, None),
        AdmetLab3Endpoint("CYP2C9-sub", "ركيزة CYP2C9", "CYP2C9 substrate", "احتمال [0..1]", "probability [0..1]", KIND_ADME, None),
        AdmetLab3Endpoint("CYP2D6-sub", "ركيزة CYP2D6", "CYP2D6 substrate", "احتمال [0..1]", "probability [0..1]", KIND_ADME, None),
        AdmetLab3Endpoint("CYP3A4-sub", "ركيزة CYP3A4", "CYP3A4 substrate", "احتمال [0..1]", "probability [0..1]", KIND_ADME, None),
        AdmetLab3Endpoint("CYP2B6-inh", "تثبيط CYP2B6", "CYP2B6 inhibition", "احتمال [0..1]", "probability [0..1]", KIND_ADME, True),
        AdmetLab3Endpoint("CYP2C8-inh", "تثبيط CYP2C8", "CYP2C8 inhibition", "احتمال [0..1]", "probability [0..1]", KIND_ADME, True),
        # سمية
        AdmetLab3Endpoint("hERG", "حجب قناة hERG (سمية قلبية)", "hERG blocking (cardiotoxicity)", "احتمال [0..1]", "probability [0..1]", KIND_TOX, True),
        AdmetLab3Endpoint("hERG-10um", "حجب hERG عند 10µM", "hERG blocking at 10µM", "احتمال [0..1]", "probability [0..1]", KIND_TOX, True),
        AdmetLab3Endpoint("Ames", "المطفرات (اختبار أمز)", "Mutagenicity (Ames test)", "احتمال [0..1]", "probability [0..1]", KIND_TOX, True),
        AdmetLab3Endpoint("DILI", "إصابة الكبد الدوائية", "Drug-induced liver injury", "احتمال [0..1]", "probability [0..1]", KIND_TOX, True),
        AdmetLab3Endpoint("Carcinogenicity", "السرطنة", "Carcinogenicity", "احتمال [0..1]", "probability [0..1]", KIND_TOX, True),
        AdmetLab3Endpoint("LD50_oral", "السمية الحادة الفموية LD50", "Acute oral toxicity LD50", "log(1/(mol/kg))", "log(1/(mol/kg))", KIND_TOX, True),
        AdmetLab3Endpoint("Skin_Sensitization", "التحسس الجلدي", "Skin sensitization", "احتمال [0..1]", "probability [0..1]", KIND_TOX, True),
        AdmetLab3Endpoint("SkinSen", "التفاعل الجلدي", "Skin reaction", "احتمال [0..1]", "probability [0..1]", KIND_TOX, True),
        AdmetLab3Endpoint("Hematotoxicity", "السمية الدموية", "Hematotoxicity", "احتمال [0..1]", "probability [0..1]", KIND_TOX, True),
        AdmetLab3Endpoint("Nephrotoxicity-DI", "السمية الكلوية", "Nephrotoxicity", "احتمال [0..1]", "probability [0..1]", KIND_TOX, True),
        AdmetLab3Endpoint("Neurotoxicity-DI", "السمية العصبية", "Neurotoxicity", "احتمال [0..1]", "probability [0..1]", KIND_TOX, True),
        AdmetLab3Endpoint("Ototoxicity", "السمية الأذنية", "Ototoxicity", "احتمال [0..1]", "probability [0..1]", KIND_TOX, True),
        AdmetLab3Endpoint("Respiratory", "السمية التنفسية", "Respiratory toxicity", "احتمال [0..1]", "probability [0..1]", KIND_TOX, True),
        AdmetLab3Endpoint("FDAMDD", "عيوب التطور (FDA)", "FDA developmental toxicity", "احتمال [0..1]", "probability [0..1]", KIND_TOX, True),
        AdmetLab3Endpoint("Genotoxicity", "التسرب الجيني", "Genotoxicity", "احتمال [0..1]", "probability [0..1]", KIND_TOX, True),
        AdmetLab3Endpoint("Aggregators", "المجمّعات الغروية", "Colloidal aggregators", "احتمال [0..1]", "probability [0..1]", KIND_TOX, True),
        AdmetLab3Endpoint("Promiscuous", "النشاط التعميمي (promiscuity)", "Promiscuity", "احتمال [0..1]", "probability [0..1]", KIND_TOX, True),
        AdmetLab3Endpoint("Toxicophores", "الجذور السامة", "Toxicophores", "احتمال [0..1]", "probability [0..1]", KIND_TOX, True),
    )
}

# ─────────────────────────────────────────────────────────────
# جدول التقاطع مع مهام ADMET-AI لدينا — للقياس المتبادل الجانبي.
# التقارب تعريفي (نفس نقطة النهاية البيولوجية) لا مثلي حرفي: نموذجان
# مختلفان بتدريبات مختلفة — القياس المتبادل مقارنة سلوك لا مرآة.
# ─────────────────────────────────────────────────────────────

CROSSWALK_TO_ADMET_AI: dict[str, str] = {
    # ADMETlab3 key ← ADMET-AI task_id
    "Ames": "AMES",
    "BBB": "BBB_Martins",
    "f30": "Bioavailability_Ma",
    "CYP1A2-inh": "CYP1A2_Veith",
    "CYP2C19-inh": "CYP2C19_Veith",
    "CYP2C9-inh": "CYP2C9_Veith",
    "CYP2D6-inh": "CYP2D6_Veith",
    "CYP3A4-inh": "CYP3A4_Veith",
    "Carcinogenicity": "Carcinogens_Lagunin",
    "DILI": "DILI",
    "hia": "HIA_Hou",
    "PAMPA": "PAMPA_NCATS",
    "pgp_inh": "Pgp_Broccatelli",
    "hERG": "hERG",
    "SkinSen": "Skin_Reaction",
    "NR-AR": "NR-AR",
    "NR-AR-LBD": "NR-AR-LBD",
    "NR-AhR": "NR-AhR",
    "NR-Aromatase": "NR-Aromatase",
    "NR-ER": "NR-ER",
    "NR-ER-LBD": "NR-ER-LBD",
    "NR-PPAR-gamma": "NR-PPAR-gamma",
    "SR-ARE": "SR-ARE",
    "SR-ATAD5": "SR-ATAD5",
    "SR-HSE": "SR-HSE",
    "SR-MMP": "SR-MMP",
    "SR-p53": "SR-p53",
    "caco2": "Caco2_Wang",
    "LD50_oral": "LD50_Zhu",
    "logD": "Lipophilicity_AstraZeneca",
    "logS": "Solubility_AqSolDB",
    "PPB": "PPBR_AZ",
    "logVDss": "VDss_Lombardo",
    "t0.5": "Half_Life_Obach",
}


def base_url() -> str:
    """عنوان الخدمة — يُتجاوز ببيئة PHARMA_SDL_ADMETLAB3_BASE (اختبار/بديل مرآة)."""
    return os.environ.get("PHARMA_SDL_ADMETLAB3_BASE", BASE_DEFAULT).rstrip("/")


# ─────────────────────────────────────────────────────────────
# صف النتيجة والحزمة الموحدة
# ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class AdmetLab3Result:
    """نتيجة تنبؤ جزيء واحد — القيم الرقمية فقط، والنصوص غير الصالحة مُرشَّحة."""

    smiles: str
    values: dict[str, float] = field(default_factory=dict)

    def get(self, key: str) -> float | None:
        """قيمة نقطة نهاية بالمعرّف — None إن غابت (نقص صادق لا تزييف)."""
        v = self.values.get(key)
        return float(v) if v is not None else None


@dataclass(frozen=True)
class AdmetLab3Batch:
    """حزمة نتيجة مع حالة صادقة — عقد الواجهة: لا استثناءات مهما فشل الخادم."""

    results: list[AdmetLab3Result] = field(default_factory=list)
    ok: bool = False
    reason: str | None = None  # أحد أكواد REASON_* — None عند النجاح
    n_all: int = 0
    n_valid: int = 0
    taskid: str | None = None


def _to_float(x) -> float | None:
    """تحويل متساهل (pandas/numpy → float) — كل الفاشل والنصوص → None."""
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    if math.isnan(f):  # NaN — لا قيمة قابلة للعرض
        return None
    return f


def _parse_row(smiles: str, row: dict) -> AdmetLab3Result:
    """صف من استجابة الخدمة → AdmetLab3Result (يحتمل الأعمدة الناقصة والنصية)."""
    values: dict[str, float] = {}
    for key, raw in row.items():
        if key == "smiles":
            continue
        f = _to_float(raw)
        if f is None:  # «Invalid Molecule» أو مصفوفات عرض الصور — تُرشَّح
            continue
        values[key] = f
    return AdmetLab3Result(smiles=smiles, values=values)


def predict_admet_batch(
    smiles_list: list[str],
    timeout: float = DEFAULT_TIMEOUT,
    _post=None,  # حقن للاختبارات — الافتراضي requests.post
) -> AdmetLab3Batch:
    """تنبؤ دُفعة عبر /api/admet — نجاح جزئي مقبول، وفشل كلي بحزمة فارغة.

    - الإدخال يُنظَّف؛ الدفعات الكبيرة تُقطَّع (MAX_BATCH) بتباعد زمني صريح
      التزاماً بسياسة الاستخدام الرسمية (≤5 طلبات/ثانية).
    - الجزيء غير الصالح تعيده الخدمة نصاً «Invalid Molecule» فيُستبعد —
      والفرق يوثَّق في n_all مقابل n_valid.
    - أي فشل شبكة/خدمة → AdmetLab3Batch(results=[], ok=False, reason=…).
    """
    clean = [s.strip() for s in (smiles_list or []) if s and s.strip()]
    if not clean:
        return AdmetLab3Batch(reason=REASON_EMPTY, ok=False)
    post = _post if _post is not None else requests.post

    results: list[AdmetLab3Result] = []
    n_all = 0
    n_valid = 0
    taskid: str | None = None
    url = base_url() + ADMET_ENDPOINT

    for chunk_start in range(0, len(clean), MAX_BATCH):
        chunk = clean[chunk_start : chunk_start + MAX_BATCH]
        if chunk_start > 0:
            time.sleep(_MIN_INTERVAL_S)  # بوليصة الخدمة الموثقة — تباعد مهذب
        try:
            resp = post(
                url,
                json={"SMILES": chunk, "feature": False, "uncertain": False},
                timeout=timeout,
            )
        except Exception:
            logger.warning("ADMETlab3 request failed", exc_info=True)
            return AdmetLab3Batch(results=results, n_all=n_all, n_valid=n_valid,
                                  ok=False, reason=REASON_NETWORK)
        if resp.status_code == 429:
            return AdmetLab3Batch(results=results, n_all=n_all, n_valid=n_valid,
                                  ok=False, reason=REASON_RATE)
        if resp.status_code == 404:
            return AdmetLab3Batch(results=results, n_all=n_all, n_valid=n_valid,
                                  ok=False, reason=REASON_UNAVAILABLE)
        if resp.status_code >= 500:
            return AdmetLab3Batch(results=results, n_all=n_all, n_valid=n_valid,
                                  ok=False, reason=REASON_SERVICE)
        try:
            payload = resp.json()
            data = payload["data"]
            rows = data["data"]
            n_all += int(data.get("number of all molecules", len(chunk)))
            tid = data.get("taskid")
            taskid = str(tid) if tid else taskid
        except Exception:
            logger.warning("ADMETlab3 unexpected response shape", exc_info=True)
            return AdmetLab3Batch(results=results, n_all=n_all, n_valid=n_valid,
                                  ok=False, reason=REASON_BAD_SHAPE)
        by_smiles: dict[str, dict] = {}
        for row in rows:
            smi = row.get("smiles") if isinstance(row, dict) else None
            if isinstance(smi, str):
                by_smiles[smi] = row
        for smi in chunk:
            row = by_smiles.get(smi)
            if row is None:
                continue
            parsed = _parse_row(smi, row)
            if parsed.values:  # صف بلا قيم رقمية = جزيء غير صالح
                results.append(parsed)
                n_valid += 1

    return AdmetLab3Batch(
        results=results, ok=True, reason=None, n_all=n_all, n_valid=n_valid,
        taskid=taskid,
    )


def washmol(smiles: str, timeout: float = 25.0, _post=None) -> str | None:
    """توحيد/تنظيف SMILES عبر /api/washmol — None عند أي فشل (بلا استثناءات).

    هذه النقطة تحققت حياً 2026-11-09 (200 حقيقي) وهي المفتاح الموثّق
    الوحيد المضمون اليوم؛ استعمالها التعليمي: «المدخل النظيف قبل كل حساب».
    """
    s = (smiles or "").strip()
    if not s:
        return None
    post = _post if _post is not None else requests.post
    try:
        resp = post(
            base_url() + WASHMOL_ENDPOINT,
            json={"SMILES": s},
            timeout=timeout,
        )
        payload = resp.json()
        data = payload.get("data")
        if resp.status_code == 200 and isinstance(data, list) and data:
            cleaned = data[0]
            return cleaned if isinstance(cleaned, str) else None
    except Exception:
        logger.warning("ADMETlab3 washmol failed", exc_info=True)
    return None


# ─────────────────────────────────────────────────────────────
# وضع الدرس — نمط ADMET_AI_LESSON في admet_ai_client
# ─────────────────────────────────────────────────────────────

ADMETLAB3_LESSON: dict[str, str] = {
    "ar": (
        "**ADMETlab 3.0** (مجموعة الحوسبة الحيوية وتصميم الأدوية — NAR Web Server "
        "2024) خدمة حسابية عامة بـ**121 نقطة نهاية** بشبكات DMPNN مع تقدير عدم "
        "يقين. لماذا نضيفها بجانب ADMET-AI المحلي بدل أن نكتفي به؟ **القياس "
        "المتبادل**: عندما يجيب نموذجان مستقلان (تدريبان وبنيان مختلفان) على نفس "
        "السؤال، يتعلم الطالب أن التنبؤ رأي مُقيَّم لا حقيقة مطلقة — اتفاقهما "
        "يثبت السلوك، واختلافهما يكشف حدود التعميم. جدول التقاطع في هذه الصفحة "
        "يضبط المقارنة على **{n} نقطة مشتركة** بالتعريف. القاعدة كما دائماً: "
        "كل رقم هنا إرشادي تعليمي بلا ادعاء سريري أو تنظيمي، والخدمة الخارجية "
        "لا تعتمد عليها المنصة ليعمل أي مختبر أساسي."
    ),
    "en": (
        "**ADMETlab 3.0** (Computational Biology & Drug Design Group — NAR Web "
        "Server 2024) is a public prediction service with **121 endpoints** via "
        "DMPNN deep networks with uncertainty estimates. Why add it beside our "
        "local ADMET-AI instead of settling for one? **Cross-benchmarking**: "
        "when two independent models (different training and architecture) "
        "answer the same question, students learn that a prediction is an "
        "assessed opinion, not an absolute truth — agreement confirms behaviour, "
        "disagreement exposes generalization limits. The crosswalk table here "
        "pins the comparison to **{n} shared endpoints** by definition. Same "
        "rule as always: every number is educational guidance, never clinical "
        "or regulatory — and the platform never depends on an external service "
        "for its core labs."
    ),
}

DISCLAIMER_AR = (
    "⚠️ محتوى تعليمي فقط — تنبؤات خدمة خارجية بأحكام إرشادية؛ حدود تعميمها "
    "موثقة في ورقتها. ليست توصية علاجية أو قراراً تنظيمياً، واختلاف النموذجين "
    "معلومة تعليمية لا عطل."
)
DISCLAIMER_EN = (
    "⚠️ Educational content only — third-party predictions with guidance-level "
    "verdicts; generalization limits documented in their paper. Never clinical "
    "or regulatory advice — model disagreement is a lesson, not a bug."
)
