"""اختبارات API التجارب والاعتماد + النقل JSONL (P2، تقييم #3/#4)."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from pharma_sdl.api.app import create_app
from pharma_sdl.experiments.portability import export_jsonl, import_jsonl
from pharma_sdl.experiments.registry import ExperimentRecord, ExperimentRegistry
from pharma_sdl.validation.gate import ValidationState


@pytest.fixture(autouse=True)
def isolated_registry(monkeypatch, tmp_path):
    """سجل تجريبي معزول لكل اختبار — المفردات تُبنى على قاعدة مؤقتة."""
    from pharma_sdl.api import deps
    from pharma_sdl.api.deps import app_settings
    from pharma_sdl.config import reset_settings

    monkeypatch.setenv("PHARMA_SDL_EXPERIMENTS_DB", str(tmp_path / "exp.sqlite3"))
    monkeypatch.setenv("PHARMA_SDL_JOBS_DB", str(tmp_path / "jobs.sqlite3"))
    reset_settings()
    app_settings.cache_clear()
    deps._registry = None
    yield
    reset_settings()
    app_settings.cache_clear()
    deps._registry = None


def _seed(registry: ExperimentRegistry) -> ExperimentRecord:
    record = ExperimentRecord(
        hypothesis_ar="أفضل مرشحي المكتبة نقطة انطلاق معتدة",
        question="ما ترتيب المكتبة؟",
        target_id="7VH8_A",
        engine_used="simulation",
    )
    registry.begin(record)
    registry.complete(
        record.experiment_id,
        counts={"input": 2, "screened": 2},
        top_hits=[
            {"rank": 1, "name": "a", "smiles": "CCO", "kcal": -3.1},
            {"rank": 2, "name": "b", "smiles": "CCC", "kcal": -2.9},
        ],
        lesson="خط أساس موثق",
    )
    return record


def test_experiments_endpoints_read_memory(tmp_path):
    db = tmp_path / "exp.sqlite3"
    registry = ExperimentRegistry(db)
    record = _seed(registry)
    client = TestClient(create_app())
    listed = client.get("/api/v1/experiments")
    assert listed.status_code == 200
    ids = [e["experiment_id"] for e in listed.json()]
    assert record.experiment_id in ids
    full = client.get(f"/api/v1/experiments/{record.experiment_id}")
    assert full.status_code == 200
    assert full.json()["hypothesis_ar"] == "أفضل مرشحي المكتبة نقطة انطلاق معتدة"
    assert full.json()["top_hits"][0]["smiles"] == "CCO"
    lineage = client.get(f"/api/v1/experiments/{record.experiment_id}/lineage")
    assert lineage.status_code == 200
    assert len(lineage.json()) == 1
    missing = client.get("/api/v1/experiments/no-such-id")
    assert missing.status_code == 404


def test_validation_card_roundtrip_persists_history(tmp_path):
    db = tmp_path / "exp.sqlite3"
    registry = ExperimentRegistry(db)
    record = _seed(registry)
    client = TestClient(create_app())
    base = f"/api/v1/experiments/{record.experiment_id}"
    # البداية: بطاقة افتراضية صادقة UNVALIDATED بلا تاريخ مُختلق
    card = client.get(f"{base}/validation").json()
    assert card["state"] == "UNVALIDATED"
    assert card["history"] == []
    # ترقيتان مشروعتان مع مرفقات الحالة التجريبية
    assert client.post(
        f"{base}/validation/promote",
        json={"to": "COMPUTATIONALLY_VALIDATED", "reason": "فحوص موثقة", "actor": "ق1"},
    ).status_code == 200
    assert client.post(
        f"{base}/validation/promote",
        json={"to": "EXPERIMENTALLY_SUPPORTED", "reason": "FRET", "actor": "ق1",
              "assay_ref": "assay-9"},
    ).status_code == 200
    # البطاقة المحفوظة تحمل التاريخ كاملاً — «لماذا رُقّيت؟» من السجل
    card = client.get(f"{base}/validation").json()
    assert card["state"] == "EXPERIMENTALLY_SUPPORTED"
    assert len(card["history"]) == 2
    assert card["history"][1]["assay_ref"] == "assay-9"
    # والسجل يحمل البطاقة مع التجربة نفسها
    stored = registry.get(record.experiment_id)
    assert stored.validation_card is not None
    assert stored.validation_state == ValidationState.EXPERIMENTALLY_SUPPORTED.value
    # إعادة تشغيل (نسخة سجل جديدة) لا تفقد البطاقة
    reopened = ExperimentRegistry(db)
    reopened_card = reopened.validation_card_of(record.experiment_id)
    assert reopened_card.state is ValidationState.EXPERIMENTALLY_SUPPORTED
    assert len(reopened_card.history) == 2


def test_portability_export_import_roundtrip(tmp_path):
    src = tmp_path / "src.sqlite3"
    registry = ExperimentRegistry(src)
    parent = _seed(registry)
    child = ExperimentRecord(
        hypothesis_ar="جولة استكشاف تقرأ الأب",
        target_id="7VH8_A",
        parent_experiment_id=parent.experiment_id,
    )
    registry.begin(child)
    registry.complete(child.experiment_id, counts={"input": 1, "screened": 1})

    jsonl = tmp_path / "export.jsonl"
    count = export_jsonl(registry, jsonl)
    assert count == 2
    lines = jsonl.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    assert all(json.loads(line)["experiment_id"] for line in lines)  # كل سطر تجربة كاملة

    # قاعدة هدف جديدة فارغة → الاستيراد يحفظ المعرّفات وسلسلة الأسلاف
    dst = ExperimentRegistry(tmp_path / "dst.sqlite3")
    imported = import_jsonl(dst, jsonl)
    assert imported == 2
    chain = dst.lineage(child.experiment_id)
    assert [r.experiment_id for r in chain] == [parent.experiment_id, child.experiment_id]
    # إعادة الاستيراد آمنة (التكرار يُتخطى) — وبالإجبار يكتب
    assert import_jsonl(dst, jsonl) == 0
    assert import_jsonl(dst, jsonl, overwrite=True) == 2


def test_portability_rejects_corrupt_line(tmp_path):
    registry = ExperimentRegistry(tmp_path / "exp.sqlite3")
    bad = tmp_path / "bad.jsonl"
    bad.write_text('{"experiment_id": "x"}\n', encoding="utf-8")  # بلا فرضية — سجل غير صالح
    from pharma_sdl.errors import ValidationError

    with pytest.raises(ValidationError):
        import_jsonl(registry, bad)
