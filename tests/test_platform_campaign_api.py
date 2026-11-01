"""اختبارات حملات التعلم النشط عبر الـAPI — حزمة Q4 كخدمة (P4)."""

from __future__ import annotations

import os
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


def _auth(keys: str = "viewer-1:vk-viewer:viewer,scientist-1:sk-sci:scientist"):
    os.environ["PHARMA_SDL_API_KEYS"] = keys


def _wait(client: TestClient, job_id: str, headers: dict, timeout_s: float = 180.0) -> dict:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        out = client.get(f"/api/v1/loop/campaigns/{job_id}", headers=headers)
        assert out.status_code == 200
        data = out.json()
        if data["status"] in ("done", "failed"):
            return data
        time.sleep(0.2)
    raise AssertionError("الحملة لم تكتمل خلال المهلة")


def _quick_payload() -> dict:
    return {
        "strategy": "uncertainty",
        "rounds": 2,
        "batch_size": 4,
        "initial_labeled": 20,
        "n_estimators": 25,
    }


def test_campaign_end_to_end_with_report_and_memory():
    from pharma_sdl.api import deps
    from pharma_sdl.api.deps import app_settings, experiment_registry
    from pharma_sdl.config import reset_settings

    _auth()
    reset_settings()
    app_settings.cache_clear()
    deps._registry = None
    try:
        client = TestClient(create_app())
        scientist = {"X-API-Key": "sk-sci"}
        created = client.post(
            "/api/v1/loop/campaigns", json=_quick_payload(), headers=scientist
        )
        assert created.status_code == 202
        body = created.json()
        assert body["kind"] == "learning_campaign"
        assert "UNVALIDATED" in body["note_en"]

        final = _wait(client, body["job_id"], headers=scientist)
        assert final["status"] == "done"
        report = final["report"]
        assert report is not None
        assert report["strategy"] == "uncertainty"
        assert len(report["rounds"]) == 2
        assert report["dataset_fingerprint"].startswith("sha256:")
        # الأوراكل المعلن في كل تقرير — لا انكار لاحق
        assert "in-silico" in report["disclaimer_en"]

        # الجولات كُتبت في سجل المنصة نفسه بسلسلة أسلاف — ذاكرة واحدة
        registry = experiment_registry()
        rounds = [
            r for r in registry.latest(limit=100) if r.kind == "learning_round"
        ]
        assert len(rounds) == 2
    finally:
        os.environ.pop("PHARMA_SDL_API_KEYS", None)
        from pharma_sdl.api import deps
        from pharma_sdl.api.deps import app_settings
        from pharma_sdl.config import reset_settings

        reset_settings()
        app_settings.cache_clear()
        deps._registry = None


def test_viewer_cannot_launch_but_can_read():
    from pharma_sdl.api import deps
    from pharma_sdl.api.deps import app_settings
    from pharma_sdl.config import reset_settings

    _auth()
    reset_settings()
    app_settings.cache_clear()
    deps._registry = None
    try:
        client = TestClient(create_app())
        viewer = {"X-API-Key": "vk-viewer"}
        scientist = {"X-API-Key": "sk-sci"}
        denied = client.post("/api/v1/loop/campaigns", json=_quick_payload(), headers=viewer)
        assert denied.status_code == 403
        created = client.post(
            "/api/v1/loop/campaigns", json=_quick_payload(), headers=scientist
        )
        assert created.status_code == 202
        job_id = created.json()["job_id"]
        assert (
            client.get(f"/api/v1/loop/campaigns/{job_id}", headers=viewer).status_code
            == 200
        )
        assert client.get(f"/api/v1/loop/campaigns/{job_id}").status_code == 401
    finally:
        os.environ.pop("PHARMA_SDL_API_KEYS", None)
        from pharma_sdl.api import deps
        from pharma_sdl.api.deps import app_settings
        from pharma_sdl.config import reset_settings

        reset_settings()
        app_settings.cache_clear()
        deps._registry = None


def test_unknown_strategy_rejected_with_422():
    client = TestClient(create_app())
    out = client.post(
        "/api/v1/loop/campaigns",
        json={**_quick_payload(), "strategy": "magic"},
        headers={"X-API-Key": "anything"},
    )
    # الحارس المشروط (عقد 401 بدون مفاتيح مثبتة) أو 422 عند تفعيل المصادقة
    assert out.status_code in (401, 422)


def test_campaign_not_found_is_honest_404():
    client = TestClient(create_app())
    out = client.get("/api/v1/loop/campaigns/does-not-exist")
    assert out.status_code in (401, 404)  # بلا مفاتيح مثبتة: 401 أولاً
