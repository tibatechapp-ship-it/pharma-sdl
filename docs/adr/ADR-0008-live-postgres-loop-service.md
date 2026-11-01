# ADR-0008 — التخزين الحي الحقيقي (PostgreSQL) + الحلقة كخدمة + مقاييس صادقة

**الحالة:** مقبول · **التاريخ:** 2026-11-01 · **السياق:** P3 — إكمال وعد ADR-0007 المؤجَّل

## السياق

ADR-0007 سلّم «طريق الترقية إلى PostgreSQL» بلا كود حي: مخطط جاهز
(`deploy/postgres/schema.sql`) + نقل JSONL + شرط التفعيل الموثق. وفي تقييم
ما قبل P2 وُثّق صراحة: «PostgreSQL/Celery/Redis كخدمات قيد التشغيل لا تُشغَّل
بلا بنية حقيقية — بلا كود غير مُختبر ادّعاؤه داعماً». P3 هو حين صار الشرط
قابلاً للاختبار فعلاً: خادم PostgreSQL مضمّن (pgserver) يجعل كود الخلفية
الحية قابلاً للتحقق في CI ومحلياً بلا بنية خارجية.

## القرار

**1) مخزنان حيّان بنفس العقود حرفياً** — لا واجهات جديدة ولا انحراف:

- `experiments/pg_store.py` → `PostgresExperimentStore`: نفس دوال
  `ExperimentRegistry` (begin/upsert/complete/fail/attach_validation/
  validation_card_of/get/latest/lineage/stats/validation_stats/count) —
  payload = `ExperimentRecord` كاملاً في عمود JSONB **ككائن لا نص مضاعف
  الترميز**، فاستعلامات `payload->>'…'` تعمل، والمخطط يُنصَب ذاتياً مطابقاً
  لـschema.sql بما فيه المفتاح الأجنبي على `parent_experiment_id`.
- `jobs/pg_store.py` → `PostgresJobStore`: نفس دوال `SQLiteJobStore`
  (submit/get/result_of/list/stats + توثيق المقاطع `interrupted by service
  restart` عند الإقلاع + تنظيف TTL) — ونتائج pydantic تعود كما كُتبت.
- فشل الاتصال خطأ منصة مترجم `store_unavailable` (503) — لا انهيار غامض.

**2) الاختيار من الإعدادات لا من الكود** (`config.py`):
`PHARMA_SDL_STORE=sqlite|postgres` + `PHARMA_SDL_PG_DSN` — غياب DSN أو
psycopg خطأ صريح مُعلَّل. المصنعان: `experiments.get_experiment_registry()`
و`jobs.get_job_store()`؛ و`/health` يعلن `store_backend` — لا خلفية خفية.

**3) الحلقة المغلقة كخدمة** (`api/routes/loop.py`):
`POST /api/v1/loop/runs` (scientist) مهمة دائمة من نوع `closed_loop` تشغّل
`run_closed_loop` (قبلنا بارامتر `registry` اختياري — كتابة في سجل المنصة
نفسه) على المنصة المضيفة sqlite أو postgres بالضبط بنفس الكود؛
`GET /api/v1/loop/runs/{id}` يقرأ الجولات الثلاث من الطابور الدائم.
كل النتائج UNVALIDATED — بوابة الاعتماد P1 بشرية حصراً، ولا مسار API يرقّى آلياً.
وضع العرض: قفل المحرك على القائمة المسموحة وسقف top_n مفروض في مسار التنفيذ.

**4) مقاييس صادقة** (`GET /api/v1/metrics`, viewer):
تجارب بحسب الحالة وحالة الاعتماد (`validation_stats` على الخلفيتين)، مهام
بحسب الحالة، الخلفية الحية، المحركات المتاحة — تُقرأ لحظة الطلب بلا كاش.

**5) استراتيجية الاختبار — بلا mocks:**
pgserver (خادم PostgreSQL مضمّن فعلي) يشغّل اختبارات تكافؤ العقد بين
الخلفيتين على نفس التسلسل، واختبار الترقية من طرف إلى طرف: حلقة كاملة على
SQLite → `export-experiments` JSONL → استيراد في PostgreSQL → سلسلة الأسلاف
والحالات تنجو حرفياً. (`import_jsonl` رُتِّب زمنياً صعوداً ليعمل فوق مخازن FK
بأي ترتيب ملف.)

## البدائل المرفوضة

- **Celery/Redis الآن:** نفس منطق ADR-0007 — الشرط المعلن (مستخدمون متعددون
  متزامنون، مهام > 10 دقائق، تعدد نسخ API) لم يتحقق؛ `PostgresJobStore`
  يغطي الحالة الوسيطة بنفس العقد، وCelery يبقى استبدالاً محلياً عند نضوجه.
- **ORM / SQLAlchemy:** طبقة إضافية بلا حاجة — psycopg الخام + JSONB أوضح
  وأقرب لعقد SQLite الحرفي.
- **Connection pool:** كل عملية اتصال قصير العمر — بأمرَي كتابة من تكلفة
  pool، ومناسب لحجم فريق علمي واحد؛ يُعاد النظر عند تعدد النسخ.
- **خدمة postgres في CI بدل pgserver:** مساران للاختبار يشتّتان الصدق —
  pgserver واحد يشغّل نفس الاختبارات محلياً وفي CI بنفس الكود.

## النتائج

- الترقية الموعودة صارت زراً لا مشروعاً: `PHARMA_SDL_STORE=postgres`.
- docker-compose: خدمة `postgres` بملف تعريف `pg` + DSN جاهز.
- كل اختبارات P0–P3 تُشغَّل في CI (platform.yml) — 391 اختباراً محلياً.
