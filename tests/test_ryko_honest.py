"""التدهور الصادق — كل حد نطاق = رفض مُعلَّل ثنائي اللغة (لا صمت ولا رقم مُختلق)."""

from __future__ import annotations

import pytest

from pharma_sdl.ryko import get_engine
from pharma_sdl.ryko.errors import RykoInputError, RykoUnknownOpError


@pytest.fixture(scope="module")
def engine():
    return get_engine()


def _assert_bilingual(exc):
    """الرفض يحمل سببه بالعربية والإنجليزية — عقد الرسائل."""
    assert exc.ar.strip() and exc.en.strip()
    assert " | " in str(exc)


def test_half_life_rejects_zero_ke(engine):
    with pytest.raises(RykoInputError) as e:
        engine.compute("math", "half_life", ke=0)
    _assert_bilingual(e.value)


def test_half_life_rejects_negative_ke(engine):
    with pytest.raises(RykoInputError) as e:
        engine.compute("math", "half_life", ke=-0.5)
    _assert_bilingual(e.value)


def test_auc_rejects_unsorted_times(engine):
    with pytest.raises(RykoInputError) as e:
        engine.compute("math", "auc_trapz", times=[0, 2, 1], concs=[1, 2, 3])
    _assert_bilingual(e.value)


def test_bioavailability_rejects_impossible_f(engine):
    # AUCpo > AUCiv بجرعتين متساويتين ⇒ F>1 — مستحيل فيزيولوجياً
    with pytest.raises(RykoInputError) as e:
        engine.compute("math", "bioavailability", auc_po=100, auc_iv=50,
                       dose_po=10, dose_iv=10)
    _assert_bilingual(e.value)


def test_convert_rejects_cross_family(engine):
    with pytest.raises(RykoInputError) as e:
        engine.compute("math", "convert", value=1, from_unit="mg", to_unit="mL")
    _assert_bilingual(e.value)


def test_binding_dg_rejects_zero_kd(engine):
    with pytest.raises(RykoInputError) as e:
        engine.compute("physics", "binding_dg", kd_um=0)
    _assert_bilingual(e.value)


def test_binding_dg_rejects_below_absolute_zero(engine):
    with pytest.raises(RykoInputError) as e:
        engine.compute("physics", "binding_dg", kd_um=1.0, temp_c=-300)
    _assert_bilingual(e.value)


def test_stokes_rejects_zero_radius(engine):
    with pytest.raises(RykoInputError) as e:
        engine.compute("physics", "stokes_einstein", radius_nm=0)
    _assert_bilingual(e.value)


def test_chem_rejects_invalid_smiles(engine):
    with pytest.raises(RykoInputError) as e:
        engine.compute("chem", "validate_smiles", smiles="not-a-molecule")
    _assert_bilingual(e.value)


def test_chem_rejects_empty_smiles(engine):
    with pytest.raises(RykoInputError) as e:
        engine.compute("chem", "validate_smiles", smiles="")
    _assert_bilingual(e.value)


def test_ionization_rejects_pka_out_of_range(engine):
    with pytest.raises(RykoInputError) as e:
        engine.compute("chem", "ionization_fraction", pka=15, ph=7, acid=True)
    _assert_bilingual(e.value)


def test_korsmeyer_rejects_percentages(engine):
    # الأجزاء يجب أن تكون 0–1 لا نسباً مئوية
    with pytest.raises(RykoInputError) as e:
        engine.compute("pharmaceutics", "korsmeyer_peppas",
                       times_h=[1, 2], fraction_released=[50, 80])
    _assert_bilingual(e.value)


def test_cockcroft_gault_rejects_impossible_age(engine):
    with pytest.raises(RykoInputError) as e:
        engine.compute("pharmaceutics", "cockcroft_gault", age_y=150, weight_kg=70,
                       scr_mg_dl=1.0, male=True)
    _assert_bilingual(e.value)


def test_loading_dose_rejects_f_above_one(engine):
    with pytest.raises(RykoInputError) as e:
        engine.compute("pharmaceutics", "loading_dose", vd_l=40,
                       target_conc_mg_l=2, bioavailability_f=1.5)
    _assert_bilingual(e.value)


def test_hill_ec50_requires_below_emax(engine):
    with pytest.raises(RykoInputError) as e:
        engine.compute("pharma", "ec50_from_effect", effect=80, emax=80, conc=100)
    _assert_bilingual(e.value)


def test_hill_rejects_zero_ec50(engine):
    with pytest.raises(RykoInputError) as e:
        engine.compute("pharma", "hill_effect", conc=10, emax=100, ec50=0)
    _assert_bilingual(e.value)


def test_cyp_kb_rejects_unknown_honestly(engine):
    # ما ليس في القاعدة المعلنة يُرفض — لا استنتاج ولا اكتمال زائف
    with pytest.raises(RykoUnknownOpError) as e:
        engine.compute("pharma", "cyp_lookup", drug="unschedulable-drug-xyz")
    _assert_bilingual(e.value)


def test_ddd_kb_rejects_unknown_honestly(engine):
    with pytest.raises(RykoUnknownOpError) as e:
        engine.compute("pharma", "ddd_lookup", drug="unknown-drug-xyz")
    _assert_bilingual(e.value)


def test_diagnostics_rejects_probability_above_one(engine):
    with pytest.raises(RykoInputError) as e:
        engine.compute("diagnostics", "ppv_npv", sensitivity=1.5, specificity=0.9,
                       prevalence=0.1)
    _assert_bilingual(e.value)


def test_post_test_rejects_boundary_probability(engine):
    with pytest.raises(RykoInputError) as e:
        engine.compute("diagnostics", "post_test_probability",
                       pre_test_prob=1.0, likelihood_ratio=9)
    _assert_bilingual(e.value)


def test_likelihood_ratios_rejects_specificity_one(engine):
    with pytest.raises(RykoInputError) as e:
        engine.compute("diagnostics", "likelihood_ratios", sensitivity=0.9, specificity=1.0)
    _assert_bilingual(e.value)


def test_kappa_rejects_empty_table(engine):
    with pytest.raises(RykoInputError) as e:
        engine.compute("diagnostics", "kappa", a=0, b=0, c=0, d=0)
    _assert_bilingual(e.value)
