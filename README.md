<p align="center">
  <img src=".github/assets/banner.svg" alt="Pharma SDL — مختبر الفارما الذاتي" width="100%">
</p>

# 🧬 Pharma SDL — مختبر الفارما الذاتي

> **"من الكتاب إلى الكود — من النظرية إلى الاكتشاف"**

منصة عربية تفاعلية لتعليم واكتشاف الأدوية بالذكاء الاصطناعي.

<p align="center">
  <a href="https://github.com/tibatechapp-ship-it/pharma-sdl/actions/workflows/tests.yml"><img src="https://github.com/tibatechapp-ship-it/pharma-sdl/actions/workflows/tests.yml/badge.svg" alt="Tests"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT"></a>
  <img src="https://img.shields.io/badge/Python-3.11%20%7C%203.12-3776AB?logo=python&logoColor=white" alt="Python 3.11 | 3.12">
  <img src="https://img.shields.io/badge/Streamlit-UI-FF4B4B?logo=streamlit&logoColor=white" alt="Streamlit">
  <a href="https://github.com/tibatechapp-ship-it/pharma-sdl/actions/workflows/tests.yml"><img src="https://img.shields.io/endpoint?url=https%3A%2F%2Fraw.githubusercontent.com%2Ftibatechapp-ship-it%2Fpharma-sdl%2Fmain%2Fbadges%2Ftests.json" alt="اختبارات — رقم حي يُحدّثه CI من التشغيل الفعلي"></a>
  <a href=".github/workflows/platform.yml"><img src="https://github.com/tibatechapp-ship-it/pharma-sdl/actions/workflows/platform.yml/badge.svg" alt="Platform API"></a>
  <img src="https://img.shields.io/badge/API-v0.15.0%20%28FastAPI%29-009688?logo=fastapi&logoColor=white" alt="إصدار المنصة 0.15.0 — واجهة API مبنية بFastAPI (OpenAPI version=__version__)">
</p>

---

## 🚀 v0.15.0 — P14: مختبر Boltz-2 — المقارنة ثلاثية الطبقات

> **الجديد في v0.15.0:** البُعد البنيوي يدخل خط القرار — أول مرة يقف
> الجزيء أمام **ثلاث طبقات تسعير**: نموذجنا السريع (أجزاء ثانية، CPU)،
> وVina المستقبَل مرجعياً (دقائق، CPU)، و**Boltz-2** (MIT CSAIL، رخصة
> MIT كاملة) رأسُ تقاربٍ مدرّب على فيزياء FEP+/CASP16 يمنح **بنية +
> قرابة معاً** في ~20 ثانية GPU عبر دفتر Colab مكتمل
> ([Lab08](notebooks/Lab08_Boltz2_CoFolding.ipynb)). لوحة مرجعية حية
> خارج العينة (نيرماتريلڤير + PF-00835231 مقابل Mpro) بمراسِ ChEMBL
> موثّقة بمعرّفاتها — نيرماتريلڤير: ML **5.94** / Vina **5.68** مقابل
> مرجع 7.51، وPF-00835231: ML **5.90** / Vina **6.43** مقابل مرجع 8.10
> — **تحت-تقدير منهجي موثّق** (انضغاط نحو وسط السلالة + ليغاند تساهمي
> أمام دوال غير تساهمية)، والطبقة الثالثة تبقى `unavailable_offline`
> **صادقة** حتى تشغيل Colab واحد — لا قيمة مختلقة واحدة. الدرس
> «متى نثق بأي طبقة» بقواعده الخمس موثّق كدالة ومُبلّغاً:
> [STRUCTURE-TIERS-P14](docs/audit/STRUCTURE-TIERS-P14.md).

---

## 🚀 v0.14.0 — P13: ADMET-AI — من نموذجين إلى 41 نقطة نهاية في مركز ADMET

> **في v0.14.0:** عميل **ADMET-AI v2** (هارفارد، رخصة MIT) محلياً على
> CPU بلا شبكة — مجموعة 5 طيّات
> لنموذجَين متعددَي المهام مُدرّبَين على بيانات TDC: **41 نقطة نهاية**
> (31 تصنيف + 10 انحدار) + 3 إنذارات بنيوية + 8 وصفات فيزيوكيميائية،
> ولكل قيمة **مئين مقابل الأدوية المعتمدة في DrugBank**. القياس الحي
> مجمّد بفحوص صدق: تيرفينادين (المسحوب لإطالة QT) hERG **0.970** مقابل
> أسبرين **0.021**، وإيتراكونازول DILI **0.994** وذوبان **−5.57**،
> ووارفارين ارتباط بلازما **94.3%** (المعروف ~99%). وتبقى النزاهة
> كما هي: أثرا نموذج خارج التوزيع منشوران بصدق (PPBR سالب للميتفورمين،
> وأكثر من 100% للإيتراكونازول). الحزمة اختيارية `pip install -e ".[admet]"`
> والغياب يعرض تلميح تثبيت بلا تزييف قيم. التقرير:
> [MODEL-ADMET-AI-P13](docs/audit/MODEL-ADMET-AI-P13.md).

```bash
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install admet-ai
python3 scripts/run_admet_ai_p13.py   # القياس الحي المجمد — بلا شبكة
```

## 🚀 v0.13.0 — P12: القياس الخارجي الرسمي — المختبر السابع على TDC

> **الجديد في v0.13.0:** أول مرة يقاس فيها المشروع على مرجع **لا نملكه**:
> مهمتا انحدار من المجموعة المرجعية الرسمية `admet_group` في Therapeutics
> Data Commons — بتقسيمها الرسمي المثبّت، وبذور لوحتها [1..5]، والنتيجة
> كما تحسبها دالة التقييم الرسمية `evaluate_many` لا حسبتنا. خط v0.12.0
> المعتمد (بصمة تكرارات + RF300/mf=0.3) حلّ على **Solubility** (9,982 جزيء)
> بـ MAE **1.031 ± 0.024** — المرتبة 16/18، متقدماً على خط أساس البصمات
> المنشور (Morgan+MLP: 1.203) بفارق **0.172** — وعلى **Lipophilicity**
> (4,200 جزيء) بـ MAE **0.709 ± 0.006** تحت المدخلات الـ19 كلها؛ فجوة
> **+0.25…+0.29** عن الأفضل هي سقف فئة «بصمة+RF» مقاساً الآن لا مُخمَّناً،
> والذراع التشخيصية تبرئ إعداد P11 (sqrt أسوأ في المهمتين). التقرير:
> [MODEL-BENCHMARK-TDC-P12](docs/audit/MODEL-BENCHMARK-TDC-P12.md).

```bash
pip install PyTDC --no-deps && pip install 'setuptools<81'
python3 scripts/evaluate_tdc_p12.py   # يعمل دون شبكة من النسخة المجمدة
```

## 🚀 v0.12.0 — P11: ترقية نموذج الفعالية — A/B/C/D على البروتوكول المنشور

> **الجديد في v0.12.0:** أول مرحلة من [خطة التطوير](docs/plan/) تنفَّذ بنفس
> صدق P0: المرتكز يعيد الأرقام المنشورة **بتطابق حرفي** (`anchor_check.match=true`)
> ثم تُقارن أربعة أذرع على **نفس** التقسيمات. النتيجة: بصمة Morgan
> **بالتكرارات** + `max_features=0.3` ترفع R² الهيكلي **0.489 → 0.509 ± 0.090**
> (يفوق المرتكز في كل بذرة من البذور الخمس) والعشوائي **0.436 → 0.468**،
> وتتصلح معايرة عدم اليقين قفزةً (ρ: 0.134 → **0.327**). ونتيجتان سلبيتان
> منشورتان بصدق: الوصف الفيزيوكيميائي وHistGB لا يفوزان على سلالة Mpro
> المتقاربة (0.472 / 0.429) — كتلة الوصف معلّقة جاهزة لبيانات P12
> غير المتجانسة. الهدف 0.55 يحتاج تنويع بيانات لا أشجاراً أكثر.
> التقرير: [MODEL-UPGRADE-P11](docs/audit/MODEL-UPGRADE-P11.md).

```python
from core.ml_potency import train_default_model
m = train_default_model()          # بصمة تكرارات + max_features=0.3 (v0.12.0)
m.predict("CC1([C@@H]2[C@H]1[C@H](N(C2)C(=O)[C@H](C(C)(C)C)NC(=O)C(F)(F)F)C(=O)N[C@@H](C[C@@H]3CCNC3=O)C#N)C")
# نموذج بديل بفترة كمّية فعلية:
from core.ml_potency import train_potency_model
m2 = train_potency_model(smiles, pic50, model_kind="histgb", include_descriptors=True)
```

## 🚀 v0.11.0 — جهة الميدان: طبقة الأجهزة ومراقب جودة القراءات (P10)

> **الجديد في v0.11.0:** P9 قال «هنا تُوصَل الأجهزة» عند البوابة؛ هذه
> المرحلة تبني **ما خلف نقطة الرفع**: بروتوكول `InstrumentDriver`
> موحّد، سواقة `FRETReaderDriver` (SCPI عبر TCP بـbuffer استقبال
> دائم)، محاكي جهاز واقعي (`pharma-sdl simulator`)، و**مراقب جودة
> خمس طبقات** يمنع رفع أي قراءة مستحيلة فيزيائياً أو خارج ضوابط
> الصفيحة. القراءة المحاكاة تحمل `SIMULATED-…` تلقائياً؛ والحقيقية
> تتطلب موافقة بشرية ≥ 16 حرفاً وإلا `SafetyViolation`. والجسر إلى
> البوابة صادق بالبناء: **الكود لا يشتق IC50 من نسبة FRET واحدة** —
> القيمة المقاسة من ملاءمة المنحنى تُمرَّر صراحة (ADR-0015). ومعها
> حوكمة تمنع تكرار درس «كود يُكتب ولا يُشغَّل»: `AGENTS.md` +
> `HANDOFF.md` — القرارات البشرية الثلاثة موثقة الآن في ملف واحد.

```bash
# طرفية 1: محاكي الجهاز (عتاد الوهم)
pharma-sdl simulator --port 10001

# طرفية 2: قياس مباشر من السواقة + فحص جودة قبل الرفع
python -c "
from pharma_sdl.lab.instruments import FRETReaderDriver
from pharma_sdl.lab.anomaly_detector import LabAnomalyDetector

drv = FRETReaderDriver(host='127.0.0.1', port=10001)
drv.connect()
try:
    reading = drv.run_assay('CMP-042', '7VH8_A', 'FRET_Mpro_v1', '')
finally:
    drv.disconnect()
print(LabAnomalyDetector().analyze_reading(reading).to_dict())
"
```

---

## 🚀 v0.10.0 — الحلقة الفيزيائية: بوابة مرجعية ومسار قياسات (P9)

> **الجديد في v0.10.0:** الجهة الأخرى من العقد صارت كوداً — **بوابة
> LIMS مرجعية** تنفّذ عقد ADR-0013 حرفياً: أوامر عمل تُحفظ في sqlite
> وتنجو من إعادة التشغيل، تعرّج مُكرَّم من الخادم، دورة حالة صريحة
> (pending → running → completed/failed) بدورين بمفتاحين. **صدقها
> البنيوي: لا تختلق رقماً واحداً** — النتائج لا تدخل إلا برفع صريح
> من جهة المختبر، وهنا بالضبط تُوصَل الأجهزة. ومعها **مسار القياسات**:
> النتائج المقبولة تدخل ذاكرة المنصة الدائمة (JSONL + سجل تجريبي
> `kind="lab_batch"`) — والمحاكاة تُرفض استثناءً من هذا المسار.
> وإصلاحان صادقان لفجوتي P7: انهيار كامن في تسجيل الجودة
> (`registry.add` غير موجودة) وسكربت القياس المعلَن المفقود — أُنشئ
> وشُغِّل: الأرقام تتكاثر حرفياً (ADR-0014).

```bash
# تشغيل البوابة المرجعية (الجهة الأخرى من العقد)
pharma-sdl gateway --port 8100

# الدائرة كاملة: أفضل مرشحي الحلقة ← المختبر ← الذاكرة
python -c "
from pharma_sdl.lab import run_physical_confirmation, MeasurementIngestor
print(run_physical_confirmation(
    [{'smiles': 'CCO', 'name': 'ethanol', 'kcal': -8.0}],
    ingestor=MeasurementIngestor('data/measurements.jsonl'),
))"
```

---

## 🚀 v0.9.0 — جسر الفيزياء: عقد دفعات REST للمختبر الحقيقي (P8)

> **الجديد في v0.9.0:** المختبر لم يعد محاكاة محصورة — أصبح **مقبساً
> قابلاً للتبديل بالضبط**: عقد دفعات موحّد (تقديم ← تذكرة ← استطلاع)
> تنفذه المحاكاة والبوابة الحقيقية معاً بنفس الكود. أي خدمة LIMS/أجهزة
> تنفذ العقد المرجعي تصبح «المختبر» بمتغيري بيئة (`PHARMA_SDL_LIMS_URL`
> + `_TOKEN`) — بلا تغيير سطر واحد. انضباط عقود ChEMBL نفسه مطبَّق على
> الأجهزة: دفعة بخرق واحد تُرفض كاملة، وبوابة «حقيقية» تعلِم
> `simulated=true` تُرفض فوراً. **والحد الصادق**: لا جهاز في CI — ما
> أُنجز هو النقطة التي تُوصَل عندها الفيزياء، لا ادعاء أنها وُصلت
> (ADR-0013).

```bash
# أي خلفية تعمل الآن فعلاً؟ — صدق تشغيلي معلن لا خمّاس
curl -s localhost:8000/api/v1/lab/backend -H "X-API-Key: $VIEWER_KEY" | jq

# عقد الدفعات: تقديم ← تذكرة ← استطلاع (المحاكاة تكتمل فوراً)
curl -s -X POST localhost:8000/api/v1/lab/batches \
  -H "X-API-Key: $SCIENTIST_KEY" -H "Content-Type: application/json" \
  -d '{"assays": [{"smiles": "CCO", "dg_kcal": -8.0}], "idempotency_key": "run-1"}'
curl -s localhost:8000/api/v1/lab/batches/$BATCH_ID -H "X-API-Key: $VIEWER_KEY" | jq
```

---

## 🚀 v0.8.0 — مقاييس صدق الأهداف: الجودة تُقاس وتُنشر لا تُدَّعى (P7)

> **الجديد في v0.8.0:** لكل هدف من الثلاثة **رقم تعميم منشور**: R² وMAE
> على هياكل Bemis–Murcko محجوزة لا يمرّ هيكل واحد بين التدريب والاختبار،
> بتغطية conformal مقاسة بجانب الاسمية — بمعمارية الإنتاج حرفياً (300
> شجرة، بذرة 0). النتائج كما هي بلا تجميل: **Mpro R²=0.537** (الأقوى)،
> وAChE 0.432 وEGFR 0.403 بتغطية مقاسة **أدنى من الاسمية** (0.850/0.861
> مقابل 0.90) — رقم حقيقي يُنشر ويُفسَّر (ADR-0012). والحد الصادق: جودة
> النموذج لا تُصحّح تنبؤات المكتبة — الفرز يبقى UNVALIDATED.

```bash
# مقاييس الجودة المنشورة — قراءة أرشيف لا حساب حي
curl -s localhost:8000/api/v1/tibb/quality \
  -H "X-API-Key: $VIEWER_KEY" | jq '.targets[] | {target_id, r2, mae, measured_coverage}'
```

## 🚀 v0.7.0 — توسيع الأهداف: ثلاثة أهداف مُدرَّبة بنفس الكود (P6)

> **الجديد في v0.7.0:** سجل أهداف معلن (`TARGETS`) — المركبات النبوية الـ17
> تُفرز الآن ضد **ثلاثة أهداف**: Mpro (الأصلي) + **AChE** (CHEMBL220،
> الفئة العصبية/الكولينية) + **EGFR** (CHEMBL203، بروتين كيناز) — كل هدف
> بنموذجه على بياناته المُخَرَّجة بعقد Mpro نفسها (900 صف، IC50 حصراً،
> pchembl ≥ 5 مطبق محلياً). أول فرز إنتاجي (UNVALIDATED، 300 شجرة):
> **pinocembrin أولَاً على AChE (6.351)** و**CAPE أولَاً على EGFR (5.868)**
> pIC50 متنبأ بها. قرار موثق (ADR-0011): AChE بدل «القنوات الأيونية»
> حرفياً — جودة التخريج تتقدم على حرفية الفئة. وهدف جديد = بيانات
> مُخَرَّجة + مواصفة واحدة، وحارس شحّة في النواة (`MIN_DATASET_ROWS = 300`).

```bash
# الأهداف المُدرّبة — بأحجام بياناتها وقصص اختيارها
curl -s localhost:8000/api/v1/tibb/targets | jq '.targets[].target_id'
# فرز المكتبة على AChE بدل الافتراضي Mpro
curl -s -X POST localhost:8000/api/v1/tibb/screen \
  -H "Authorization: Bearer $SCIENTIST_TOKEN" \
  -H 'Content-Type: application/json' -d '{"target_id": "CHEMBL220"}'
```

## 🚀 v0.6.0 — مكتبة الطب النبوي: التوثيق التراثي يلتزم عقود الصدق (P5)

> **الجديد في v0.6.0:** العسل وحبة البركة والشعير — والحجامة والكاي كإجرائين
> موثقين — كخط اكتشاف كامل: **17 مركباً بجزيئات مُدقَّقة من PubChem**، وتخريج
> دقيق بالدرجة الفعلية («متفق عليه»: البخاري 5687/5688 + مسلم 2213 للحبة
> السوداء...)، وطبقات دليل حديث T0–T3 بمراجع منشورة، وفرز حاسوبي على نموذج
> MPRO الإنتاجي في خط `predicted_potency` حصراً — **الثيموكينون في المركز
> الأول (5.908 pIC50 متنبأ بها)** نتيجة للتحقق التجريبي لا ادعاء فعالية.
> المبدأ (ADR-0010): التوثيق التراثي قيمة ثقافية لا يُنتج درجات؛ والدليل
> العلمي طبقة منفصلة تُقاس بمعايير الطب الحديث.

## 🚀 v0.5.0 — التعلم النشط واليقين المُعايَر: الحلقة تتعلّم (P4)

> **الجديد في v0.5.0:** حزمة الربع الرابع من الخطة v1.1 أصبحت كوداً — حملات
> تعلم نشط **تُحدّث النموذج من نتائج كل جولة** وتُقاس على اختبار scaffold ثابت
> لا تلمسه الاختيارات، مع **Conformal Prediction** بتغطية فعلية مقاسة بجانب
> الاسمية. والبوابة Go/No-Go محققة بأرقام مقاسة: **UCB تفوق العشوائي بـ+0.51
> pIC50** وتصل لأعلى فعالية في البيانات (9.45) بحلول الجولة 4 من 8.
> كل ما في v0.4.0 أدناه يعمل كما هو بلا أي كسر.

**الحلقة تصبح متعلّمة:**

```bash
# حملة تعلم نشط عبر الـAPI — النموذج يُحدَّث من نتائج كل جولة
curl -s -X POST localhost:8000/api/v1/loop/campaigns \
  -H 'Content-Type: application/json' \
  -d '{"strategy": "ucb", "rounds": 6, "batch_size": 8}'
curl -s localhost:8000/api/v1/loop/campaigns/<job_id> | python3 -m json.tool
# → منحنى أفضل فعالية مكتشفة + فترات conformal + تغطية فعلية — كلها UNVALIDATED

# الدليل المرجعي الكامل (4 استراتيجيات × 3 بذور):
python scripts/learning_campaign.py   # → docs/audit/ACTIVE-LEARNING-CAMPAIGN.md
```

**الأوراكل صادق بالتصميم:** in-silico يكشف قياسات pChEMBL من مجموعة البيانات
المعتمدة حصراً (لا مخبر)، وضع العرض يفرض سقوفه الحسابية في مسار التنفيذ،
وخط pIC50 يبقى منفصلاً عن خطي Docking/المخبر — لا دمج درجات أبداً.

---

## 🚀 v0.4.0 — منصة API-First: تخزين حي حقيقي + حلقة كخدمة (P3)

> **الجديد في v0.4.0:** إكمال وعد ADR-0007 بكود حي مُختبر فعلاً — مخزنان فوق
> PostgreSQL بنفس العقود حرفياً، تُختبر على خادم PostgreSQL مضمّن (لا mocks)،
> والحلقة المغلقة تصبح نقطة نهاية: `POST /api/v1/loop/runs` — ثلاث جولات
> متسلسلة بالأسلاف في مهمة دائمة، كلها UNVALIDATED (بوابة الاعتماد بشرية حصراً).
> كل ما في v0.3.0 أدناه يعمل كما هو بلا أي كسر.

**الترقية الحية صارت زراً لا مشروعاً:**

```bash
# الافتراضي — SQLite الدائم (بلا خدمات):
uvicorn pharma_sdl.api.app:create_app --factory --port 8000

# PostgreSQL الحي (ADR-0008) — نفس العقود حرفياً:
pip install 'pharma-sdl[pg]'
export PHARMA_SDL_STORE=postgres
export PHARMA_SDL_PG_DSN=postgresql://user:pass@host:5432/pharma_sdl
#   أو بالحاويات: docker compose --profile pg up --build

# ترحيل الذاكرة القديمة:
pharma-sdl export-experiments --db data/experiments.sqlite3 --out exp.jsonl
pharma-sdl import-experiments --db "$PHARMA_SDL_PG_DSN" --in exp.jsonl
```

نقاط نهاية P3:

```bash
# الحلقة المغلقة كخدمة — ثلاث جولات (خط أساس ← استكشاف ← توظيف) مهمة دائمة
curl -s -X POST localhost:8000/api/v1/loop/runs \
  -H 'Content-Type: application/json' -d '{"target_id": "7VH8_A", "top_n": 3}'
curl -s localhost:8000/api/v1/loop/runs/<job_id> | python3 -m json.tool
# → rounds: 3 متسلسلة بالأسلاف، كلها UNVALIDATED

# عدّادات صادقة من الذاكرة الحية (sqlite | postgres معلن في /health أيضاً)
curl -s localhost:8000/api/v1/metrics | python3 -m json.tool
```

---

## 🚀 v0.3.0 — منصة API-First محصّنة: هوية، ذاكرة، قبول هندسي

> **الخبر:** طبقة جديدة كاملة `pharma_sdl/` تحوّل المشروع من تطبيق تعليمي إلى
> **منصة اكتشاف أدوية تشغيلية** وفق [الخطة الاستراتيجية v1.1](docs/plan/PharmaSDL_Strategic_Plan_v1.1.pdf) —
> واللوحة التعليمية أسفله تعمل كما هي بلا أي كسر.

**خط التشغيل الكامل:** تنقية ← فرز ظاهري ← إجماع علاجي ← مختبر ← تقرير —
بمحركات قابلة للتبديل وسياسات أهداف صريحة (Mpro **غير تساهمي حصراً**).

| الوحدة | ماذا تفعل |
|---|---|
| `curation` | توحيد + إزالة تكرار (InChIKey) + PAINS + Lipinski/Veber + **بوابة الرؤوس التساهمية** — كل رفض مسبَّب عربي/إنجليزي |
| `targets` | سجل أهداف بسياسات: 7VH8 (Mpro) و7CMD (PLpro) بصناديق ربط مُتحقق منها |
| `engines` | `simulation` (حتمي، دائماً متاح) · `vina` (ربط فعلي) · `boltz2` (تقارب مباشر عبر بوابة) — التراجع بينها **مُعلَن** |
| `screening` | جولة فرز كاملة من نداء واحد — **الهيكل الهزّ من الخطة منفَّذ** |
| `affinity` | جسر Cheng-Prusoff (ΔG ≈ −1.364×pIC50) مع حكم اتفاق صريح |
| `lab` | مقبس مختبر موحّد (P8): عقد دفعات + جسر LIMS REST حقيقي بالضبط + صندوق صادر — FRET محاكى هو الخلفية الافتراضية بعلامة `simulated=true` |
| `reporting` | تقرير Markdown/JSON ثنائي اللغة لكل جولة |
| `api` | FastAPI + طابور مهام + OpenAPI تفاعلي على `/docs` |

### ⚡ جرب المنصة في 60 ثانية

```bash
pip install -r requirements.txt -r requirements-dev.txt

# بوابة الـAPI مع توثيق تفاعلي
uvicorn pharma_sdl.api.app:create_app --factory --port 8000
#   → http://localhost:8000/docs

# أو من سطر الأوامر مباشرة
pharma-sdl engines
pharma-sdl targets
pharma-sdl screen --target 7VH8_A --ligands data/demo_ligands.csv --top 10

# أو بالحاويات (API على :8000 + لوحة على :8501)
docker compose up --build
```

نداء فرز حي (وضع العرض — 24 جزيء جاهزون):

```bash
curl -s -X POST localhost:8000/api/v1/screening/runs \
  -H 'Content-Type: application/json' -d '{"target_id": "7VH8_A", "top_n": 5}'
# → 202 {"job_id": "...", "run_url": "..."} ثم:
curl -s localhost:8000/api/v1/screening/runs/<job_id> | python3 -m json.tool
curl -s "localhost:8000/api/v1/screening/runs/<job_id>/report?lang=ar"
```

📖 التفاصيل الكاملة: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) ·
[قرارات التصميم ADR-0001…0008](docs/adr/) · [CHANGELOG](CHANGELOG.md)

---

## 🌐 Live Demo

_قيد النشر_

> 📖 **دليل المنصة (GitHub Pages)**: <https://tibatechapp-ship-it.github.io/pharma-sdl/>
> (فعّل من Settings → Pages → Branch: main / folder: docs)

> إذا لم يكن الرابط يعمل، شغّل محلياً: `streamlit run app.py`

## ✨ Features
- 🏭 **Make**: توليد SMILES بـ RDKit
- 🔬 **Test**: محاكاة hERG + LDL-C
- 🧠 **Analyze**: تعلم نشط (UCB + Pareto)
- 🧬 **PROTAC**: Vepdegestrant (أول PROTAC معتمد)
- 🔌 **PubChem**: جلب بيانات حقيقية (مخزّنة ساعة — أداء أعلى)
- 🧪 **MIC Lab**: PK/PD للمضادات الحيوية (3 مضادات، 3 مؤشرات)
- 🧬 **PROTAC Lab**: Vepdegestrant (Hook Effect, ternary complex)
- 🧫 **CYP2C19**: طب شخصي (4 أنماط، CPIC 2022، بيانات قطر)
- 🤖 **Predict**: تنبؤ pIC50 بتعلم آلي حقيقي — RandomForest على بصمات Morgan مدرّب على قياسات Mpro من ChEMBL (900 جزيء) مع فترة ثقة من تباين الأشجار
- 🎓 **Capstone**: خط الاكتشاف الكامل «من الهدف إلى القرار» — مكتبة (PubChem حي أو محلية) → فلترة ADME (Lipinski+Veber) → تنبؤ ML → قرار PK/PD (C90 من Hill مقابل Cmax فموي) → تقرير PDF عربي جاهز للتنزيل
- 🧲 **Docking**: ربط جزيئي حقيقي بـ AutoDock Vina + Meeko على مستقبلات PDB مُجهّزة مسبقاً (Mpro 7VH8 — نفس هدف نموذج ML، وPLpro 7CMD)، عرض البوز ثلاثي الأبعاد بـ 3Dmol.js، وضع درس عربي كامل، ومقارنة فيزياء↔ML عبر جسر Cheng-Prusoff (ΔG ≈ −1.364×pIC50) — سبرنت 4
- 💊 **PGx**: توصيات الصيدلة الجينية لخمسة جينات (CYP2D6 · TPMT · UGT1A1 · CYP2C19 · CYP3A5) — جلب حي من CPIC API بكاش 24 ساعة + احتياطي مدمج فوري + تنبيه تعليمي دائم — سبرنت 4
- 🧪 **ADMET Hub (Ersilia)**: نماذج مفتوحة موثّقة (hERG CardioToxNet + ذوبان SolTranNet) عبر خادم Ersilia محلي — بلا مفاتيح، وعند غياب الخادم مرجعية دوائية موثّقة بدل أرقام مختلقة — سبرنت 5
- 🌱 **توسيع المكتبة**: جيران تشابه حقيقيون من PubChem (بلا مفتاح) أو BRICS محلي عبر RDKit (بلا شبكة) — المصدر يُعلَن دائماً — سبرنت 6
- 🎯 **التوليد الموجّه بالهدف**: مكافئ ChatChemTS/ChemTSv2 محلي 100% — حلقات BRICS حول أفضل الناجين بقيود هدف صريحة (MW/LogP/TPSA/تشابه) ودالة مكافأة شفافة، مع رسم بنيوي 2D لكل ناجٍ — بلا مفتاح ولا TensorFlow وبلا اشتراك — سبرنت 9
- 🗂️ **التصنيف الدوائي**: دليل ATC لمنظمة الصحة العالمية — 23 مجموعة ثنائية اللغة (البنسلينات، الفلوروكينولونات، الستاتينات…) بآليات العمل والأعضاء، تصنيف فوري لاسم عربي/إنجليزي/SMILES + ATC حي من RxNorm (بلا مفتاح) + درس «ما المتبع عالمياً» — سبرنت 10
- 🔬 **المحلل الداخلي للبوزات**: محرك تسجيل ثانٍ صنعناه محلياً (اتصالات/روابط H/تعارضات) يقرأ نفس بوزات Vina — درس «دالتا تسجيل، نتائج مختلفة» — سبرنت 7
- 🌐 **تحقق Boltz-2 (opt-in)**: ميزة اختيارية بمفتاح المستخدم من البيئة فقط (JAPANFOLD_API_KEY) — كل المختبرات تعمل بلا مفتاح — سبرنت 7
- ⚙️ **القراءة التلقائية**: خط كامل من نقرة واحدة — مكتبة حول البذرة → فلتر ADME محلي → ربط Vina → المحلل الداخلي → فلتر ADMET (Ersilia إن توفّر وإلا محلي) → أعلام PGx صادقة → تقرير PDF عربي — سبرنت 8
- 🌐 **مبدّل عربي/إنجليزي** في الشريط الجانبي (يغطي العنوان والتبويبات الجديدة والقوالب العامة)

### 🤖 Model Card (Predict)
| البند | القيمة |
|---|---|
| البيانات | قياسات IC50 حقيقية لـ SARS-CoV-2 Mpro (CHEMBL4523582) — وسيط pchembl لكل جزيء، نظيفة من قياسات data_validity_comment |
| الميزات | بصمات Morgan (radius=2، 2048 بت) |
| النموذج | RandomForestRegressor (300 شجرة، random_state=42) |
| الأداء | R² ≈ 0.44 (عشوائي) · **R² = 0.49 ± 0.10 هيكلياً (Scaffold Split)** — تقرير التقييم المستقل بالأسفل |
| عدم اليقين | تباين تنبؤات الأشجار — **إشارة نسبية غير معايَرة تجريبياً** (ρ ≈ 0.37 مع الخطأ الهيكلي) |
| الحدود | ميزات ثنائية الأبعاد فقط، بيانات فحص واحد (Mpro) — لا يستخدم لقرارات سريرية |

### 🔬 التحقق العلمي — عقد الصدق

بعد التدقيق العلمي P0 (2026-11) اعتمدت المنصة:

- **مسارات الدرجات الثلاثة** (`pharma_sdl/scores.py`): درجة الالتحام ≠ الفعالية المتنبأ بها ≠
  النشاط التجريبي — ثلاثة أرقام بطبيعة مختلفة، لا تُدمج ولا تُقارن عبر أهداف مختلفة،
  وكل مسار يحمل حدود تفسيره الصريحة في الـAPI والتقارير والواجهة.
- **التحذير العلمي/الطبي في كل مخرج** — واجهة، تقارير Markdown/PDF، واستجابات API
  (حقل `disclaimer_ar/en` في كل نتيجة فرز) — لا في التوثيق فقط.
- **تقرير تقييم مستقل قابل لإعادة الإنتاج**:
  [`docs/audit/MODEL-EVALUATION-REPORT.md`](docs/audit/MODEL-EVALUATION-REPORT.md) —
  Random مقابل Scaffold Split، خطوط أساس (متوسط + أقرب جار Tanimoto)، فجوة التعميم،
  معايرة عدم اليقين، وتدقيق التسرب الهيكلي — كل رقم محسوب فعلاً:
  ```bash
  python3 scripts/evaluate_generalization.py   # ~80 ثانية → JSON
  python3 scripts/build_audit_report.py        # JSON → التقرير
  ```

### 🧠 الحلقة المغلقة + الذاكرة التجريبية + بوابة الاعتماد (P1)

المنصة الآن تنفّذ «حلقة واحدة مغلقة» — فرضية ← تنفيذ ← تقييم ← ذاكرة ←
جولة تالية تقرأ ما سبق:

- **سجل تجارب دائم (SQLite)** — النتائج لا تضيع بعد إعادة التشغيل؛ كل
  تجربة تحمل بصمة المدخلات + git commit + الفرضية + الدرس المستفاد.
- **بوابة اعتماد بأربع حالات** — كل نتيجة تولد `UNVALIDATED`، والترقية
  بشرية موثقة خطوة واحدة فقط (لا ترقية تلقائية أبداً).
- **الحلقة جاهزة للتشغيل**:
  ```bash
  pharma-sdl loop              # فرضية ← تنفيذ ← تقييم ← ذاكرة ← جولة تالية
  pharma-sdl experiments       # قراءة الذاكرة التجريبية
  ```

### 🛡️ المصادقة والأدوار + العرض العام المحدود + القبول الهندسي (P2)

بعد تقييم كامل (docs/audit/PLATFORM-EVALUATION-P1.md) عُلجت 9 إشكاليات —
أبرزها: المهام لم تعد تضيع بعد إعادة التشغيل، وبوابة الاعتماد صارت لها هوية:

- **مفاتيح API وأدوار صارمة** — `viewer < scientist < admin`، والترقية
  الاعتمادية عبر API **admin حصراً** مع توقيع (`actor`) إلزامي:
  ```bash
  PHARMA_SDL_API_KEYS="lab:sk-...:admin,batch:sk-...:scientist,read:sk-...:viewer"
  curl -H "X-API-Key: sk-..." http://localhost:8000/api/v1/auth/whoami
  ```
  المفاتيح تُجزَّأ sha256 عند التحميل؛ الوضع المفتوح (تطوير فقط) معلن في /health.
- **ترقية اعتماد عبر API** — البطاقة كاملة (التاريخ والمرفقات) تُحفظ في السجل:
  `GET /api/v1/experiments/{id}/validation` ثم `POST …/validation/promote`.
- **وضع عرض عام محدود** (`PHARMA_SDL_DEMO_MODE=1`) — حد معدل لكل IP
  (`429` + ترويسات X-RateLimit)، قفل المحركات على `simulation`، سقوف أدنى.
- **طابور دائم (ADR-0007)** — النتائج تُستعاد والمقاطعة تُوثَّق بعد أي إعادة نشر.
- **قبول إعادة الربط ضد البلورة** — معيار المجال: RMSD ≤ 2.0 Å:
  ```bash
  python scripts/fetch_reference_ligands.py   # مرة واحدة (مُلتزم أصلاً)
  python scripts/redocking_suite.py           # 7VH8: 0.93 Å · 7CMD: 0.17 Å ✅
  ```
- **طريق PostgreSQL جاهز** — `pharma-sdl export-experiments` + deploy/postgres/schema.sql.

## 🚀 Quick Start
```bash
git clone https://github.com/tibatechapp-ship-it/pharma-sdl.git
cd pharma-sdl
pip install -r requirements.txt
streamlit run app.py
```

## 🧪 Tests
```bash
pytest -v
pytest --cov=core --cov-report=html
```

## 📚 Tech Stack
Python 3.11 | **FastAPI (منصة v0.2.0)** | Streamlit | RDKit | AutoDock Vina 1.2 | Meeko | 3Dmol.js | scikit-learn | Plotly | PubChem API | CPIC API | Ersilia Model Hub | JapanFold API | ReportLab | Docker

## 🤝 المساهمة والتوثيق

| الملف | المحتوى |
|---|---|
| [CONTRIBUTING.md](CONTRIBUTING.md) | بيئة التطوير، سير العمل، معايير القبول |
| [SECURITY.md](SECURITY.md) | سياسة الإبلاغ عن الثغرات وسياسة المفاتيح |
| [CHANGELOG.md](CHANGELOG.md) | سجل التغييرات الإصداري |
| [docs/ROADMAP-2026.md](docs/ROADMAP-2026.md) | خارطة السبرنت 9+ |

الـIssues والـPRs لهما قوالب جاهزة: [تقرير علة](.github/ISSUE_TEMPLATE/bug_report.yml) · [اقتراح ميزة](.github/ISSUE_TEMPLATE/feature_request.yml) · [قالب PR](.github/PULL_REQUEST_TEMPLATE.md).

## 🗺️ سجل السبرنتات

| # | النطاق | الحالة |
|---|---|---|
| 1 | كاش PubChem · README · دفاتر Colab | ✅ |
| 2 | Lab06 ML (pIC50 + فترة ثقة) · تبويب Predict | ✅ |
| 3 | Capstone: خط اكتشاف كامل + تقرير PDF عربي | ✅ |
| 4 | Docking (Vina+Meeko) · PGx (CPIC) · مبدّل لغة · GitHub Pages | ✅ |
| 5 | ADMET Hub (Ersilia) — نماذج موثّقة بلا مفاتيح + مرجعية مدمجة | ✅ |
| 6 | توسيع المكتبة (PubChem/BRICS) · عميل JapanFold موثّق بالعقد الفعلي | ✅ |
| 7 | المحلل الداخلي للبوزات (محرك ثانٍ محلي) · تحقق Boltz-2 opt-in | ✅ |
| 8 | القراءة التلقائية: زر واحد من البذرة إلى تقرير PDF عربي | ✅ |
| 9 | التوليد الموجّه بالهدف — مكافئ ChatChemTS محلي حتمي بلا مفتاح (ChatChemTS يشترط OpenAI مدفوع) | ✅ |
| 10 | التصنيف الدوائي ATC (23 مجموعة + RxNorm حي) + رسم 2D + إثراء MIC بالمجموعات | ✅ |
| 11 | قياس TDC · تحسين Predict بـdescriptors · دفتر Boltz-2 | 📋 [ROADMAP-2026](docs/ROADMAP-2026.md) · [الاستراتيجية](docs/STRATEGY-2026.md) |
| **12** | **النقلة النوعية: منصة API-First — `pharma_sdl/` بـ9 وحدات، FastAPI، Vina حقيقي خلف عقد محركات، بوابة التساهمية، Docker، 46 اختباراً** | ✅ [v0.2.0](CHANGELOG.md) · [المعمارية](docs/ARCHITECTURE.md) |
| **P0–P1** | التدقيق العلمي المستقل (scaffold split، ثلاث درجات، تقرير بأرقام حقيقية) + بوابة الاعتماد الأربع حالات + السجل التجريبي الدائم + الحلقة المغلقة | ✅ [v0.2.x](CHANGELOG.md) |
| **P2** | المصادقة وRBAC (admin حصراً يرقّى) + وضع عرض محدود + مهام دائمة (SQLite) + جناح redocking بلورية مرجعية (RMSD ≤ 2 Å) | ✅ [v0.3.0](CHANGELOG.md) · [ADR-0006/0007](docs/adr/) |
| **P3** | التخزين الحي الحقيقي: PostgreSQL بنفس العقود (مُختبر على خادم مضمّن — لا mocks) + الحلقة المغلقة كخدمة + مقاييس صادقة + ترقية JSONL من طرف إلى طرف | ✅ [v0.4.0](CHANGELOG.md) · [ADR-0008](docs/adr/ADR-0008-live-postgres-loop-service.md) |
| **P4** | التعلم النشط واليقين المُعايَر (حزمة Q4): حملات تُحدّث النموذج من نتائجها، أربعة معايير اختيار، Conformal Prediction بتغطية مقاسة، دليل Go/No-Go: UCB +0.51 pIC50 فوق العشوائي | ✅ [v0.5.0](CHANGELOG.md) · [ADR-0009](docs/adr/ADR-0009-active-learning-conformal.md) · [الدليل](docs/audit/ACTIVE-LEARNING-CAMPAIGN.md) |
| **P5** | مكتبة الطب النبوي: 17 مركباً مُدقَّقاً (عسل 9 · حبة البركة 6 · شعير 2) بتخريج دقيق «متفق عليه» وطبقات دليل T0–T3 وفرز UNVALIDATED على نموذج الإنتاج — الثيموكينون في المركز الأول على MPRO | ✅ [v0.6.0](CHANGELOG.md) · [ADR-0010](docs/adr/ADR-0010-prophetic-medicine-library.md) |
| **P6** | توسيع الأهداف: سجل TARGETS معلن — Mpro + AChE (CHEMBL220) + EGFR (CHEMBL203) بتخريج موحد (900 صف لكل هدف) وحارس شحّة في النواة وفرز ثلاثي UNVALIDATED — pinocembrin أولاً على AChE وCAPE أولاً على EGFR | ✅ [v0.7.0](CHANGELOG.md) · [ADR-0011](docs/adr/ADR-0011-multi-target-expansion.md) |
| **P7** | مقاييس صدق الأهداف: لكل هدف R²/MAE على هياكل محجوزة وتغطية conformal مقاسة — Mpro R²=0.537 والأهداف الجديدة بتغطية أدنى من الاسمية منشورة كما هي — الأرشيف مُلزم والـAPI يقرأه بلا حساب حي | ✅ [v0.8.0](CHANGELOG.md) · [ADR-0012](docs/adr/ADR-0012-target-quality-metrics.md) · [التقرير](docs/audit/TIBB-QUALITY.md) |
| **P8** | جسر الفيزياء: عقد دفعات REST للمختبر الحقيقي (`LabBatchClient` + `HttpLimsLab` + صندوق صادر) — التكامل الفعلي ضبطُ تهيئة لا إعادة كتابة، وعقد نتائج صارم يرفض الدفعة المخرقة كاملة — لا جهاز في CI والحد مُعلن | ✅ [v0.9.0](CHANGELOG.md) · [ADR-0013](docs/adr/ADR-0013-physical-lab-bridge.md) |
| **P9** | الحلقة الفيزيائية: بوابة LIMS مرجعية أمينة أوامر عمل (لا تختلق رقماً — الرفع من الميدان حصراً) + مسار قياسات يعيد المقبول إلى الذاكرة الدائمة + تسوية ما بعد المقاطعة + إصلاح فجوتي P7 (انهيار كامن في التسجيل وسكربت القياس المفقود — الأرقام تتكاثر حرفياً) | ✅ [v0.10.0](CHANGELOG.md) · [ADR-0014](docs/adr/ADR-0014-physical-loop-gateway-and-measurements.md) |
| **P10** | جهة الميدان: بروتوكول أجهزة موحد (`InstrumentDriver`) + سواقة FRET عبر SCPI/TCP + محاكي جهاز واقعي + مراقب جودة خمس طبقات (Recall=100% وFPR=0% مُقاسان على الحالات المصطنعة) + موافقة بشرية إلزامية للحقيقي + حوكمة الوكلاء (`AGENTS.md`/`HANDOFF.md`) — مؤجل بقرار: وكلاء LLM ومكدس Grafana | ✅ [v0.11.0](CHANGELOG.md) · [ADR-0015](docs/adr/ADR-0015-bench-instrument-layer-and-reading-qc.md) · [دليل التوصيل](docs/HARDWARE_HANDOFF.md) |
| **P11** | ترقية نموذج الفعالية بصدق P0: A/B/C/D مقترن على البروتوكول المنشور — بصمة التكرارات + mf=0.3 ترفع R² الهيكلي 0.489→**0.509** والعشوائي 0.436→**0.468** ومعايرة اليقين ρ 0.134→**0.327**؛ ونتيجتان سلبيتان منشورتان (الوصف 0.472، HistGB 0.429) — هدف 0.55 يحتاج بيانات P12 لا أشجاراً | ✅ [v0.12.0](CHANGELOG.md) · [التقرير](docs/audit/MODEL-UPGRADE-P11.md) · [الخطة §5.2](docs/plan/) |
| **P12** | القياس الخارجي الرسمي (TDC `admet_group`): أول قياس على مرجع لا نملكه — تقسيم Scaffold الرسمي المثبّت وبذور اللوحة [1..5] ومقياس `evaluate_many` الرسمي — خط v0.12.0 المعتمد: **Solubility MAE 1.031 ± 0.024** (مرتبة 16/18، يتفوق على خط أساس البصمات المنشور Morgan+MLP 1.203 بفارق 0.172) و**Lipophilicity MAE 0.709 ± 0.006**؛ فجوة +0.25…+0.29 عن الأفضل = سقف فئة «بصمة+RF» مقاساً لا مُخمَّناً — البيانات الرسمية مجمدة بـSHA256 والقياس دون شبكة | ✅ [v0.13.0](CHANGELOG.md) · [التقرير](docs/audit/MODEL-BENCHMARK-TDC-P12.md) · [الخطة §3](docs/plan/) |
| **P13** | مركز ADMET يتوسّع من نموذجين إلى **41 نقطة نهاية**: عميل ADMET-AI v2 (هارفارد، MIT) محلياً على CPU بلا شبكة — مجموعة 5 طيّات متعددة المهام على بيانات TDC + مئينات DrugBank لكل قيمة — قياس حي مجمّد بفحوص صدق دوائية (تيرفينادين hERG 0.970 مقابل أسبرين 0.021؛ إيتراكونازول DILI 0.994؛ وارفارين PPBR 94.3%) — أثرا خارج التوزيع منشوران بصدق — الحزمة اختيارية `[admet]` والغياب بلا تزييف | ✅ [v0.14.0](CHANGELOG.md) · [التقرير](docs/audit/MODEL-ADMET-AI-P13.md) · [الخطة](docs/ROADMAP-2026.md) |
| **P14** | البُعد البنيوي يدخل خط القرار: **المقارنة ثلاثية الطبقات** (ML ← Vina ← **Boltz-2** co-folding، رخصة MIT، رأس تقارب FEP+/CASP16) — محرك `core/three_tier.py` + عميل بيان مجمّد بعقد الوحدات الرسمي + دفتر Colab مكتمل (تسلسل Mpro 306 ببصمة sha256) + لوحة حية خارج العينة بمراسِ ChEMBL موثقة — تحت-تقدير منهجي موثّق وطبقة ثالثة `unavailable_offline` **صادقة** حتى تشغيل Colab واحد — الدرس «متى نثق بأي طبقة» بقواعده الخمس | ✅ [v0.15.0](CHANGELOG.md) · [التقرير](docs/audit/STRUCTURE-TIERS-P14.md) · [الدفتر](notebooks/Lab08_Boltz2_CoFolding.ipynb) |

### إعادة توليد المستقبلات المُجهّزة
```bash
python scripts/prepare_receptors.py   # ينزّل 7VH8/7CMD من RCSB ويجهّز PDBQT ويتحقق بالـself-dock
```

## 📄 License
MIT © 2026

## 📓 Notebooks

| # | المختبر | Colab | الوقت |
|---|---|---|---|
| 01 | الحركية الدوائية (PK) | [![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/tibatechapp-ship-it/pharma-sdl/blob/main/download/Lab01-Pharmacokinetics/Lab01_Pharmacokinetics.ipynb) | 45 دقيقة |
| 02 | اكتشاف الأدوية (RDKit) | [![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/tibatechapp-ship-it/pharma-sdl/blob/main/download/Lab02-Drug-Discovery-RDKit/Lab02_Drug_Discovery_RDKit.ipynb) | 60 دقيقة |
| 03 | PK/PD المضادات | [![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/tibatechapp-ship-it/pharma-sdl/blob/main/download/Lab03-PKPD-Antibiotics/Lab03_PKPD_Antibiotics.ipynb) | 60 دقيقة |
| 04 | PROTAC (Vepdegestrant) | [![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/tibatechapp-ship-it/pharma-sdl/blob/main/download/Lab04-PROTAC/Lab04_PROTAC_Vepdegestrant.ipynb) | 45 دقيقة |
| 05 | CYP2C19 (قطر) | [![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/tibatechapp-ship-it/pharma-sdl/blob/main/download/Lab05-CYP2C19/Lab05_CYP2C19.ipynb) | 45 دقيقة |
| 06 | التنبؤ بالفعالية (ML) | [![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/tibatechapp-ship-it/pharma-sdl/blob/main/download/Lab06-ML-Potency/Lab06_ML_Potency.ipynb) | 60 دقيقة |

### 🧠 خط التعلم الكامل (14 مرحلة)
PK → RDKit Discovery → PK/PD المضادات → PROTAC → CYP2C19 → **ML التنبؤ** → **Capstone: من الهدف إلى القرار** → **Docking ثلاثي الأبعاد (Vina)** → **PGx السريري (CPIC)** → **ADMET (Ersilia)** → **المحلل الداخلي للبوزات** → **القراءة التلقائية الشاملة** → **التوليد الموجّه بالهدف** → **التصنيف الدوائي ATC**
