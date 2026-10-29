"""اختبارات التوليد الموجّه بالهدف (S9) — كلها offline بلا شبكة ولا مفتاح.

المكافئ المحلي لـ ChatChemTS/ChemTSv2: نفس أمر الجناح
pytest -m "not integration and not slow" — بلا TensorFlow وبلا اعتماديات جديدة.
"""
from __future__ import annotations

import pytest
from rdkit import Chem

from core.goalgen import (
    ENGINE,
    KNOWN_VIOLATIONS,
    REASON_INVALID,
    REASON_NO_SURVIVORS,
    GoalSpec,
    _violations,
    generate_toward_goal,
)

ASPIRIN = "CC(=O)OC1=CC=CC=C1C(=O)O"


@pytest.fixture(scope="module")
def report():
    """تقرير واحد لكل وحدة — المحرك حتمي فلا يتغير بين الاختبارات."""
    return generate_toward_goal(ASPIRIN, rounds=3, pool_per_round=40, top_keep=5)


# ── العقود الأساسية ──────────────────────────────────────────


def test_invalid_seed_returns_reason():
    r = generate_toward_goal("NOT_SMILES")
    assert r.reason == REASON_INVALID
    assert r.survivors == ()
    assert r.pool_size == 0


def test_empty_seed_returns_reason():
    r = generate_toward_goal("   ")
    assert r.reason == REASON_INVALID


def test_valid_seed_produces_survivors(report):
    assert report.reason is None
    assert len(report.survivors) >= 1


def test_engine_documented(report):
    assert report.engine == ENGINE == "local-brics-directed"


def test_seed_recorded_canonical(report):
    assert Chem.MolToSmiles(Chem.MolFromSmiles(ASPIRIN)) == report.seed


# ── جودة الناجين ────────────────────────────────────────────


def test_survivors_are_valid_smiles(report):
    for c in report.survivors:
        assert Chem.MolFromSmiles(c.smiles) is not None, c.smiles


def test_survivors_respect_goal(report):
    g = report.goal
    for c in report.survivors:
        assert g.mw_min <= c.mw <= g.mw_max
        assert c.logp <= g.logp_max
        assert c.tpsa <= g.tpsa_max
        assert c.hbd <= g.hbd_max
        assert c.hba <= g.hba_max
        assert c.sim >= g.sim_floor
        assert c.qed >= g.qed_min
        assert not c.violations


def test_survivors_deduplicated(report):
    smiles = [c.smiles for c in report.survivors]
    assert len(smiles) == len(set(smiles))
    assert ASPIRIN not in smiles  # البذرة نفسها تُستبعد دائماً


def test_survivors_sorted_by_reward(report):
    rewards = [c.reward for c in report.survivors]
    assert rewards == sorted(rewards, reverse=True)


def test_reward_and_components_in_unit_range(report):
    for c in report.survivors:
        assert 0.0 <= c.reward <= 1.0
        assert 0.0 <= c.sim <= 1.0
        assert 0.0 <= c.qed <= 1.0


def test_pool_bounded_by_rounds(report):
    assert report.rounds_run <= 3
    assert report.pool_size <= 3 * 40


# ── الحتمية والسلوك الحدي ───────────────────────────────────


def test_deterministic():
    a = generate_toward_goal(ASPIRIN, rounds=2, pool_per_round=30, top_keep=4)
    b = generate_toward_goal(ASPIRIN, rounds=2, pool_per_round=30, top_keep=4)
    assert [c.smiles for c in a.survivors] == [c.smiles for c in b.survivors]
    assert a.pool_size == b.pool_size


def test_impossible_goal_reports_no_survivors():
    """تشابه 0.95 مستحيل لغير البذرة (المستبعدة) → لا ناجين بلا انهيار."""
    strict = GoalSpec(sim_floor=0.95)
    r = generate_toward_goal(ASPIRIN, goal=strict)
    assert r.survivors == ()
    assert r.reason == REASON_NO_SURVIVORS
    assert r.pool_size > 0  # القياس حدث فعلاً ولم يختصر


# ── مفاتيح المخالفات ────────────────────────────────────────


def test_known_violations_keys():
    assert KNOWN_VIOLATIONS == frozenset(
        {"mw_low", "mw_high", "logp", "tpsa", "hbd", "hba", "sim", "qed"}
    )


def test_violations_mapping():
    spec = GoalSpec(mw_min=300, mw_max=400, logp_max=3, tpsa_max=90,
                    hbd_max=2, hba_max=6, sim_floor=0.4, qed_min=0.5)
    assert _violations(spec, 250, 4, 50, 1, 3, 0.7, 0.5) == ("mw_low", "logp")
    assert _violations(spec, 450, 4, 100, 3, 7, 0.4, 0.3) == (
        "mw_high", "logp", "tpsa", "hbd", "hba", "sim", "qed",
    )
    assert _violations(spec, 350, 2, 60, 1, 4, 0.8, 0.6) == ()
