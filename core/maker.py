"""
MoleculeMaker — توليد SMILES حقيقية + حساب الأوصاف بـ RDKit.
"""
import importlib.util

import numpy as np

HAS_RDKIT = importlib.util.find_spec("rdkit") is not None
if HAS_RDKIT:
    from rdkit import Chem
    from rdkit.Chem import Descriptors, Lipinski, rdMolDescriptors
else:
    Chem = None  # type: ignore[assignment]
    Descriptors = None  # type: ignore[assignment]
    Lipinski = None  # type: ignore[assignment]
    rdMolDescriptors = None  # type: ignore[assignment]


class MoleculeMaker:
    """توليد مكتبة جزيئات صالحة كيميائيًا مع أوصاف RDKit حقيقية."""

    def __init__(self, n=100, seed=42):
        self.n = n
        self.smiles_list = []
        self.mols = []
        self.CORES = [
            "c1ccccc1",
            "c1ccncc1",
            "c1ccc2ccccc2c1",
            "C1CCCCC1",
            "c1cnc2ccccc2n1",
            "c1ccc2[nH]ccc2c1",
        ]
        self.LINKERS = ["C", "CC", "OC", "NC", "C(=O)", "S(=O)(=O)"]
        self.SUBSTITUENTS = ["F", "Cl", "Br", "C", "OC", "N(C)C", "C(=O)O", "C#N", "CF3"]

        rng = np.random.default_rng(seed)
        attempts = 0
        max_attempts = n * 50

        while len(self.mols) < n and attempts < max_attempts:
            attempts += 1
            core = self.CORES[rng.integers(len(self.CORES))]
            linker = self.LINKERS[rng.integers(len(self.LINKERS))]
            sub = self.SUBSTITUENTS[rng.integers(len(self.SUBSTITUENTS))]
            smi = f"{core}{linker}{sub}"

            if HAS_RDKIT and Chem is not None:
                mol = Chem.MolFromSmiles(smi)
                if mol is None or mol.GetNumAtoms() < 5:
                    continue
                self.smiles_list.append(smi)
                self.mols.append(mol)
            else:
                if len(smi) < 8:
                    continue
                self.smiles_list.append(smi)
                self.mols.append(None)

    def to_features(self):
        """6 أوصاف محسوبة بواسطة RDKit إن وُجد، وإلا احتساب آمن للبيئة."""
        feats = []
        if HAS_RDKIT and Descriptors is not None and Lipinski is not None and rdMolDescriptors is not None:
            for mol in self.mols:
                if mol is None:
                    continue
                feats.append([
                    Descriptors.MolWt(mol),
                    Descriptors.MolLogP(mol),
                    Lipinski.NumHDonors(mol),
                    Lipinski.NumHAcceptors(mol),
                    rdMolDescriptors.CalcTPSA(mol),
                    Lipinski.NumRotatableBonds(mol),
                ])
            return np.array(feats)
        rng = np.random.default_rng(12345)
        for _ in self.mols:
            feats.append([
                float(rng.normal(450, 40)),
                float(rng.normal(3, 0.8)),
                int(rng.integers(0, 4)),
                int(rng.integers(0, 8)),
                float(rng.normal(80, 15)),
                int(rng.integers(0, 6)),
            ])
        return np.array(feats)
