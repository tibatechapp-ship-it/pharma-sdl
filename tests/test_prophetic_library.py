"""اختبارات مكتبة الطب النبوي — حزمة P5: جزيئات مُدقَّقة وتوثيق صادق."""

from __future__ import annotations

import numpy as np
import pytest
from rdkit import Chem
from rdkit.Chem.rdMolDescriptors import CalcMolFormula

from pharma_sdl.prophetic import (
    COMPOUNDS,
    EVIDENCE_TIERS,
    HADITH_GRADES,
    PROCEDURES,
    SOURCE_NOTES,
    TIER_LABELS,
    library_summary,
    run_library_screen,
)

SOURCES = {"العسل", "حبة البركة", "الشعير"}


# ── الجزيئات ──


@pytest.mark.parametrize("compound", COMPOUNDS, ids=lambda c: c.name_en)
def test_compound_smiles_parses_and_formula_matches_rdkit(compound):
    """كل جزيء يُحلَّل في RDKit وصيغته المحسوبة تطابق الموثقة حرفياً."""
    mol = Chem.MolFromSmiles(compound.smiles)
    assert mol is not None, f"SMILES غير قابل للتحليل: {compound.name_en}"
    assert CalcMolFormula(mol) == compound.formula, compound.name_en
    assert compound.molecular_weight > 0


def test_unique_smiles_across_library():
    """لا تكرار جزيئي — كل مركب بجزيء واحد لا أكثر."""
    smiles = [c.smiles for c in COMPOUNDS]
    assert len(smiles) == len(set(smiles))


def test_compounds_cover_the_three_sources():
    """المواد الثلاث في النص مغطاة: العسل + حبة البركة + الشعير."""
    assert {c.source for c in COMPOUNDS} == SOURCES
    assert len(COMPOUNDS) == 17  # 9 عسل + 6 حبة البركة + 2 شعير


# ── التوثيق التراثي ──


def test_hadith_docs_graded_and_referenced():
    """كل توثيق تراثي بدرجة مقبولة ومرجع متخَرَّج وراوي — لا استثناء."""
    docs = [c.source_hadith for c in COMPOUNDS] + [p.hadith for p in PROCEDURES]
    assert docs, "لا مكتبة بلا توثيق"
    for d in docs:
        assert d.grade in HADITH_GRADES, d.reference
        assert any(
            k in d.reference for k in ("البخاري", "مسلم", "قرآن")
        ), f"مرجع غير متخَرَّج: {d.reference}"
        assert d.text_ar.strip() and d.narrator.strip()


def test_no_unsupported_grade_claims():
    """الصدق المنهجي: الدرجة المتفق عليه — لا ادعاء متواتر بلا تحقيق."""
    assert all(c.source_hadith.grade == "متفق عليه" for c in COMPOUNDS)


def test_procedures_have_no_molecules_and_stay_out_of_computational_path():
    """الإجراءات بلا جزيء — لا تُفرَز حاسوبياً بنيوياً."""
    assert len(PROCEDURES) == 2  # الحجامة + الكاي
    for p in PROCEDURES:
        assert "حاسوبي" in p.computational_note
        assert p.evidence_tier in EVIDENCE_TIERS


# ── الدليل الحديث ──


def test_evidence_tiers_valid_and_labeled():
    """كل مادة بطبقة دليل صحيحة وعلامة عربية مقابلة ومرجع منشور."""
    for c in COMPOUNDS:
        assert c.evidence_tier in EVIDENCE_TIERS
        assert c.evidence_tier in TIER_LABELS
        assert len(c.evidence_note) > 20
    # الثيموكينون أعلى طبقة في المكتبة (قبل سريري) — لا تضخيم لسريري
    tq = next(c for c in COMPOUNDS if c.name_en == "thymoquinone")
    assert tq.evidence_tier == "T2_preclinical"


def test_barley_polymer_documented_not_featurized():
    """بيتا جلوكان بوليمر — موثق في ملاحظات المصادر لا في المكتبة الجزيئية."""
    assert "الشعير" in SOURCE_NOTES
    assert "بيتا جلوكان" in SOURCE_NOTES["الشعير"]
    assert all("glucan" not in c.name_en for c in COMPOUNDS)


# ── الإخلاءات ──


def test_summary_counts_and_disclaimers():
    """الملخص بأعداد صادقة وإخلاء مزدوج (عربي/إنجليزي)."""
    s = library_summary()
    assert s["n_compounds"] == 17
    assert s["n_procedures"] == 2
    assert s["by_source"] == {"العسل": 9, "حبة البركة": 6, "الشعير": 2}
    assert "ليس دليلاً على فعالية" in s["disclaimer_ar"]
    assert "not clinical-efficacy" in s["disclaimer_en"]


# ── الفرز الحاسوبي ──


def test_screen_lane_discipline_and_unvalidated():
    """كل صف في خط predicted_potency وUNVALIDATED — بلا درجة تحاليم."""
    report = run_library_screen(n_estimators=50, seed=0)
    assert report.lane == "predicted_potency"
    assert report.n_compounds == 17
    assert len(report.rows) == 17
    for row in report.rows:
        assert row.lane == "predicted_potency"
        assert row.validation_state == "UNVALIDATED"
        assert 0.0 <= row.predicted_pic50 <= 15.0  # نطاق pIC50 معقول
        assert row.tree_std >= 0.0
    # مرتبة تنازلياً حسب التنبؤ
    preds = [r.predicted_pic50 for r in report.rows]
    assert preds == sorted(preds, reverse=True)


def test_screen_is_seed_deterministic():
    """نفس البذرة → نفس التقرير بايت-ببايت (عقد الحتمية)."""
    a = run_library_screen(n_estimators=40, seed=7)
    b = run_library_screen(n_estimators=40, seed=7)
    assert a.rows == b.rows
    assert a.dataset_fingerprint == b.dataset_fingerprint


def test_screen_featurizer_parity_with_production():
    """التمثيل نفسه موافق حرفياً لمواصفات الإنتاج — اختبار تقاطعي."""
    from pharma_sdl.active_learning import featurize as prod_featurize
    from pharma_sdl.prophetic import COMPOUNDS as C

    X, idx = prod_featurize([c.smiles for c in C])
    assert X.shape[0] == len(C) == 17  # كل المكتبة قابلة للتمثيل
    assert X.shape[1] == 2048  # Morgan radius=2, 2048 bit — نفس عقد الإنتاج
    assert idx == list(range(len(C)))


def test_screen_no_featurization_loss():
    """كل مركبات المكتبة تُمثَّل — لا مركب يفقد بلا اكتشاف."""
    X, idx = run_library_screen.__globals__["featurize"](
        [c.smiles for c in COMPOUNDS]
    )
    assert len(idx) == len(COMPOUNDS)
    assert np.isfinite(X).all()
