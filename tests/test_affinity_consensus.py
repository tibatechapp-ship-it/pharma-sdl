"""اختبارات جسر الإجماع العلاجي — مصفوفة الأحكام الكاملة على consensus_row.

الوحدة كانت 0٪ تغطية في التقييم الشامل 2026-11-13 (17 عبارة — أسرع مكسب
قابل للقياس). هذه المصفوفة تقفل كل فروع الحكم الثلاثة وحدودهما وحالات
البيانات الناقصة، وتثبت أن الجسر واحد لا اثنان (re-export من core.docking).
"""

from __future__ import annotations

from core.docking import pic50_to_dg_kcal
from pharma_sdl.affinity import consensus


def _row(vina, pic50):
    return consensus.consensus_row(vina, pic50)


def test_reexports_single_bridge():
    """الوحدة تعيد استخدام جسر core.docking — لا جسر ثانٍ بجوار الأول."""
    assert consensus.pic50_to_dg_kcal is pic50_to_dg_kcal


def test_missing_vina_side_gives_no_verdict():
    dg = pic50_to_dg_kcal(8.0)
    row = _row(None, 8.0)
    assert row["vina_kcal"] is None
    assert row["dg_from_pic50"] == round(dg, 2)
    assert row["gap"] is None
    assert row["verdict_ar"] == "بيانات ناقصة — لا حكم"
    assert row["verdict_en"] == "insufficient data — no verdict"


def test_missing_pic50_side_gives_no_verdict():
    row = _row(-8.4, None)
    assert row["dg_from_pic50"] is None
    assert row["gap"] is None
    assert "ناقصة" in row["verdict_ar"]


def test_both_missing_gives_no_verdict():
    row = _row(None, None)
    assert row["vina_kcal"] is None
    assert row["dg_from_pic50"] is None
    assert row["gap"] is None


def test_close_gap_is_consistent():
    dg = pic50_to_dg_kcal(9.0)
    row = _row(round(dg - 1.0, 4), 9.0)
    assert row["verdict_en"] == "consistent"
    assert row["verdict_ar"] == "متسق"
    assert abs(row["gap"]) <= 2.0


def test_gap_of_exactly_two_is_still_consistent():
    dg = pic50_to_dg_kcal(7.0)
    row = _row(round(dg - 2.0, 4), 7.0)
    assert row["verdict_en"] == "consistent"


def test_moderate_gap_awaits_assay():
    dg = pic50_to_dg_kcal(7.0)
    row = _row(round(dg - 3.0, 4), 7.0)
    assert row["verdict_en"] == "acceptable, await assay"
    assert row["verdict_ar"] == "مقبول بانتظار القياس"


def test_gap_of_exactly_four_is_acceptable():
    dg = pic50_to_dg_kcal(7.0)
    row = _row(round(dg - 4.0, 4), 7.0)
    assert row["verdict_en"] == "acceptable, await assay"


def test_large_gap_requires_human_review():
    dg = pic50_to_dg_kcal(7.0)
    row = _row(round(dg - 5.0, 4), 7.0)
    assert row["verdict_en"] == "human review required"
    assert row["verdict_ar"] == "مراجعة بشرية مطلوبة"


def test_gap_is_judged_by_absolute_value_in_both_directions():
    """الفجوة تُحكَم بالمقدار المطلق — Vina أقوى أو أضعف من القياس سواء."""
    dg = pic50_to_dg_kcal(7.0)
    stronger = _row(round(dg + 5.0, 4), 7.0)
    weaker = _row(round(dg - 5.0, 4), 7.0)
    assert stronger["verdict_en"] == weaker["verdict_en"] == "human review required"
    assert stronger["gap"] > 0 and weaker["gap"] < 0


def test_values_rounded_to_two_decimals():
    row = _row(-8.41234444, 6.177)
    assert row["vina_kcal"] == -8.41
    assert row["dg_from_pic50"] == round(pic50_to_dg_kcal(6.177), 2)
    assert row["gap"] == round(-8.41234444 - pic50_to_dg_kcal(6.177), 2)
