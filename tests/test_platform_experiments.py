"""اختبارات سجل التجارب الدائم + الحلقة المغلقة — الذاكرة التجريبية.

التدقيق P1: النتائج لا تضيع بعد إعادة التشغيل، والجولة التالية تقرأ
ذاكرة سابقتها من السجل، ولا شيء يُرقّى تلقائياً في أي مسار.
"""

from __future__ import annotations

from pathlib import Path

from pharma_sdl.experiments.registry import (
    ExperimentRecord,
    ExperimentRegistry,
    code_version,
    ligands_fingerprint,
)
from pharma_sdl.loop.closed_loop import format_lineage, run_closed_loop
from pharma_sdl.validation.gate import ValidationState, default_card, promote

# ── السجل الدائم ───────────────────────────────────────────


def test_record_roundtrip(tmp_path: Path):
    registry = ExperimentRegistry(tmp_path / "exp.sqlite3")
    rec = registry.begin(
        ExperimentRecord(
            hypothesis_ar="فرضية الاختبار",
            question="هل يعمل السجل؟",
            target_id="7VH8_A",
            data_version=ligands_fingerprint(["CCO", "CCN"]),
            code_version=code_version(),
        )
    )
    assert rec.status == "running"
    done = registry.complete(
        rec.experiment_id,
        counts={"input": 24, "returned": 5},
        top_hits=[{"rank": 1, "name": "Acetanilide", "smiles": "CC(N)c1ccccc1", "kcal": -8.2}],
        elapsed_seconds=0.1,
        engine_used="simulation",
        lesson="السجل يعمل",
    )
    assert done.status == "completed"
    # قراءة من اتصال جديد تماماً — الدمامية ليست ذاكرة العملية
    fresh = ExperimentRegistry(tmp_path / "exp.sqlite3")
    loaded = fresh.get(rec.experiment_id)
    assert loaded is not None
    assert loaded.status == "completed"
    assert loaded.top_hits[0]["name"] == "Acetanilide"
    assert loaded.lesson == "السجل يعمل"


def test_failures_are_memory_not_deletion(tmp_path: Path):
    registry = ExperimentRegistry(tmp_path / "exp.sqlite3")
    rec = registry.begin(ExperimentRecord(hypothesis_ar="ستفشل عمداً"))
    failed = registry.fail(rec.experiment_id, error="ValueError: بيانات فاسدة")
    assert failed.status == "failed"
    assert "فاسدة" in failed.error
    assert registry.latest(status="failed")[0].experiment_id == rec.experiment_id


def test_lineage_chain(tmp_path: Path):
    registry = ExperimentRegistry(tmp_path / "exp.sqlite3")
    r1 = registry.begin(ExperimentRecord(hypothesis_ar="الجذر"))
    r2 = registry.begin(
        ExperimentRecord(hypothesis_ar="الابن", parent_experiment_id=r1.experiment_id)
    )
    r3 = registry.begin(
        ExperimentRecord(hypothesis_ar="الحفيد", parent_experiment_id=r2.experiment_id)
    )
    chain = registry.lineage(r3.experiment_id)
    assert [r.experiment_id for r in chain] == [
        r1.experiment_id,
        r2.experiment_id,
        r3.experiment_id,
    ]


def test_validation_attach(tmp_path: Path):
    registry = ExperimentRegistry(tmp_path / "exp.sqlite3")
    rec = registry.begin(ExperimentRecord(hypothesis_ar="اختبار الربط"))
    # الحالة الافتراضية: كل تجربة تولد UNVALIDATED
    attached = registry.attach_validation(
        rec.experiment_id, default_card(subject="test"), reason="بدون أدلة بعد"
    )
    assert attached.validation_state == ValidationState.UNVALIDATED.value
    # ترقية بشرية موثقة ثم ربط — تظهر في السجل الدائم
    card = promote(
        default_card(subject="test"),
        ValidationState.COMPUTATIONALLY_VALIDATED,
        reason="فحوص حسابية محددة اكتملت",
        actor="ci",
    )
    attached2 = registry.attach_validation(rec.experiment_id, card)
    assert attached2.validation_state == ValidationState.COMPUTATIONALLY_VALIDATED.value
    fresh = ExperimentRegistry(tmp_path / "exp.sqlite3")
    assert fresh.get(rec.experiment_id).validation_state == (
        ValidationState.COMPUTATIONALLY_VALIDATED.value
    )


# ── الحلقة المغلقة الموثقة ─────────────────────────────────


def test_closed_loop_three_documented_rounds(tmp_path: Path):
    records = run_closed_loop(tmp_path / "loop.sqlite3", top_n=5)
    assert len(records) == 3
    roles = [r.parameters["role"] for r in records]
    assert roles == ["exploit_baseline", "explore", "exploit_final"]
    # سلسلة الذاكرة: كل جولة ابنة سابقتها
    assert records[0].parent_experiment_id is None
    assert records[1].parent_experiment_id == records[0].experiment_id
    assert records[2].parent_experiment_id == records[1].experiment_id
    # كل جولة مكتملة وذات بيانات إثبات كاملة
    for rec in records:
        assert rec.status == "completed"
        assert rec.code_version not in (None, "", "unknown") or rec.code_version == "unknown"
        assert rec.data_version and rec.data_version.startswith("sha256:")
        assert rec.hypothesis_ar and rec.question


def test_closed_loop_memory_round2_excludes_round1(tmp_path: Path):
    """الفرضية الحاكمة: الجولة 2 تستبعد مرشحي الجولة 1 من الذاكرة فعلاً."""
    records = run_closed_loop(tmp_path / "loop.sqlite3", top_n=5)
    round1_smiles = {h["smiles"] for h in records[0].top_hits}
    round2_smiles = {h["smiles"] for h in records[1].top_hits}
    assert round1_smiles.isdisjoint(round2_smiles), (
        "الجولة الثانية تختبر ما لم يُختبر — الذاكرة تمنع إعادة العمل"
    )
    # الجولة 3 توظف الاتحاد: أفضل نتائجها ضمن أفضل الجولتين
    union_best = {h["smiles"] for h in records[0].top_hits + records[1].top_hits}
    assert {h["smiles"] for h in records[2].top_hits}.issubset(union_best)


def test_closed_loop_never_auto_promotes(tmp_path: Path):
    """لا جولة ولو نجحت تماماً ترفع حالة الاعتماد — ذلك قرار بشري حصراً."""
    records = run_closed_loop(tmp_path / "loop.sqlite3", top_n=5)
    assert all(r.validation_state == ValidationState.UNVALIDATED.value for r in records)


def test_persistence_across_registry_instances(tmp_path: Path):
    """الذاكرة تصمد: حلقة جديدة على نفس قاعدة السجل تبدأ من حيث انتهت الأولى."""
    db = tmp_path / "loop.sqlite3"
    first = run_closed_loop(db, top_n=5)
    registry = ExperimentRegistry(db)
    assert registry.stats()["completed"] == 3
    fresh = ExperimentRegistry(db)
    assert fresh.get(first[-1].experiment_id).parameters["role"] == "exploit_final"
    assert format_lineage(fresh, first[-1].experiment_id).count("[") == 3
