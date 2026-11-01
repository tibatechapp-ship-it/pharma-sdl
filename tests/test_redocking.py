"""اختبارات إعادة الربط — القبول الهندسي الصادق (P2، تقييم #7).

ثلاث طبقات صدق:
    1) اختبارات تعمل في كل بيئة: مساعد RMSD ضد مرجع مُصنَّع يدوياً + سلامة
       المراجع البلورية الملتزمة (InChIKey يقابل SMILES المرجعي).
    2) إعادة ربط حقيقية ضد البلورة — RMSD ≤ 2.0 Å و‖ΔΔG‖ ≤ 2.5 kcal —
       تُخطَّى بصدق (skip) إن غاب vina/meeko أو المرجع البلوري، فلا فشل
       زائف ولا «نجاح» بلا قياس.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest
from rdkit import Chem

from pharma_sdl.engines.redocking import (
    DDG_ACCEPTANCE_KCAL,
    RMSD_ACCEPTANCE_ANGSTROM,
    has_redocking_stack,
    load_reference_ligand,
    pose_rmsd,
    redock_reference,
    reference_path,
    targets_with_references,
)

REPO = Path(__file__).resolve().parent.parent


# ── 1) مساعد RMSD — يعمل في كل بيئة ─────────────────────────


def _distorted_probe(offset: float = 2.0) -> tuple[Chem.Mol, Chem.Mol]:
    """جزيء ثلاثي معلوم الإحداثيات + نسخة بشوّه ذرّي معلوم (لا إزاحة صلبة).

    GetBestRMS يحاذي الصلب أولاً — الانتقال والدوران يُمحَيان، فالبصمة
    الحقيقية للتشوّه هي تحرّك ذرة واحدة: RMSD = offset/√3 ≈ 1.155 لـ2 Å.
    """
    template = Chem.MolFromSmiles("CNO")
    probe = Chem.Mol(template)
    ref = Chem.Mol(template)
    for mol, third_pos in ((ref, (0.0, 1.5, 0.0)), (probe, (0.0, 1.5 + offset, 0.0))):
        conf = Chem.Conformer(3)
        conf.SetAtomPosition(0, (0.0, 0.0, 0.0))
        conf.SetAtomPosition(1, (1.5, 0.0, 0.0))
        conf.SetAtomPosition(2, third_pos)
        mol.RemoveAllConformers()
        mol.AddConformer(conf, assignId=True)
    return probe, ref


def test_pose_rmsd_identical_is_zero():
    probe, _ = _distorted_probe()
    assert pose_rmsd(probe, probe) == pytest.approx(0.0, abs=1e-6)


def test_pose_rmsd_detects_distortion():
    """ذرة مزاحة 2 Å تعطي RMSD بعيداً عن الصفر بعد المحاذاة الصلبة المثلى،
    والتشوّه المضاعف يضاعف القياس تقريباً — الحساسية لا العمى."""
    probe, ref = _distorted_probe(offset=2.0)
    r2 = pose_rmsd(probe, ref)
    assert 0.5 < r2 < 1.5  # المحاذاة المثلى وزّعت الخطأ — بلا صفر ولا ضخامة
    probe4, ref4 = _distorted_probe(offset=4.0)
    r4 = pose_rmsd(probe4, ref4)
    assert r4 > 1.8 * r2  # استجابة شبه خطية للتشوّه


def test_pose_rmsd_rejects_different_molecules():
    from pharma_sdl.errors import ValidationError

    benzamide = Chem.MolFromSmiles("O=C(N)c1ccccc1")
    caffeine = Chem.MolFromSmiles("Cn1cnc2c1c(=O)n(C)c(=O)n2C")
    with pytest.raises(ValidationError):
        pose_rmsd(benzamide, caffeine)


# ── 2) سلامة المراجع البلورية الملتزمة — كل بيئة ─────────────


def test_reference_ligands_match_co_crystal_smiles():
    """المرجع البلوري الملتزم يقابل SMILES الليغاند المشتبك (InChIKey)."""
    import json

    raw = json.loads(
        (REPO / "data" / "receptors" / "receptors.json").read_text(encoding="utf-8")
    )
    for target in raw:
        path = reference_path(target["id"])
        assert path.exists(), f"المرجع البلوري مفقود: {path} — شغّل scripts/fetch_reference_ligands.py"
        mol = load_reference_ligand(target["id"])
        heavy = Chem.RemoveAllHs(mol)
        template = Chem.RemoveAllHs(Chem.MolFromSmiles(target["demo_smiles"]))
        assert heavy.GetNumAtoms() == template.GetNumAtoms()
        key_mol = Chem.MolToInchiKey(heavy)
        key_tpl = Chem.MolToInchiKey(template)
        assert key_mol == key_tpl, (
            f"InChIKey المرجع البلوري ({key_mol}) لا يقابل SMILES المرجعي ({key_tpl}) "
            f"للهدف {target['id']}"
        )
        assert mol.GetConformer() is not None


# ── 3) إعادة الربط الحقيقية — skip صادق بلا بنية ربط ─────────


@pytest.mark.skipif(not has_redocking_stack(), reason="vina/meeko غير متاحين في هذه البيئة")
@pytest.mark.skipif(
    len(targets_with_references()) == 0, reason="لا مراجع بلورية — شغّل fetch_reference_ligands.py"
)
@pytest.mark.parametrize("target_id", [t["id"] for t in targets_with_references()])
def test_redocking_crystal_acceptance(target_id: str):
    """إعادة ربط الليغاند المشتبك: RMSD ≤ 2.0 Å و‖ΔΔG‖ ≤ 2.5 kcal."""
    result = redock_reference(target_id, exhaustiveness=8, n_poses=9)
    assert result.rmsd_best is not None, f"لا RMSD — فشل تحويل البوزات: {result.failures}"
    assert result.best_kcal is not None
    assert math.isfinite(result.rmsd_best)
    # عتبات المجال المعلنة — لا تخفيف صامت
    assert result.rmsd_best <= RMSD_ACCEPTANCE_ANGSTROM, (
        f"RMSD {result.rmsd_best:.2f} Å > {RMSD_ACCEPTANCE_ANGSTROM} Å — "
        f"الوضع المتنبأ لا يقابل البلورة: {result.failures}"
    )
    assert result.ddg_error is not None and result.ddg_error <= DDG_ACCEPTANCE_KCAL, (
        f"|ΔΔG| {result.ddg_error} > {DDG_ACCEPTANCE_KCAL} — الدرجة انحرفت عن مرجع self-dock"
    )
    assert result.accepted, result.failures
