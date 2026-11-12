"""التحقق الذهبي — قيم مُحسوبة يدوياً لكل وحدة (docs/ryko/RYKO-MASTER-PLAN.md §6-1)."""

from __future__ import annotations

import math

import pytest

from pharma_sdl.ryko import get_engine


@pytest.fixture(scope="module")
def engine():
    return get_engine()


def approx(a: float, b: float, tol: float = 1e-9) -> bool:
    return math.isclose(a, b, rel_tol=tol, abs_tol=tol)


# ── U1 math ──


def test_convert_mass(engine):
    r = engine.compute("math", "convert", value=500, from_unit="mg", to_unit="g")
    assert approx(r.value, 0.5)


def test_convert_mass_to_mmol(engine):
    # 500 mg بمولية 150 g/mol ⇒ 3.3333 mmol
    r = engine.compute("math", "convert", value=500, from_unit="mg", to_unit="mmol",
                       molar_mass=150)
    assert approx(r.value, 500e-3 / 150 * 1e3)


def test_auc_trapz_hand_computed(engine):
    # Σ (C1+C2)/2·Δt = 9 + 6.5 + 7 = 22.5
    r = engine.compute("math", "auc_trapz", times=[0, 1, 2, 4], concs=[10, 8, 5, 2])
    assert approx(r.value, 22.5)


def test_auc_trapz_log_tail(engine):
    # الذيل الأخير: 5·2/ln(5/2) = 10.9137 — الإجمالي 9 + 6.5 + ذيل
    tail = 5 * 2 / math.log(5 / 2)
    r = engine.compute("math", "auc_trapz", times=[0, 1, 2, 4], concs=[10, 8, 5, 2],
                       log_tail=True)
    assert approx(r.value, 9 + 6.5 + tail)


def test_half_life_golden(engine):
    r = engine.compute("math", "half_life", ke=0.231)
    assert approx(r.value, math.log(2) / 0.231)
    assert approx(r.value, 3.0006, tol=1e-3)


def test_ke_roundtrip(engine):
    r = engine.compute("math", "ke_from_half_life", t_half_h=3.0006)
    assert approx(r.value, 0.231, tol=1e-3)


def test_clearance_and_vd(engine):
    cl = engine.compute("math", "clearance", dose_mg=100, auc=22.5)
    assert approx(cl.value, 100 / 22.5)
    vd = engine.compute("math", "volume_distribution", cl_l_h=cl.value, ke=0.231)
    assert approx(vd.value, (100 / 22.5) / 0.231)


def test_bioavailability_half(engine):
    r = engine.compute("math", "bioavailability", auc_po=22.5, auc_iv=45,
                       dose_po=100, dose_iv=100)
    assert approx(r.value, 0.5)


def test_ci95_of_constant(engine):
    r = engine.compute("math", "ci95_mean", values=[10, 10, 10])
    assert approx(r.extra["sd"], 0.0)
    assert approx(r.extra["ci95_lower"], 10.0)
    assert approx(r.extra["ci95_upper"], 10.0)


def test_linear_fit_perfect(engine):
    r = engine.compute("math", "linear_fit", xs=[1, 2, 3], ys=[3, 5, 7])
    assert approx(r.value, 2.0)
    assert approx(r.extra["intercept"], 1.0)
    assert approx(r.extra["r_squared"], 1.0)


# ── U2 physics ──


def test_binding_dg_one_micromolar(engine):
    # ΔG = 8.314462618 × 298.15 × ln(1e-6) J → kcal ⇒ −8.185
    r = engine.compute("physics", "binding_dg", kd_um=1.0, temp_c=25.0)
    assert approx(r.value, -8.185, tol=1e-3)


def test_dg_kd_roundtrip(engine):
    dg = engine.compute("physics", "binding_dg", kd_um=0.42, temp_c=37.0)
    kd = engine.compute("physics", "kd_from_dg", dg_kcal=dg.value, temp_c=37.0)
    assert approx(kd.value, 0.42, tol=1e-6)


def test_stokes_einstein_water(engine):
    # r=0.5nm، η=1mPa·s، 25°C ⇒ D≈4.37e-10 m²/s
    r = engine.compute("physics", "stokes_einstein", radius_nm=0.5,
                       viscosity_mpa_s=1.0, temp_c=25.0)
    assert approx(r.value, 4.367e-10, tol=1e-2)


def test_arrhenius_same_temperature(engine):
    r = engine.compute("physics", "arrhenius_ratio", ea_j_per_mol=50000,
                       temp1_c=25, temp2_c=25)
    assert approx(r.value, 1.0)


def test_arrhenius_warm_faster(engine):
    r = engine.compute("physics", "arrhenius_ratio", ea_j_per_mol=50000,
                       temp1_c=25, temp2_c=35)
    assert r.value > 1.0


def test_vant_hoff_thermoneutral(engine):
    r = engine.compute("physics", "vant_hoff_ratio", dh_j_per_mol=0,
                       temp1_c=25, temp2_c=40)
    assert approx(r.value, 1.0)


def test_fick_flux_linear(engine):
    r = engine.compute("physics", "fick_flux", diff_m2_s=1e-9, area_m2=1.0,
                       delta_c_mol_m3=1.0, thickness_m=1e-4)
    assert approx(r.value, 1e-5)


# ── U3 chem ──


def test_validate_smiles_canonical(engine):
    r = engine.compute("chem", "validate_smiles", smiles="C(C)O")
    assert r.value == "CCO"


def test_ethanol_descriptors(engine):
    r = engine.compute("chem", "descriptors", smiles="CCO")
    assert approx(r.extra["mw"], 46.07, tol=1e-2)
    assert -0.5 <= r.value <= 0.5  # cLogP إيثانول حول الصفر


def test_lipinski_aspirin_pass(engine):
    r = engine.compute("chem", "lipinski", smiles="CC(=O)Oc1ccccc1C(=O)O")
    assert r.value == "pass"
    assert r.extra["violations"] == []


def test_ionization_aspirin_stomach(engine):
    # حمض pKa=3.5 عند pH=1.5 ⇒ 1/(1+10^-2) ≈ 0.9901 غير متأين
    r = engine.compute("chem", "ionization_fraction", pka=3.5, ph=1.5, acid=True)
    assert approx(r.value, 0.9901, tol=1e-3)


def test_ionization_base_at_pka(engine):
    r = engine.compute("chem", "ionization_fraction", pka=9.0, ph=9.0, acid=False)
    assert approx(r.value, 0.5)


# ── U4 pharmaceutics ──


def test_higuchi_perfect_data(engine):
    r = engine.compute("pharmaceutics", "higuchi_k",
                       times_h=[1, 4, 9], amounts_released=[2, 4, 6])
    assert approx(r.value, 2.0)
    assert approx(r.extra["r_squared"], 1.0)


def test_korsmeyer_peppas_fickian(engine):
    # Q = 0.3·t^0.4 ⇒ k=0.3، n≈0.4 ≤ 0.45 ⇒ انتشار فِك (كل الأجزاء ≤1)
    r = engine.compute("pharmaceutics", "korsmeyer_peppas",
                       times_h=[1, 4, 9], fraction_released=[0.3, 0.5223, 0.7225])
    assert approx(r.value, 0.3, tol=1e-3)
    assert approx(r.extra["n"], 0.4, tol=1e-2)
    assert r.extra["interpretation"] == "fickian"


def test_dose_number_and_bcs(engine):
    d0 = engine.compute("pharmaceutics", "dose_number", dose_mg=500,
                        solubility_mg_ml=2.5)
    assert approx(d0.value, 0.8)
    assert engine.compute("pharmaceutics", "bcs_class",
                          dose_number=0.8, permeability_high=True).value == "I"
    assert engine.compute("pharmaceutics", "bcs_class",
                          dose_number=0.8, permeability_high=False).value == "III"
    assert engine.compute("pharmaceutics", "bcs_class",
                          dose_number=2.0, permeability_high=True).value == "II"
    assert engine.compute("pharmaceutics", "bcs_class",
                          dose_number=2.0, permeability_high=False).value == "IV"


def test_cockcroft_gault_golden(engine):
    # ((140-40)×70)/(72×1.0) = 97.222
    r = engine.compute("pharmaceutics", "cockcroft_gault", age_y=40, weight_kg=70,
                       scr_mg_dl=1.0, male=True)
    assert approx(r.value, 97.222, tol=1e-3)
    f = engine.compute("pharmaceutics", "cockcroft_gault", age_y=40, weight_kg=70,
                       scr_mg_dl=1.0, male=False)
    assert approx(f.value, 97.222 * 0.85, tol=1e-3)


def test_loading_and_maintenance(engine):
    ld = engine.compute("pharmaceutics", "loading_dose", vd_l=40, target_conc_mg_l=2)
    assert approx(ld.value, 80.0)
    md = engine.compute("pharmaceutics", "maintenance_rate", cl_l_h=5, css_mg_l=10)
    assert approx(md.value, 50.0)


def test_infusion_css(engine):
    r = engine.compute("pharmaceutics", "infusion_css", rate_mg_h=50, cl_l_h=5, ke=0.231)
    assert approx(r.value, 10.0)
    assert approx(r.extra["t95_h"], 4.32 * 3.0006, tol=1e-3)


def test_pediatric_dose(engine):
    r = engine.compute("pharmaceutics", "pediatric_dose", weight_kg=20, mg_per_kg=15)
    assert approx(r.value, 300.0)


def test_noyes_whitney(engine):
    r = engine.compute("pharmaceutics", "noyes_whitney_rate", diff_cm2_s=1e-5,
                       area_cm2=1.0, cs_minus_c_mg_ml=1.0, h_cm=0.01)
    assert approx(r.value, 1e-3)


# ── U5 pharma ──


def test_hill_at_ec50_is_half(engine):
    r = engine.compute("pharma", "hill_effect", conc=100, emax=80, ec50=100, hill_coeff=2)
    assert approx(r.value, 40.0)


def test_hill_ec50_roundtrip(engine):
    ec = engine.compute("pharma", "ec50_from_effect", effect=40, emax=80, conc=100,
                        hill_coeff=2)
    assert approx(ec.value, 100.0)


def test_therapeutic_index_and_csf(engine):
    ti = engine.compute("pharma", "therapeutic_index", td50=500, ed50=50)
    assert approx(ti.value, 10.0)
    csf = engine.compute("pharma", "certain_safety_factor", td1=1000, ed99=10)
    assert approx(csf.value, 100.0)


def test_cheng_prusoff(engine):
    # 100/(1+100/10) = 9.0909
    r = engine.compute("pharma", "cheng_prusoff_ki", ic50=100, ligand_nm=100, kd_nm=10)
    assert approx(r.value, 9.0909, tol=1e-3)


def test_cyp_kb_declared_entries(engine):
    r = engine.compute("pharma", "cyp_lookup", drug="ketoconazole")
    assert r.extra["roles"]["cyp3a4"] == "strong_inhibitor"
    r2 = engine.compute("pharma", "cyp_lookup", drug="Amoxicillin")
    assert r2.extra["roles"]["cyp"] == "no_major_cyp"


def test_ddd_kb_declared_values(engine):
    r = engine.compute("pharma", "ddd_lookup", drug="amoxicillin")
    assert r.extra["ddd"] == "1 g" and r.extra["atc"] == "J01CA04"
    r2 = engine.compute("pharma", "ddd_lookup", drug="paracetamol")
    assert r2.extra["ddd"] == "3 g"


# ── diagnostics (مرحلة 2 — بذرة) ──


def test_ppv_npv_golden(engine):
    # Se=Sp=0.9، π=0.1 ⇒ PPV=0.5، NPV=0.81/0.82
    r = engine.compute("diagnostics", "ppv_npv", sensitivity=0.9, specificity=0.9,
                       prevalence=0.1)
    assert approx(r.value, 0.5)
    assert approx(r.extra["npv"], 0.81 / 0.82)


def test_likelihood_ratios_golden(engine):
    r = engine.compute("diagnostics", "likelihood_ratios", sensitivity=0.9, specificity=0.9)
    assert approx(r.value, 9.0)
    assert approx(r.extra["lr_minus"], 1.0 / 9.0)


def test_post_test_probability_fagan(engine):
    # 0.1 → odds 1/9 ×9 = 1 → 0.5 — متسق مع PPV الذهبي
    r = engine.compute("diagnostics", "post_test_probability",
                       pre_test_prob=0.1, likelihood_ratio=9.0)
    assert approx(r.value, 0.5)


def test_kappa_perfect_agreement(engine):
    # a=45,b=5,c=5,d=45 ⇒ Po=0.9، Pe=0.5 ⇒ κ=0.8
    r = engine.compute("diagnostics", "kappa", a=45, b=5, c=5, d=45)
    assert approx(r.value, 0.8)
