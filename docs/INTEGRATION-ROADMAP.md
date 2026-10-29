# 🧩 خريطة دمج النماذج الخارجية في pharma-sdl — بيئة آلية تدريجية

> الهدف: منصة عربية متقدمة تعمل **auto** — توليد ← تحقق ← التحقام ← ADMET ← PGx ← قرار.
> المبدأ الحاكم: **تكامل لا إعادة بناء** — كل تقنية تدخل كعميل رقيق في `core/clients/`
> يتبع نمط `fetch_analog_library` (فشل الشبكة لا يرمي استثناءً؛ fallback واضح للمستخدم)،
> ومع كل عميل اختبارات offline بـmock + اختبار integration موسوم.
>
> ⚠️ **علامة التحقق**: التقنيات الموسومة «يتطلب تحقق» جاءت من مسح خارجي ولم تُختبر
> نقاط نهايتها/حزمها فعلياً بعد — لا تبنِ عليها إنتاجاً قبل خطوة تحقق واحدة (curl/pip).

## 0) الأساس الحالي — مكتمل في فرع `feat/pharma-hardening`

تثبيت اعتماديات دقيق (==) · تغطية كامل المشروع بلا floor وهمي · اختبارات AppTest
للواجهة · مقارنة RF مقابل GradientBoosting (R²/RMSE) · لافتة stlite التوجيهية.
**لا شيء من ما يلي يبدأ قبل دمج هذا الفرع في main.**

## 1) طبقات خط الأنابيب الآلي — من يفعل ماذا؟

| الطبقة | التقنية | طريقة الدمج | حالة التحقق | الوحدة المستهدفة |
|---|---|---|---|---|
| توليد الجزيئات | JapanFold (HTTP async) | عميل REST: submit→poll→fetch | ⚠️ يتطلب تحقق | `core/clients/japanfold.py` |
| توليد محادثة | ChatChemTS (FastAPI) | microservice محلي + عميل HTTP | ⚠️ يتطلب تحقق | خدمة منفصلة + `core/clients/chatchemts.py` |
| التحقام (سريع) | Matcha | API أو كود مفتوح | ⚠️ يتطلب تحقق | `core/clients/matcha.py` |
| التحقام (كلاسيكي) | DockThor | `pip install dock-thor-client` | ⚠️ تحقق الحزمة | `core/clients/dockthor.py` |
| التحقام (محلي دائم) | AutoDock Vina | مدمج فعلاً ✅ | ✅ يعمل | `core/docking.py` |
| ADMET/QSAR | Ersilia Model Hub | `pip install ersilia` + CLI/serve | ✅ متحقق (مشروع ناضج) | `core/clients/ersilia_client.py` |
| بروتين↔ليغاند | ProtoBind-Diff | PyTorch + GPU | ❌ خارج النطاق حالياً | — |
| مساعد لغوي | OLMo2-7B-BioMed-Chem | خدمة vLLM منفصلة | ❌ ثقيل للتشغيل المباشر | خدمة خارجية |
| هياكل ديناميكية | K-Fold / SG4D | pip / سحابة | ⚠️ تحقق اسم الحزمة (تصادم محتمل على PyPI) / ❌ حسابات سحابية | — |
| سير عمل مرئي | VERA | سطح مكتب، ليس API | ❌ غير قابل للدمج المباشر | — |

**قاعدة الخندق التعليمي**: أي عميل جديد يعرض نتائجه **بجانب** محركنا المحلي (Vina/RF)
كما فعلنا مع Vina↔ML — الطالب يقارن، ولا تعتمد المنصة على خدمة خارجية ليعمل شيء أساسي.

## 2) المسار الأول: Ersilia — ✅ تحقّق ودمج (S5)

**نتائج خطوة التحقق (2026-10-29 — من مستودعات ersilia-os مباشرة):**

| النموذج | الوصف | المخرجات | الحالة |
|---|---|---|---|
| `eos2ta5` | CardioToxNet — حجب قناة hERG (12,620 مركباً، الحاجب < 10 µM) | `Score` — احتمالية 0–1 | Ready · Local ✅ |
| `eos6oli` | SolTranNet — الذوبانية المائية logS (AqSolDB، RMSE 1.46) | `Value` — logS (mol/L) | Ready · Local ✅ |

**عقد النداء الموثّق من `ersilia/serve/standard_api.py` (فرع master):**
`POST {base}/run` بجسم قائمة صفوف `[{"input": "<smiles>"}, ...]`،
والاستجابة `[{"input": ..., "<output_col>": value}, ...]` — اسم عمود
المخرجات يختلف بين النماذج (score/value) فيُفسَّر بمرونة.

**ما نُفِّذ في S5 (فرع `feat/s5-ersilia-integration`):**
- `core/clients/ersilia_client.py` — عميل رقيق: `predict_admet` / `predict_admet_batch`،
  تفسير مرن للأشكال، فشل الشبكة → None/[] (نمط `fetch_analog_library`)،
  كتالوج `MODELS` + أحكام تعليمية `verdict` + مرجعية مدمجة `FALLBACK_REFERENCE`
  (أمثلة دوائية موثّقة: تيرفينادين/سيزابريد/هالوبيريدول/أسبرين، وإيتراكونازول/غريسيوفولفين/إيبوبروفين/باراسيتامول) — بلا أرقام مزيفة.
- تبويب «🧪 مركز ADMET» (13 تبويباً الآن): دُفعة SMILES → تنبؤ حي مخزَّن بالجلسة
  (النجاحات فقط)، وعند غياب الخادم: مرجعية تعليمية + أوامر التشغيل.
- اختبارات `tests/test_ersilia.py` — كلها mock بلا شبكة (14 اختباراً) + نداء حي موسوم `integration`.
- بلا اعتماديات جديدة: العميل `requests` فقط؛ خادم Ersilia يُثبَّت في بيئة مستقلة.

## 3) المسار الثاني: JapanFold للتوليد (بعد خطوة تحقق واحدة)

خطوة التحقق أولاً (توثيق النقطة الفعلية في هذا الملف قبل كتابة أي كود):

```bash
# TODO(verify): حدّث URL من وثائق JapanFold الرسمية ثم:
curl -sS -X POST "$JAPANFOLD_URL/jobs" -H "Content-Type: application/json" \
  -d '{"mode":"generate","num_molecules":10,"seed_mol":"CC(=O)Oc1ccccc1C(=O)O"}'
# النمط المتوقع: استجابة 202 مع job_id → استعلام دوري كل 3 ثوان حتى UNBLOCKED
```

عميل async بنمط موحد:

```python
def submit_job(payload: dict) -> str: ...
def poll_job(job_id: str, deadline_s: float = 120.0) -> dict | None: ...
def expand_library(seed_smiles: list[str], n: int = 20) -> list[str] | None:
    """None عند فشل الشبكة — يستدعيه تبويب Make كخيار «توسيع بالذكاء»."""
```

## 4) المسار الثالث: محرك التحقام الثاني (Matcha/DockThor)

بعد تحقق `pip index versions dock-thor-client` (هل الحزمة موجودة فعلاً؟):

1. أضف `engine` selector في تبويب Docking: `Vina (محلي) | DockThor (سحابي)`.
2. قيَن DockThor تكتب في نفس `DockingResult` (وحدة `dataclass` موجودة) —
   الواجهة والعرض ثلاثي الأبعاد لا يتغيران؛ درس الطالب: «نفس الليغاند، محركان،
   فرق الدرجات = اختلاف دوال التسجيل».
3. Matcha يدخل لاحقاً كخيار «سريع» بعد نشر مخطط API الفعلي في هذا الملف.

## 5) المحرك الآلي الشامل — `core/auto_pipeline.py` (السبت الأخير)

```python
@dataclass
class AutoReport:
    target: str
    library_size: int
    docked: int
    admet_passed: int
    pgx_flags: list[str]
    best_smiles: str
    report_pdf: bytes | None

def run_auto_pipeline(target_pdb: str, n_library: int = 50,
                      use_japanfold: bool = False,
                      admet_model: str | None = None) -> AutoReport:
    """زر واحد: مكتبة (Capstone) → (توسيع JapanFold اختياري) → Vina
    → فلتر ADMET (Ersilia اختياري) → علم PGx → تقرير عربي PDF."""
```

قواعده الصارمة: كل خطوة خارجية اختيارية وfallback فوري للوضع المحلي؛
التقرير يوثّق أي محركات استُخدمت فعلاً؛ بلا أي توكن في الكود (متغيرات بيئة فقط).

## 6) ترتيب السبرنتات المقترح

| السبرنت | المحتوى | المعيار الجاهزية |
|---|---|---|
| S5 | ✅ **منجز** — دمج `feat/pharma-hardening` في main + عميل Ersilia وتبويب ADMET | اختبارات mock خضراء + تحقق موثّق أعلاه (النداء الحي بانتظار `ersilia serve` محلياً) |
| S6 | JapanFold: تحقق → عميل → «توسيع المكتبة» في Make | job حي موثق + fallback |
| S7 | DockThor/Matcha كمحرك ثانٍ في Docking | نفس DockingResult يعمل بمحركين |
| S8 | `auto_pipeline.py` + زر «قراءة تلقائية» في Capstone | تقرير PDF كامل من نقرة واحدة |

## 7) قواعد ثابتة أيا كان السبرنت

1. لا نلمس `deploy-hf.yml.disabled` ولا نضيف خطوات نشر — قرار النشر منفصل.
2. كل نداء شبكة: `timeout` صريح + لا استثناءات للواجهة + كاش صريح.
3. كل ميزة تعليمية: نص عربي «لماذا يهم سريرياً؟» من مكتبة الحالات.
4. إخلاء المسؤولية التعليمي في كل مخرجات — المنصة تدريب لا توصية علاجية.
