"""اختبارات الحلقة المغلقة كخدمة (P3) — الفلسفة عبر الـAPI بلا ترقية آلية."""

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from pharma_sdl.api.app import create_app


@pytest.fixture(autouse=True)
def isolated_platform(monkeypatch, tmp_path):
    """منصة معزولة لكل اختبار — سجل وطابور على قواعد مؤقتة."""
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


def _wait_loop(client: TestClient, job_id: str, timeout_s: float = 90.0) -> dict:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        out = client.get(f"/api/v1/loop/runs/{job_id}")
        assert out.status_code == 200
        data = out.json()
        if data["status"] in ("done", "failed"):
            return data
        time.sleep(0.2)
    raise AssertionError("الحلقة لم تكتمل خلال المهلة")


def test_loop_run_end_to_end_three_chained_rounds():
    client = TestClient(create_app())
    created = client.post("/api/v1/loop/runs", json={"target_id": "7VH8_A", "top_n": 2})
    assert created.status_code == 202
    body = created.json()
    assert body["kind"] == "closed_loop"
    assert body["status"] in ("pending", "running")
    assert "UNVALIDATED" in body["note_en"]

    data = _wait_loop(client, body["job_id"])
    assert data["status"] == "done"
    rounds = data["rounds"]
    assert data["round_count"] == len(rounds) == 3
    roles = [r["parameters"]["role"] for r in rounds]
    assert roles == ["exploit_baseline", "explore", "exploit_final"]
    # سلسلة الأسلاف مكتوبة كما كُتبت
    assert rounds[0]["parent_experiment_id"] is None
    assert rounds[1]["parent_experiment_id"] == rounds[0]["experiment_id"]
    assert rounds[2]["parent_experiment_id"] == rounds[1]["experiment_id"]
    # لا ترقية آلية — كل الجولات UNVALIDATED
    assert all(r["validation_state"] == "UNVALIDATED" for r in rounds)
    # المحرك وطريقة كل نتيجة معلنان — لا غموض
    assert all(r["engine_used"] == "simulation" for r in rounds)

    # الذاكرة واحدة: سلسلة الأسلاف تُقرأ من مسار التجارب نفسه
    lineage = client.get(f"/api/v1/experiments/{rounds[2]['experiment_id']}/lineage")
    assert lineage.status_code == 200
    assert len(lineage.json()) == 3


def test_loop_memory_persists_in_platform_registry():
    """جولات الحلقة تُكتب في سجل المنصة نفسه — تُقرأ بعد انتهاء المهمة."""
    from pharma_sdl.api.deps import experiment_registry

    client = TestClient(create_app())
    created = client.post("/api/v1/loop/runs", json={"top_n": 2})
    data = _wait_loop(client, created.json()["job_id"])
    last_id = data["rounds"][-1]["experiment_id"]
    record = experiment_registry().get(last_id)
    assert record is not None
    assert record.status == "completed"


def test_viewer_cannot_start_loop_but_can_read():
    from pharma_sdl.api import deps
    from pharma_sdl.api.deps import app_settings
    from pharma_sdl.config import reset_settings

    keys = "viewer-1:vk-viewer:viewer,scientist-1:sk-sci:scientist"
    import os

    os.environ["PHARMA_SDL_API_KEYS"] = keys
    reset_settings()
    app_settings.cache_clear()
    deps._registry = None
    try:
        client = TestClient(create_app())
        viewer = {"X-API-Key": "vk-viewer"}
        scientist = {"X-API-Key": "sk-sci"}
        denied = client.post(
            "/api/v1/loop/runs", json={"top_n": 2}, headers=viewer
        )
        assert denied.status_code == 403
        created = client.post(
            "/api/v1/loop/runs", json={"top_n": 2}, headers=scientist
        )
        assert created.status_code == 202
        job_id = created.json()["job_id"]
        assert client.get(f"/api/v1/loop/runs/{job_id}", headers=viewer).status_code == 200
        anon = client.get(f"/api/v1/loop/runs/{job_id}")
        assert anon.status_code == 401
    finally:
        os.environ.pop("PHARMA_SDL_API_KEYS", None)
        reset_settings()
        app_settings.cache_clear()
        deps._registry = None


def test_demo_mode_locks_engine_and_caps_top_n(monkeypatch):
    from pharma_sdl.api import deps
    from pharma_sdl.api.deps import app_settings
    from pharma_sdl.config import reset_settings
    from pharma_sdl.jobs import reset_job_store

    monkeypatch.setenv("PHARMA_SDL_DEMO_MODE", "1")
    monkeypatch.setenv("PHARMA_SDL_RATE_LIMIT", "0")
    reset_settings()
    app_settings.cache_clear()
    deps._registry = None
    reset_job_store()
    try:
        client = TestClient(create_app())
        locked = client.post("/api/v1/loop/runs", json={"engine": "vina", "top_n": 5})
        assert locked.status_code == 422
        assert locked.json()["detail"]["code"] == "engine_not_allowed_demo"

        created = client.post("/api/v1/loop/runs", json={"top_n": 25})
        assert created.status_code == 202
        data = _wait_loop(client, created.json()["job_id"])
        assert data["status"] == "done"
        # السقف مفروض في مسار التنفيذ: top_n المحفوظ في الجولة = سقف العرض (10)
        assert data["rounds"][0]["parameters"]["top_n"] == 10
    finally:
        monkeypatch.delenv("PHARMA_SDL_DEMO_MODE", raising=False)
        reset_job_store()
        reset_settings()
        app_settings.cache_clear()
        deps._registry = None


def test_unknown_loop_job_returns_404():
    client = TestClient(create_app())
    missing = client.get("/api/v1/loop/runs/no-such-id")
    assert missing.status_code == 404
    assert missing.json()["detail"]["code"] == "loop_run_not_found"
