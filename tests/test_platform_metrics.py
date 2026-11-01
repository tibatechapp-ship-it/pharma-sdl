"""اختبارات المقاييس التشغيلية (P3) — عدّادات صادقة تطابق المخازن لحظة الطلب."""

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from pharma_sdl.api.app import create_app
from pharma_sdl.experiments.registry import ExperimentRecord, ExperimentRegistry


@pytest.fixture(autouse=True)
def isolated_platform(monkeypatch, tmp_path):
    from pharma_sdl.api import deps
    from pharma_sdl.api.deps import app_settings
    from pharma_sdl.config import reset_settings
    from pharma_sdl.jobs import reset_job_store

    monkeypatch.setenv("PHARMA_SDL_EXPERIMENTS_DB", str(tmp_path / "exp.sqlite3"))
    monkeypatch.setenv("PHARMA_SDL_JOBS_DB", str(tmp_path / "jobs.sqlite3"))
    monkeypatch.setenv("PHARMA_SDL_STORE", "sqlite")
    reset_settings()
    app_settings.cache_clear()
    deps._registry = None
    reset_job_store()
    yield
    reset_job_store()
    reset_settings()
    app_settings.cache_clear()
    deps._registry = None


def test_metrics_counts_match_registry_honestly():
    from pharma_sdl.api.deps import app_settings

    db_path = app_settings().experiments_db
    registry = ExperimentRegistry(db_path)

    done = ExperimentRecord(hypothesis_ar="أ", target_id="7VH8_A", engine_used="simulation")
    registry.begin(done)
    registry.complete(done.experiment_id, counts={"input": 1}, top_hits=[])

    failed = ExperimentRecord(hypothesis_ar="ب", target_id="7VH8_A", engine_used="simulation")
    registry.begin(failed)
    registry.fail(failed.experiment_id, "ValueError: خطأ موثق")

    client = TestClient(create_app())
    out = client.get("/api/v1/metrics")
    assert out.status_code == 200
    data = out.json()
    assert data["experiments_by_status"] == {"completed": 1, "failed": 1}
    assert data["experiments_by_validation_state"] == {"UNVALIDATED": 2}
    assert data["registry_backend"] == "sqlite"
    assert data["auth_mode"] == "open"
    assert "simulation" in data["engines_available"]
    assert data["version"]

    # مهمة حقيقية واحدة تُحتسب مكتملة
    from pharma_sdl.api.deps import job_store

    job = job_store().submit("screening", lambda: {"ok": True})
    deadline = time.time() + 15
    while time.time() < deadline:
        if job_store().get(job.id).status in {"done", "failed"}:
            break
        time.sleep(0.05)
    refreshed = client.get("/api/v1/metrics").json()
    assert refreshed["jobs_by_status"].get("done") == 1


def test_metrics_reports_postgres_backend_label(monkeypatch):
    """التسمية صادقة مع الإعدادات حتى حين لا يُستعلام المخزن فعلياً هنا."""
    from pharma_sdl.api import deps
    from pharma_sdl.api.deps import app_settings
    from pharma_sdl.config import reset_settings

    monkeypatch.setenv("PHARMA_SDL_STORE", "postgres")
    monkeypatch.setenv("PHARMA_SDL_PG_DSN", "postgresql://user:pass@localhost:59999/db")
    reset_settings()
    app_settings.cache_clear()
    deps._registry = None
    try:
        client = TestClient(create_app())
        # /health يعلن الخلفية المُعدّة — بلا اتصال (التسمية من الإعدادات لا ادعاء عمل)
        health = client.get("/api/v1/health").json()
        assert health["store_backend"] == "postgres"
        # /metrics يستدعي المخزن فعلاً → فشل صريح مترجم (لا انهيار غامض)
        out = client.get("/api/v1/metrics")
        assert out.status_code == 503
        assert out.json()["code"] == "store_unavailable"
    finally:
        monkeypatch.delenv("PHARMA_SDL_STORE", raising=False)
        monkeypatch.delenv("PHARMA_SDL_PG_DSN", raising=False)
        reset_settings()
        app_settings.cache_clear()
        deps._registry = None


def test_health_announces_store_backend_default():
    client = TestClient(create_app())
    health = client.get("/api/v1/health").json()
    assert health["store_backend"] == "sqlite"
