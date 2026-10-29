"""اختبارات واجهة المستخدم عبر streamlit.testing (Hardening P1-3 + S5).

الفلسفة: الواجهة جزء من العقد — 13 تبويباً تعمل بلا استثناء، مبدّل اللغة
يبدّل فعلاً، والأزرار الحية تستجيب. الاختبارات سريعة افتراضياً؛ الربط
الحقيقي بـVina موسوم slow، وCPIC الحي موسوم integration (نفس أمر الجناح:
pytest -m "not integration and not slow").
"""
from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parent.parent / "app.py"
PGX_OFFLINE = "📚 مدمج فوري (بلا شبكة)"
PGX_LIVE = "🌐 CPIC حي (كاش 24 ساعة)"


@pytest.fixture(scope="module")
def at():
    """تطبيق واحد لكل وحدة — كل تفاعل يعيد تشغيل السكربت (جلسة متصلة)."""
    at = AppTest.from_file(str(APP), default_timeout=300)
    at.run()
    return at


# ── الإقلاع والبنية ──────────────────────────────────────────


def test_boot_without_exception(at):
    assert not at.exception, f"boot exception: {at.exception}"


def test_thirteen_tabs(at):
    assert len(at.tabs) == 13


def test_sidebar_language_switcher_defaults_to_arabic(at):
    sel = at.selectbox(key="lang")
    assert sel is not None
    assert sel.value == "العربية"


def test_no_stlite_banner_in_full_runtime(at):
    """البيئة الكاملة لا تعرض لافتة stlite."""
    banners = [w.value for w in at.warning if "stlite" in w.value.lower()]
    assert not banners


# ── التدويل ──────────────────────────────────────────────────


def test_language_switch_roundtrip(at):
    title_ar = at.title[0].value
    at.selectbox(key="lang").set_value("English").run()
    assert not at.exception
    title_en = at.title[0].value
    assert title_en != title_ar
    tabs_en = [tb.label for tb in at.tabs]
    assert any("Docking" in lb for lb in tabs_en)
    assert any("PGx" in lb for lb in tabs_en)
    assert any("ADMET" in lb for lb in tabs_en)
    at.selectbox(key="lang").set_value("العربية").run()
    assert not at.exception
    assert at.title[0].value == title_ar


# ── تفاعلات التبويبات السريعة ────────────────────────────────


def test_make_button_interaction(at):
    at.button(key="make_btn").click().run()
    assert not at.exception


def test_predict_button_interaction(at):
    at.button(key="pred_btn").click().run()
    assert not at.exception


def test_pgx_widgets_offline_default_and_gene_switch(at):
    assert at.selectbox(key="pgx_gene") is not None
    radio = at.radio(key="pgx_src")
    assert radio.value == PGX_OFFLINE
    at.selectbox(key="pgx_gene").set_value("TPMT").run()
    assert not at.exception


def test_ml_comparison_button(at):
    """زر المقارنة ينتج تقارير صالحة تُخزَّن في الجلسة (بلا استثناء)."""
    at.button(key="mlcmp_btn").click().run()
    assert not at.exception
    reports = at.session_state["mlcmp"]
    assert reports is not None and len(reports) == 2
    names = {r.name for r in reports}
    assert names == {"RandomForest", "GradientBoosting"}


def test_admet_tab_widgets_and_fallback(at):
    """تبويب ADMET: قائمة النموذجين موجودة، وزر التنبؤ بلا خادم يعرض
    المرجعية التعليمية المدمجة ولا يرمي استثناءً (فشل شبكة ≠ انهيار)."""
    sel = at.selectbox(key="admet_model")
    assert sel is not None
    assert "CardioToxNet" in sel.value
    ta = at.text_area(key="admet_input")
    assert "CC(=O)OC1=CC=CC=C1C(=O)O" in ta.value  # أسبرين في الأمثلة
    at.button(key="admet_btn").click().run()
    assert not at.exception
    # بلا خادم Ersilia → لافتة «لا ردّ من الخادم» والمرجعية المدمجة
    infos = [w.value for w in at.info]
    assert any("Ersilia" in v for v in infos)


# ── تفاعلات ثقيلة (موسومة) ──────────────────────────────────


@pytest.mark.slow
def test_docking_real_vina_interaction(at):
    at.select_slider(key="dock_exh").set_value(4).run()
    at.button(key="dock_btn").click().run()
    assert not at.exception
    res = at.session_state["dock_res"]
    assert res is not None, "docking result missing"
    assert -15.0 < res.best < 0.0, f"implausible ΔG: {res.best}"
    # زرا Docking (PDB + PDBQT) — زرا Capstone يظهران فقط إن شُغّل قبله
    assert len(at.get("download_button")) >= 2


@pytest.mark.integration
def test_pgx_live_cpic_source(at):
    at.radio(key="pgx_src").set_value(PGX_LIVE).run()
    assert not at.exception
    at.radio(key="pgx_src").set_value(PGX_OFFLINE).run()
    assert not at.exception
