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

## 2) أوامر البدء — المسار الأول: Ersilia (الأنضج والأقرب لبيئتنا)

```bash
# 1. التثبيت في بيئة مخصصة (لا نلمس requirements.txt المثبَّت بدقة قبل التحقق)
python -m venv .venv-ersilia && source .venv-ersilia/bin/activate
pip install ersilia

# 2. اختر نموذجاً من https://hub.ersilia.io (سمية hERG، CYP مثبطة، ذوبان…)
ersilia fetch <model-id>
ersilia serve <model-id>          # يفتح API محلي على المنفذ الافتراضي

# 3. نداء تجريبي بأسبرين
curl -X POST http://localhost:7860/run \
  -H "Content-Type: application/json" \
  -d '{"inputs":[{"input":"CC(=O)Oc1ccccc1C(=O)O"}]}'
```

هيكل العميل المستهدف (`core/clients/ersilia_client.py`) — يتبع النمط المعتمد:

```python
ERSILIA_BASE = os.environ.get("ERSILIA_BASE", "http://localhost:7860")

@dataclass(frozen=True)
class AdmetRow:
    model_id: str
    smiles: str
    endpoint: str          # مثل "hERG_inhibition"
    value: float
    verdict_ar: str        # حكم تعليمي عربي

def predict_admet(smiles: str, model_id: str, timeout: float = 15.0) -> AdmetRow | None:
    """نداء واحد — يرجع None عند أي فشل شبكة (نمط fetch_analog_library)."""
    try:
        resp = requests.post(f"{ERSILIA_BASE}/run", json=..., timeout=timeout)
        resp.raise_for_status()
        return _parse(resp.json())
    except (requests.RequestException, KeyError, ValueError):
        return None
```

ثم تبويب أو قسم ADMET في Capstone: مرّر أفضل 5 جزيئات من خط Capstone على
نموذج سمية واحد، وقارن الترتيب قبل/بعد فلتر ADMET — درس قوي جداً.

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
| S5 (الآن) | دمج `feat/pharma-hardening` ثم Ersilia ADMET عميل+تبويب | اختبارات mock خضراء + نداء حي موثق |
| S6 | JapanFold: تحقق → عميل → «توسيع المكتبة» في Make | job حي موثق + fallback |
| S7 | DockThor/Matcha كمحرك ثانٍ في Docking | نفس DockingResult يعمل بمحركين |
| S8 | `auto_pipeline.py` + زر «قراءة تلقائية» في Capstone | تقرير PDF كامل من نقرة واحدة |

## 7) قواعد ثابتة أيا كان السبرنت

1. لا نلمس `deploy-hf.yml.disabled` ولا نضيف خطوات نشر — قرار النشر منفصل.
2. كل نداء شبكة: `timeout` صريح + لا استثناءات للواجهة + كاش صريح.
3. كل ميزة تعليمية: نص عربي «لماذا يهم سريرياً؟» من مكتبة الحالات.
4. إخلاء المسؤولية التعليمي في كل مخرجات — المنصة تدريب لا توصية علاجية.
