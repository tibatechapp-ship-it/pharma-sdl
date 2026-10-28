"""اختبارات MoleculeMaker."""
import pytest

try:
    from rdkit import Chem
    RDKIT_AVAILABLE = True
except ImportError:
    RDKIT_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not RDKIT_AVAILABLE,
    reason="rdkit not installed (Termux) — will run on CI"
)

from core.maker import MoleculeMaker


def test_valid_smiles(maker):
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
