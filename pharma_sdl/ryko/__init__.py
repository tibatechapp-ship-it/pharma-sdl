"""Ryko — العقل العلمي لمنصة Pharma SDL (docs/ryko/RYKO-MASTER-PLAN.md).

الوحدات (6):
    math          — الرياضيات والحساب الدوائي (وحدات، AUC، توافر، إحصاء)
    physics       — الفيزياء (ΔG للربط، انتشار، Arrhenius، van't Hoff، Fick)
    chem          — الكيمياء (RDKit، Lipinski، أيونبة Henderson-Hasselbalch)
    pharmaceutics — الصيدلانيات (انحلال، BCS، جرعات، تسريب)
    pharma        — الفارماكولوجيا (Hill، مؤشر أمان، Cheng-Prusoff، CYP/DDD معلنة)
    diagnostics   — مرحلة 2 (بذرة بايزية: PPV/NPV/LR/kappa — بلا تشخيص سريري)

كل عملية تعيد إيصالاً (قيمة + معادلة + مصدر + افتراضات + بصمة SHA-256)
قابلاً للتحقق دون اتصال، عبر RykoEngine أو بوابة /api/v1/ryko.
"""

from __future__ import annotations

from .engine import MODULE_TITLES, OPS, RYKO_VERSION, OpSpec, RykoEngine
from .errors import RykoError, RykoInputError, RykoUnknownOpError
from .receipts import RykoReceipt

__version__ = RYKO_VERSION
__all__ = [
    "MODULE_TITLES",
    "OPS",
    "RYKO_VERSION",
    "OpSpec",
    "RykoEngine",
    "RykoError",
    "RykoInputError",
    "RykoReceipt",
    "RykoUnknownOpError",
    "__version__",
]

_ENGINE: RykoEngine | None = None


def get_engine() -> RykoEngine:
    """المحرك المفرد — بلا حالة، فالمفرد هنا للتسجيل فقط لا للمخزن."""
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = RykoEngine()
    return _ENGINE
