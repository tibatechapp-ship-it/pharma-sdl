"""اختبارات مراقب جودة القراءات — كل طبقة لها حالة، وRecall/FPR مُقاسان (P10).

معيار القبول من دورة كشف الشذوذ: كل الحالات المصطنعة تُرفض
(Recall = 100%) والنتائج الطبيعية لا تُرفض (FPR < 10%) — مُقاسان
هنا لا مُدَّعيان.
"""

from __future__ import annotations

from datetime import UTC, datetime

import numpy as np
import pytest

from pharma_sdl.lab.anomaly_detector import (
    AnomalyReason,
    AnomalySeverity,
    LabAnomalyDetector,
)
from pharma_sdl.lab.instruments.base import InstrumentReading

_NORMAL = {
    "experiment_id": "EXP-NORMAL-001",
    "raw_value": 0.65,
    "ic50_um": None,
    "standard_error": 0.02,
    "control_positive": 0.15,
    "control_negative": 0.95,
    "temperature_c": 37.0,
}


@pytest.fixture
def detector() -> LabAnomalyDetector:
    return LabAnomalyDetector()


@pytest.fixture
def trained_detector() -> LabAnomalyDetector:
    """مراقب مدرَّب على 200 قراءة تاريخية طبيعية."""
    rng = np.random.default_rng(42)
    history = [
        {
            "raw_value": float(rng.normal(0.65, 0.05)),
            "standard_error": 0.02,
            "control_positive": 0.15,
            "control_negative": 0.95,
        }
        for _ in range(200)
    ]
    d = LabAnomalyDetector()
    d.train_on_history(history)
    return d


def _reading(raw_value: float) -> InstrumentReading:
    return InstrumentReading(
        experiment_id="EXP-QC",
        compound_id="CMP-QC",
        target_id="7VH8_A",
        instrument_serial="SN-QC",
        timestamp=datetime.now(UTC),
        raw_value=raw_value,
        standard_error=0.02,
        control_positive=0.15,
        control_negative=0.95,
        calibration_curve_hash="h",
        operator_id="op",
        approval_token="SIMULATED-abc",
        simulated=True,
    )


# ── الطبقة 1: الحدود الفيزيائية ──────────────────────────────────


class TestPhysicalLimits:
    def test_normal_reading_passes(self, detector):
        report = detector.analyze(dict(_NORMAL))
        assert AnomalyReason.PHYSICAL_IMPOSSIBILITY not in report.reasons
        assert report.should_reject is False

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("raw_value", -1.0),
            ("raw_value", 15.0),
            ("ic50_um", -5.0),
            ("ic50_um", 1e9),
            ("temperature_c", 75.0),
            ("standard_error", 10.0),
            ("control_positive", 1.5),
        ],
    )
    def test_violation_is_critical_and_rejected(self, detector, field, value):
        report = detector.analyze({**_NORMAL, field: value})
        assert AnomalyReason.PHYSICAL_IMPOSSIBILITY in report.reasons
        assert report.severity is AnomalySeverity.CRITICAL
        assert report.should_reject is True

    def test_all_violations_listed_not_just_first(self, detector):
        report = detector.analyze({**_NORMAL, "raw_value": -1.0, "temperature_c": 100.0})
        assert len(report.details["physical_violations"]) >= 2

    def test_missing_optional_fields_are_not_violations(self, detector):
        report = detector.analyze({"experiment_id": "EXP-MIN", "raw_value": 0.65})
        assert AnomalyReason.PHYSICAL_IMPOSSIBILITY not in report.reasons


# ── الطبقة 2: الضوابط وZ' ────────────────────────────────────────


class TestControls:
    def test_between_controls_passes(self, detector):
        report = detector.analyze(dict(_NORMAL))
        assert report.details["control_check"]["passed"] is True

    def test_above_negative_control_fails(self, detector):
        report = detector.analyze({**_NORMAL, "raw_value": 0.97})
        assert AnomalyReason.CONTROL_VIOLATION in report.reasons

    def test_below_positive_control_fails(self, detector):
        report = detector.analyze({**_NORMAL, "raw_value": 0.10})
        assert AnomalyReason.CONTROL_VIOLATION in report.reasons

    def test_missing_controls_marked_failed(self, detector):
        report = detector.analyze({"experiment_id": "EXP-NO-CTRL", "raw_value": 0.65})
        assert report.details["control_check"]["passed"] is False

    def test_control_violation_is_anomalous_and_rejected(self, detector):
        """خروج عن الضوابط (2.0 داخل الحدود الفيزيائية) ⇒ ANOMALOUS رفض."""
        report = detector.analyze({**_NORMAL, "raw_value": 2.0})
        assert report.severity is AnomalySeverity.ANOMALOUS
        assert report.should_reject is True

    def test_z_prime_computed_from_declared_noise(self, detector):
        """se=0.02 و|0.95−0.15|=0.8 ⇒ Z' = 1 − 6·0.02/0.8 = 0.85."""
        report = detector.analyze(dict(_NORMAL))
        assert 0.7 < report.details["control_check"]["z_prime_factor"] <= 1.0


# ── الطبقة 3: الإحصاء التاريخي ───────────────────────────────────


class TestStatistics:
    def test_far_value_gets_big_z_score(self, trained_detector):
        report = trained_detector.analyze({**_NORMAL, "raw_value": 0.90})
        assert abs(report.z_score) > 2.0

    def test_typical_value_gets_small_z_score(self, trained_detector):
        report = trained_detector.analyze(dict(_NORMAL))
        assert abs(report.z_score) < 2.0

    def test_no_history_means_neutral_z(self, detector):
        assert detector.analyze(dict(_NORMAL)).z_score == 0.0

    def test_insufficient_history_keeps_z_neutral(self):
        d = LabAnomalyDetector()
        d.train_on_history([{"raw_value": 0.65} for _ in range(5)])
        assert d.analyze(dict(_NORMAL)).z_score == 0.0


# ── الطبقة 4: IsolationForest ────────────────────────────────────


class TestIsolationForest:
    def test_untrained_detector_is_neutral(self, detector):
        assert detector.analyze(dict(_NORMAL)).isolation_forest_score == 0.0

    def test_trained_detector_produces_finite_score(self, trained_detector):
        score = trained_detector.analyze(dict(_NORMAL)).isolation_forest_score
        assert isinstance(score, float)
        assert np.isfinite(score)

    def test_multivariate_anomaly_caught_by_forest(self, trained_detector):
        """raw عادي لكن الضوابط منحلة — النمط متعدد المتغيرات يلتقطه الغابة."""
        report = trained_detector.analyze(
            {**_NORMAL, "control_positive": 0.9, "control_negative": 0.2}
        )
        assert report.isolation_forest_score != 0.0


# ── الطبقة 5: الانجراف الزمني (ddof=1) ───────────────────────────


class TestTemporalDrift:
    def test_drift_detected_on_shifted_window(self):
        detector = LabAnomalyDetector()
        detector._history = (
            [{"raw_value": 0.65 + (i % 3) * 0.01} for i in range(20)]
            + [{"raw_value": 0.75 + (i % 3) * 0.01} for i in range(10)]
        )
        assert detector._temporal_drift() is True

    def test_stable_history_no_false_drift(self):
        detector = LabAnomalyDetector()
        detector._history = [
            {"raw_value": 0.65 + 0.01 * ((i % 5) - 2)} for i in range(30)
        ]
        assert detector._temporal_drift() is False

    def test_short_history_skips_temporal_layer(self, detector):
        detector._history = [{"raw_value": 0.65} for _ in range(10)]
        assert detector._temporal_drift() is False


# ── الحكم والتوصيات ──────────────────────────────────────────────


class TestVerdict:
    def test_normal_is_acceptable(self, detector):
        report = detector.analyze(dict(_NORMAL))
        assert report.severity is AnomalySeverity.NORMAL
        assert report.is_acceptable() is True

    def test_suspicious_is_review_not_reject(self, detector):
        """z بين 2 و3 فقط ⇒ SUSPICIOUS — مراجعة بشرية لا رفض آلي."""
        trained = trained_detector_no_fixture()
        report = trained.analyze({**_NORMAL, "raw_value": 0.80})
        assert report.severity is AnomalySeverity.SUSPICIOUS
        assert report.should_reject is False
        assert report.is_acceptable() is True

    def test_critical_has_urgent_recommendation(self, detector):
        report = detector.analyze({**_NORMAL, "raw_value": -1.0})
        assert any("رفض فوري" in rec for rec in report.recommendations)

    def test_control_violation_mentions_plate(self, detector):
        report = detector.analyze({**_NORMAL, "raw_value": 2.0})
        assert any("الصفيحة" in rec for rec in report.recommendations)

    def test_report_to_dict_roundtrip(self, detector):
        data = detector.analyze({**_NORMAL, "raw_value": -1.0}).to_dict()
        assert data["severity"] == "critical"
        assert data["should_reject"] is True
        assert "physical_impossibility" in data["reasons"]


def trained_detector_no_fixture() -> LabAnomalyDetector:
    rng = np.random.default_rng(7)
    history = [
        {
            "raw_value": float(rng.normal(0.65, 0.05)),
            "standard_error": 0.02,
            "control_positive": 0.15,
            "control_negative": 0.95,
        }
        for _ in range(200)
    ]
    d = LabAnomalyDetector()
    d.train_on_history(history)
    return d


# ── المعياران المعلنان: Recall وFPR ─────────────────────────────


class TestRecallAndFPR:
    @pytest.mark.parametrize(
        "mutated",
        [
            {"raw_value": -0.5},  # نسبة سالبة
            {"raw_value": 50.0},  # نسبة مستحيلة
            {"raw_value": -0.1},  # تحت الصفر قليلاً
            {"ic50_um": -10.0},  # IC50 سالبة
            {"temperature_c": 75.0},  # حرارة فوق أي بروتوكول
            {"standard_error": 10.0},  # خطأ قياس فج
            {"control_positive": 0.0, "control_negative": 0.0, "raw_value": 0.65},  # ضوابط صفر
            {"raw_value": 2.0},  # فوق الضوابط
        ],
    )
    def test_synthetic_anomaly_rejected(self, detector, mutated):
        report = detector.analyze({**_NORMAL, **mutated, "experiment_id": "EXP-SYN"})
        assert report.should_reject is True, report.to_dict()

    def test_recall_is_100_percent_on_synthetic_suite(self, detector):
        mutations = [
            {"raw_value": -0.5},
            {"raw_value": 50.0},
            {"raw_value": -0.1},
            {"raw_value": 2.0},
            {"ic50_um": -10.0},
            {"temperature_c": 75.0},
            {"standard_error": 10.0},
            {"control_positive": 0.0, "control_negative": 0.0},
        ]
        detected = sum(
            1
            for m in mutations
            if detector.analyze({**_NORMAL, **m, "experiment_id": "EXP-SYN"}).should_reject
        )
        assert detected / len(mutations) == 1.0

    def test_fpr_below_10_percent_on_normals(self, detector):
        """100 قراءة طبيعية — لا رفض آلي (المستهدف < 10%)."""
        rng = np.random.default_rng(123)
        rejected = 0
        n = 100
        for i in range(n):
            result = {
                "experiment_id": f"EXP-NP-{i}",
                "raw_value": float(rng.normal(0.65, 0.03)),
                "standard_error": 0.02,
                "control_positive": 0.15,
                "control_negative": 0.95,
                "temperature_c": 37.0,
            }
            if detector.analyze(result).should_reject:
                rejected += 1
        assert rejected / n < 0.10, f"FPR = {rejected / n:.2%}"


# ── الجسر من القراءة ─────────────────────────────────────────────


class TestAnalyzeReading:
    def test_normal_device_reading_is_acceptable(self, detector):
        report = detector.analyze_reading(_reading(0.625))
        assert report.is_acceptable() is True

    def test_impossible_device_reading_is_critical(self, detector):
        report = detector.analyze_reading(_reading(-0.5))
        assert report.severity is AnomalySeverity.CRITICAL
        assert report.should_reject is True

    def test_missing_controls_in_reading_fail_layer_two(self, detector):
        reading = InstrumentReading(
            experiment_id="EXP-QC2",
            compound_id="CMP-QC",
            target_id="7VH8_A",
            instrument_serial="SN-QC",
            timestamp=datetime.now(UTC),
            raw_value=0.65,
            standard_error=0.02,
            control_positive=None,
            control_negative=None,
            calibration_curve_hash="h",
            operator_id="op",
            approval_token="SIMULATED-abc",
            simulated=True,
        )
        report = detector.analyze_reading(reading)
        assert report.details["control_check"]["passed"] is False
