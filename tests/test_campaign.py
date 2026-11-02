"""اختبارات حملة التعلم المغلقة — الحزمة Q4: التعلم من النتائج بذاكرة (P4)."""

from __future__ import annotations

import itertools
import json

import pytest

from pharma_sdl.campaign import run_campaign
from pharma_sdl.experiments.registry import ExperimentRegistry

QUICK = {
    "initial_labeled": 30,
    "batch_size": 4,
    "rounds": 2,
    "n_estimators": 25,
}


def _quick(**overrides):
    params = {**QUICK, **overrides}
    return run_campaign(**params)


def test_campaign_structure_and_monotone_discovery():
    report = _quick(strategy="greedy", seed=0)
    assert report.strategy == "greedy"
    assert len(report.rounds) == QUICK["rounds"]
    assert len(report.cumulative_best_curve) == QUICK["rounds"] + 1
    # «أفضل مكتشف» تراكمي لا ينقص أبداً — بحكم البناء
    curve = report.cumulative_best_curve
    assert all(a <= b for a, b in itertools.pairwise(curve))
    assert report.final_best_true == curve[-1]
    # كل دفعة بحجمها المطلوب (المخزون أكبر من الدفعة في هذا الإعداد)
    for rnd in report.rounds:
        assert len(rnd.batch) == QUICK["batch_size"]
        assert rnd.n_labeled > 0
        assert 0.0 <= rnd.conformal_coverage_empirical <= 1.0
        assert set(rnd.test_metrics) >= {"r2", "mae", "rmse"}
        # كل صف دفعة يحمل تنبؤه وفترته وحقيقته — لا صف عاري
        for row in rnd.batch:
            assert {"smiles", "predicted_pic50", "tree_std", "interval_lo",
                    "interval_hi", "true_pic50"} <= set(row)
    # إخلاء المسؤولية يسافر مع التقرير
    assert "UNVALIDATED" in report.disclaimer_en
    assert "in-silico" in report.disclaimer_en or "in_silico" in report.disclaimer_en


def test_campaign_deterministic_with_same_seed():
    a = _quick(strategy="ucb", seed=3)
    b = _quick(strategy="ucb", seed=3)
    # runtime_seconds قياس حائط لا حتمية نموذج — يُستبعد من المقارنة البايتية
    # (كشفه CI 2026-11-02: نفس البذرة أعطت 0.4 و0.5 ثانية فقط، وكل القيم
    # العلمية متطابقة بايت-ببايت)
    da, db = a.model_dump(), b.model_dump()
    da.pop("runtime_seconds", None)
    db.pop("runtime_seconds", None)
    assert da == db


def test_campaign_different_strategies_differ():
    r = _quick(strategy="random", seed=1)
    g = _quick(strategy="greedy", seed=1)
    assert r.strategy != g.strategy
    # الدفعات الفعلية مختلفة (الترتيب بينهما قد يصادف — فنقارن المجموعات الكلية)
    smiles_r = [row["smiles"] for rnd in r.rounds for row in rnd.batch]
    smiles_g = [row["smiles"] for rnd in g.rounds for row in rnd.batch]
    assert smiles_r != smiles_g


def test_unknown_strategy_rejected():
    with pytest.raises(ValueError):
        _quick(strategy="magic")


def test_invalid_config_rejected():
    with pytest.raises(ValueError):
        _quick(rounds=0)
    with pytest.raises(ValueError):
        _quick(initial_labeled=5)
    with pytest.raises(ValueError):
        _quick(batch_size=0)


def test_campaign_logs_rounds_to_registry_with_parent_chain(tmp_path):
    """الذاكرة الحية: كل جولة سجل مكتمل بسلسلة أسلاف وحالة UNVALIDATED."""
    registry = ExperimentRegistry(tmp_path / "camp.sqlite3")
    _quick(strategy="uncertainty", seed=2, registry=registry)
    rounds = [r for r in registry.latest(limit=100) if r.kind == "learning_round"]
    assert len(rounds) == QUICK["rounds"]
    # سلسلة الأسلاف: من آخر جولة نصل للجذر عبر parent_experiment_id — الحلقة تقرأ سابقتها
    last_record = max(rounds, key=lambda r: r.parameters.get("round", 0))
    chain = registry.lineage(last_record.experiment_id)
    assert len(chain) == QUICK["rounds"]  # الجولتان كلتاهما في السلسلة
    assert chain[0].parent_experiment_id is None  # الجذر
    assert all(r.validation_state == "UNVALIDATED" for r in chain)
    assert all(r.engine_used == "sklearn-rf" for r in chain)
    assert all("active_learning/" in (r.method or "") for r in chain)
    assert all(r.parameters["oracle"] == "in_silico_dataset_truth" for r in chain)
    assert all(r.status == "completed" for r in chain)


def test_report_serializes_cleanly_to_json(tmp_path):
    report = _quick(strategy="random", seed=5)
    text = report.model_dump_json()
    back = json.loads(text)
    assert back["strategy"] == "random"
    assert back["dataset_fingerprint"].startswith("sha256:")
    assert back["config"]["test_split"] == "scaffold_bemis_murcko"
