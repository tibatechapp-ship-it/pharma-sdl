"""اختبارات طبقة الكيمياء — التوحيد والواصفات وفلاتر الأمان."""

from __future__ import annotations

from rdkit import Chem

from pharma_sdl.chemistry.filters import (
    detect_warheads,
    lipinski_flags,
    pains_alerts,
    sa_score,
    veber_flags,
)
from pharma_sdl.chemistry.molecules import canonicalize, largest_fragment, parse_smiles

ASPIRIN = "CC(=O)Oc1ccccc1C(=O)O"
CAFFEINE = "Cn1cnc2c1c(=O)n(C)c(=O)n2C"
NIRMATRELVIR = (
    "CC1(C2C1C(N(C2)C(=O)C(C(C)(C)C)NC(=O)C(F)(F)F)"
    "C(=O)NC(CC3CCNC3=O)C#N)C"
)


def test_canonicalize_aspirin_descriptors():
    rec = canonicalize(ASPIRIN)
    assert abs(rec.mol_weight - 180.16) < 0.2
    assert rec.inchikey and rec.inchikey.startswith("BSYNRY")  # InChIKey الأسبرين
    assert rec.heavy_atoms == 13


def test_salt_stripping_largest_fragment():
    rec = canonicalize("[Na+].[O-]C(=O)c1ccccc1")  # بنزوات الصوديوم
    assert rec.mol_weight < 130  # الصوديوم زال — بقي حمض البنزويك/أيونه
    assert rec.heavy_atoms == 9  # 6C حلقة + 1C كربوكسيل + 2O
    mol = largest_fragment(parse_smiles("[Na+].[O-]C(=O)c1ccccc1"))
    assert "Na" not in Chem.MolToSmiles(mol)


def test_invalid_smiles_raises():
    import pytest

    from pharma_sdl.chemistry.molecules import InvalidSmiles

    with pytest.raises(InvalidSmiles):
        parse_smiles("this-is-not-smiles")


def test_warhead_detection_hard_and_nitrile():
    acrylamide = parse_smiles("C=CC(=O)Nc1ccccc1")
    names = {w.name for w in detect_warheads(acrylamide)}
    assert "acrylamide" in names

    nir = parse_smiles(NIRMATRELVIR)
    nir_names = {w.name for w in detect_warheads(nir)}
    assert "nitrile" in nir_names  # رأس نيرماتريلڤير التساهمي

    caffeine = parse_smiles(CAFFEINE)
    assert detect_warheads(caffeine) == []


def test_pains_alerts_rhodanine_and_catechol():
    # رودانين عطري (PAINS ene_rhod) + كاتيكول (PAINS catechol)
    aryl_rhodanine = parse_smiles("O=C1NC(=S)SC1=C1C=CC=CC=C1")
    assert pains_alerts(aryl_rhodanine), "PAINS يجب أن يصطاد الرودانين العطري"
    assert pains_alerts(parse_smiles("Oc1ccccc1O")), "PAINS يجب أن يصطاد الكاتيكول"
    assert pains_alerts(parse_smiles(CAFFEINE)) == []


def test_sa_score_graceful():
    value = sa_score(parse_smiles(ASPIRIN))
    assert value is None or (0.0 <= value <= 10.0)  # صدق: إما متاح وإلا None


def test_lipinski_and_veber_flags():
    behenic = canonicalize("CCCCCCCCCCCCCCCCCCCC(=O)O")  # حمض بيهينيك C22
    assert "LogP>5" in lipinski_flags(behenic)
    caffeine_rec = canonicalize(CAFFEINE)
    assert lipinski_flags(caffeine_rec) == []
    assert veber_flags(caffeine_rec) == []
