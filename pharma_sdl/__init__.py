"""Pharma SDL — طبقة المنصة التشغيلية (API-First).

v0.2.0 — النقلة النوعية: من تطبيق تعليمي Streamlit إلى منصة مكوّنات تشغيلية،
وفق الخطة الاستراتيجية v1.1 (docs/plan/PharmaSDL_Strategic_Plan_v1.1.pdf):

    تنقية المكتبة ← الفرز الظاهري ← الإجماع العلاجي ← المختبر ← التقرير
    بمحركات قابلة للتبديل: Vina محلياً · Boltz-2 عن بُعد · محاكاة حتمية للتجارب وCI

خريطة الوحدات (9):
    chemistry  — كيمياء حاسوبية وفلاتر أمان (PAINS · رؤوس تساهمية · Lipinski/Veber)
    targets    — سجل الأهداف وسياساتها (Mpro 7VH8 — غير تساهمي حصراً)
    engines    — سجل محركات التسجيل القابلة للتبديل (Simulation/Vina/Boltz-2)
    curation   — خط تنقية المكتبة: توحيد، إزالة تكرار، فلاتر مع مسار تدقيق
    screening  — منسّق الفرز الظاهري (Walking Skeleton — من نقطة API واحدة)
    affinity   — جسور الإجماع: Cheng-Prusoff (ΔG ≈ −1.364 × pIC50)
    lab        — واجهة المختبر الذاتي (FRET محاكى الآن — مقبس للدمج الحقيقي)
    reporting  — تقارير Markdown/JSON ثنائية اللغة لكل جولة فرز
    api        — بوابة FastAPI + طابور مهام داخلي + OpenAPI

الطبقة التعليمية (core/ + app.py) تبقى كما هي وتبنى فوق هذه المنصة تدريجياً.
"""

from __future__ import annotations

__version__ = "0.10.0"
__all__ = ["Settings", "__version__", "get_settings"]


def __getattr__(name: str):
    if name in {"Settings", "get_settings"}:
        from pharma_sdl.config import Settings, get_settings

        return {"Settings": Settings, "get_settings": get_settings}[name]
    raise AttributeError(f"module 'pharma_sdl' has no attribute {name!r}")
