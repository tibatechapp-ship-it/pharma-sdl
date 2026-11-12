# 🔌 دليل توصيل جهاز FRET حقيقي — نقطة الوصل البشرية (HANDOFF #1)

> P8/P9 أوصلا العقد حتى نقطة الرفع في البوابة؛ P10 بنى جهة الميدان
> كاملة. **المقبس جاهز — توصيل السلك الفيزيائي قرارك أنت.**

## ✅ ما هو جاهز ومُختبَر (619 اختباراً عند لحظة P10 — 767 في 2026-11)

- بروتوكول `InstrumentDriver` موحّد (runtime-checkable)
- سواقة `FRETReaderDriver` — SCPI عبر TCP، buffer استقبال دائم
- محاكي واقعي: `pharma-sdl simulator` (اختبار كل شيء بلا عتاد)
- مراقب جودة خمس طبقات يمنع رفع القراءات المستحيلة
- جسر `reading_to_payload` — لا يشتق IC50 ولا يكذب في `simulated`

## 🎯 الجلسة الميدانية الكاملة (على المحاكي — تدريب)

```bash
# طرفية 1 — محاكي الجهاز
pharma-sdl simulator --port 10001

# طرفية 2 — جلسة بروتوكولية كاملة
python - <<'EOF'
import json, secrets
from pharma_sdl.lab.instruments import FRETReaderDriver, reading_to_payload
from pharma_sdl.lab.anomaly_detector import LabAnomalyDetector

drv = FRETReaderDriver(host="127.0.0.1", port=10001, simulated=True)
drv.connect()
try:
    hash_curve = drv.calibrate([0.0, 0.25, 0.5, 1.0])
    reading = drv.run_assay(
        compound_id="CMP-042", target_id="7VH8_A",
        protocol_name="FRET_Mpro_v1", approval_token="",
    )
finally:
    drv.disconnect()

qc = LabAnomalyDetector().analyze_reading(reading)
print(json.dumps({"reading": reading.to_dict(), "qc": qc.to_dict()}, ensure_ascii=False, indent=2))
if not qc.should_reject:
    # ic50_um هنا من ملاءمة منحنى الجرعة — قيمة بشرية لا يخترعها الكود
    row = reading_to_payload(reading, smiles="O=C(N)c1ccccc1", ic50_um=0.42)
    print("جاهز للرفع إلى البوابة:", json.dumps(row, ensure_ascii=False))
EOF
```

النتيجة المتوقعة: قراءة `simulated=True` بين الضوابط، وتقرير QC
`normal`، وصف جاهز — لكنه صف محاكاة **وسترفضه بوابة حقيقية** إن حاول
الرفع عبرها، وهذا هو السلوك الصحيح.

## 🚀 التبديل إلى الجهاز الحقيقي

### 1. تحقق من الجهاز

| الجهاز | المنفذ الافتراضي | ملاحظات |
| :--- | :--- | :--- |
| Tecan Spark | 10001 | فعّل SCPI/Remote من إعدادات الجهاز |
| BMG CLARIOstar | 10001 | تحقق من دليل البروتوكول |
| PerkinElmer EnVision | حسب الإصدار | قد يحتاج جسر TCP-serial |

إذا كان جهازك Serial/USB فقط: اكتب سواقة جديدة تنفذ
`InstrumentDriver` (نفس العقد) — لا تعدّل `FRETReaderDriver`.

### 2. البيئة

```bash
# .env — الجهاز الحقيقي قرار موثق في ثلاثة أسطر
PHARMA_SDL_INSTRUMENT_HOST=192.168.1.50
PHARMA_SDL_INSTRUMENT_SIMULATED=false     # ← السطر الحاسم
LAB_OPERATOR_ID=tech_001
```

### 3. جلسة التحقق الأولى (بلا صفيحة تجريبية)

```python
from pharma_sdl.config import get_settings
from pharma_sdl.lab.instruments import make_instrument_driver

drv = make_instrument_driver(get_settings())   # من البيئة — لا قيم مبعثرة
drv.connect()
print(drv.get_status(), drv.serial_number)
print("بصمة المعايرة:", drv.calibrate([0.0, 0.25, 0.5, 1.0]))
drv.disconnect()
```

### 4. أول قياس حقيقي

- [ ] رمز موافقة بشرية ≥ 16 حرفاً من بوابة الاعتماد جاهز
- [ ] الضوابط الإيجابية والسالبة في الصفيحة
- [ ] `LAB_OPERATOR_ID` مضبوط
- [ ] ثم نفس الجلسة أعلاه مع `approval_token=<الرمز>` — القراءة
  ستحمل `simulated=False` تلقائياً، ورفعها للبوابة المرجعية عبر
  `POST /batches/{id}/results` يجعلها قابلة للبلع في مسار
  القياسات (`MeasurementIngestor`) وتبقى UNVALIDATED حتى ترقية
  بشرية موثقة.

## ⚠️ أول جلسة على الحقيقي تعيد ضبط الحدود

حدود `PHYSICAL_LIMITS` وقيم الضوابط في `ANOMALY_POLICY.md` جاءت من
البروتوكول لا من الميدان. بعد أول يوم قياس حقيقي: قارن توزيع
القراءات الحقيقية بالحدود، وحدّث الأرقام بقرار موثق (ADR/إدخال
سياسة) — الأرقام تتبع الواقع لا العكس.

## 🚨 استكشاف الأخطاء

| العَرَض | السبب المحتمل | الحل |
| :--- | :--- | :--- |
| `InstrumentConnectionError` عند connect | IP/منفذ أو جدار ناري | `ping` + تحقق من منفذ SCPI |
| `ERROR: unknown command` | الجهاز لا يدعم الأمر | راجع دليل الجهاز — نفس العقد يبقى، الأوامر تتعدل |
| `SafetyViolation: رمز موافقة` | الجهاز حقيقي والرمز غائب/قصير | ولّد رمزاً من بوابة الاعتماد |
| `SafetyViolation: حد القياسات` | تجاوز 10/ساعة | انتظر النافذة — الحماية مقصودة |
| `الحرارة لم تستقر` | غطاء الصفيحة/التهوية | راجع ضبط الحاضنة قبل إعادة المحاولة |
| `simulated=True` بالخطأ | `PHARMA_SDL_INSTRUMENT_SIMULATED` لم يضبط false | راجع `.env` |
