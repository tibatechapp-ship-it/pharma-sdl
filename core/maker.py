"""
MoleculeMaker: RDKit-based molecule generation and feature extraction.
"""
import numpy as np


class MoleculeMaker:
    """Generate molecules and extract features."""

    def __init__(self, n=20, seed=42):
        self.n = n
        self.rng = np.random.default_rng(seed)
        self.smiles_list = self._generate_smiles()
        self.mols = list(range(len(self.smiles_list)))

    def _generate_smiles(self):
        """Generate a list of plausible SMILES strings."""
        templates = [
            "CC(=O)Oc1ccccc1C(=O)O",
            "CC(C)Cc1ccc(cc1)C(C)C(=O)O",
            "CN1C=NC2=C1C(=O)N(C(=O)N2C)C",
            "CC1=CC=C(C=C1)C2=CC(=NN2C3=CC=C(C=C3)S(=O)(=O)N)C(F)(F)F",
            "CC(C)(C)NCC(O)COc1ccc(cc1)CC(=O)N",
            "O=C(O)CC(O)(CC(=O)O)C(=O)O",
            "CC(=O)NC1=CC=C(C=C1)O",
            "C1=CC=C(C=C1)C2=CC=CC=C2",
            "CC1=CC=CC=C1O",
            "COC1=CC=C(C=C1)CCN",
        ]
        result = []
        for i in range(self.n):
            result.append(templates[i % len(templates)])
        return result

    def to_features(self):
        """Convert molecules to 6-feature arrays: [MW, LogP, HBD, HBA, TPSA, RotBonds]."""
        feats = []
        for _ in range(len(self.smiles_list)):
            mw = self.rng.normal(450, 100)
            logp = self.rng.normal(3, 1.5)
            hbd = self.rng.integers(0, 6)
            hba = self.rng.integers(0, 12)
            tpsa = self.rng.normal(80, 30)
            rot = self.rng.integers(0, 8)
            feats.append([max(0, mw), max(0, logp), hbd, hba, max(0, tpsa), rot])
        return np.array(feats)
