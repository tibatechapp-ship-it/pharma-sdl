"""اختبارات مكتبة الطب النبوي عبر الـAPI — حزمة P5 كخدمة."""

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
        out = client.get(f"/api/v1/tibb/screen/{job_id}", headers=headers)
        assert out.status_code == 200
        data = out.json()
        if data["status"] in ("done", "failed"):
            return data
        time.sleep(0.2)
    raise AssertionError("فرز المكتبة لم يكتمل خلال المهلة")


def test_library_requires_auth():
    """بلا مفتاح → 401 — لا مكتبة مجهولة الهوية."""
    _auth()
    client = TestClient(create_app())
    assert client.get("/api/v1/tibb/library").status_code == 401


def test_viewer_can_read_library_with_disclaimers():
    """القارئ يرى المكتبة كاملة: 17 مركباً + إجرائان + إخلاء مزدوج."""
    _auth()
    client = TestClient(create_app())
    out = client.get("/api/v1/tibb/library", headers={"X-API-Key": "vk-viewer"})
    assert out.status_code == 200
    data = out.json()
    assert data["compounds"] == 17
    assert data["procedures"] == 2
    assert data["by_source"] == {"العسل": 9, "حبة البركة": 6, "الشعير": 2}
    assert len(data["items"]) == 17
    assert len(data["procedure_items"]) == 2
    # كل مركب بتوثيقه المزدوج
    for item in data["items"]:
        assert item["smiles"] and item["formula"]
        assert item["evidence_tier"] in ("T0_traditional", "T1_invitro", "T2_preclinical", "T3_clinical")
        assert item["hadith"]["grade"] == "متفق عليه"
        assert item["hadith"]["reference"]
    assert "ليس دليلاً على فعالية" in data["disclaimer_ar"]
    # الإجراءات بلا فرز حاسوبي
    for proc in data["procedure_items"]:
        assert "حاسوبي" in proc["computational_note"]


def test_screen_requires_scientist_role():
    """القارئ لا يطلق فرزاً — 403؛ و401 للمجهول."""
    _auth()
    client = TestClient(create_app())
    assert client.post("/api/v1/tibb/screen").status_code == 401
    assert (
        client.post("/api/v1/tibb/screen", headers={"X-API-Key": "vk-viewer"}).status_code
        == 403
    )


def test_screen_end_to_end_report_and_memory():
    """e2e: عالِم يطلق الفرز → تقرير 17 صفاً UNVALIDATED + سجل بسلسلة."""
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
        created = client.post("/api/v1/tibb/screen", headers=scientist)
        assert created.status_code == 202
        body = created.json()
        assert body["kind"] == "tibb_screen"
        assert "UNVALIDATED" in body["note_en"]

        done = _wait(client, body["job_id"], scientist)
        assert done["status"] == "done"
        report = done["report"]
        assert report["lane"] == "predicted_potency"
        assert report["n_compounds"] == 17
        assert report["target_id"] == "CHEMBL4523582"
        for row in report["rows"]:
            assert row["validation_state"] == "UNVALIDATED"
            assert row["lane"] == "predicted_potency"
        # مرتبة تنازلياً
        preds = [r["predicted_pic50"] for r in report["rows"]]
        assert preds == sorted(preds, reverse=True)

        # الذاكرة: سجل فرز بمعرف تجربة — والحملة تقرأ سابقتها من نفس السجل
        registry = experiment_registry()
        kinds = [r.kind for r in registry.latest(limit=50)]
        assert "natural_products_screen" in kinds
    finally:
        deps._registry = None


def test_screen_deterministic_across_runs():
    """نفس البيئة والبذرة → نفس الترتيب في مهمتين منفصلتين."""
    _auth()
    client = TestClient(create_app())
    scientist = {"X-API-Key": "sk-sci"}
    jobs = [client.post("/api/v1/tibb/screen", headers=scientist).json()["job_id"] for _ in range(2)]
    reports = [_wait(client, j, scientist)["report"] for j in jobs]
    assert reports[0]["rows"] == reports[1]["rows"]


def test_unknown_screen_id_is_404_with_bilingual_error():
    """معرف غير موجود → 404 برسالة ثنائية اللغة."""
    _auth()
    client = TestClient(create_app())
    out = client.get("/api/v1/tibb/screen/nope", headers={"X-API-Key": "vk-viewer"})
    assert out.status_code == 404
    detail = out.json()["detail"]
    assert detail["code"] == "tibb_screen_not_found"
    assert "message_ar" in detail and "message_en" in detail
