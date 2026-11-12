"""U3 — الكيمياء: جسر RDKit + أيونبة Henderson-Hasselbalch (§3 U3).

الوحدة تعتمد RDKit المثبت في المنصة (لا شبكة)، وتوفّر جسراً واحداً إلى
الطبقة التعليمية `core/physchem` (نمط «تثبيت الجسر الواحد»).
المصادر: RDKit 2026.09 (Crippen 1999، Ertl 2000)؛ Lipinski 1997.
"""

from __future__ import annotations

import math

from .errors import RykoInputError

_HBD_MAX, _HBA_MAX, _MW_MAX, _LOGP_MAX = 5, 10, 500.0, 5.0


def _mol(smiles: str):
    """حاكم SMILES: تحليل أو رفض مُعلَّل (لا صمت)."""
    from rdkit import Chem, RDLogger

    RDLogger.DisableLog("rdApp.*")
    if not isinstance(smiles, str) or not smiles.strip():
        raise RykoInputError(
            "SMILES مطلوب — سلسلة غير فارغة.",
            "SMILES required — a non-empty string.",
        )
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        raise RykoInputError(
            f"SMILES غير صالح: «{smiles}» — رفض صادق بلا تخمين.",
            f"Invalid SMILES: '{smiles}' — honest rejection, no guessing.",
        )
    return mol


def validate_smiles(smiles: str):
    """تحقق وتوحيد SMILES — يعيد الكانوني وقيم ثقة."""
    from rdkit import Chem

    mol = _mol(smiles)
    return Chem.MolToSmiles(mol), {"atoms": mol.GetNumAtoms()}


def descriptors(smiles: str):
    """الناقل الفيزيائي-الكيميائي المعلن: MW، cLogP، TPSA، HBD، HBA، RB، HA."""
    from rdkit.Chem import Crippen, Descriptors, rdMolDescriptors
    from rdkit.Chem import Lipinski as RDKitLipinski

    mol = _mol(smiles)
    mw = float(Descriptors.MolWt(mol))
    clogp = float(Crippen.MolLogP(mol))
    tpsa = float(rdMolDescriptors.CalcTPSA(mol))
    hbd = int(RDKitLipinski.NumHDonors(mol))
    hba = int(RDKitLipinski.NumHAcceptors(mol))
    rb = int(Descriptors.NumRotatableBonds(mol))
    ha = int(mol.GetNumHeavyAtoms())
    return clogp, {
        "mw": mw,
        "clogp": clogp,
        "tpsa": tpsa,
        "hbd": hbd,
        "hba": hba,
        "rotatable_bonds": rb,
        "heavy_atoms": ha,
    }


def lipinski(smiles: str):
    """قواعد Lipinski الخمس — حكم صريح بكل قاعدة (لا نتيجة عمياء)."""
    _, d = descriptors(smiles)
    rules = {
        "mw_le_500": d["mw"] <= _MW_MAX,
        "clogp_le_5": d["clogp"] <= _LOGP_MAX,
        "hbd_le_5": d["hbd"] <= _HBD_MAX,
        "hba_le_10": d["hba"] <= _HBA_MAX,
    }
    violations = [k for k, ok in rules.items() if not ok]
    verdict = "pass" if len(violations) < 2 else "fail"
    return verdict, {**d, "rules": rules, "violations": violations}


def ionization_fraction(pka: float, ph: float, acid: bool = True):
    """الجزء غير المتأين — Henderson-Hasselbalch.

    حمض: f_un = 1/(1+10^(pH−pKa)) · قاعدة: f_un = 1/(1+10^(pKa−pH)).
    مثال ذهبي: حمض pKa=3.5 عند pH=1.5 (معدة) ⇒ ≈0.990 غير متأين.
    """
    p1, p2 = _num("pka", pka), _num("ph", ph)
    if not (0.0 <= p1 <= 14.0):
        raise RykoInputError(
            f"pKa خارج النطاق الفيزيائي 0–14 (وصل: {pka}).",
            f"pKa outside the physical 0–14 range (got: {pka}).",
        )
    if not (0.0 <= p2 <= 14.0):
        raise RykoInputError(
            f"pH خارج النطاق 0–14 (وصل: {ph}).",
            f"pH outside the 0–14 range (got: {ph}).",
        )
    if acid:
        f_un = 1.0 / (1.0 + 10 ** (p2 - p1))
    else:
        f_un = 1.0 / (1.0 + 10 ** (p1 - p2))
    return f_un, {"pka": p1, "ph": p2, "species": "acid" if acid else "base"}


def physchem_bridge(smiles: str):
    """جسر واحد إلى `core/physchem.physchem_vector` — ربط وثيق بالطبقة التعليمية.

    يعيد المتجه مع أسماء ملامسه كما تعلنها الطبقة التعليمية؛ ويترجم أي
    فشل (SMILES/لا RDKit) إلى رفض مُعلَّل بدل استثناء خام.
    """
    try:
        from core.physchem import physchem_vector
    except Exception as exc:  # pragma: no cover — لا RDKit فقط
        raise RykoInputError(
            f"جسر physchem غير متاح: {exc}",
            f"physchem bridge unavailable: {exc}",
        ) from exc
    vec = physchem_vector(smiles)
    if vec is None:
        raise RykoInputError(
            f"SMILES غير صالح لجسر physchem: «{smiles}».",
            f"Invalid SMILES for the physchem bridge: '{smiles}'.",
        )
    return float(vec[0]), {
        "vector_len": int(vec.size),
        "vector_head": [round(float(x), 6) for x in vec[:6]],
    }


def _num(name: str, value: float) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        raise RykoInputError(
            f"المدخل «{name}» يجب أن يكون رقماً.",
            f"Input '{name}' must be a number.",
        ) from None
    if not math.isfinite(v):
        raise RykoInputError(
            f"المدخل «{name}» يجب أن يكون رقماً منتهياً.",
            f"Input '{name}' must be a finite number.",
        )
    return v
