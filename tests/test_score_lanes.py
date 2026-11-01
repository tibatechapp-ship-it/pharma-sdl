"""اختبارات عقد الصدق — مسارات الدرجات الثلاثة + التحذير العلمي/الطبي.

التدقيق العلمي P0 (2026-11): التحذير يسافر مع البيانات (وليس في التوثيق فقط)،
وكل تقرير فرز يحمل أسطورة المسارات الثلاثة — لا «درجة موحدة» في أي مخرج.
"""

from __future__ import annotations

from pharma_sdl.curation.loader import load_ligands_csv
from pharma_sdl.models import ScreeningResult
from pharma_sdl.reporting.report import build_json, build_markdown
from pharma_sdl.scores import (
    DISCLAIMER_AR,
    DISCLAIMER_EN,
    SCORE_LANES,
    disclaimer_md,
    lanes_legend_md,
)
from pharma_sdl.screening.runner import run_screening

DEMO_CSV = "data/demo_ligands.csv"


# ── عقد المسارات الثلاثة ─────────────────────────────────────


def test_exactly_three_score_lanes():
    assert set(SCORE_LANES) == {"docking_score", "predicted_potency", "experimental_activity"}


def test_lanes_are_bilingual_and_bounded():
    for lane in SCORE_LANES.values():
        assert lane.label_ar and lane.label_en
        assert lane.nature_ar and lane.nature_en
        assert lane.limit_ar and lane.limit_en, "كل مسار يحمل حدود تفسيره الصريحة"
        assert lane.unit


def test_disclaimer_is_nontrivial_bilingual():
    for text in (DISCLAIMER_AR, DISCLAIMER_EN):
        assert len(text) > 200, "التحذير نص كامل لا سطر شكلي"
        assert "تنبيه علمي وطبي" in DISCLAIMER_AR
        assert "medical notice" in DISCLAIMER_EN


def test_markdown_helpers_render():
    legend = lanes_legend_md("ar")
    assert "درجة الالتحام" in legend and "النشاط التجريبي" in legend
    assert lanes_legend_md("en") != legend
    assert disclaimer_md("ar").startswith("> ⚠️")


# ── التحذير يسافر مع النتائج ────────────────────────────────


def test_screening_result_carries_disclaimer():
    result = run_screening("7VH8_A", load_ligands_csv(DEMO_CSV), engine_name="simulation")
    assert result.disclaimer_ar == DISCLAIMER_AR
    assert result.disclaimer_en == DISCLAIMER_EN
    # JSON كامل يحمل التحذير — أي مستهلك API يقبله مع البيانات
    assert DISCLAIMER_AR in build_json(result)


def test_report_markdown_contains_lanes_and_disclaimer():
    result = run_screening("7VH8_A", load_ligands_csv(DEMO_CSV), engine_name="simulation")
    md = build_markdown(result, lang="ar")
    assert "مسارات الدرجات" in md
    assert "درجة الالتحام" in md and "الفعالية المتنبأ بها" in md
    assert "تنبيه علمي وطبي" in md
    md_en = build_markdown(result, lang="en")
    assert "Score lanes" in md_en and "medical notice" in md_en


def test_default_result_instantiation_has_disclaimer():
    bare = ScreeningResult(
        run_id="x",
        target_id="7VH8_A",
        target_label_ar="م",
        target_label_en="M",
        engine_requested="simulation",
        engine_used="simulation",
    )
    assert bare.disclaimer_ar and bare.disclaimer_en
