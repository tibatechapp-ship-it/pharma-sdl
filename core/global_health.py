"""الصحة العالمية — نماذج مفتوحة لمرضَين يهملهما السوق (P15).

خطوة التحقق (2026-11-05 — مستودعات ersilia-os الرسمية على GitHub،
كما تقتضي docs/INTEGRATION-ROADMAP.md: «لا تبنِ إنتاجاً قبل خطوة تحقق»):

- eos4zfy  MAIP          عمود المخرجات: ["maip_score"] — درجة النشاط
           ضد المرحلة الدموية من Plasmodium falciparum (مكافئ منصة MAIP،
           Bosc et al. 2021) — float باتجاه high، مقياس غير محدود
           (ترتيبي: الأعلى أنشط)
- eos8d8a  MycPermCheck  عمود المخرجات: ["mycpermcheck"] — احتمال نفاذية
           غلاف M. tuberculosis الخلوي — float في [0,1] باتجاه high،
           مُدرَّب على مركبات نشطة (MIC < 10 µM، MW < 500 Da)

العبء العالمي الموثَّق (WHO 2024، بيانات 2023):
- الملاريا: 263 مليون حالة و597 ألف وفاة (World Malaria Report 2024) —
  نحو 11 مليون حالة أكثر من 2022
- السل: 10.8 مليون إصابة و1.25 مليون وفاة (Global TB Report 2024) —
  عاد عام 2023 القاتل المعدني الأول عالمياً متجاوزاً كوفيد-19

القمع ثلاثي المراحل (نمط three_tier.py): درجة المرضى ← بوابة ADMET ←
المختبر الرطب (مختبر MIC/PK-PD). كل مرحلة رخيصة تسبق أغلى منها، ولا
مرحلة تتجاوز حكم أعلى منها — وكل عميل يتدهور بصدق (لا قيمة مختلقة).
"""
from __future__ import annotations

from dataclasses import dataclass

from core.clients import ersilia_client as ec

# ─────────────────────────────────────────────────────────────
# بطاقات الممرضين — أرقام WHO موثّقة لا إحصاءات مزيفة
# ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class PathogenCard:
    """بطاقة ممرض موثّقة — النموذج، والعبء العالمي بمرجعه."""

    pathogen_id: str
    name_ar: str
    name_en: str
    agent_ar: str
    agent_en: str
    model_id: str  # مرجع إلى ec.MODELS
    endpoint: str
    who_cases: str
    who_deaths: str
    who_year: str
    who_source_ar: str
    who_source_en: str
    burden_note_ar: str
    burden_note_en: str


PATHOGENS: dict[str, PathogenCard] = {
    "malaria": PathogenCard(
        pathogen_id="malaria",
        name_ar="الملاريا",
        name_en="Malaria",
        agent_ar="المتصوّرة المنجلية (Plasmodium falciparum)",
        agent_en="Plasmodium falciparum",
        model_id="eos4zfy",
        endpoint="maip_score",
        who_cases="263 مليون",
        who_deaths="597 ألف",
        who_year="2023",
        who_source_ar="تقرير الملاريا العالمي 2024 (منظمة الصحة العالمية)",
        who_source_en="World Malaria Report 2024 (WHO)",
        burden_note_ar="نحو 11 مليون حالة أكثر من 2022 — التقدم توقف والفجوة التمويلية تتسع.",
        burden_note_en="About 11 million more cases than 2022 — progress has stalled and the funding gap widens.",
    ),
    "tuberculosis": PathogenCard(
        pathogen_id="tuberculosis",
        name_ar="السل",
        name_en="Tuberculosis",
        agent_ar="عصية السل (Mycobacterium tuberculosis)",
        agent_en="Mycobacterium tuberculosis",
        model_id="eos8d8a",
        endpoint="mtb_permeability_prob",
        who_cases="10.8 مليون",
        who_deaths="1.25 مليون",
        who_year="2023",
        who_source_ar="التقرير العالمي عن السل 2024 (منظمة الصحة العالمية)",
        who_source_en="Global Tuberculosis Report 2024 (WHO)",
        burden_note_ar="عاد عام 2023 القاتل المعدني الأول عالمياً متجاوزاً كوفيد-19.",
        burden_note_en="In 2023 it returned to being the world's leading infectious killer, surpassing COVID-19.",
    ),
}


# ─────────────────────────────────────────────────────────────
# القمع ثلاثي المراحل — كل مرحلة رخيصة تسبق أغلى منها
# ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class FunnelStage:
    """مرحلة في قمع الصحة العالمية — للتبويب وللدرس."""

    stage_id: int
    title_ar: str
    title_en: str
    tool_ar: str
    tool_en: str
    cost_ar: str
    cost_en: str


PATHOGEN_FUNNEL: tuple[FunnelStage, ...] = (
    FunnelStage(
        1,
        "درجة النشاط ضد الممرض",
        "Pathogen activity score",
        "Ersilia حي — eos4zfy/eos8d8a عبر خادم محلي",
        "Live Ersilia — eos4zfy/eos8d8a via local server",
        "ثوانٍ لكل جزيء (CPU)",
        "Seconds per molecule (CPU)",
    ),
    FunnelStage(
        2,
        "بوابة ADMET",
        "ADMET gate",
        "hERG + الذوبانية — نفس عميل Ersilia (أو ADMET-AI المحلي)",
        "hERG + solubility — same Ersilia client (or local ADMET-AI)",
        "ثوانٍ لكل جزيء (CPU)",
        "Seconds per molecule (CPU)",
    ),
    FunnelStage(
        3,
        "المختبر الرطب — MIC ثم PK/PD",
        "Wet lab — MIC then PK/PD",
        "مختبر MIC في تبويب MIC Lab: Cmax/MIC وfT>MIC وAUC/MIC",
        "MIC Lab tab: Cmax/MIC, fT>MIC and AUC/MIC indices",
        "أيام إلى أسابيع — التجربة الحقيقية تحكم",
        "Days to weeks — the real experiment decides",
    ),
)


@dataclass(frozen=True)
class PathogenRow:
    """قراءة موحّدة لجزيء ضد ممرض — حية أو متدهورة بصدق."""

    smiles: str
    pathogen_id: str
    model_id: str
    endpoint: str
    value: float | None
    status: str  # live | unavailable_offline | invalid_input
    verdict_ar: str
    verdict_en: str


def _smiles_valid(smiles: str) -> bool:
    """تحقق RDKit إن توفر — وإلا تُترك البطاقة للخادم نفسه."""
    try:
        from rdkit import Chem
    except ImportError:
        return True
    return Chem.MolFromSmiles(smiles) is not None


def assess_candidate(
    smiles: str,
    pathogen_id: str,
    client_fn=None,
    timeout: float | None = None,
    base_url: str | None = None,
) -> PathogenRow:
    """جزيء واحد ضد ممرض واحد — التدهور صادق في كل الحالات الثلاث.

    client_fn قابل للحقن (نمط الاختبارات) — افتراضه نداء Ersilia الحي.
    """
    card = PATHOGENS.get(pathogen_id)
    if card is None:
        raise ValueError(f"unknown pathogen_id: {pathogen_id} — known: {sorted(PATHOGENS)}")
    smi = smiles.strip()
    if not smi or not _smiles_valid(smi):
        return PathogenRow(
            smiles=smiles,
            pathogen_id=pathogen_id,
            model_id=card.model_id,
            endpoint=card.endpoint,
            value=None,
            status="invalid_input",
            verdict_ar="إدخال غير صالح — تُستبعد البطاقة" ,
            verdict_en="Invalid input — card excluded",
        )
    fn = client_fn or ec.predict_admet
    row = fn(smi, card.model_id, timeout=timeout, base_url=base_url)
    if row is None:
        return PathogenRow(
            smiles=smi,
            pathogen_id=pathogen_id,
            model_id=card.model_id,
            endpoint=card.endpoint,
            value=None,
            status="unavailable_offline",
            verdict_ar="خادم Ersilia غير متاح — لا قيمة مختلقة" ,
            verdict_en="Ersilia server unavailable — no fabricated value",
        )
    return PathogenRow(
        smiles=row.smiles,
        pathogen_id=pathogen_id,
        model_id=card.model_id,
        endpoint=card.endpoint,
        value=row.value,
        status="live",
        verdict_ar=ec.verdict(card.model_id, row.value, "ar"),
        verdict_en=ec.verdict(card.model_id, row.value, "en"),
    )


def assess_panel(
    pathogen_id: str,
    smiles_list: list[str] | None = None,
    client_fn=None,
) -> list[PathogenRow]:
    """اللوحة المرجعية كاملة ضد ممرض — النجاح الجزئي مقبول ولا يُخفى."""
    smis = smiles_list if smiles_list is not None else list(GLOBAL_PRESETS.values())
    return [assess_candidate(s, pathogen_id, client_fn=client_fn) for s in smis]


# ─────────────────────────────────────────────────────────────
# قرار القمع — متى نكمل إلى المرحلة التالية؟
# ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class FunnelVerdict:
    """حكم القمع: أبعد مرحلة يمكن الوصول إليها + السبب الصادق."""

    stage_reached: int  # 0 توقف قبل كل شيء · 1 توقف عند المرضى · 2 توقف عند ADMET · 3 للمختبر
    decision_ar: str
    decision_en: str
    reason_ar: str
    reason_en: str


def funnel_decision(
    pathogen_id: str,
    pathogen_value: float | None,
    herg_value: float | None = None,
    logs_value: float | None = None,
) -> FunnelVerdict:
    """القواعد الخمس للقمع — كل فرع قابل للاختبار وموثق في تقرير P15.

    1. لا قيمة حية → توقف صادق (لا قرارات على بيانات غائبة).
    2. نشاط الممرض تحت العتبة → توقف عند المرحلة 1: جزيء غير نشط
       لا يستحق بوابة السمية إطلاقاً — أرخص إخفاق ممكن.
    3. نشط لكن hERG مرتفع → توقف عند المرحلة 2 (فشل السمية أغلى).
    4. نشط لكن الذوبان ضعيف → توقف عند المرحلة 2 (فشل الصياغة).
    5. النشاط + ADMET سليمان → المرحلة 3: المختبر الرطب يحكم (MIC/PK-PD).
    """
    card = PATHOGENS.get(pathogen_id)
    if card is None:
        raise ValueError(f"unknown pathogen_id: {pathogen_id} — known: {sorted(PATHOGENS)}")
    if pathogen_value is None:
        return FunnelVerdict(
            0,
            "توقف صادق",
            "Honest stop",
            "لا قيمة حية من النموذج — لا قرار على بيانات غائبة.",
            "No live model value — no decision on missing data.",
        )
    if pathogen_id == "malaria":
        weak = pathogen_value < ec.MAIP_ACTIVE
        weak_reason_ar = "درجة MAIP تحت عتبة النشاط — جزيء غير نشط لا يستحق بوابة السمية إطلاقاً (أرخص إخفاق ممكن)."
        weak_reason_en = "MAIP score below the activity threshold — an inactive molecule never merits the toxicity gate (the cheapest possible failure)."
    else:
        weak = pathogen_value < ec.PERM_BAD
        weak_reason_ar = "نفاذية الغلاف ضعيفة — الجزيء لن يلتقي بضعه داخل الخلية أصلاً."
        weak_reason_en = "Weak envelope permeability — the molecule will never even meet its intracellular target."
    if weak:
        return FunnelVerdict(
            1,
            "توقف — بلا نشاط ضد الممرض",
            "Stop — no pathogen activity",
            weak_reason_ar,
            weak_reason_en,
        )
    herg_bad = herg_value is not None and herg_value > ec.HERG_HIGH
    if herg_bad:
        return FunnelVerdict(
            2,
            "توقف — بوابة السمية القلبية",
            "Stop — cardiotoxicity gate",
            "النشاط متوقع لكن خطر hERG مرتفع — أغلى إخفاق أن يسقط المرشح في السريرية.",
            "Activity is predicted but hERG risk is high — the costliest failure is falling in the clinic.",
        )
    sol_bad = logs_value is not None and logs_value < ec.SOL_BAD
    if sol_bad:
        return FunnelVerdict(
            2,
            "توقف — بوابة الذوبان",
            "Stop — solubility gate",
            "النشاط متوقع لكن الذوبان عقبة تطوير — صياغة غير ممكنة بأدوات عادية.",
            "Activity is predicted but solubility is a development risk — no routine formulation possible.",
        )
    return FunnelVerdict(
        3,
        "مرشح للمختبر الرطب",
        "Candidate for the wet lab",
        "نشاط + ADMET سليمان — تُقاس MIC تجريبياً ثم تُبنى مؤشرات PK/PD في تبويب MIC Lab.",
        "Activity + ADMET clean — measure MIC experimentally, then build PK/PD indices in the MIC Lab tab.",
    )


# ─────────────────────────────────────────────────────────────
# اللوحة المرجعية — 5 جزيئات موثقة SMILES + أوزان مرجعية
# ─────────────────────────────────────────────────────────────

# الأوزان الجزيئية المرجعية من الأدبيات (تُفحص في التجميد بتسامح ±0.5)
# كل SMILES أدناه مُتحقَّق منه من PubChem (PUG REST، 2026-11-05) بمعرّفات CID
GLOBAL_PRESETS: dict[str, str] = {
    "أرتيميسينين — أساس علاج الملاريا (CID 68827)": (
        "C[C@@H]1CC[C@H]2[C@H](C(=O)O[C@H]3[C@@]24[C@H]1CC[C@](O3)(OO4)C)C"
    ),
    "كلوروكين — نشط تاريخياً (مقاومة) (CID 2726)": (
        "CCN(CC)CCCC(C)NC1=C2C=CC(=CC2=NC=C1)Cl"
    ),
    "باراسيتامول — مرجعية سالبة (لا مضاد للملاريا) (CID 1983)": (
        "CC(=O)NC1=CC=C(C=C1)O"
    ),
    "إيزونيازيد — أول خط لعلاج السل (CID 3767)": "C1=CN=CC=C1C(=O)NN",
    "بيرازيناميد — أول خط لعلاج السل (CID 1042)": "C1=CN=C(C=N1)C(=O)N",
}

GLOBAL_PRESET_MW: dict[str, float] = {
    "C[C@@H]1CC[C@H]2[C@H](C(=O)O[C@H]3[C@@]24[C@H]1CC[C@](O3)(OO4)C)C": 282.33,
    "CCN(CC)CCCC(C)NC1=C2C=CC(=CC2=NC=C1)Cl": 319.90,
    "CC(=O)NC1=CC=C(C=C1)O": 151.16,
    "C1=CN=CC=C1C(=O)NN": 137.14,
    "C1=CN=C(C=N1)C(=O)N": 123.11,
}


# ─────────────────────────────────────────────────────────────
# الدرس العربي — القواعد الخمس
# ─────────────────────────────────────────────────────────────

GLOBAL_LESSON: dict[str, str] = {
    "ar": (
        "أمراض الفقر لا تجذب السوق: **الملاريا** أوقفت 263 مليون حالة و597 ألف "
        "وفاة في 2023، و**السل** عاد القاتل المعدني الأول عالمياً (10.8 مليون "
        "إصابة، 1.25 مليون وفاة) — ومع ذلك تبقى كيمياء الأمراض المهملة هامشية "
        "في الصناعة. هنا يقلب المصدر المفتوح المعادلة: **منصة MAIP** (eos4zfy، "
        "Bosc et al. 2021) تُرجع درجة النشاط ضد المرحلة الدموية من المتصوّرة "
        "المنجلية — كلما ارتفعت الدرجة زاد النشاط المتوقع، والأصح استخدامها "
        "ترتيبياً لا قطعياً. و**MycPermCheck** (eos8d8a) يُرجع احتمال اختراق "
        "غلاف العصية السلية — الجدار الشمعي الذي يجعل مضادات قوية عديمة "
        "الفائدة إن لم تعبره (النموذج مُدرَّب على MW < 500، فالجزيئات الأضخم "
        "خارج مجاله). **القاعدة الحاكمة: القمع** — درجة المرضى تفرز الآلاف "
        "بالثواني، ثم بوابة ADMET (هل يرفضه الجسم؟)، ثم المختبر الرطب حيث "
        "تُقاس MIC وتُبنى مؤشرات PK/PD. النماذج المفتوحة لا تصنع دواءً — "
        "لكنها تُوفر على مختبرات البلدان الفقيرة سنوات من الفرز الأعمى."
    ),
    "en": (
        "Diseases of poverty don't attract markets: **malaria** caused 263 "
        "million cases and 597,000 deaths in 2023, and **tuberculosis** returned "
        "as the world's leading infectious killer (10.8 million cases, 1.25 "
        "million deaths) — yet neglected-disease chemistry remains marginal in "
        "industry. Open source flips the equation: the **MAIP** platform "
        "(eos4zfy, Bosc et al. 2021) returns a blood-stage P. falciparum "
        "activity score — higher means more predicted activity, and it is best "
        "used for ranking rather than hard cut-offs. **MycPermCheck** (eos8d8a) "
        "returns the probability of crossing the mycobacterial envelope — the "
        "waxy barrier that renders potent antibiotics useless if they cannot "
        "cross it (trained on MW < 500, so larger molecules are out of domain). "
        "**The governing rule: the funnel** — the pathogen score screens "
        "thousands in seconds, then the ADMET gate (does the body reject it?), "
        "then the wet lab where MIC is measured and PK/PD indices are built. "
        "Open models make no drug — but they spare poor countries' laboratories "
        "years of blind screening."
    ),
}


def trust_lesson(lang: str = "ar") -> str:
    """الدرس المعلن — نمط three_tier.trust_lesson."""
    return GLOBAL_LESSON.get(lang, GLOBAL_LESSON["ar"])


def panel_df(rows: list[PathogenRow], lang: str = "ar") -> list[dict]:
    """صفوف اللوحة جاهزة للعرض — أسماء أعمدة ثنائية اللغة."""
    ar = lang == "ar"
    col_smiles = "SMILES"
    col_value = "القيمة" if ar else "Value"
    col_status = "الحالة" if ar else "Status"
    col_verdict = "الحكم" if ar else "Verdict"
    status_ar = {"live": "🌐 حي", "unavailable_offline": "غير متاح دون شبكة", "invalid_input": "إدخال غير صالح"}
    status_en = {"live": "🌐 live", "unavailable_offline": "unavailable offline", "invalid_input": "invalid input"}
    out: list[dict] = []
    for r in rows:
        val = "—" if r.value is None else f"{r.value:.3f}"
        out.append(
            {
                col_smiles: r.smiles,
                col_value: val,
                col_status: status_ar.get(r.status, r.status) if ar else status_en.get(r.status, r.status),
                col_verdict: r.verdict_ar if ar else r.verdict_en,
            }
        )
    return out


def funnel_df(rows: list[FunnelVerdict], lang: str = "ar") -> list[dict]:
    """صفوف قرار القمع جاهزة للعرض."""
    ar = lang == "ar"
    col_stage = "المرحلة" if ar else "Stage"
    col_decision = "القرار" if ar else "Decision"
    col_reason = "السبب" if ar else "Reason"
    stage_ar = {0: "—", 1: "١ · المرضى", 2: "٢ · ADMET", 3: "٣ · المختبر الرطب"}
    stage_en = {0: "—", 1: "1 · Pathogen", 2: "2 · ADMET", 3: "3 · Wet lab"}
    return [
        {
            col_stage: stage_ar.get(v.stage_reached, str(v.stage_reached)) if ar else stage_en.get(v.stage_reached, str(v.stage_reached)),
            col_decision: v.decision_ar if ar else v.decision_en,
            col_reason: v.reason_ar if ar else v.reason_en,
        }
        for v in rows
    ]
