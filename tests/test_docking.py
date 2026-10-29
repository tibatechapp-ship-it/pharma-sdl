"""اختبارات Docking — بلا شبكة؛ الربط الفعلي يتطلب vina (متوفر في CI).

تغطي: جسر Cheng-Prusoff، تجهيز الليغاند، تحويل PDBQT→PDB، ملفات المستقبلات
المُجهَّزة، HTML العرض، والربط الحقيقي بخيط واحد صغير (أسرع من ثانية قليلة).
"""
import math

import pytest
from rdkit import Chem

from core.docking import (
    RT_KCAL,
    DockingResult,
    _element_from_ad_type,
    build_3d_html,
    estimate_summary_row,
    load_receptors,
    pic50_to_dg_kcal,
    pose_pdbqt_to_pdb,
    prepare_ligand,
    split_poses,
)

ASPIRIN = "CC(=O)OC1=CC=CC=C1C(=O)O"

try:
    from core.docking import HAS_VINA

    if HAS_VINA:
        from core.docking import dock_ligand
except ImportError:  # pragma: no cover
    HAS_VINA = False


# ── جسر Cheng-Prusoff ──

def test_pic50_to_dg_math():
    """ΔG = −RT·ln10·pIC50 — إعادة حساب مستقلة."""
    expected = -(RT_KCAL * math.log(10.0)) * 8.0
    assert math.isclose(pic50_to_dg_kcal(8.0), expected, rel_tol=1e-9)
    assert math.isclose(pic50_to_dg_kcal(8.0), -10.914, abs_tol=0.01)


def test_pic50_to_dg_monotonic_and_zero():
    assert pic50_to_dg_kcal(0.0) == 0.0
    assert pic50_to_dg_kcal(9.0) < pic50_to_dg_kcal(7.0) < 0


def test_estimate_summary_row():
    row = estimate_summary_row(-8.5, 7.8)
    assert row["vina_kcal"] == -8.5
    assert row["dg_from_pic50"] == round(pic50_to_dg_kcal(7.8), 2)
    assert math.isclose(row["gap"], round(-8.5 - pic50_to_dg_kcal(7.8), 2))
    assert estimate_summary_row(None, 7.0)["gap"] is None


# ── تجهيز الليغاند ──

def test_prepare_ligand_returns_pdbqt_and_mol():
    pdbqt, mol = prepare_ligand(ASPIRIN)
    assert pdbqt and "ROOT" in pdbqt
    assert mol.GetNumAtoms() >= 13  # أسبرين + Hs
    assert mol.GetNumConformers() >= 1  # بنيّة ثلاثية الأبعاد فعلية


def test_prepare_ligand_invalid_smiles_raises():
    with pytest.raises(ValueError):
        prepare_ligand("not-a-smiles")


def test_prepare_ligand_empty_raises():
    with pytest.raises(ValueError):
        prepare_ligand("")


# ── تحويل البوزات ──

def test_element_from_ad_type():
    assert _element_from_ad_type("OA") == "O"
    assert _element_from_ad_type("NA") == "N"
    assert _element_from_ad_type("A") == "C"
    assert _element_from_ad_type("Cl") == "Cl"
    assert _element_from_ad_type("XX") == "C"  # نوع مجهول → كربون افتراضي


def test_pose_pdbqt_to_pdb_roundtrip_atoms():
    pdbqt, _ = prepare_ligand(ASPIRIN)
    pose = "\n".join(
        l for l in pdbqt.splitlines() if l.startswith(("ATOM", "HETATM"))
    )
    pose = "MODEL 1\n" + pose + "\nEND MODEL\n"
    pdb = pose_pdbqt_to_pdb(pose)
    atom_lines = [l for l in pdb.splitlines() if l.startswith(("ATOM", "HETATM"))]
    assert atom_lines, "لا ذرات في PDB المحوَّل"
    # كل سطر بطول PDB قياسي (≥ 66) مع عمود عنصر قرب 77-78
    for l in atom_lines:
        assert len(l) >= 78
        assert l[76:78].strip() != ""
    # لا أعمدة شحنات PDBQT متبقية في العمود 70-76 (تُقص)
    assert all(l[66:76].strip() == "" for l in atom_lines)


def test_pose_pdbqt_to_pdb_empty_raises():
    with pytest.raises(ValueError):
        pose_pdbqt_to_pdb("REMARK empty\n")


def test_split_poses():
    fake = "MODEL 1\nATOM a\nEND MODEL\nMODEL 2\nATOM b\nEND MODEL\n"
    blocks = split_poses(fake)
    assert len(blocks) == 2
    assert blocks[1].startswith("MODEL 2")
    assert split_poses("no blocks") == []


# ── المستقبلات المُجهَّزة ──

@pytest.fixture(scope="module")
def receptors():
    recs = load_receptors()
    assert len(recs) >= 1, "receptors.json فارغ"
    return recs


def test_receptor_metadata_sane(receptors):
    for r in receptors:
        assert len(r.center) == 3 and len(r.box_size) == 3
        assert 15 <= max(r.box_size) <= 30
        assert r.receptor_file.endswith(".pdbqt")
        assert Chem.MolFromSmiles(r.demo_smiles) is not None, r.id


def test_receptor_pdbqt_files_exist(receptors):
    for r in receptors:
        path = r.receptor_file_path
        assert path.exists(), f"مفقود: {path}"
        txt = path.read_text()
        # مستقبل صلب: بلا ROOT/BRANCH — ذرات ATOM بصيغة PDBQT مع شحنات وأصناف AD4
        n_atoms = sum(1 for l in txt.splitlines() if l.startswith(("ATOM", "HETATM")))
        assert n_atoms > 1500, f"{r.id}: مستقبل صغير جداً ({n_atoms})"
        # هيدروجين قطبي موجود (شرط دالة التسجيل الهيدروجينية لـVina)
        assert any(l[77:79].strip() == "HD" for l in txt.splitlines()
                   if l.startswith(("ATOM", "HETATM")))


def test_receptor_notes_bilingual(receptors):
    for r in receptors:
        assert r.note_ar and r.note_en


# ── عرض 3Dmol ──

def test_build_3d_html_structure(receptors):
    pdb = "ATOM      1  N   UNL     1      0.000   0.000   0.000  1.00  0.00           N\n"
    html = build_3d_html(receptors[0].receptor_file_path, pdb, div_id="testdiv")
    assert "3Dmol" in html and "testdiv" in html
    assert "addModel" in html and "zoomTo" in html
    # المستقبل مضمّن نصياً (سطر من PDBQT يظهر في HTML)
    first_atom = next(
        l for l in receptors[0].receptor_file_path.read_text().splitlines()
        if l.startswith(("ATOM", "HETATM"))
    )
    assert first_atom.strip() in html


# ── الربط الفعلي (vina) ──

@pytest.mark.skipif(not HAS_VINA, reason="vina غير مثبت")
def test_full_dock_small_ligand(receptors):
    """ربط حقيقي كامل بلغاند صغير وشدة بحث منخفضة — فحص دخان للمستوى الحي."""
    rec = receptors[0]
    res = dock_ligand(ASPIRIN, rec, n_poses=3, exhaustiveness=4)
    assert isinstance(res, DockingResult)
    assert len(res.scores) >= 1
    assert all(s < 0 for s in res.scores), f"طاقات موجبة غير منطقية: {res.scores}"
    assert res.best is not None and res.best >= -16.0  # سقف علوي منطقي لأسرين
    assert len(res.poses_pdbqt) == len(res.scores)
    pdb = res.best_pose_pdb()
    assert pdb.startswith(("ATOM", "HETATM", "MODEL")) or "ATOM" in pdb
    assert res.engine == "vina"


@pytest.mark.skipif(not HAS_VINA, reason="vina غير مثبت")
def test_dock_result_energies_shape(receptors):
    rec = receptors[0]
    res = dock_ligand(ASPIRIN, rec, n_poses=2, exhaustiveness=4)
    for row in res.energies:
        assert len(row) == 5  # total, inter, intra, torsions, intra_best
        assert isinstance(row[0], float)
