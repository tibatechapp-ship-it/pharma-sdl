"""مراقب جودة القراءات الميدانية — خمس طبقات قبل الرفع إلى البوابة (P10).

القراءة الخام من الجهاز ليست دليلاً بعد: هذه الوحدة «العقل الناقد»
الذي يفحص كل قراءة قبل أن تُحوَّل إلى صف نتائج يُرفع للبوابة
المرجعية. القراءة `CRITICAL`/`ANOMALOUS` **لا تُرفع أبداً** — سياسة
القبول كاملة في `docs/ANOMALY_POLICY.md`.

الطبقات الخمس مستقلة — تعطيل واحدة لا يكسر البقية:

1. **حدود فيزيائية مطلقة** ⇒ `CRITICAL` رفض فوري (الفيزياء لا تفاوض).
2. **نطاق الضوابط + Z'** — خارج [موجب، سالب] ⇒ `CONTROL_VIOLATION`،
   وZ' يُحتسب ويُعرض (قرار رفض الصفيحة عند Z'<0.5 بشري اليوم — ADR-0015).
3. **Z-score** مقابل تاريخ الجهاز (يحتاج ≥ 20 قراءة تاريخية).
4. **IsolationForest** — أنماط متعددة المتغيرات (scikit-learn تبعية
   مثبتة في المشروع حصراً).
5. **انجراف زمني** — انحراف متوسط آخر 10 قراءات عن سابقاتها (ddof=1:
   انحراف العينة لا الانحراف المُزاح — على n صغير الفرق يصنع قرارات).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, ClassVar

import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

from pharma_sdl.lab.instruments.base import InstrumentReading

logger = logging.getLogger(__name__)


class AnomalySeverity(str, Enum):
    """شدة الحكم على القراءة — تُرجم إلى قرار رفع/رفض وفق السياسة."""

    NORMAL = "normal"
    SUSPICIOUS = "suspicious"
    ANOMALOUS = "anomalous"
    CRITICAL = "critical"


class AnomalyReason(str, Enum):
    """سبب الشذوذ — يظهر في التقرير وقرارات المراجعة البشرية."""

    STATISTICAL_OUTLIER = "statistical_outlier"
    PHYSICAL_IMPOSSIBILITY = "physical_impossibility"
    CONTROL_VIOLATION = "control_violation"
    CALIBRATION_DRIFT = "calibration_drift"
    TEMPORAL_INCONSISTENCY = "temporal_inconsistency"
    INSTRUMENT_NOISE = "instrument_noise"


@dataclass
class AnomalyReport:
    """حكم مراقب الجودة على قراءة واحدة — أسبابه وأرقامه وتوصياته."""

    experiment_id: str
    severity: AnomalySeverity
    reasons: list[AnomalyReason] = field(default_factory=list)
    confidence: float = 0.0
    z_score: float = 0.0
    isolation_forest_score: float = 0.0
    historical_percentile: float = 50.0
    recommendations: list[str] = field(default_factory=list)
    should_reject: bool = False
    details: dict[str, Any] = field(default_factory=dict)

    def is_acceptable(self) -> bool:
        """هل تُرفع القراءة؟ قبول تلقائي للعادي والمشتبه به مع مراجعة."""
        return not self.should_reject and self.severity in (
            AnomalySeverity.NORMAL,
            AnomalySeverity.SUSPICIOUS,
        )

    def to_dict(self) -> dict[str, Any]:
        """تمثيل JSONي — لأرشيف الجلسة وسجل التدقيق."""
        return {
            "experiment_id": self.experiment_id,
            "severity": self.severity.value,
            "reasons": [r.value for r in self.reasons],
            "confidence": round(self.confidence, 3),
            "z_score": round(self.z_score, 3),
            "isolation_forest_score": round(self.isolation_forest_score, 3),
            "historical_percentile": round(self.historical_percentile, 1),
            "recommendations": self.recommendations,
            "should_reject": self.should_reject,
        }


class LabAnomalyDetector:
    """مراقب جودة متعدد الطبقات لقراءات جهاز واحد.

    الاستخدام الميداني:
        detector = LabAnomalyDetector()
        detector.train_on_history(previous_readings)  # اختياري — ≥ 20 قراءة
        report = detector.analyze_reading(reading)
        if report.should_reject:
            ...  # لا رفع إلى البوابة — إعادة قياس أو مراجعة
    """

    #: الحدود الفيزيائية المطلقة (الوحدات: نسبة FRET، µM، °C).
    PHYSICAL_LIMITS: ClassVar[dict[str, tuple[float, float]]] = {
        "raw_value": (0.0, 10.0),
        "ic50_um": (0.0, 1000.0),
        "standard_error": (0.0, 5.0),
        "control_positive": (0.0, 1.0),
        "control_negative": (0.0, 1.0),
        "temperature_c": (0.0, 60.0),
    }
    #: الحد الأدنى للتدريب الإحصائي — أقل من ذلك لا إحصاء ولا ادعاء.
    MIN_TRAINING_SAMPLES: int = 20

    def __init__(self, history_window: int = 200) -> None:
        self.history_window = history_window
        self._history: list[dict[str, Any]] = []
        self._forest: IsolationForest | None = None
        self._scaler: StandardScaler | None = None
        self._trained = False

    # ── التدريب ──────────────────────────────────────────────────

    def train_on_history(self, historical: list[dict[str, Any]]) -> None:
        """تدريب الطبقات الإحصائية على تاريخ قراءات الجهاز الطبيعي.

        أقل من `MIN_TRAINING_SAMPLES` ⇒ تُحفظ القراءات للعرض فقط ولا
        يُدَّعى تدريب — Z-score وIsolationForest يبقيان محايدين صراحة.
        """
        self._history = list(historical)
        if len(historical) < self.MIN_TRAINING_SAMPLES:
            logger.info(
                "تاريخ غير كافٍ للتدريب (%d < %d) — الطبقات الإحصائية محايدة معلنة",
                len(historical),
                self.MIN_TRAINING_SAMPLES,
            )
            return
        self._history = list(historical)[-self.history_window :]
        features = self._extract_features(self._history)
        self._scaler = StandardScaler()
        scaled = self._scaler.fit_transform(features)
        self._forest = IsolationForest(n_estimators=100, contamination=0.05, random_state=42)
        self._forest.fit(scaled)
        self._trained = True
        logger.info("دُرِّب مراقب الجودة على %d قراءة تاريخية", len(self._history))

    # ── التحليل ──────────────────────────────────────────────────

    def analyze(self, result: dict[str, Any]) -> AnomalyReport:
        """تحليل قيم قراءة (dict) عبر الطبقات الخمس → تقرير بقرار رفع/رفض."""
        experiment_id = str(result.get("experiment_id") or "unknown")
        reasons: list[AnomalyReason] = []
        confidence = 0.0
        details: dict[str, Any] = {}

        # 1) الحدود الفيزيائية — رفض فوري لا تفاوض
        violations = self._check_physical_limits(result)
        if violations:
            reasons.append(AnomalyReason.PHYSICAL_IMPOSSIBILITY)
            confidence = max(confidence, 0.95)
            details["physical_violations"] = violations

        # 2) نطاق الضوابط + Z'
        control_check = self._check_controls(result)
        details["control_check"] = control_check
        if not control_check["passed"]:
            reasons.append(AnomalyReason.CONTROL_VIOLATION)
            confidence = max(confidence, 0.75)

        # 3) Z-score التاريخي
        z_score = self._z_score(result)
        if abs(z_score) > 3.0:
            reasons.append(AnomalyReason.STATISTICAL_OUTLIER)
            confidence = max(confidence, 0.55)
        elif abs(z_score) > 2.0:
            confidence = max(confidence, 0.30)

        # 4) IsolationForest (متعدد المتغيرات)
        iso = self._isolation_score(result)
        if iso < -0.5:
            reasons.append(AnomalyReason.INSTRUMENT_NOISE)
            confidence = max(confidence, 0.45)

        # 5) الانجراف الزمني
        if self._temporal_drift():
            reasons.append(AnomalyReason.TEMPORAL_INCONSISTENCY)
            confidence = max(confidence, 0.40)

        severity = self._severity(reasons, confidence)
        return AnomalyReport(
            experiment_id=experiment_id,
            severity=severity,
            reasons=reasons,
            confidence=min(confidence, 1.0),
            z_score=z_score,
            isolation_forest_score=iso,
            historical_percentile=self._percentile(result),
            recommendations=self._recommendations(severity, reasons),
            should_reject=severity in (AnomalySeverity.ANOMALOUS, AnomalySeverity.CRITICAL),
            details=details,
        )

    def analyze_reading(
        self, reading: InstrumentReading, *, temperature_c: float = 37.0
    ) -> AnomalyReport:
        """تحليل قراءة جهاز مباشرة — الجسر المريح من `InstrumentReading`."""
        return self.analyze(
            {
                "experiment_id": reading.experiment_id,
                "raw_value": reading.raw_value,
                "ic50_um": None,  # القراءة الخام بلا IC50 — يدخل لاحقاً من الملاءمة
                "standard_error": reading.standard_error,
                "control_positive": reading.control_positive,
                "control_negative": reading.control_negative,
                "temperature_c": temperature_c,
            }
        )

    # ── الطبقات ──────────────────────────────────────────────────

    def _check_physical_limits(self, result: dict[str, Any]) -> list[str]:
        """كل خروق الحدود المطلقة تُجمع — الرفض يذكرها كلها لا أولها."""
        violations: list[str] = []
        for name, (low, high) in self.PHYSICAL_LIMITS.items():
            value = result.get(name)
            if value is None:
                continue
            try:
                number = float(value)  # type: ignore[arg-type]
            except (TypeError, ValueError):
                violations.append(f"{name} ليس عدداً: {value!r}")
                continue
            if not low <= number <= high:
                violations.append(f"{name}={number} خارج [{low}, {high}]")
        return violations

    def _check_controls(self, result: dict[str, Any]) -> dict[str, Any]:
        """القراءة يجب أن تقع بين الضابطين — وZ' يوثَّق للمراجعة البشرية."""
        try:
            ctrl_pos = result.get("control_positive")
            ctrl_neg = result.get("control_negative")
            raw = result.get("raw_value")
            if ctrl_pos is None or ctrl_neg is None or raw is None:
                return {"passed": False, "reason": "قيم ضوابط مفقودة"}
            ctrl_pos, ctrl_neg, raw = float(ctrl_pos), float(ctrl_neg), float(raw)
            se_raw = result.get("standard_error")
            se = float(se_raw) if se_raw is not None else 0.01
        except (TypeError, ValueError):
            return {"passed": False, "reason": "قيم غير رقمية"}
        low, high = min(ctrl_pos, ctrl_neg), max(ctrl_pos, ctrl_neg)
        denom = abs(ctrl_neg - ctrl_pos)
        z_prime = 1.0 - (6.0 * se / denom) if denom > 1e-9 else 0.0
        return {
            "passed": low <= raw <= high,
            "z_prime_factor": round(z_prime, 3),
            "bounds": [low, high],
            "raw_value": raw,
        }

    def _z_score(self, result: dict[str, Any]) -> float:
        """انحراف القراءة المعياري عن تاريخ الجهاز (0.0 بلا تاريخ كافٍ)."""
        values = [
            float(r.get("raw_value"))
            for r in self._history
            if r.get("raw_value") is not None
        ]
        if len(values) < 2:
            return 0.0
        mean, std = float(np.mean(values)), float(np.std(values, ddof=1))
        if std < 1e-9:
            return 0.0
        try:
            raw = float(result.get("raw_value"))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return 0.0
        return (raw - mean) / std

    def _isolation_score(self, result: dict[str, Any]) -> float:
        """نقاط IsolationForest — سالب = نمط شاذ (0.0 بلا تدريب)."""
        if not self._trained or self._forest is None or self._scaler is None:
            return 0.0
        scaled = self._scaler.transform(self._extract_features([result]))
        return float(self._forest.decision_function(scaled)[0])

    def _temporal_drift(self) -> bool:
        """انحراف متوسط آخر 10 قراءات > 2σ (عينة ddof=1) عن العشرين قبلها."""
        if len(self._history) < 30:
            return False
        recent = [
            float(r.get("raw_value"))
            for r in self._history[-10:]
            if r.get("raw_value") is not None
        ]
        older = [
            float(r.get("raw_value"))
            for r in self._history[-30:-10]
            if r.get("raw_value") is not None
        ]
        if len(recent) < 5 or len(older) < 10:
            return False
        older_std = float(np.std(older, ddof=1))
        if older_std < 1e-6:
            return False
        return abs(float(np.mean(recent)) - float(np.mean(older))) > 2.0 * older_std

    def _percentile(self, result: dict[str, Any]) -> float:
        """موقع القراءة في التوزيع التاريخي — سياق للمراجع البشري."""
        values = sorted(
            float(r.get("raw_value"))
            for r in self._history
            if r.get("raw_value") is not None
        )
        if not values:
            return 50.0
        try:
            raw = float(result.get("raw_value"))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return 50.0
        return 100.0 * sum(1 for v in values if v < raw) / len(values)

    # ── الحكم والتوصيات ──────────────────────────────────────────

    def _severity(self, reasons: list[AnomalyReason], confidence: float) -> AnomalySeverity:
        if AnomalyReason.PHYSICAL_IMPOSSIBILITY in reasons:
            return AnomalySeverity.CRITICAL
        if confidence >= 0.70:
            return AnomalySeverity.ANOMALOUS
        if confidence >= 0.45:
            return AnomalySeverity.SUSPICIOUS
        return AnomalySeverity.NORMAL

    def _recommendations(self, severity: AnomalySeverity, reasons: list[AnomalyReason]) -> list[str]:
        """توصيات عملية للمشغل — بالعربية أولاً لأن ميداننا عربي."""
        recs: list[str] = []
        if severity is AnomalySeverity.CRITICAL:
            recs.append("رفض فوري — القراءة مستحيلة فيزيائياً ولا تُرفع للبوابة")
            recs.append("افحص الجهاز والمعايرة قبل أي قياس تالٍ")
        elif severity is AnomalySeverity.ANOMALOUS:
            recs.append("أعد القياس بصفيف جديد وراجع ضوابط الصفيحة")
        elif severity is AnomalySeverity.SUSPICIOUS:
            recs.append("مراجعة بشرية قبل الرفع — كرر القياس بتكرارات أكثر")
        if AnomalyReason.CONTROL_VIOLATION in reasons:
            recs.append("ضوابط الصفيحة خارجة — كل قراءات هذه الصفيحة مشكوك فيها")
        if AnomalyReason.TEMPORAL_INCONSISTENCY in reasons:
            recs.append("انجراف زمني مكتشف — أعد المعايرة بمعايير جديدة")
        if AnomalyReason.INSTRUMENT_NOISE in reasons:
            recs.append("نمط ضوضاء غير معتاد — افحص التلوث البصري وثبات الحرارة")
        return recs

    def _extract_features(self, rows: list[dict[str, Any]]) -> np.ndarray:
        """ميزات موحدة للتعلم: [raw, se, ctrl_pos, ctrl_neg]."""
        features: list[list[float]] = []
        for row in rows:
            try:
                features.append(
                    [
                        float(row.get("raw_value") or 0.0),
                        float(row.get("standard_error") or 0.0),
                        float(row.get("control_positive") or 0.0),
                        float(row.get("control_negative") or 0.0),
                    ]
                )
            except (TypeError, ValueError):
                features.append([0.0, 0.0, 0.0, 0.0])
        return np.array(features, dtype=float)


__all__ = [
    "AnomalyReason",
    "AnomalyReport",
    "AnomalySeverity",
    "LabAnomalyDetector",
]
