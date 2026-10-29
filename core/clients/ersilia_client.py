"""عميل Ersilia Model Hub — تنبؤات ADMET حية من نماذج مفتوحة مُتحقَّق منها.

خطوة التحقق (2026-10-29 — من مستودعات ersilia-os على GitHub، كما تقتضي
docs/INTEGRATION-ROADMAP.md: «لا تبنِ إنتاجاً قبل خطوة تحقق واحدة»):

- eos2ta5  CardioToxNet-hERG  Output: ["Score"]  احتمالية حجب قناة hERG
           (مدرَّب على 12,620 مركباً من BindingDB/ChEMBL، الحاجبون < 10 µM)
- eos6oli  SolTranNet         Output: ["Value"] الذوبانية المائية logS
           (مدرَّب على AqSolDB، RMSE متقاطع 1.46 — مُصفّاة تلتقط 94.8%
           من غير الذائبة في تحدي التنبؤ بالذوبانية)
كلاهما Status: Ready، Deployment: Local (خادم محلي عبر `ersilia serve`).

عقد النداء الموثَّق من ersilia/serve/standard_api.py (فرع master):
    POST {base}/run   body: [{"input": "<smiles>"}, ...]
    الاستجابة: [{"input": "<smiles>", "<output_col>": value}, ...]
اسم عمود المخرجات يختلف بين النماذج (score/value/...) ويُفسَّر بمرونة —
نفس مبدأ PubChemClient مع تغيّر أسماء حقول PubChem.

المبدأ الحاكم (نمط fetch_analog_library/fetch_cpic): فشل الشبكة لا يرمي
استثناءً — يُرجع None وتعرض الواجهة المرجعية التعليمية المدمجة.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

import requests

ERSILIA_BASE = os.environ.get("ERSILIA_BASE", "http://localhost:7860").rstrip("/")
ERSILIA_TIMEOUT = 15.0

# حقول المحرف/الإدخال في صفوف الاستجابة — لا تُعتبر قيم تنبؤ
_META_KEYS = frozenset({"key", "input", "text", "lookup_input"})


# ─────────────────────────────────────────────────────────────
# كتالوج النماذج المُتحقَّق منها
# ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ErsiliaModel:
    """بطاقة نموذج Ersilia موثّق — للتبويب ولتفسير المخرجات."""

    model_id: str
    name_ar: str
    name_en: str
    endpoint: str  # معرّف نقطة النهاية، مثل "hERG_blockade_prob"
    endpoint_ar: str
    endpoint_en: str
    column_hint: str  # اسم عمود المخرجات المعروف (تلميح، ليس شرطاً)
    unit_ar: str
    unit_en: str
    low_good: bool  # هل انخفاض القيمة أفضل؟


MODELS: dict[str, ErsiliaModel] = {
    "eos2ta5": ErsiliaModel(
        model_id="eos2ta5",
        name_ar="سمية القلب hERG (CardioToxNet)",
        name_en="hERG cardiotoxicity (CardioToxNet)",
        endpoint="hERG_blockade_prob",
        endpoint_ar="احتمالية حجب قناة hERG",
        endpoint_en="Probability of hERG channel blockade",
        column_hint="score",
        unit_ar="احتمال بين 0 و 1",
        unit_en="probability in [0, 1]",
        low_good=True,
    ),
    "eos6oli": ErsiliaModel(
        model_id="eos6oli",
        name_ar="الذوبانية المائية (SolTranNet)",
        name_en="Aqueous solubility (SolTranNet)",
        endpoint="logS_mol_per_L",
        endpoint_ar="لوغاريتم الذوبانية المائية (logS)",
        endpoint_en="Aqueous solubility (logS)",
        column_hint="value",
        unit_ar="mol/L (مقياس لوغاريتمي)",
        unit_en="mol/L (log scale)",
        low_good=False,
    ),
}


@dataclass(frozen=True)
class AdmetRow:
    """صف تنبؤ ADMET موحّد — حي من Ersilia أو معروض بجانبه احتياطي تعليمي."""

    model_id: str
    smiles: str
    endpoint: str
    value: float
    verdict_ar: str
    verdict_en: str


# ─────────────────────────────────────────────────────────────
# الحكم التعليمي على القيمة
# ─────────────────────────────────────────────────────────────

# حدود الأحكام إرشادية تعليمية (وليست عتبات تنظيمية) — موثّقة في وضع الدرس
HERG_LOW, HERG_HIGH = 0.1, 0.3
SOL_GOOD, SOL_BAD = -2.0, -4.0


def verdict(model_id: str, value: float, lang: str = "ar") -> str:
    """حكم تعليمي قصير على قيمة التنبؤ — بلا ادعاء سريري."""
    ar = lang == "ar"
    if model_id == "eos2ta5":
        if value < HERG_LOW:
            return "خطر منخفض" if ar else "Low risk"
        if value <= HERG_HIGH:
            return "منطقة رمادية — مراقبة" if ar else "Grey zone — monitor"
        return "خطر مرتفع — فحوص QT" if ar else "High risk — QT follow-up"
    if model_id == "eos6oli":
        if value > SOL_GOOD:
            return "ذوبان جيد" if ar else "Good solubility"
        if value >= SOL_BAD:
            return "ذوبان متوسط" if ar else "Moderate solubility"
        return "ذوبان ضعيف — عقبة تطوير" if ar else "Poor solubility — development risk"
    raise ValueError(f"unknown model_id: {model_id}")


# ─────────────────────────────────────────────────────────────
# المرجعية التعليمية المدمجة (احتياطي بلا شبكة)
# ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ReferenceRow:
    """صف مرجعي تعليمي موثّق — أحكام فئوية من أدبيات معروفة، بلا أرقام مزيفة."""

    example_ar: str
    example_en: str
    category_ar: str
    category_en: str
    note_ar: str
    note_en: str


# قيم/أحكام موثّقة من الأدبيات: تيرفينادين وسيزابريد سُحِبا/قيّدا بسبب
# إطالة QT عبر hERG؛ الإيتراكونازول عملياً غير ذائب؛ الباراسيتامول جيد الذوبان.
FALLBACK_REFERENCE: dict[str, list[ReferenceRow]] = {
    "eos2ta5": [
        ReferenceRow(
            "تيرفينادين", "Terfenadine",
            "خطر مرتفع", "High risk",
            "سُحب من الأسواق (1997/1998) بسبب إطالة QT المميتة عبر حجب hERG.",
            "Withdrawn (1997/1998) over fatal QT prolongation via hERG blockade.",
        ),
        ReferenceRow(
            "سيزابريد", "Cisapride",
            "خطر مرتفع", "High risk",
            "قيود سحب واسعة بعد حالات اضطراب نظم قلبي — نفس آلية hERG.",
            "Broadly restricted/withdrawn after cardiac arrhythmia cases — same hERG mechanism.",
        ),
        ReferenceRow(
            "هالوبيريدول", "Haloperidol",
            "متوسط إلى مرتفع", "Moderate to high",
            "إطالة QT موثّقة تعتمد على الجرعة — مراقبة تخطيط القلب.",
            "Dose-dependent QT prolongation documented — ECG monitoring required.",
        ),
        ReferenceRow(
            "أسبرين", "Aspirin",
            "منخفض", "Low",
            "لا إشارة hERG ذات معنى عند التعرضات العلاجية المعتادة.",
            "No meaningful hERG signal at usual therapeutic exposures.",
        ),
    ],
    "eos6oli": [
        ReferenceRow(
            "إيتراكونازول", "Itraconazole",
            "ضعيف جداً", "Very poor",
            "عملياً غير ذائب — صياغته تتطلب مذيبات وأنظمة توصيل خاصة.",
            "Practically insoluble — formulation needs special solvents/delivery.",
        ),
        ReferenceRow(
            "غريسيوفولفين", "Griseofulvin",
            "ضعيف", "Poor",
            "ذوبان ضعيف كلاسيكي يقلّل الامتصاص الفموي ويقتضي جسيمات دقيقة.",
            "Classic poor solubility reducing oral absorption; micronization needed.",
        ),
        ReferenceRow(
            "إيبوبروفين", "Ibuprofen",
            "متوسط", "Moderate",
            "ذوبان مقبول مع حساسية للـ pH المعدي — مثال BCS class II.",
            "Acceptable solubility, pH-sensitive — a BCS class II example.",
        ),
        ReferenceRow(
            "باراسيتامول", "Paracetamol",
            "جيد", "Good",
            "ذوبان جيد يدعم صيغاً فموية متعددة — مثال BCS class I.",
            "Good solubility supports many oral forms — a BCS class I example.",
        ),
    ],
}

SERVER_HINT_AR = (
    "لتشغيل خادم Ersilia محلياً (بيئة مستقلة عن التطبيق):\n"
    "```bash\npip install ersilia\n"
    "ersilia fetch eos2ta5\n"
    "ersilia serve eos2ta5   # الخادم على http://localhost:7860\n```"
    "\nيمكن تغيير العنوان بمتغير البيئة `ERSILIA_BASE`."
)
SERVER_HINT_EN = (
    "To run an Ersilia server locally (independent from this app):\n"
    "```bash\npip install ersilia\n"
    "ersilia fetch eos2ta5\n"
    "ersilia serve eos2ta5   # server on http://localhost:7860\n```"
    "\nOverride the URL with the `ERSILIA_BASE` environment variable."
)

DISCLAIMER_AR = (
    "⚠️ محتوى تعليمي فقط — تنبؤات نماذج بحثية مفتوحة بحدود تعميم معروفة. "
    "الأحكام إرشادية وليست توصية علاجية أو قراراً تنظيمياً."
)
DISCLAIMER_EN = (
    "⚠️ Educational content only — predictions from open research models with "
    "known generalization limits. Verdicts are indicative, never clinical or regulatory advice."
)

# نص وضع الدرس — نمط LESSON في core/docking.py
ADMET_LESSON: dict[str, str] = {
    "ar": (
        "معظم المرشحات الدوائية لا تفشل في السرير لأنها ضعيفة التثبيط، بل لأن جسمها "
        "يرفضها: **سمية قلبية** (حجب قناة hERG البوتاسية يطيل QT ويسبب اضطراب نظم "
        "مميت — سحب تيرفينادين وسيزابريد الدرس الأشهر)، و**ذوبان ضعيف** يجعل الدواء "
        "لا يُمتص. نموذج **CardioToxNet** (eos2ta5) يُرجع احتمالية حجب hERG — كلما "
        "اقتربت من 1 زاد الخطر، وحدود الحكم {hlow}/{hhigh} إرشادية تعليمية وليست "
        "عتبات تنظيمية. نموذج **SolTranNet** (eos6oli) يُرجع الذوبانية لوغاريتمياً "
        "logS (mol/L): فوق {sgood} ذوبان جيد (≥ 10 mmol/L)، وتحت {sbad} ضعيف "
        "(< 0.1 mmol/L). درّس القاعدة: **الفيزياء تُظهر قدرة الربط، وADMET يُظهر "
        "هل سيصل الدواء إلى الهدف أصلاً**."
    ),
    "en": (
        "Most drug candidates don't fail clinically because they bind poorly, but "
        "because the body rejects them: **cardiotoxicity** (blocking the hERG "
        "potassium channel prolongs QT and causes fatal arrhythmia — the terfenadine "
        "and cisapride withdrawals are the classic lesson), and **poor solubility** "
        "that prevents absorption. **CardioToxNet** (eos2ta5) returns an hERG "
        "blockade probability — closer to 1 means higher risk; the {hlow}/{hhigh} "
        "verdict thresholds are educational conventions, not regulatory cut-offs. "
        "**SolTranNet** (eos6oli) returns logS in mol/L: above {sgood} is good "
        "(≥ 10 mmol/L), below {sbad} is poor (< 0.1 mmol/L). Remember: **physics "
        "shows binding ability; ADMET shows whether the drug ever reaches its target**."
    ),
}.copy()


# ─────────────────────────────────────────────────────────────
# التفسير المرن للمخرجات
# ─────────────────────────────────────────────────────────────

def _to_float(value) -> float | None:
    """تحويل متساهل لأي شكل رقمي تُرجعه نماذج Ersilia (كل الأشكال الفاشلة → None)."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, list) and len(value) == 1:
        return _to_float(value[0])
    if isinstance(value, dict):
        for sub in value.values():
            f = _to_float(sub)
            if f is not None:
                return f
        return None
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def _extract_value(row: dict, model: ErsiliaModel) -> float | None:
    """استخراج قيمة التنبؤ من صف استجابة — يتسامح مع اختلاف أسماء الأعمدة."""
    # 1. عمود النموذج المعروف (score / value / ...)
    for key in {model.column_hint, model.column_hint.lower()}:
        if key in row:
            f = _to_float(row[key])
            if f is not None:
                return f
    # 2. الاسم العام القديم outcome
    if "outcome" in row:
        f = _to_float(row["outcome"])
        if f is not None:
            return f
    # 3. أي مفتاح آخر غير مفاتيح المحارف — أول قيمة رقمية
    for key, val in row.items():
        if key in _META_KEYS:
            continue
        f = _to_float(val)
        if f is not None:
            return f
    return None


def _iter_result_rows(payload) -> list[dict]:
    """تسطيح أشكال الاستجابة المتعددة إلى قائمة صفوف قاموسية.

    الأشكال المقبولة: [ {...}, ... ] | {"outputs": [...]} | {"result": [...] | {...}}
    | dict مفرد. الصفوف غير القاموسية تُستبعد (تُعالج في parse على مستوى الصف).
    """
    if isinstance(payload, dict):
        if isinstance(payload.get("outputs"), list):
            payload = payload["outputs"]
        elif isinstance(payload.get("result"), list):
            payload = payload["result"]
        elif "result" in payload and isinstance(payload["result"], dict):
            payload = [payload["result"]]
        elif payload:
            payload = [payload]
        else:
            return []
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    return []


# ─────────────────────────────────────────────────────────────
# نداء الخادم — النمط المعتمد: None عند أي فشل
# ─────────────────────────────────────────────────────────────

def _parse_row(row: dict, model: ErsiliaModel, fallback_smiles: str) -> AdmetRow | None:
    """صف استجابة → AdmetRow أو None إن لم توجد قيمة قابلة للتفسير."""
    value = _extract_value(row, model)
    if value is None:
        return None
    smiles = str(row.get("input") or row.get("text") or fallback_smiles)
    return AdmetRow(
        model_id=model.model_id,
        smiles=smiles,
        endpoint=model.endpoint,
        value=value,
        verdict_ar=verdict(model_id=model.model_id, value=value, lang="ar"),
        verdict_en=verdict(model_id=model.model_id, value=value, lang="en"),
    )


def predict_admet(
    smiles: str,
    model_id: str,
    timeout: float | None = None,
    base_url: str | None = None,
) -> AdmetRow | None:
    """نداء واحد لخادم Ersilia — يُرجع None عند أي فشل شبكة أو شكل غير متوقع.

    التوقيع يتبع مخطط docs/INTEGRATION-ROADMAP.md حرفياً.
    """
    model = MODELS.get(model_id)
    if model is None:
        raise ValueError(
            f"unknown Ersilia model_id: {model_id} — known: {sorted(MODELS)}"
        )
    rows = _run_server([smiles], model, timeout=timeout, base_url=base_url)
    return rows[0] if rows else None


def predict_admet_batch(
    smiles_list: list[str],
    model_id: str,
    timeout: float | None = None,
    base_url: str | None = None,
) -> list[AdmetRow]:
    """تنبؤ دُفعة — النجاح الجزئي مقبول: الصفوف غير القابلة للتفسير تُستبعد فقط.

    الترتيب يتبع ترتيب النداء عند توفر الصفوف؛ الصفوف الفائضة/الناقصة لا تُخطئ.
    """
    model = MODELS.get(model_id)
    if model is None:
        raise ValueError(
            f"unknown Ersilia model_id: {model_id} — known: {sorted(MODELS)}"
        )
    clean = [s.strip() for s in smiles_list if s and s.strip()]
    if not clean:
        return []
    return _run_server(clean, model, timeout=timeout, base_url=base_url)


def _run_server(
    smiles_list: list[str],
    model: ErsiliaModel,
    timeout: float | None,
    base_url: str | None,
) -> list[AdmetRow]:
    """النداء الفعلي — أي استثناء شبكة/تفسير → قائمة فارغة (لا تنهار الواجهة)."""
    base = (base_url or ERSILIA_BASE).rstrip("/")
    effective_timeout = ERSILIA_TIMEOUT if timeout is None else timeout
    body = [{"input": smi} for smi in smiles_list]
    try:
        resp = requests.post(
            f"{base}/run", json=body, timeout=effective_timeout
        )
        resp.raise_for_status()
        payload = resp.json()
        rows = _iter_result_rows(payload)
        parsed: list[AdmetRow] = []
        for smi, row in zip(smiles_list, rows):
            parsed_row = _parse_row(row, model, fallback_smiles=smi)
            if parsed_row is not None:
                parsed.append(parsed_row)
        return parsed
    except (requests.RequestException, ValueError, TypeError, KeyError):
        return []


def fallback_reference_df(model_id: str, lang: str = "ar") -> list[dict]:
    """المرجعية التعليمية المدمجة كصفوف جاهزة للعرض — بلا شبكة ودون ادعاء تنبؤ."""
    rows = FALLBACK_REFERENCE.get(model_id, [])
    ar = lang == "ar"
    return [
        {
            "مثال" if ar else "Example": r.example_ar if ar else r.example_en,
            "الفئة" if ar else "Category": r.category_ar if ar else r.category_en,
            "لماذا؟" if ar else "Why?": r.note_ar if ar else r.note_en,
        }
        for r in rows
    ]
