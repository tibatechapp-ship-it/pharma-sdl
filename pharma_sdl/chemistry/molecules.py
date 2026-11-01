"""توحيد الجزيئات ووصفها — RDKit.

SMILES خام → أكبر جزء (إزالة الأملاح) → SMILES قياسي + InChIKey + واصفات
(الوزن الجزيئي، cLogP، TPSA، HBD/HBA، الروابط الدوارة، الذرات الثقيلة).
هذا هو «الوصف الكيميائي الموحّد» الذي تُرتَّب ويُقارَن على أساسه كل الجولات.
"""

from __future__ import annotations

from dataclasses import dataclass

from rdkit import Chem, RDLogger
from rdkit.Chem import Crippen, Descriptors, Lipinski, rdMolDescriptors

# كتم تحذيرات RDKit الإجرائية — الأخطاء الحقيقية تعود كاستثناءات واضحة.
RDLogger.DisableLog("rdApp.*")


class InvalidSmiles(ValueError):
    """SMILES غير قابل للقراءة — رسالة عربية واضحة للاتصال."""


@dataclass(frozen=True)
class MoleculeRecord:
    """الوصف الموحّد لجزيء بعد التوحيد."""

    input_smiles: str
    canonical_smiles: str
    inchikey: str | None
    mol_weight: float
    clogp: float
    tpsa: float
    hbd: int
    hba: int
    rotatable_bonds: int
    heavy_atoms: int


def parse_smiles(smiles: str) -> Chem.Mol:
    """SMILES → جزيء RDKit مُعقَّم، مع رسالة خطأ صادقة عند الفشل."""
    if not smiles or not smiles.strip():
        raise InvalidSmiles("SMILES فارغ — لا يوجد ما يُحلَّل")
    mol = Chem.MolFromSmiles(smiles.strip())
    if mol is None:
        raise InvalidSmiles(f"SMILES غير صالح: {smiles.strip()[:80]}")
    return mol


def largest_fragment(mol: Chem.Mol) -> Chem.Mol:
    """أكبر جزء متصل — إزالة الأملاح/المذيبات من التمثيل."""
    frags = Chem.GetMolFrags(mol, asMols=True, sanitizeFrags=True)
    if len(frags) == 1:
        return frags[0]
    return max(frags, key=lambda m: m.GetNumHeavyAtoms())


def describe(mol: Chem.Mol) -> dict[str, object]:
    """الواصفات الأساسية لجزيء مُعقَّم."""
    return {
        "mol_weight": round(float(Descriptors.MolWt(mol)), 2),
        "clogp": round(float(Crippen.MolLogP(mol)), 2),
        "tpsa": round(float(rdMolDescriptors.CalcTPSA(mol)), 2),
        "hbd": int(Lipinski.NumHDonors(mol)),
        "hba": int(Lipinski.NumHAcceptors(mol)),
        "rotatable_bonds": int(Lipinski.NumRotatableBonds(mol)),
        "heavy_atoms": int(mol.GetNumHeavyAtoms()),
    }


def canonicalize(smiles: str) -> MoleculeRecord:
    """المسار الكامل: SMILES خام → MoleculeRecord موحّد."""
    mol = largest_fragment(parse_smiles(smiles))
    inchikey: str | None
    try:
        inchikey = Chem.MolToInchiKey(mol) or None
    except Exception:  # noqa: BLE001 — InChI قد يفشل على بنى نادرة، لا نُسقط الجزيء
        inchikey = None
    props = describe(mol)
    return MoleculeRecord(
        input_smiles=smiles.strip(),
        canonical_smiles=Chem.MolToSmiles(mol),
        inchikey=inchikey,
        **props,  # type: ignore[arg-type]
    )
