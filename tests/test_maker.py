"""اختبارات MoleculeMaker."""
import pytest
try:
    from rdkit import Chem
    HAS_RDKIT = True
except ImportError:
    HAS_RDKIT = False
from core.maker import MoleculeMaker

def test_valid_smiles(maker):
    if not HAS_RDKIT:
        pytest.skip('rdkit not installed')
    for smi in maker.smiles_list:
        assert Chem.MolFromSmiles(smi) is not None


def test_feature_shape(maker):
    feats = maker.to_features()
    assert feats.shape[1] == 6
    assert feats.shape[0] == len(maker.mols)


def test_no_negative(maker):
    feats = maker.to_features()
    assert (feats >= 0).all()


def test_lipinski_acceptable(maker):
    feats = maker.to_features()
    violations = (
        (feats[:, 0] > 500) | (feats[:, 1] > 5)
        | (feats[:, 2] > 5) | (feats[:, 3] > 10)
    )
    assert violations.mean() < 0.5
