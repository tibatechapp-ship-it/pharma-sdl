"""اختبارات مقاييس صدق الأهداف — P7: الجودة تُقاس وتُنشر ولا تُدَّعى.

نطاق الاختبار:
    - البروتوكول نفسه (scaffold مزدوج، بلا تسريب، حتمية البذرة).
    - سلامة الأرشيف المنشور data/tibb-quality.json (بصمات تطابق البيانات).
    - الـAPI يقرأ الأرشيف كما هو — viewer يقرأ، بلا مفتاح 401.
"""

from __future__ import annotations

import json

import numpy as np
import pytest

from pharma_sdl.prophetic import TARGETS
from pharma_sdl.quality import (
    QUALITY_ARTIFACT,
    load_published_quality,
    measure_target_quality,
)
from pharma_sdl.splits import scaffold_split_indices

# ── البروتوكول: القياس بحد ذاته ──


def test_measure_rejects_untrained_target():
    """هدف خارج السجل يُرفض — لا قياس لهدف غير مُدرّب."""
    with pytest.raises(ValueError, match="CHEMBL999"):
        measure_target_quality("CHEMBL999", n_estimators=20)


def test_measure_mpro_small_honest_shapes():
    """قياس مصغّر على Mpro: الأحجام تتجمع صح والمقاييس في مداها المنطقي."""
    q = measure_target_quality("CHEMBL4523582", n_estimators=20)
    assert q.n_rows == 900
    assert q.n_fit + q.n_calib + q.n_test <= q.n_rows
    assert q.n_test == 900 - q.n_fit - q.n_calib
    assert q.n_scaffolds > q.n_rows // 3  # بيانات Mpro متنوعة الهياكل
    assert -1.0 <= q.r2 <= 1.0
    assert q.mae > 0 and q.rmse >= q.mae  # RMSE ≥ MAE بتعريف
    assert 0.0 <= q.measured_coverage <= 1.0
    assert q.nominal_coverage == 0.9
    assert q.finite_sample_guarantee is True
    assert q.dataset_fingerprint.startswith("sha256:")
    assert q.code_version  # بصمة الكود مسجلة


@pytest.mark.parametrize("tid", ["CHEMBL220", "CHEMBL203"])
def test_measure_expanded_targets(tid):
    """الأهداف الموسعة تُقاس بذات البروتوكول — بلا استثناء."""
    q = measure_target_quality(tid, n_estimators=20)
    assert q.target_id == tid
    assert q.n_rows == 900
    assert -1.0 <= q.r2 <= 1.0
    assert 0.0 <= q.measured_coverage <= 1.0
    assert q.q_hat > 0


def test_measure_seed_deterministic():
    """البذرة نفسها → القياس نفسه حرفياً — عقد الحتمية عام كالفرز."""
    a = measure_target_quality("CHEMBL4523582", n_estimators=20, seed=3)
    b = measure_target_quality("CHEMBL4523582", n_estimators=20, seed=3)
    assert a.r2 == b.r2 and a.mae == b.mae and a.rmse == b.rmse
    assert a.q_hat == b.q_hat and a.measured_coverage == b.measured_coverage
    assert (a.n_fit, a.n_calib, a.n_test) == (b.n_fit, b.n_calib, b.n_test)


def test_no_scaffold_leakage_in_protocol():
    """البروتوكول بلا تسريب: اختبار القياس لا يشترك هيكلاً مع الملاءمة.

    نعيد تقسيم البروتوكول نفسه (نفس البذور) ونتحقق أن أي تقاطع هيكلي بين
    fit وtest مستحيل — المرآة المباشرة لوعود splits.py.
    """
    import pandas as pd

    from pharma_sdl.prophetic import MPRO_TARGET
    from pharma_sdl.splits import murcko_scaffold

    df = pd.read_csv(MPRO_TARGET.dataset_path).dropna(
        subset=["smiles", "pchembl_value"]
    )
    smiles = df["smiles"].astype(str).tolist()
    idx_pool, idx_test = scaffold_split_indices(smiles, seed=0, test_size=0.2)
    pool_smiles = [smiles[i] for i in idx_pool]
    idx_fit_local, _ = scaffold_split_indices(pool_smiles, seed=1, test_size=0.25)
    idx_fit = idx_pool[idx_fit_local]

    scf = [murcko_scaffold(s) for s in smiles]
    fit_scaffolds = {scf[i] for i in idx_fit}
    test_scaffolds = {scf[i] for i in idx_test}
    assert fit_scaffolds.isdisjoint(test_scaffolds)  # صفر تسريب هياكل
    assert len(idx_fit) + len(idx_test) <= len(smiles)


# ── الأرشيف المنشور — سلامة قبل العرض ──


def test_published_artifact_exists_and_complete():
    """الأرشيف منشور ويغطي الأهداف الثلاثة ببروتوكول كامل."""
    assert QUALITY_ARTIFACT.exists()
    artifact = load_published_quality()
    assert set(artifact.keys()) >= {
        "protocol",
        "note_ar",
        "note_en",
        "measured_on",
        "code_version",
        "targets",
    }
    ids = [t["target_id"] for t in artifact["targets"]]
    assert set(ids) == set(TARGETS)  # الأهداف الثلاثة كلها
    assert len(ids) == len(set(ids))  # بلا تكرار


def test_published_fingerprints_match_data_files():
    """بصمة كل هدف في الأرشيف تطابق بصمة ملف بياناته الحقيقي — لا قياس قديم."""
    from pharma_sdl.experiments.registry import dataset_fingerprint

    artifact = load_published_quality()
    for t in artifact["targets"]:
        spec = TARGETS[t["target_id"]]
        assert t["dataset_fingerprint"] == dataset_fingerprint(spec.dataset_path), (
            f"بصمة {t['target_id']} في الأرشيف لا تطابق ملف البيانات — "
            f"القياس قديم، أعد scripts/measure_tibb_quality.py"
        )


def test_published_metrics_within_plausible_ranges():
    """أرقام الأرشيف في مداها المنطقي — لا NaN ولا قيم خارجة."""
    artifact = load_published_quality()
    for t in artifact["targets"]:
        assert np.isfinite(t["r2"]) and -1.0 <= t["r2"] <= 1.0
        assert np.isfinite(t["mae"]) and t["mae"] > 0
        assert np.isfinite(t["rmse"]) and t["rmse"] >= t["mae"]
        assert 0.0 <= t["measured_coverage"] <= 1.0
        assert t["n_rows"] == 900 and t["n_estimators"] == 300
        assert t["seed"] == 0 and t["nominal_coverage"] == 0.9


# ── الـAPI — الأرشيف للقراءة حصراً ──


@pytest.fixture(autouse=True)
def isolated_platform(monkeypatch, tmp_path):
    """منصة معزولة لكل اختبار — سجل وطابور على قواعد مؤقتة."""
    import os

    from pharma_sdl.api import deps
    from pharma_sdl.api.deps import app_settings
    from pharma_sdl.config import reset_settings
    from pharma_sdl.jobs import reset_job_store

    monkeypatch.setenv("PHARMA_SDL_EXPERIMENTS_DB", str(tmp_path / "exp.sqlite3"))
    monkeypatch.setenv("PHARMA_SDL_JOBS_DB", str(tmp_path / "jobs.sqlite3"))
    monkeypatch.setenv("PHARMA_SDL_STORE", "sqlite")
    os.environ["PHARMA_SDL_API_KEYS"] = (
        "viewer-1:vk-viewer:viewer,scientist-1:sk-sci:scientist"
    )
    reset_settings()
    app_settings.cache_clear()
    deps._registry = None
    reset_job_store()
    yield
    reset_job_store()
    reset_settings()
    app_settings.cache_clear()
    deps._registry = None


def test_quality_requires_auth():
    """بلا مفتاح → 401 — لا مقاييس مجهولة المصدر."""
    from fastapi.testclient import TestClient

    from pharma_sdl.api.app import create_app

    client = TestClient(create_app())
    assert client.get("/api/v1/tibb/quality").status_code == 401


def test_viewer_reads_published_quality_as_is():
    """القارئ يرى الأرشيف كما هو — الأرقام المنشورة حرفياً بلا حساب حي."""
    from fastapi.testclient import TestClient

    from pharma_sdl.api.app import create_app

    client = TestClient(create_app())
    out = client.get("/api/v1/tibb/quality", headers={"X-API-Key": "vk-viewer"})
    assert out.status_code == 200
    body = out.json()
    published = json.loads(QUALITY_ARTIFACT.read_text(encoding="utf-8"))
    assert [t["r2"] for t in body["targets"]] == [
        t["r2"] for t in published["targets"]
    ]
    assert body["measured_on"] == published["measured_on"]
    assert len(body["targets"]) == 3
    # ملاحظة الحدود الصادقة تصل للعميل دائماً
    assert "UNVALIDATED" in body["note_en"]
