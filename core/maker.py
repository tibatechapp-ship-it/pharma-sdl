"""
MoleculeMaker — توليد SMILES حقيقية + حساب الأوصاف بـ RDKit.
"""
import numpy as np
from rdkit import Chem
from rdkit.Chem import Descriptors, Lipinski, rdMolDescriptors


class MoleculeMaker:
    """توليد مكتبة جزيئات صالحة كيميائيًا مع أوصاف RDKit حقيقية."""

    CORES = [
        'c1ccccc1',
        'c1ccncc1',
        'c1ccc2ccccc2c1',
        'C1CCCCC1',
        'c1cnc2ccccc2n1',
        'c1ccc2[nH]ccc2c1',
    ]
    LINKERS = ['C', 'CC', 'OC', 'NC', 'C(=O)', 'S(=O)(=O)']
    SUBSTITUENTS = ['F', 'Cl', 'Br', 'C', 'OC', 'N(C)C', 'C(=O)O', 'C#N', 'CF3']

    def __init__(self, n=100, seed=42):
        self.n = n
        self.smiles_list = []
        self.mols = []

        rng = np.random.default_rng(seed)
        attempts = 0
        max_attempts = n * 50

        while len(self.mols) < n and attempts < max_attempts:
            attempts += 1
            core = self.CORES[rng.integers(len(self.CORES))]
            linker = self.LINKERS[rng.integers(len(self.LINKERS))]
            sub = self.SUBSTITUENTS[rng.integers(len(self.SUBSTITUENTS))]
            smi = f"{core}{linker}{sub}"

            mol = Chem.MolFromSmiles(smi)
            if mol is None or mol.GetNumAtoms() < 5:
                continue

            self.smiles_list.append(smi)
            self.mols.append(mol)

    def to_features(self):
        """6 أوصاف حقيقية محسوبة من SMILES بواسطة RDKit."""
        feats = []
        for mol in self.mols:
            feats.append([
                Descriptors.MolWt(mol),
                Descriptors.MolLogP(mol),
                Lipinski.NumHDonors(mol),
                Lipinski.NumHAcceptors(mol),
                rdMolDescriptors.CalcTPSA(mol),
                Lipinski.NumRotatableBonds(mol),
            ])
        return np.array(feats)
