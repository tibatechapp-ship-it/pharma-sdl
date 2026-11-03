"""اختبارات كتلة الوصف الفيزيوكيميائي — P11 (حتمية، محلية، بلا شبكة)."""
import numpy as np
import pytest

from core.physchem import DESCRIPTOR_NAMES, physchem_matrix, physchem_vector

ASPIRIN = "CC(=O)OC1=CC=CC=C1C(=O)O"
NIRMATRELVIR = (
    "CC1([C@@H]2[C@H]1[C@H](N(C2)C(=O)[C@H](C(C)(C)C)NC(=O)C(F)(F)F)"
    "C(=O)N[C@@H](C[C@@H]3CCNC3=O)C#N)C"
)
BAD_SMILES = "this_is_not_a_smiles"


def test_descriptor_names_contract():
    """ترتيب الأعمدة عقد ثابت — 20 عموداً بأسماء فريدة."""
    assert len(DESCRIPTOR_NAMES) == 20
    assert len(set(DESCRIPTOR_NAMES)) == 20
    assert all(isinstance(n, str) and n for n in DESCRIPTOR_NAMES)


def test_aspirin_known_values():
    """قيم مرجعية معروفة للأسبرين (MW/logP/TPSA) — تحقق فيزيائي."""
    d = dict(zip(DESCRIPTOR_NAMES, physchem_vector(ASPIRIN)))
    assert abs(d["mol_wt"] - 180.16) < 0.5
    assert abs(d["exact_mol_wt"] - 180.042) < 0.1
    assert abs(d["crippen_logp"] - 1.31) < 0.15
    assert abs(d["tpsa"] - 63.6) < 2.0
    assert d["h_donors"] == 1
    assert d["formal_charge"] == 0
    assert 0 < d["aromatic_proportion"] <= 1.0


def test_vector_shape_dtype_finite():
    v = physchem_vector(NIRMATRELVIR)
    assert v is not None
    assert v.shape == (20,)
    assert v.dtype == np.float64
    assert np.isfinite(v).all()


def test_determinism():
    """نفس الجزيء → نفس المتجه حرفياً (لا عشوائية في الوصف)."""
    a = physchem_vector(NIRMATRELVIR)
    b = physchem_vector(NIRMATRELVIR)
    assert a is not None and b is not None
    assert np.array_equal(a, b)


def test_invalid_returns_none():
    assert physchem_vector(BAD_SMILES) is None
    assert physchem_vector("") is None
    assert physchem_vector(None) is None  # type: ignore[arg-type]


def test_matrix_drops_invalid_and_keeps_index():
    X, idx = physchem_matrix([ASPIRIN, BAD_SMILES, NIRMATRELVIR])
    assert X.shape == (2, 20)
    assert idx == [0, 2]


def test_matrix_empty():
    X, idx = physchem_matrix([BAD_SMILES])
    assert X.shape == (0, 20)
    assert idx == []
