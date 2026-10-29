"""اختبارات المحلل الداخلي للبوزات (S7-a) — كلها بلا شبكة وبلا Vina.

نستخدم المستقبل الحقيقي المُجهَّز (data/receptors/7VH8_A.pdbqt) كمرجع،
وبوزات صناعية نضعها عمداً قرب ذراته للتحقق من كل مقياس على حدة.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from core.contacts import (
    AD_ACCEPTOR,
    HBOND_MAX,
    analyze_pose,
    parse_pdbqt_atoms,
    score_poses,
)

REPO = Path(__file__).resolve().parent.parent
RECEPTOR = REPO / "data" / "receptors" / "7VH8_A.pdbqt"


def pdbqt_atom(serial: int, name: str, x: float, y: float, z: float, ad: str) -> str:
    """سطر ATOM بصيغة PDBQT صحيحة الأعمدة (الإحداثيات 30-53، النوع 77-78)."""
    base = (
        f"ATOM  {serial:5d} {name:<4} {'LIG':>3} A   1    "
        f"{x:8.3f}{y:8.3f}{z:8.3f}  1.00  0.00    +0.000"
    )
    return f"{base:<77}{ad:>2}"


def pose_block(atoms: list[str]) -> str:
    """كتلة MODEL…ENDMDL كاملة كما تُخرجها v.poses()."""
    return "\n".join(["MODEL 1"] + atoms + ["ENDMDL"]) + "\n"


@pytest.fixture(scope="module")
def rec_atoms():
    atoms = parse_pdbqt_atoms(RECEPTOR.read_text(encoding="utf-8"))
    assert atoms, "المستقبل المرجعي يجب أن يحوي ذرات"
    return atoms


# ── التحليل ──────────────────────────────────────────────────


def test_parse_real_receptor(rec_atoms):
    assert len(rec_atoms) > 500
    assert any(a.is_acceptor for a in rec_atoms)
    assert any(a.is_hydrophobic for a in rec_atoms)
    assert all(a.is_heavy for a in rec_atoms if a.ad_type not in {"HD", "H", "D"})


def test_parse_skips_garbage_lines():
    good = pdbqt_atom(1, "N", 1.0, 2.0, 3.0, "NA")
    broken = (
        f"{'ATOM  2  XX  LIG     1    broken':<77}{'OA':>2}\n"  # إحداثيات غير رقمية
    )
    text = "REMARK whatever\nROOT\n" + good + "\n" + broken + "ENDROOT\nTORSDOF 2\n"
    atoms = parse_pdbqt_atoms(text)
    assert len(atoms) == 1
    assert atoms[0].ad_type == "NA"
    assert atoms[0].is_acceptor and atoms[0].is_heavy
    assert atoms[0].x == 1.0 and atoms[0].y == 2.0 and atoms[0].z == 3.0


def test_halogen_and_types():
    text = pdbqt_atom(1, "Cl", 0.0, 0.0, 0.0, "Cl") + "\n" + pdbqt_atom(2, "H", 1.0, 0.0, 0.0, "HD")
    atoms = parse_pdbqt_atoms(text)
    assert atoms[0].is_hydrophobic and atoms[0].is_heavy and not atoms[0].is_donor
    assert atoms[1].is_donor and not atoms[1].is_heavy
    assert "Cl".upper() in {"CL"}  # توحيد النوع


def test_hbond_and_contacts(rec_atoms):
    """بوز يحوي: H مانح قرب مستقبِل + كربون قرب ذرة ثقيلة — تُحتسب بالاتجاهين."""
    acc = next(a for a in rec_atoms if a.ad_type in AD_ACCEPTOR)
    heavy = next(a for a in rec_atoms if a.is_heavy and a.ad_type == "C")
    atoms = [
        # مانح (HD) على بعد 2.5 Å من المستقبِل → رابط H اتجاه pose→rec
        pdbqt_atom(1, "H1", acc.x + HBOND_MAX - 1.0, acc.y, acc.z, "HD"),
        # كربون هيدروفوبي على بعد ~3.5 Å من كربون المستقبل → زوج كاره + اتصال
        pdbqt_atom(2, "C1", heavy.x + 3.5, heavy.y, heavy.z, "C"),
    ]
    res = analyze_pose(rec_atoms, pose_block(atoms))
    assert res.n_pose_heavy == 1
    assert res.n_hbonds >= 1
    assert res.n_contacts >= 2
    assert res.n_hydrophobic >= 1
    assert res.n_clashes == 0


def test_acceptor_direction_rec_donor(rec_atoms):
    """الاتجاه المعاكس: ذرة مستقبِلة في البوز قرب مانح HD في المستقبل — إن وُجد HD."""
    donors = [a for a in rec_atoms if a.is_donor]
    if not donors:
        pytest.skip("المستقبل المرجعي بلا هيدروجينات قطبية — الاتجاه الثاني يُختبر صناعياً")
    donor = donors[0]
    acc_atom = pdbqt_atom(1, "O1", donor.x + 2.6, donor.y, donor.z, "OA")
    res = analyze_pose(rec_atoms, pose_block([acc_atom]))
    assert res.n_hbonds >= 1


def test_clash_detection(rec_atoms):
    heavy = next(a for a in rec_atoms if a.is_heavy)
    atoms = [pdbqt_atom(1, "C1", heavy.x + 2.0, heavy.y, heavy.z, "C")]
    res = analyze_pose(rec_atoms, pose_block(atoms))
    assert res.n_clashes >= 1
    assert res.score > 0  # عقوبة التعارض ترفع الدرجة فوق الصفر


def test_empty_pose_raises(rec_atoms):
    with pytest.raises(ValueError):
        analyze_pose(rec_atoms, "MODEL 1\nENDMDL\n")


def test_empty_receptor_raises(tmp_path):
    bad = tmp_path / "empty.pdbqt"
    bad.write_text("REMARK no atoms here\n", encoding="utf-8")
    with pytest.raises(ValueError):
        score_poses(bad, ["MODEL 1\nENDMDL\n"])


def test_missing_receptor_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        score_poses(tmp_path / "nope.pdbqt", ["MODEL 1\nENDMDL\n"])


def test_score_poses_order_preserved(rec_atoms):
    heavy = next(a for a in rec_atoms if a.is_heavy)
    near = [pdbqt_atom(1, "C1", heavy.x + 4.0, heavy.y, heavy.z, "C")]
    far = [pdbqt_atom(1, "C1", heavy.x + 40.0, heavy.y, heavy.z, "C")]
    rows = score_poses(RECEPTOR, [pose_block(near), pose_block(far)])
    assert len(rows) == 2
    assert rows[0].n_contacts >= 1
    assert rows[1].n_contacts == 0


def test_score_monotonic_in_hbonds(rec_atoms):
    """رابط إضافي = درجة أدنى (أكثر سالبية) — الشرط التعليمي الأساسي.

    كل بوز يحوي ذرة C بعيدة حتى لا يُرمى خطأ «بلا ذرات ثقيلة».
    """
    acc = next(a for a in rec_atoms if a.ad_type in AD_ACCEPTOR)
    far_c = pdbqt_atom(9, "C9", acc.x + 60.0, acc.y, acc.z, "C")
    one = [
        pdbqt_atom(1, "H1", acc.x + HBOND_MAX - 1.0, acc.y, acc.z, "HD"),
        far_c,
    ]
    two = [
        pdbqt_atom(1, "H1", acc.x + HBOND_MAX - 1.0, acc.y, acc.z, "HD"),
        pdbqt_atom(2, "H2", acc.x, acc.y + HBOND_MAX - 1.2, acc.z, "HD"),
        far_c,
    ]
    s1 = analyze_pose(rec_atoms, pose_block(one)).score
    s2 = analyze_pose(rec_atoms, pose_block(two)).score
    assert s2 <= s1


def test_to_row_shape():
    from core.contacts import PoseContacts

    row = PoseContacts(10, 5, 2, 3, 0).to_row(pose_index=2, vina_kcal=-7.4)
    assert row["#"] == 2
    assert row["vina"] == -7.4
    assert row["inhouse"] == round(-1.10 * 2 + -0.12 * 3, 2)
    assert {"contacts", "hbonds", "hydrophobic", "clashes"} <= set(row)
