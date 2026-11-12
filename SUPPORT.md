# دعم المستخدمين | Support Guide

> كيف تحصل على المساعدة في Pharma SDL — وبأي ترتيب؟
> (هذا الملف معيار Google للترحيب الرسمي: يفرق بين «دعم الاستخدام» و«الإبلاغ عن ثغرة»)

## سؤال استخدام؟ كيف… لماذا… | How-to questions

**العربية**

1. **ابدأ بالدليل**: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — خريطة المنصة الكاملة
   (تطبيق Streamlit + منصة FastAPI + خط الاكتشاف الثماني).
2. **الأسئلة الشائعة**: [`CONTRIBUTING.md`](CONTRIBUTING.md) يشرح بيئة التطوير والاختبارات.
3. **افتح Discussion أو Issue** على GitHub بوسم `question` — اذكر: الإصدار
   (`pharma_sdl.__version__`)، الخطوة التي حصلت عندها المشكلة، وما توقعته مقابل ما حدث.
4. **صفحة المنصة الحية**: https://tibatechapp-ship-it.github.io/pharma-sdl/

**English**

1. Start with the architecture guide: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).
2. Development setup and test conventions: [`CONTRIBUTING.md`](CONTRIBUTING.md).
3. Open a GitHub issue labeled `question` — include version, step, expected vs actual.

## ثغرة أمنية؟ لا تفتح Issue | Security vulnerability

لا تُنشر الثغرات علناً أبداً — اتبع [`SECURITY.md`](SECURITY.md):
الإبلاغ الخاص أولاً، رد خلال 7 أيام، إصلاح ونشر advisory بعد الإصلاح.

## خطأ برمجي أو اقتراح ميزة | Bug / feature request

- **خطأ قابل لإعادة الإنتاج**: [.github/ISSUE_TEMPLATE/bug_report.yml](.github/ISSUE_TEMPLATE/bug_report.yml)
- **اقتراح ميزة**: [.github/ISSUE_TEMPLATE/feature_request.yml](.github/ISSUE_TEMPLATE/feature_request.yml)

**قاعدة ذهبية**: كل تقرير خطأ يُرفق به «الرقم المعلن» الذي خرق عدالته —
منصة الصدق بنيوياً تُشخَّص من أرقامها.

## المساهمة | Contributing

طريق الـPR الكامل من الفكرة إلى الدمج موثق في [`CONTRIBUTING.md`](CONTRIBUTING.md) —
والسلوك المتوقع في [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md).

## زمن الاستجابة المتوقع | Response expectations

| النوع | القناة | الهدف |
|------|--------|-------|
| ثغرة أمنية | خاص (SECURITY.md) | أول رد ≤ 7 أيام |
| خطأ برمجي | Issue عام | أول رد ≤ أسبوع |
| سؤال استخدام | Issue بوسم `question` | أفضل جهد |
| مساهمة PR | Pull Request | مراجعة ≤ أسبوع |
