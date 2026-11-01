"""اختبارات المصادقة وRBAC (P2، تقييم #5) — هوية بشرية لكل ترقية اعتماد."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from pharma_sdl.api.app import create_app
from pharma_sdl.api.auth import Role, hash_key, parse_api_keys, resolve_principal
from pharma_sdl.errors import ValidationError

KEYS = "adm:adm-secret-1:admin,sci:sci-secret-2:scientist,view:view-secret-3:viewer"


@pytest.fixture
def enforced_app(monkeypatch, tmp_path):
    """نسخة تطبيق بمصادقة مفعلة وسجلات معزولة."""
    from pharma_sdl.api import deps
    from pharma_sdl.api.demo import reset_limiter
    from pharma_sdl.api.deps import app_settings
    from pharma_sdl.config import reset_settings
    from pharma_sdl.jobs.runner import reset_job_store

    monkeypatch.setenv("PHARMA_SDL_API_KEYS", KEYS)
    monkeypatch.setenv("PHARMA_SDL_EXPERIMENTS_DB", str(tmp_path / "exp.sqlite3"))
    monkeypatch.setenv("PHARMA_SDL_JOBS_DB", str(tmp_path / "jobs.sqlite3"))
    reset_settings()
    app_settings.cache_clear()
    reset_job_store()
    reset_limiter()
    deps._registry = None
    yield
    reset_settings()
    app_settings.cache_clear()
    reset_job_store()
    reset_limiter()
    deps._registry = None


# ── وحدة التفكيك — صرامة مسبقة ───────────────────────────────


def test_parse_api_keys_roles_and_hashing():
    principals = parse_api_keys(KEYS)
    assert len(principals) == 3
    assert all(isinstance(k, str) and len(k) == 64 for k in principals)  # sha256 hex
    roles = sorted(p.role for p in principals.values())
    assert roles == [Role.ADMIN, Role.SCIENTIST, Role.VIEWER]
    # لا سر خام في القيم المخزنة
    assert all("secret" not in k for k in principals)


def test_parse_api_keys_rejects_malformed_and_unknown_role():
    with pytest.raises(ValidationError):
        parse_api_keys("bad-format-only-two-parts:admin")
    with pytest.raises(ValidationError):
        parse_api_keys("x:secret:superuser")
    # سر مكرر فعلاً → بصمة مكررة → رفض صريح
    with pytest.raises(ValidationError):
        parse_api_keys("a:same:admin,b:same:viewer")


def test_hash_key_deterministic_and_salt_free():
    assert hash_key("abc") == hash_key("abc")
    assert hash_key("abc") != hash_key("abd")


def test_open_mode_gives_explicit_admin(monkeypatch):
    monkeypatch.setenv("PHARMA_SDL_API_KEYS", "")
    from pharma_sdl.api.deps import app_settings
    from pharma_sdl.config import reset_settings

    reset_settings()
    app_settings.cache_clear()
    principal = resolve_principal(None)
    assert principal.role is Role.ADMIN
    assert principal.key_id == "anonymous"
    reset_settings()
    app_settings.cache_clear()


# ── الواجهة — 401/403 صادقة عبر TestClient ──────────────────


def test_health_and_version_stay_open_without_key(enforced_app):
    client = TestClient(create_app())
    assert client.get("/api/v1/health").status_code == 200
    assert client.get("/api/v1/version").status_code == 200


def test_missing_key_is_401_not_403(enforced_app):
    client = TestClient(create_app())
    resp = client.get("/api/v1/targets")
    assert resp.status_code == 401
    assert resp.json()["code"] == "unauthorized"


def test_unknown_key_is_401(enforced_app):
    client = TestClient(create_app())
    resp = client.get("/api/v1/targets", headers={"X-API-Key": "not-a-key"})
    assert resp.status_code == 401


def test_viewer_reads_but_cannot_screen(enforced_app):
    client = TestClient(create_app())
    ok = client.get("/api/v1/targets", headers={"X-API-Key": "view-secret-3"})
    assert ok.status_code == 200
    denied = client.post(
        "/api/v1/screening/runs",
        json={"target_id": "7VH8_A", "engine": "simulation", "top_n": 2,
              "ligands": [{"name": "x", "smiles": "CCO"}]},
        headers={"X-API-Key": "view-secret-3"},
    )
    assert denied.status_code == 403
    assert denied.json()["code"] == "forbidden"


def test_scientist_screens_but_cannot_promote(enforced_app):
    client = TestClient(create_app())
    # مختبر: يطلق فرزاً بنجاح
    accepted = client.post(
        "/api/v1/screening/runs",
        json={"target_id": "7VH8_A", "engine": "simulation", "top_n": 2,
              "ligands": [{"name": "x", "smiles": "CCO"}]},
        headers={"X-API-Key": "sci-secret-2"},
    )
    assert accepted.status_code == 202
    # تجربة موجودة للترقية
    from pharma_sdl.api import deps

    rec = ExperimentSeed.create(deps.experiment_registry())
    denied = client.post(
        f"/api/v1/experiments/{rec.experiment_id}/validation/promote",
        json={"to": "COMPUTATIONALLY_VALIDATED", "reason": "فحوص حسابية", "actor": "عالِم"},
        headers={"X-API-Key": "sci-secret-2"},
    )
    assert denied.status_code == 403


def test_admin_promotes_via_gate_contract(enforced_app):
    client = TestClient(create_app())
    from pharma_sdl.api import deps

    rec = ExperimentSeed.create(deps.experiment_registry())
    # قفزة ممنوعة — البوابة ترفض حتى admin
    jump = client.post(
        f"/api/v1/experiments/{rec.experiment_id}/validation/promote",
        json={"to": "INDEPENDENTLY_REPRODUCED", "reason": "قفزة", "actor": "مدير"},
        headers={"X-API-Key": "adm-secret-1"},
    )
    assert jump.status_code == 422
    # خطوة مشروعة
    legal = client.post(
        f"/api/v1/experiments/{rec.experiment_id}/validation/promote",
        json={"to": "COMPUTATIONALLY_VALIDATED", "reason": "فحوص محددة موثقة", "actor": "مدير الجودة"},
        headers={"X-API-Key": "adm-secret-1"},
    )
    assert legal.status_code == 200
    assert legal.json()["state"] == "COMPUTATIONALLY_VALIDATED"
    # الحالة التسعة تتطلب مرجع فحص — بلا مرجع 422
    missing = client.post(
        f"/api/v1/experiments/{rec.experiment_id}/validation/promote",
        json={"to": "EXPERIMENTALLY_SUPPORTED", "reason": "بلا مرجع", "actor": "مدير"},
        headers={"X-API-Key": "adm-secret-1"},
    )
    assert missing.status_code == 422
    # مرجع موجود → ترقية
    with_ref = client.post(
        f"/api/v1/experiments/{rec.experiment_id}/validation/promote",
        json={"to": "EXPERIMENTALLY_SUPPORTED", "reason": "FRET مؤكد",
              "actor": "مدير", "assay_ref": "assay-2026-001"},
        headers={"X-API-Key": "adm-secret-1"},
    )
    assert with_ref.status_code == 200
    # التاريخ محفوظ في البطاقة لا نص حالة فقط
    card = client.get(
        f"/api/v1/experiments/{rec.experiment_id}/validation",
        headers={"X-API-Key": "view-secret-3"},
    )
    assert card.status_code == 200
    assert len(card.json()["history"]) == 2  # ترقيتان الناجحتان فقط — المرفوضات بلا تاريخ
    # التخفيض admin فقط وموثق
    revoked = client.post(
        f"/api/v1/experiments/{rec.experiment_id}/validation/revoke",
        json={"reason": "خطأ في الفحص اكتُشف لاحقاً", "actor": "مدير"},
        headers={"X-API-Key": "adm-secret-1"},
    )
    assert revoked.status_code == 200
    assert revoked.json()["state"] == "UNVALIDATED"
    assert len(revoked.json()["history"]) == 3  # لا محو — كل شيء في التاريخ


def test_whoami_reports_role_without_secrets(enforced_app):
    client = TestClient(create_app())
    resp = client.get("/api/v1/auth/whoami", headers={"X-API-Key": "view-secret-3"})
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"key_id": "view", "role": "viewer", "auth_mode": "enforced"}
    assert "secret" not in resp.text


class ExperimentSeed:
    """إنشاء تجربة مكتملة واحدة للاختبارات — بلا حلقة كاملة."""

    @staticmethod
    def create(registry):
        from pharma_sdl.experiments.registry import ExperimentRecord

        record = ExperimentRecord(
            hypothesis_ar="فرضية اختبار المصادقة",
            target_id="7VH8_A",
            engine_used="simulation",
        )
        registry.begin(record)
        registry.complete(
            record.experiment_id,
            counts={"input": 1, "screened": 1},
            top_hits=[{"rank": 1, "name": "ethanol", "smiles": "CCO", "kcal": -3.1}],
        )
        return record
