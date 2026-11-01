"""اختبارات خط التنقية — الأسباب موثقة والسياسة محكومة."""

from __future__ import annotations

from pharma_sdl.curation.loader import load_ligands_inline
from pharma_sdl.curation.pipeline import run_curation
from pharma_sdl.models import LigandInput
from pharma_sdl.targets.registry import get_target

ACRYLAMIDE = "C=CC(=O)Nc1ccccc1"
CAFFEINE = "Cn1cnc2c1c(=O)n(C)c(=O)n2C"
BENZAMIDE = "O=C(N)c1ccccc1"
RHODANINE = "O=C1NC(=S)SC1=C1C=CC=CC=C1"  # رودانين عطري — PAINS ene_rhod


def _rows():
    return [
        LigandInput(name="caféine", smiles=CAFFEINE),
        LigandInput(name="benzamide", smiles=BENZAMIDE),
        LigandInput(name="caféine-mirror", smiles="Cn1c(=O)c2c(ncn2C)n(C)c1=O"),  # تكرار
        LigandInput(name="bad", smiles="not-a-smiles"),
        LigandInput(name="acrylamide-trap", smiles=ACRYLAMIDE),
    ]


def test_curation_rejects_covalent_under_mpro_policy():
    policy = get_target("7VH8_A").policy
    report = run_curation(_rows(), policy)
    by_stage = {}
    for r in report.rejected:
        by_stage.setdefault(r.stage, []).append(r)
    assert len(by_stage.get("covalent_gate", [])) == 1
    rejection = by_stage["covalent_gate"][0]
    assert "تساهم" in rejection.reason_ar
    kept_names = {c.name for c in report.kept}
    assert "acrylamide-trap" not in kept_names
    assert {"caféine", "benzamide"} <= kept_names


def test_curation_counts_are_consistent():
    report = run_curation(_rows(), get_target("7VH8_A").policy)
    assert report.counts["input"] == 5
    assert report.counts["kept"] == len(report.kept)
    assert report.counts["kept"] + report.counts["rejected"] == report.counts["input"]
    assert report.counts["duplicates_removed"] == 1


def test_curation_keeps_covalent_when_policy_allows():
    from pharma_sdl.targets.models import TargetPolicy

    permissive = TargetPolicy(non_covalent_only=False, reason_ar="اختبار", reason_en="test")
    report = run_curation(_rows(), permissive)
    kept_names = {c.name for c in report.kept}
    assert "acrylamide-trap" in kept_names  # يُحفظ لكن الأعلام تبقى موثقة
    trap = next(c for c in report.kept if c.name == "acrylamide-trap")
    assert "acrylamide" in trap.warhead_alerts


def test_curation_reject_pains_option():
    # الكاتيكول: PAINS (catechol) وليس رأساً تساهمياً — عزل نقي لمرحلة pains
    rows = _rows() + [LigandInput(name="catechol", smiles="Oc1ccccc1O")]
    report = run_curation(rows, get_target("7VH8_A").policy, reject_pains=True)
    pains = [r for r in report.rejected if r.stage == "pains"]
    assert any(r.name == "catechol" for r in pains)


def test_curation_flags_documented_not_deleted():
    report = run_curation(_rows(), get_target("7VH8_A").policy)
    for lig in report.kept:
        assert isinstance(lig.lipinski_flags, list)
        assert isinstance(lig.pains_alerts, list)


def test_empty_input_raises():
    import pytest

    from pharma_sdl.errors import ValidationError

    with pytest.raises(ValidationError):
        run_curation([], get_target("7VH8_A").policy)


def test_inline_loader_validates():
    rows = load_ligands_inline([{"name": "x", "smiles": BENZAMIDE}])
    assert isinstance(rows[0], LigandInput)
