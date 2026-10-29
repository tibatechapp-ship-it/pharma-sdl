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
| توليد الجزيئات | PubChem تشابه + BRICS (RDKit) | `core/expander.py` — ✅ منجز S6 (JapanFold بروتيني لا جزيئي — انظر القسم 3) | ✅ متحقق | `core/expander.py` |
| التحقق الخارجي (بروتين+ليغاند) | JapanFold Boltz-2 (affinity) | عميل موثّق `core/clients/japanfold.py` — زر opt-in في S7-b | ✅ متحقق (يتطلب مفتاحاً) | `core/clients/japanfold.py` |
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

## 3) المسار الثاني: JapanFold — ✅ تحقّق (S6) — عميل جاهز، الاستخدام صُحّح

**نتائج خطوة التحقق (2026-10-29 — من الدليل الرسمي `japanfold.aiand.com/skill.md`
و`api.japanfold.aiand.com/docs` و`/v1/openapi.json`):**

JapanFold **حقيقي وموثّق** (أُطلق سبتمبر 2026 من ai& وTenstorrent — بنية حاكمة
يابانية لأدوات اكتشاف الدواء المفتوحة)، لكن قراءة عقده الفعلي صحّحت دمجَه:

| الحقيقة الموثّقة | الأثر على التخطيط السابق |
|---|---|
| نقطة واحدة `POST /v1/predictions` + `GET /v1/jobs/{id}?wait=60` (محتجَز، RFC 7240) + `/results` + `/archive` | ✅ النمط غير المتزامن كما خُطّط بالضبط |
| **مفتاح Bearer مطلوب** في كل مسار (حساب جديد برصيد 100$، فوترة لكل ساعة معالج؛ 401/402 problem+json) | ❌ ليست «بلا مفتاح» — متغير بيئة `JAPANFOLD_API_KEY` إلزامي |
| النماذج كلها **بروتينية**: boltz2 (MSA+ليغاندات+affinity)، esmfold2/-fast، openfold3، openbind، rf3، opendde/-abag، af2ig، boltzgen، rfd3، pxdesign، rfd4، esmc، saprot | ❌ **ليست توليد جزيئات صغيرة** — لا تناسب `expand_library(seed_smiles)` |
| Boltz-2 يترافق بروتين+ليغاند (Boltz YAML: `sequences` + `properties.affinity.binder`) | ✅ الاستخدام الصحيح لمنصتنا: **تحقق خارجي مستقل لطاقة ربط Vina** |

**ما نُفِّذ في S6 (فرع `feat/s6-japanfold-generation`):**
- `core/clients/japanfold.py` — عميل بالعقد الموثّق: `submit_prediction` / `poll_job`
  (انتظار محتجَز بلا sleep) / `get_results` / `build_boltz_yaml` / `boltz2_affinity`.
  أسباب فشل قابلة للبرمجة (`no_api_key`, `401_sign_in_required`, `402_out_of_credit`,
  `job_failed`, `deadline_exceeded`…) — لا مفتاح في الكود (بيئة فقط)، ولا شبكة بلا مفتاح.
- «🌱 توسيع المكتبة» في تبويب Make — بمحركين موثّقين بدل JapanFold:
  `core/expander.py`: **PubChem** fastsimilarity_2d حي (بلا مفتاح) ثم **BRICS**
  محلي بـ RDKit (بلا شبكة، Degen 2008) — والمصدر يُعلن في الواجهة دائماً.
- اختبارات mock: 19 لعميل JapanFold + 12 للتوسيع — بلا شبكة في CI.

**مؤجَّل بعد قرار المستخدم (S7-b):** زر «تحقق خارجي عبر Boltz-2» في تبويب Docking
يستدعي `boltz2_affinity` — يحتاج مفتاح المستخدم ورصيده ووظائف تستغرق دقائق،
فهو ميزة opt-in لا افتراضية.

**✅ نُفِّذ في S7-b (2026-10-29):** زر «🌐 تحقق خارجي عبر Boltz-2» في تبويب Docking —
opt-in صريح: يعمل فقط بـ`JAPANFOLD_API_KEY` من البيئة (بلا مفتاح: رسالة تشرح
كيفية الحصول عليه، وكل المختبرات المحلية تعمل كالمعتاد). النجاح يعرض حقول
affinity بجانب درجة Vina، وأي فشل (401/402/شبكة/مهلة) يُترجم لسبب مقروء
لا يُعطّل شيئاً.

## 3-سابق) خطوة التحقق الأصلية (للأرشيف)

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

## 4) المسار الثالث: المحرك الثاني — ✅ حُسم بالبناء المحلي (S7-a)

**نتيجة خطوة التحقق (2026-10-29 — pip download + فحص العجلة فعلياً):**

| المسار المخطط | ما وجدناه فعلاً | القرار |
|---|---|---|
| `pip install dock-thor-client` | الحزمة موجودة (1.2.0) لكنها **أداة مراقبة أخطاء** لخدمة dock.codes (شبيهة Sentry: `capture_event/capture_exception`) — **ليست** محرك DockThor الحقيقي (LNCC) — تصادم أسماء كما حذّرنا مع K-Fold | ❌ مسار ميت — موثّق هنا |
| Matcha (PyPI) | نفس الاسم لكن ليست التحقام الانتشاري؛ الأصل يحتاج PyTorch/GPU | ❌ خارج النطاق |
| DockThor الحقيقي | بوابة سحابية تتطلب تسجيلاً/حساباً | ❌ تحتاج اشتراكاً — مخالفة للمبدأ |

**القرار (وفق مبدأ «اعمل نفسه»):** بنينا المحرك الثاني **محلياً بالكامل** —
`core/contacts.py`: محلل تفاعلات يقرأ نفس بوزات Vina ويُعيد تقييمها هندسياً
(اتصالات ≤4.5Å، روابط H ≤3.5Å بالاتجاهين، أزواج كارهة للماء ≤4.2Å، تعارضات
<2.7Å) ودرجة تعليمية موزونة. يُعرض بجانب درجة Vina في تبويب Docking — درس
«نفس البوز، محركان، فرق الدرجات = اختلاف دوال التسجيل» (قاعدة الخندق التعليمي).
12 اختباراً على المستقبل الحقيقي 7VH8 + بوزات صناعية، بلا شبكة وبلا Vina.

## 5) المحرك الآلي الشامل — ✅ منجز (S8): `core/auto_pipeline.py`

```python
@dataclass
class AutoReport:
    seed: str; receptor_id: str; source: str; library: list[str]
    funnel: dict[str, int]; results: list[dict]
    admet_engine: str        # ersilia | local | none — يوثّق ما استُخدم فعلاً
    admet_passed: int; pgx_flags: list[str]
    best_smiles: str; best_vina: float | None; best_inhouse: float | None
    report_pdf: bytes | None

def run_auto_pipeline(seed_smiles, receptor, n_library=8, dock_top=3, ...) -> AutoReport
```

الخط: مكتبة حول البذرة (PubChem حي → BRICS محلي) → فلتر ADME محلي
(Lipinski+Veber عبر RDKit + hERG المحاكى من core.oracle) → ربط Vina
(فشل جزيء يُحتسب ولا يوقف الخط) → المحلل الداخلي (S7-a) → فلتر ADMET
(Ersilia إن استجاب خادمها وإلا المحلي — المحرك يُعلَن في الواجهة) →
أعلام PGx صادقة (حجوزات + إحالة للتبويب، لا أرقام اختراعية) →
تقرير PDF عربي (Tajawal، يعيد استخدام قمع capstone). زر «⚙️ القراءة
التلقائية» في نهاية تبويب Capstone. 11 اختباراً معزولاً (expand/dock مزافران).

## 6) ترتيب السبرنتات المقترح

| السبرنت | المحتوى | المعيار الجاهزية |
|---|---|---|
| S5 | ✅ **منجز** — دمج `feat/pharma-hardening` في main + عميل Ersilia وتبويب ADMET | اختبارات mock خضراء + تحقق موثّق أعلاه (النداء الحي بانتظار `ersilia serve` محلياً) |
| S6 | ✅ **منجز** — تحقق JapanFold الكامل + عميل بالعقد الموثّق + «توسيع المكتبة» في Make (PubChem/BRICS) | 31 اختبار mock أخضر + عقد موثّق في القسم 3 (الوظيفة الحية تحتاج مفتاح المستخدم) |
| S7 | ✅ **منجز** — القسم 4: dock-thor-client تصادم أسماء → **محلل داخلي محلي** + زر Boltz-2 opt-in | 12 اختبار محلل + الواجهة تعرض الدرجتين جنباً إلى جنب |
| S8 | ✅ **منجز** — القسم 5: `auto_pipeline.py` + زر «القراءة التلقائية» في Capstone | 11 اختبار معزول + الحزمة الكاملة 222 خضراء |

## 7) قواعد ثابتة أيا كان السبرنت

1. لا نلمس `deploy-hf.yml.disabled` ولا نضيف خطوات نشر — قرار النشر منفصل.
2. كل نداء شبكة: `timeout` صريح + لا استثناءات للواجهة + كاش صريح.
3. كل ميزة تعليمية: نص عربي «لماذا يهم سريرياً؟» من مكتبة الحالات.
4. إخلاء المسؤولية التعليمي في كل مخرجات — المنصة تدريب لا توصية علاجية.
