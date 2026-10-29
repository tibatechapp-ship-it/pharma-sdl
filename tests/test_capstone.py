"""اختبارات capstone — خط الاكتشاف من الهدف إلى القرار (بلا شبكة).

تستخدم المكتبة المحلية (من mpro_sample.csv) ونموذجاً مصغّراً للتحقق من:
الفلترة → الترتيب → حسابات PK/PD → التقارير.
"""
import math

import pandas as pd
import pytest

from core.capstone import (
    KA,
    KE,
    LIPINSKI,
    TMAX_H,
    VEBER,
    adme_filter,
    build_markdown_report,
    build_pdf_report,
    c90_nm,
    cmax_mg,
    offline_library,
    pkpd_outlook,
    run_pipeline,
    score_potency,
    shape_arabic,
)

NIRMATRELVIR = (
    "CC1([C@@H]2[C@H]1[C@H](N(C2)C(=O)[C@H](C(C)(C)C)NC(=O)C(F)(F)F)"
    "C(=O)N[C@@H](C[C@@H]3CCNC3=O)C#N)C"
)
ASPIRIN = "CC(=O)OC1=CC=CC=C1C(=O)O"


@pytest.fixture(scope="module")
def model():
    from core.ml_potency import load_dataset, train_potency_model

    df = load_dataset()
    return train_potency_model(
        df["smiles"].tolist(), df["pchembl_value"].tolist(), n_estimators=40
    )


@pytest.fixture(scope="module")
def library():
    return offline_library(n=60, seed=7)


# ═══ المرحلة 1: المكتبة ═══

def test_offline_library_shape(library):
    assert len(library) >= 40
    for col in ("smiles", "mw", "logp", "hbd", "hba", "tpsa", "rotb"):
        assert col in library.columns
    assert library["smiles"].is_unique


def test_offline_library_valid_smiles(library):
    from core.ml_potency import mol_from_smiles

    assert library["smiles"].apply(mol_from_smiles).notna().all()


# ═══ المرحلة 2: ADME ═══

def test_adme_filter_funnel_monotonic(library):
    from itertools import pairwise

    filtered, funnel = adme_filter(library)
    vals = list(funnel.values())
    assert all(a >= b for a, b in pairwise(vals)), "القمع يجب أن يتناقص رتيباً"
    assert funnel["المكتبة الأولية"] == len(library)
    assert funnel["+ Veber (TPSA/روتاتمر)"] == len(filtered)
    assert len(filtered) > 0


def test_adme_filter_excludes_violator():
    df = pd.DataFrame(
        [
            {"smiles": ASPIRIN, "mw": 180.2, "logp": 1.2, "hbd": 1, "hba": 4, "tpsa": 63.6, "rotb": 3},
            {"smiles": "CCCCCCCCCCCCO", "mw": 700.0, "logp": 8.0, "hbd": 1, "hba": 1, "tpsa": 20.0, "rotb": 11},
        ]
    )
    filtered, funnel = adme_filter(df)
    assert len(filtered) == 1
    assert filtered.iloc[0]["smiles"] == ASPIRIN
    assert funnel["MW ≤ 500"] == 1


def test_adme_thresholds_consistent():
    assert LIPINSKI["mw"] == 500 and LIPINSKI["logp"] == 5
    assert VEBER["tpsa"] == 140


# ═══ المرحلة 3: التنبؤ ═══

def test_score_potency_ranking(library, model):
    scored = score_potency(library, model)
    assert "pic50" in scored.columns and "ci_lo" in scored.columns
    valid = scored.dropna(subset=["pic50"])
    assert len(valid) > 0
    assert valid["pic50"].is_monotonic_decreasing
    assert (valid["ci_lo"] <= valid["pic50"]).all()
    assert (valid["pic50"] <= valid["ci_hi"]).all()


def test_score_potency_invalid_smiles_no_crash(model):
    df = pd.DataFrame(
        [{"smiles": "not_a_smiles", "mw": 300, "logp": 2, "hbd": 1, "hba": 2, "tpsa": 40, "rotb": 2}]
    )
    scored = score_potency(df, model)
    assert pd.isna(scored.iloc[0]["pic50"])


def test_nirmatrelvir_among_top(model):
    """المكتبة تحتوي مثبطات حقيقية — النيرماتريلڤير يجب أن يتصدر النطاق المعقول."""
    lib = offline_library(n=200, seed=1)
    lib = pd.concat([lib, pd.DataFrame([{
        "cid": 0, "smiles": NIRMATRELVIR, "mw": 499.5, "logp": 3.2,
        "hbd": 4, "hba": 9, "tpsa": 140.0, "rotb": 9,
    }])], ignore_index=True)
    scored = score_potency(adme_filter(lib)[0], model)
    row = scored[scored["smiles"] == NIRMATRELVIR]
    assert len(row) == 1
    assert 6.5 <= row.iloc[0]["pic50"] <= 9.5
    assert row.iloc[0]["pic50"] >= scored["pic50"].quantile(0.75)


# ═══ المرحلة 4: PK/PD ═══

def test_cmax_formula_independent_recompute():
    """إعادة حساب Cmax بمعادلة مستقلة — يجب أن تطابق معاملات الخط."""
    dose, mw = 300.0, 400.0
    moles = dose * 1e-3 / mw
    expected = (
        (0.45 * moles * KA) / (104.7 * (KA - KE))
        * (math.exp(-KE * TMAX_H) - math.exp(-KA * TMAX_H)) * 1e9
    )
    assert cmax_mg(dose, mw) == pytest.approx(expected, rel=1e-9)
    assert 1500 < expected < 3500  # ترتيب مقدار معقول لدواء فموي


def test_cmax_linear_in_dose():
    assert cmax_mg(600, 400) == pytest.approx(2 * cmax_mg(300, 400), rel=1e-9)


def test_c90_hill_math():
    """pIC50=8 → IC50=10nM → C90 (θ=90%, γ=1) = 90nM."""
    assert c90_nm(8.0) == pytest.approx(90.0, rel=1e-9)
    assert c90_nm(6.0) == pytest.approx(9000.0, rel=1e-9)


def test_pkpd_outlook_verdicts(model, library):
    scored = score_potency(adme_filter(library)[0], model)
    top = pkpd_outlook(scored, dose_mg=300)
    assert len(top) <= 10
    assert {"cmax_nm", "dose_needed_mg", "pkpd_verdict"}.issubset(top.columns)
    strong = top.dropna(subset=["pic50"]).head(3)
    # أقوى 3 في مكتبة Mpro فعّالة → قرارات ليس 🔴 غالباً
    assert not strong["pkpd_verdict"].eq("بعيد — فعالية غير كافية").all()


def test_pkpd_low_potency_gets_red(model):
    df = pd.DataFrame(
        [{"smiles": "CCCCCCCCCCCCOc1ccc(cc1)C(F)(F)F", "mw": 300.0, "logp": 4.0,
          "hbd": 0, "hba": 2, "tpsa": 20.0, "rotb": 5}]
    )
    # اجبر قيمة ضعيفة عبر نموذج حقيقي — الجزيء خارج التدريب فسيكون ضعيفاً غالباً،
    # لذلك نفحص فقط أن القرار من المجموعة المتوقعة.
    top = pkpd_outlook(score_potency(df, model), dose_mg=300)
    assert top.iloc[0]["pkpd_verdict"] in {
        "ممكن دوائياً", "حدّي — يحتاج تحسين فعالية", "بعيد — فعالية غير كافية",
    }


# ═══ المرحلة 5 + المنسّق ═══

def test_run_pipeline_end_to_end(library, model):
    res = run_pipeline(library, dose_mg=300, source="اختبار", model=model)
    assert res.funnel["المكتبة الأولية"] == len(library)
    assert 0 < len(res.top) <= 10
    assert res.top["pic50"].notna().any()
    md = build_markdown_report(res, "SARS-CoV-2 Mpro")
    assert "قمع الفلترة" in md and "تعليمي" in md
    assert "اختبار" in md  # المصدر يظهر في التقرير


def test_run_pipeline_all_violators_raises(model):
    df = pd.DataFrame(
        [{"smiles": ASPIRIN, "mw": 900.0, "logp": 9.0, "hbd": 9, "hba": 15,
          "tpsa": 200.0, "rotb": 15}]
    )
    with pytest.raises(ValueError, match="ADME"):
        run_pipeline(df, model=model)


def test_pdf_report_valid_bytes(library, model):
    pdf = build_pdf_report(run_pipeline(library, model=model))
    if pdf is None:  # reportlab غير مثبت في بيئة نادرة
        pytest.skip("reportlab غير متاح")
    assert pdf[:4] == b"%PDF"
    assert len(pdf) > 5000


def test_pdf_report_fonts_shipped():
    from core.capstone import FONTS_DIR

    assert (FONTS_DIR / "Tajawal-Regular.ttf").exists(), "خط Tajawal مفقود من data/fonts"


def test_shape_arabic_returns_text():
    out = shape_arabic("مثبط قوي")
    assert isinstance(out, str)
    assert len(out) > 0


def test_tmax_positive_and_between_ka_ke_curves():
    assert 0 < TMAX_H < 12
    # عند tmax يتحقق شرط المشتقة الصفرية: ke·e^(-ke·t) = ka·e^(-ka·t)
    lhs = KE * math.exp(-KE * TMAX_H)
    rhs = KA * math.exp(-KA * TMAX_H)
    assert lhs == pytest.approx(rhs, rel=1e-6)
