"""اختبارات وضع العرض العام المحدود (P2، تقييم #6) — عدالة الحساب المشترك."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from pharma_sdl.api.app import create_app
from pharma_sdl.api.demo import TokenBucketLimiter


@pytest.fixture
def demo_app(monkeypatch, tmp_path):
    """نسخة تطبيق بوضع العرض وحد معدل صغير قابل للاختبار."""
    from pharma_sdl.api import deps
    from pharma_sdl.api.demo import reset_limiter
    from pharma_sdl.api.deps import app_settings
    from pharma_sdl.config import reset_settings
    from pharma_sdl.jobs.runner import reset_job_store

    monkeypatch.setenv("PHARMA_SDL_DEMO_MODE", "1")
    monkeypatch.setenv("PHARMA_SDL_RATE_LIMIT", "4")
    monkeypatch.setenv("PHARMA_SDL_DEMO_MAX_LIGANDS", "5")
    monkeypatch.setenv("PHARMA_SDL_DEMO_MAX_TOP_N", "3")
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


# ── دلو الرموز — رياضيات صادقة ───────────────────────────────


def test_token_bucket_allows_then_denies():
    limiter = TokenBucketLimiter(rate_per_min=2)
    assert limiter.allow("ip-a")[0] is True
    assert limiter.allow("ip-a")[0] is True
    allowed, remaining, reset_s = limiter.allow("ip-a")
    assert allowed is False
    assert remaining == 0
    assert reset_s > 0
    # هوية مستقلة — لا عقاب جماعي
    assert limiter.allow("ip-b")[0] is True


def test_token_bucket_refills_over_time():
    """ساعة محقونة — إعادة الملء حتمية بلا انتظار حقيقي."""
    t = {"now": 0.0}
    limiter = TokenBucketLimiter(rate_per_min=60, clock=lambda: t["now"])  # رمز/ثانية
    for _ in range(60):
        limiter.allow("ip")
    allowed, _, _ = limiter.allow("ip")
    assert allowed is False
    t["now"] += 0.5  # نصف رمز — لا يكفي
    assert limiter.allow("ip")[0] is False
    t["now"] += 0.6  # مئّت رمز كامل
    assert limiter.allow("ip")[0] is True


# ── السلوك عبر الواجهة ───────────────────────────────────────


def test_health_declares_demo_mode(demo_app):
    client = TestClient(create_app())
    body = client.get("/api/v1/health").json()
    assert body["demo_mode"] is True
    assert body["auth_mode"] == "open"  # العرض المحدود ≠ مصادقة — كلٌّ صادق منفرداً


def test_rate_limit_headers_then_429(demo_app):
    client = TestClient(create_app())
    codes = []
    for i in range(6):
        resp = client.get("/api/v1/targets")
        codes.append(resp.status_code)
        if i == 0:
            assert "X-RateLimit-Limit" in resp.headers
    assert codes[:4] == [200, 200, 200, 200]
    assert codes[4] == 429
    blocked = client.get("/api/v1/targets")
    assert blocked.status_code == 429
    assert blocked.json()["code"] == "rate_limited"
    assert "Retry-After" in blocked.headers


def test_demo_blocks_heavy_engines(demo_app):
    client = TestClient(create_app())
    resp = client.post(
        "/api/v1/screening/runs",
        json={"target_id": "7VH8_A", "engine": "vina", "top_n": 2,
              "ligands": [{"name": "x", "smiles": "CCO"}]},
    )
    assert resp.status_code == 422
    assert resp.json()["detail"]["code"] == "engine_not_allowed_demo"
    # المحرك الافتراضي (simulation) يمر
    ok = client.post(
        "/api/v1/screening/runs",
        json={"target_id": "7VH8_A", "top_n": 2,
              "ligands": [{"name": "x", "smiles": "CCO"}]},
    )
    assert ok.status_code == 202


def test_demo_caps_ligands_and_top_n(demo_app):
    client = TestClient(create_app())
    many = client.post(
        "/api/v1/screening/runs",
        json={"target_id": "7VH8_A", "top_n": 2,
              "ligands": [{"name": f"l{i}", "smiles": "CCO"} for i in range(6)]},
    )
    assert many.status_code == 422
    assert many.json()["detail"]["code"] == "too_many_ligands"
    greedy = client.post(
        "/api/v1/screening/runs",
        json={"target_id": "7VH8_A", "top_n": 10,
              "ligands": [{"name": "x", "smiles": "CCO"}]},
    )
    assert greedy.status_code == 422
    assert greedy.json()["detail"]["code"] == "top_n_capped"


def test_rate_limit_disabled_outside_demo(monkeypatch):
    """بلا وضع عرض وبلا حد معدل صريح — لا وسيط يتصرف (سلوك التوافق)."""
    from pharma_sdl.api.demo import reset_limiter
    from pharma_sdl.api.deps import app_settings
    from pharma_sdl.config import reset_settings

    monkeypatch.setenv("PHARMA_SDL_DEMO_MODE", "0")
    monkeypatch.setenv("PHARMA_SDL_RATE_LIMIT", "0")
    reset_settings()
    app_settings.cache_clear()
    reset_limiter()
    client = TestClient(create_app())
    for _ in range(10):
        assert client.get("/api/v1/targets").status_code == 200
    reset_settings()
    app_settings.cache_clear()
    reset_limiter()
