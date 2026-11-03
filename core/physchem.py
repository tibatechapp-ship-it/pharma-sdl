"""physchem — الوصف الفيزيوكيميائي الحتمي (P11 — ترقية النموذج).

كتلة وصف فيزيوكيميائية ثابتة الترتيب (20 عموداً) تُحسب من RDKit لكل جزيء.
تُدمج مع بصمة Morgan في خط الفعالية عند `include_descriptors=True`:

    X = [Morgan FP (2048 bit)] ⊕ [physchem (20 عموداً)]

خصائص العقد:
    - حتمي لكل جزيء: لا يعتمد على أي معلومة من مجموعة الاختبار (لا تسريب).
    - ترتيب الأعمدة ثابت في DESCRIPTOR_NAMES — أي تغيير يُعدّ كسر عقد.
    - فشل الجزيء (SMILES غير صالح/شاذ) → None وليس انهياراً.
    - للأشجار (RF/HistGB) لا يحتاج توحيد مقاييس — الأعمدة تُستخدم كما هي.

المرجع العلمي: RDKit Crippen/Lipinski/rdMolDescriptors — نفس المكتبة
المستخدمة في ADMETlab ونظائرها التعليمية، بلا أي اعتماد شبكي.
"""
from __future__ import annotations

import numpy as np
from rdkit import Chem
from rdkit.Chem import Crippen, Descriptors, GraphDescriptors, Lipinski, rdMolDescriptors

# الترتيب عقد ثابت — لا تُضِف ولا تُرتبِ إلا بترقية إصدار التمثيل
DESCRIPTOR_NAMES: tuple[str, ...] = (
    "mol_wt",
    "exact_mol_wt",
    "heavy_atoms",
    "fraction_csp3",
    "rotatable_bonds",
    "h_donors",
    "h_acceptors",
    "tpsa",
    "crippen_logp",
    "crippen_mr",
    "labute_asa",
    "ring_count",
    "aromatic_rings",
    "saturated_rings",
    "aliphatic_rings",
    "formal_charge",
    "heteroatoms",
    "aromatic_proportion",
    "balaban_j",
    "bertz_ct",
)


def _mol_from_smiles(smiles: str) -> Chem.Mol | None:
    """تحليل SMILES بأمان — مستقل عن core.ml_potency لكسر الاستدعاء الدائري."""
    try:
        return Chem.MolFromSmiles(smiles) if smiles else None
    except Exception:  # noqa: BLE001
        return None


def physchem_vector(smiles: str) -> np.ndarray | None:
    """SMILES → متجه فيزيوكيميائي (20 عموداً بترتيب DESCRIPTOR_NAMES).

    يرجع None إذا فشل التحليل أو فشل أي وصف — الجزيء يُستبعد عندئذ
    من التمثيل الموسّع (نفس عقد featurize).
    """
    mol = _mol_from_smiles(smiles)
    if mol is None:
        return None
    try:
        heavy = mol.GetNumHeavyAtoms()
        n_arom_atoms = sum(1 for a in mol.GetAtoms() if a.GetIsAromatic())
        vals = (
            Descriptors.MolWt(mol),
            Descriptors.ExactMolWt(mol),
            float(heavy),
            rdMolDescriptors.CalcFractionCSP3(mol),
            float(rdMolDescriptors.CalcNumRotatableBonds(mol)),
            float(Lipinski.NumHDonors(mol)),
            float(Lipinski.NumHAcceptors(mol)),
            rdMolDescriptors.CalcTPSA(mol),
            Crippen.MolLogP(mol),
            Crippen.MolMR(mol),
            rdMolDescriptors.CalcLabuteASA(mol),
            float(rdMolDescriptors.CalcNumRings(mol)),
            float(Lipinski.NumAromaticRings(mol)),
            float(rdMolDescriptors.CalcNumSaturatedRings(mol)),
            float(rdMolDescriptors.CalcNumAliphaticRings(mol)),
            float(Chem.GetFormalCharge(mol)),
            float(Lipinski.NumHeteroatoms(mol)),
            n_arom_atoms / heavy if heavy else 0.0,
            GraphDescriptors.BalabanJ(mol),
            GraphDescriptors.BertzCT(mol),
        )
        vec = np.asarray(vals, dtype=np.float64)
        if vec.shape != (len(DESCRIPTOR_NAMES),) or not np.isfinite(vec).all():
            return None
        return vec
    except Exception:  # noqa: BLE001 — جزيء شاذ نادر لا يُسمح له بكسر الدفعة
        return None


def physchem_matrix(smiles_list: list[str]) -> tuple[np.ndarray, list[int]]:
    """قائمة SMILES → مصفوفة فيزيوكيميائية + فهارس الصالحة فقط.

    نفس عقد featurize في core.ml_potency: الاستبعاد موحّد بين الصفوف،
    والفهارس تسمح بمزامنة y والبصمات مع نفس الجزيئات.
    """
    rows: list[np.ndarray] = []
    idx: list[int] = []
    for i, smi in enumerate(smiles_list):
        vec = physchem_vector(smi)
        if vec is not None:
            rows.append(vec)
            idx.append(i)
    if not rows:
        return np.empty((0, len(DESCRIPTOR_NAMES))), []
    return np.vstack(rows), idx
