"""كشف بيئة التشغيل — stlite (WASM/Pyodide) مقابل Python كامل.

stlite يشغّل Streamlit داخل المتصفح عبر Pyodide/WASM. لا توجد عجلات
wasm لـ rdkit أو vina، لذا تعمل مختبرات كثيرة بشكل ناقص هناك.
`is_stlite` يسمح للواجهة بإظهار رسالة توجيه صريحة بدلاً من
استثناءات استيراد غامضة يراها المستخدم النهائي.
"""
from __future__ import annotations

import sys


def is_stlite() -> bool:
    """True إذا كنا داخل stlite (متصفح/WASM).

    الإشارتان الفعليتان: منصة emscripten (نظام WASM الذي يعمل عليه
    Pyodide)، أو وجود وحدة pyodide محمَّلة في sys.modules. لا نعتمد
    على اسم حزمة stlite لأن الكود يعمل داخل العملية نفسها.
    """
    if sys.platform == "emscripten":
        return True
    return "pyodide" in sys.modules
