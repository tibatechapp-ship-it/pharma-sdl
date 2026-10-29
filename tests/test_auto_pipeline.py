"""اختبارات خط القراءة التلقائية (S8) — بلا شبكة وبلا Vina حقيقي.

نستبدل expand_library وdock_ligand بمزاورف محليّة، والمستقبل حقيقي
(7VH8) حتى يعمل المحلل الداخلي على بوزات صناعية قرب ذراته.
"""
from __future__ import annotations

from pathlib import Path

import pytest

import core.auto_pipeline as ap
from core.contacts import parse_pdbqt_atoms
from core.docking import DockingResult, load_receptors

REPO = Path(__file__).resolve().parent.parent
RECEPTOR = REPO / "data" / "receptors" / "7VH8_A.pdbqt"

ASPIRIN = "CC(=O)OC1=CC=CC=C1C(=O)O"
FAT = "C" * 60  # MW ≈ 843 — يفشل Lipinski حتماً


class FakeModel:
    """نموذج potency مزيف بواجهة score_potency نفسها."""

    def predict_many(self, smiles_list):
        return [
            {
                "pic50": 6.5,
                "ci95": (6.2, 6.8),
                "ic50_nm": 316.0,
                "verdict": "قابل للتحسين",
                "icon": "🟡",
            }
            for _ in smiles_list
        ]


def _pose_near_receptor() -> str:
    """بوز صناعي: ذرة قرب أول ذرة ثقيلة في المستقبل (اتصال مضمون)."""
    atoms = parse_pdbqt_atoms(RECEPTOR.read_text(encoding="utf-8"))
    heavy = next(a for a in atoms if a.is_heavy)
    line = (
        f"ATOM  {1:5d} {'C1':<4} {'LIG':>3} A   1    "
        f"{heavy.x + 4.0:8.3f}{heavy.y:8.3f}{heavy.z:8.3f}  1.00  0.00    +0.000"
    )
    line = f"{line:<77}{'C':>2}"
    return "MODEL 1\n" + line + "\nENDMDL\n"


def _fake_dock(smiles, receptor, n_poses=3, exhaustiveness=4):
    """بديل dock_ligand — نتيجة ثابتة ببوز واحد قابل للتحليل."""
    return DockingResult(
        smiles=smiles,
        receptor_id=receptor.id,
        scores=[-7.2],
        energies=[[-7.2, -6.9, -0.4, 0.2, -6.8]],
        poses_pdbqt=[_pose_near_receptor()],
        exhaustiveness=exhaustiveness,
    )


@pytest.fixture
def receptor():
    recs = load_receptors()
    assert recs, "المستقبلات المرجعية مطلوبة للاختبار"
    return recs[0]


@pytest.fixture
def offline(monkeypatch):
    """عزل كامل عن الشبكة وVina: توسيع + ربط مزيفان."""
    monkeypatch.setattr(
        ap, "expand_library", lambda seed, n=8, mode="auto": ([], "brics")
    )
    monkeypatch.setattr(ap, "dock_ligand", _fake_dock)


# ── الحكم المحلي ─────────────────────────────────────────────


def test_local_admet_accepts_aspirin():
    from core.oracle import MultiObjectiveOracle

    ok, flags = ap.local_admet_verdict(
        ASPIRIN, oracle=MultiObjectiveOracle(seed=42)
    )
    assert ok
    assert any("مقبول" in f for f in flags)


def test_local_admet_rejects_fat_molecule():
    ok, flags = ap.local_admet_verdict(FAT)
    assert not ok
    assert any("MW" in f for f in flags)


def test_local_admet_invalid_smiles():
    ok, flags = ap.local_admet_verdict("not-a-smiles")
    assert not ok
    assert any("غير صالح" in f for f in flags)


# ── الخط الكامل ──────────────────────────────────────────────


def test_pipeline_local_engine(offline, receptor):
    rep = ap.run_auto_pipeline(
        ASPIRIN, receptor, n_library=4, dock_top=2, model=FakeModel()
    )
    assert rep.source == "brics"
    assert rep.library[0] == ASPIRIN
    assert rep.funnel["المكتبة"] >= 1
    assert rep.funnel["أُربط بـVina"] == len(rep.results)
    assert rep.admet_engine == "local"
    assert rep.admet_passed == len(rep.results)
    assert rep.results[0]["inhouse"] is not None
    assert rep.best_smiles == rep.results[0]["smiles"]
    assert rep.best_vina == pytest.approx(-7.2)
    assert any("PGx" in f or "أيض" in f for f in rep.pgx_flags)


def test_pipeline_ersilia_engine(offline, receptor, monkeypatch):
    monkeypatch.setattr(
        ap, "_ersilia_pass", lambda mid, smiles: {s: True for s in smiles}
    )
    rep = ap.run_auto_pipeline(
        ASPIRIN, receptor, n_library=4, dock_top=2, admet_model="eos2ta5"
    )
    assert rep.admet_engine == "ersilia"
    assert rep.admet_passed == len(rep.results)


def test_pipeline_ersilia_failure_falls_back_local(offline, receptor, monkeypatch):
    monkeypatch.setattr(ap, "_ersilia_pass", lambda mid, smiles: None)
    rep = ap.run_auto_pipeline(
        ASPIRIN, receptor, n_library=4, dock_top=2, admet_model="eos2ta5"
    )
    assert rep.admet_engine == "local"


def test_pipeline_report_pdf_bytes(offline, receptor):
    rep = ap.run_auto_pipeline(
        ASPIRIN, receptor, n_library=4, dock_top=2, model=FakeModel()
    )
    assert isinstance(rep.report_pdf, (bytes, type(None)))
    assert rep.report_pdf  # الخطوط متوفرة في هذا المستودع — PDF يُبنى فعلاً


def test_pipeline_empty_seed_raises(receptor):
    with pytest.raises(ValueError):
        ap.run_auto_pipeline("   ", receptor)


def test_pipeline_prefilter_blocks_fat_molecule(offline, receptor):
    """بذرة ضخمة تفشل ADME المحلي → لا ربط ولا نتائج — القمع يوثّق ذلك."""
    rep = ap.run_auto_pipeline(
        FAT, receptor, n_library=4, dock_top=2, model=FakeModel()
    )
    assert rep.funnel["ADME المحلي"] == 0
    assert rep.results == []
    assert rep.best_smiles == ""
    assert rep.best_vina is None
    assert rep.funnel["أُربط بـVina"] == 0


def test_pipeline_funnel_keys(offline, receptor):
    rep = ap.run_auto_pipeline(
        ASPIRIN, receptor, n_library=4, dock_top=2, model=FakeModel()
    )
    assert {"المكتبة", "ADME المحلي", "أُربط بـVina", "اجتاز ADMET"} <= set(rep.funnel)


def test_pipeline_no_model_no_crash(offline, receptor, monkeypatch):
    """model=None + فشل تدريب الافتراضي → تقرير None والخط يكتمل."""

    def boom():
        raise RuntimeError("no model here")

    monkeypatch.setattr("core.capstone._default_model", boom)
    rep = ap.run_auto_pipeline(ASPIRIN, receptor, n_library=4, dock_top=2)
    assert rep.results
    assert rep.report_pdf is None
