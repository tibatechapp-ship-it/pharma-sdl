"""عدم اليقين المُعايَر — Conformal Prediction (حزمة الربع الرابع من الخطة).

انحراف أشجار RF يرتبط بالخطأ (تدقيق P0: ارتباط Spearman موثّق في
docs/audit/model-evaluation-results.json) لكنه ليس فاصل ثقة ولا وعد تغطية.
فترة التنبؤ conformal تحوّل بواقي مجموعة معايرة إلى فترة بضمان تغطية تحت
فرض التبادلية وحده — بلا افتراض توزيعي وبلا نموذج جديد.

الصدق بنيوياً:
    - التغطية الاسمية (1−α) تُعلن بجانب التغطية الفعلية المقاسة دائماً —
      الوعود بلا قياس ممنوعة.
    - الفترة متماثلة حول التنبؤ (split-conformal كلاسيكي ببواقي مطلقة) —
      أبسط شكل قابل للتفسير والتحقق.
    - لا تُدمج فترات خطوط الدرجات الثلاثة أبداً: هذا وحد pIC50/pChEMBL
      (SCORE_LANES) — الدocking وقياسات المخبر عوالم منفصلة.
"""

from __future__ import annotations

import math

import numpy as np


class ConformalCalibrator:
    """معاير split-conformal — بواقي معايرة → فترة تنبؤ بتغطية اسمية 1−α.

    العقد: تمرر تنبؤات معايرة وقيمها الحقيقية مرة واحدة، ثم تطلب فترة لأي
    تنبؤ لاحق. القيمة q هي كمّية البواقي المطلقة بتصحيح العينة المحدودة
    (rank ⌈(n+1)(1−α)⌉) — نفس ضمان التغطية في أدبيات Vovk/Papadopoulos.
    """

    def __init__(
        self,
        calib_pred: np.ndarray,
        calib_true: np.ndarray,
        alpha: float = 0.10,
    ) -> None:
        if not 0.0 < alpha < 1.0:
            raise ValueError(f"alpha must be in (0, 1), got {alpha}")
        calib_pred = np.asarray(calib_pred, dtype=float)
        calib_true = np.asarray(calib_true, dtype=float)
        if calib_pred.shape != calib_true.shape or calib_pred.ndim != 1:
            raise ValueError("calib_pred and calib_true must be 1-D arrays of equal length")
        if len(calib_pred) < 2:
            raise ValueError("معايرة conformal تحتاج نقطتين على الأقل — لا معايرة بلا بواقي")
        residuals = np.abs(calib_true - calib_pred)
        n = len(residuals)
        rank = math.ceil((n + 1) * (1.0 - alpha))
        self.alpha = float(alpha)
        self.n_calib = int(n)
        self.nominal_coverage = 1.0 - float(alpha)
        # ضمان العينة المحدودة يتطلب rank ≤ n؛ لو لم يتحقق (α صغيرة جداً
        # لن=( صغير)) نصحح إلى أقصى بواقٍ ونعلن انكسار الضمان بصدق.
        self.finite_sample_guarantee = rank <= n
        self.q = float(np.sort(residuals)[min(rank, n) - 1])

    def interval(self, pred: float | np.ndarray) -> tuple[float, float] | tuple[np.ndarray, np.ndarray]:
        """فترة التنبؤ [pred−q, pred+q] — لقيمة واحدة أو مصفوفة."""
        if isinstance(pred, np.ndarray):
            return pred - self.q, pred + self.q
        return float(pred - self.q), float(pred + self.q)

    def coverage(self, preds: np.ndarray, trues: np.ndarray) -> float:
        """التغطية الفعلية المقاسة — النسبة داخل الفترة على مجموعة تقييم.

        هذه هي الرقم الذي يُعلن دائماً بجانب التغطية الاسمية: الوعد بلا قياس
        ليس علمياً.
        """
        preds = np.asarray(preds, dtype=float)
        trues = np.asarray(trues, dtype=float)
        if preds.shape != trues.shape:
            raise ValueError("preds and trues must have the same shape")
        inside = (trues >= preds - self.q) & (trues <= preds + self.q)
        return float(inside.mean()) if len(inside) else 0.0

    def summary(self) -> dict:
        """ملخص صادق للمعايرة — يُضمَّن في التقارير كما هو."""
        return {
            "method": "split_conformal_absolute_residual",
            "alpha": self.alpha,
            "n_calib": self.n_calib,
            "q_hat": round(self.q, 4),
            "nominal_coverage": round(self.nominal_coverage, 3),
            "finite_sample_guarantee": self.finite_sample_guarantee,
        }


__all__ = ["ConformalCalibrator"]
