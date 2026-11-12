"""اختبارات تحصين النشر (P16) — الإعدادات تفشل بوضوح، والمصادقة تُفرض في الإنتاج.

تغطي: بوابة الإنتاج، نموذج الثقة بالبروكسي، سقف ذاكرة حد المعدل،
تحقق الإعدادات الحدّي، وعقود النشر (compose/Dockerfile/workflow).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from pharma_sdl.api.app import create_app
from pharma_sdl.api.demo import TokenBucketLimiter

REPO = Path(__file__).resolve().parent.parent

# ── 1) بوابة الإنتاج — لا إقلاع مفتوح بلا قصد ───────────────


@pytest.fixture
def _reset_env():
    from pharma_sdl.api import deps
    from pharma_sdl.api.demo import reset_limiter
    from pharma_sdl.api.deps import app_settings
    from pharma_sdl.config import reset_settings

    reset_settings()
    app_settings.cache_clear()
    reset_limiter()
    deps._registry = None
    yield
    reset_settings()
    app_settings.cache_clear()
    reset_limiter()
    deps._registry = None


def test_production_without_keys_refuses_to_boot(monkeypatch, _reset_env, tmp_path):
    monkeypatch.setenv("PHARMA_SDL_ENV", "production")
    monkeypatch.delenv("PHARMA_SDL_API_KEYS", raising=False)
    monkeypatch.setenv("PHARMA_SDL_EXPERIMENTS_DB", str(tmp_path / "exp.sqlite3"))
    monkeypatch.setenv("PHARMA_SDL_JOBS_DB", str(tmp_path / "jobs.sqlite3"))
    from pharma_sdl.api import deps
    from pharma_sdl.api.demo import reset_limiter
    from pharma_sdl.api.deps import app_settings
    from pharma_sdl.config import reset_settings

    reset_settings()
    app_settings.cache_clear()
    reset_limiter()
    deps._registry = None
    with pytest.raises(RuntimeError, match="PHARMA_SDL_ENV=production"):
        create_app()


def test_production_with_keys_boots_and_enforces(monkeypatch, _reset_env, tmp_path):
    monkeypatch.setenv("PHARMA_SDL_ENV", "production")
    monkeypatch.setenv(
        "PHARMA_SDL_API_KEYS", "ops:sk-prod-key-123456:admin"
    )
    monkeypatch.setenv("PHARMA_SDL_EXPERIMENTS_DB", str(tmp_path / "exp.sqlite3"))
    monkeypatch.setenv("PHARMA_SDL_JOBS_DB", str(tmp_path / "jobs.sqlite3"))
    from pharma_sdl.api import deps
    from pharma_sdl.api.demo import reset_limiter
    from pharma_sdl.api.deps import app_settings
    from pharma_sdl.config import reset_settings

    reset_settings()
    app_settings.cache_clear()
    reset_limiter()
    deps._registry = None
    client = TestClient(create_app())
    body = client.get("/api/v1/health").json()
    assert body["auth_mode"] == "enforced"
    # بلا مفتاح = رفض مصادقة صادق (الوضع المفتوح لم يعد متاحاً في الإنتاج)
    assert client.get("/api/v1/targets").status_code == 401


def test_development_open_mode_unchanged(monkeypatch, _reset_env, tmp_path):
    """الوضع المفتوح حق التطوير المحلي — لا كسر للتوافق."""
    monkeypatch.delenv("PHARMA_SDL_ENV", raising=False)
    monkeypatch.delenv("PHARMA_SDL_API_KEYS", raising=False)
    monkeypatch.setenv("PHARMA_SDL_EXPERIMENTS_DB", str(tmp_path / "exp.sqlite3"))
    monkeypatch.setenv("PHARMA_SDL_JOBS_DB", str(tmp_path / "jobs.sqlite3"))
    from pharma_sdl.api import deps
    from pharma_sdl.api.demo import reset_limiter
    from pharma_sdl.api.deps import app_settings
    from pharma_sdl.config import reset_settings

    reset_settings()
    app_settings.cache_clear()
    reset_limiter()
    deps._registry = None
    client = TestClient(create_app())
    assert client.get("/api/v1/health").json()["auth_mode"] == "open"


# ── 2) نموذج الثقة بالبروكسي — الترويسة المزوّرة لا تتحايل ───


def _fake_request(xff: str | None, client_host: str = "10.0.0.9"):
    """Request مزيّف أدنى ما يمكن — ترويسة + هوية عميل فقط."""

    class _FakeHeaders(dict):
        def get(self, key, default=None):
            return dict.get(self, key.lower(), default)

    class _FakeClient:
        host = client_host

    class _FakeRequest:
        headers = _FakeHeaders()
        client = _FakeClient()

    if xff is not None:
        _FakeRequest.headers["x-forwarded-for"] = xff
    return _FakeRequest()


def test_identity_ignores_forwarded_header_by_default(monkeypatch):
    from pharma_sdl.api.demo import _identity
    from pharma_sdl.api.deps import app_settings
    from pharma_sdl.config import reset_settings

    monkeypatch.delenv("PHARMA_SDL_TRUST_PROXY", raising=False)
    reset_settings()
    app_settings.cache_clear()
    assert _identity(_fake_request("1.2.3.4, 5.6.7.8")) == "10.0.0.9"


def test_identity_uses_forwarded_header_only_when_trusted(monkeypatch):
    from pharma_sdl.api.demo import _identity
    from pharma_sdl.api.deps import app_settings
    from pharma_sdl.config import reset_settings

    monkeypatch.setenv("PHARMA_SDL_TRUST_PROXY", "1")
    reset_settings()
    app_settings.cache_clear()
    assert _identity(_fake_request("1.2.3.4, 5.6.7.8")) == "1.2.3.4"
    # وبدون ترويسة أصلاً — العودة للـIP المباشر لا "unknown" خيالية
    assert _identity(_fake_request(None)) == "10.0.0.9"


# ── 3) سقف ذاكرة حد المعدل — تنظيف وإخلاء حتميان ────────────


def test_limiter_forgets_expired_identities():
    """هوية انقضت مدة الامتلاء الكامل تُنسى — دلوّها ممتلئ والنسيان آمن."""
    t = {"now": 0.0}
    limiter = TokenBucketLimiter(rate_per_min=60, clock=lambda: t["now"])
    limiter.allow("ip-a")
    limiter.allow("ip-b")
    assert len(limiter._updated) == 2
    t["now"] += 61.0  # أبعد من أفق الامتلاء الكامل (60s)
    limiter.allow("ip-c")
    assert set(limiter._updated) == {"ip-c"}


def test_limiter_hard_cap_evicts_oldest():
    """تحويل بهويات مزيفة يضغط السقف بدل أن يهضم الذاكرة."""
    t = {"now": 100.0}
    limiter = TokenBucketLimiter(
        rate_per_min=60, clock=lambda: t["now"], max_identities=4
    )
    for i in range(10):
        limiter.allow(f"ip-{i}")
    assert len(limiter._updated) <= 4
    # الأقدم تُخلّى أولاً — الأحدث الحديثة تبقى
    assert "ip-9" in limiter._updated
    assert "ip-0" not in limiter._updated


def test_limiter_keeps_correct_math_after_prune():
    """التنظيف لا يفسد الرياضيات — هوية حية تُملأ وتُرفض كالمعتاد."""
    t = {"now": 0.0}
    limiter = TokenBucketLimiter(rate_per_min=2, clock=lambda: t["now"])
    assert limiter.allow("ip")[0] is True
    assert limiter.allow("ip")[0] is True
    assert limiter.allow("ip")[0] is False
    t["now"] += 30.0  # رمز واحد أُعيد ملؤه
    assert limiter.allow("ip")[0] is True
    assert limiter.allow("ip")[0] is False


# ── 4) التحقق الحدّي للإعدادات — خطأ النشر يظهر عند الإقلاع ──


def test_env_int_garbage_raises_and_names_the_variable(monkeypatch):
    from pharma_sdl.config import _env_int

    monkeypatch.setenv("PHARMA_SDL_RATE_LIMIT", "thirty")
    with pytest.raises(ValueError, match="PHARMA_SDL_RATE_LIMIT"):
        _env_int("PHARMA_SDL_RATE_LIMIT", 0)


def test_env_float_garbage_raises(monkeypatch):
    from pharma_sdl.config import _env_float

    monkeypatch.setenv("PHARMA_SDL_LIMS_TIMEOUT", "fast")
    with pytest.raises(ValueError, match="PHARMA_SDL_LIMS_TIMEOUT"):
        _env_float("PHARMA_SDL_LIMS_TIMEOUT", 10.0)


def test_env_bool_rejects_unknown_words(monkeypatch):
    from pharma_sdl.config import _env_bool

    monkeypatch.setenv("PHARMA_SDL_DEMO_MODE", "sure")
    with pytest.raises(ValueError, match="PHARMA_SDL_DEMO_MODE"):
        _env_bool("PHARMA_SDL_DEMO_MODE", False)


def test_settings_validate_bounds(monkeypatch):
    from pharma_sdl.config import Settings

    with pytest.raises(ValueError, match="PHARMA_SDL_PORT"):
        Settings(port=70000).validate()
    with pytest.raises(ValueError, match="PHARMA_SDL_RATE_LIMIT"):
        Settings(rate_limit_per_min=-5).validate()
    with pytest.raises(ValueError, match="PHARMA_SDL_ENV"):
        Settings(env="staging").validate()
    with pytest.raises(ValueError, match="PHARMA_SDL_STORE"):
        Settings(store_backend="oracle").validate()
    # postgres بلا DSN = رفض (لا ترقية صامتة — ADR-0008)
    with pytest.raises(ValueError, match="PHARMA_SDL_PG_DSN"):
        Settings(store_backend="postgres").validate()


def test_from_env_fail_fast_on_garbage(monkeypatch):
    from pharma_sdl.config import Settings, reset_settings

    monkeypatch.setenv("PHARMA_SDL_PORT", "eight_thousand")
    reset_settings()
    with pytest.raises(ValueError, match="PHARMA_SDL_PORT"):
        Settings.from_env()


# ── 5) عقود النشر — compose وDockerfile وworkflow ───────────


def test_compose_contract_pg_profile_is_actually_wired():
    """ملف التعريف pg يجب أن يوصل التخزين فعلياً لا ادعاءً."""
    compose = yaml.safe_load((REPO / "docker-compose.yml").read_text(encoding="utf-8"))
    assert compose["services"]["api-pg"]["profiles"] == ["pg"]
    env = compose["services"]["api-pg"]["environment"]
    assert env["PHARMA_SDL_STORE"] == "postgres"
    assert "@postgres:5432" in env["PHARMA_SDL_PG_DSN"]
    assert (
        compose["services"]["api-pg"]["depends_on"]["postgres"]["condition"]
        == "service_healthy"
    )
    # وخدمة postgres نفسها لها فحص جاهزية
    assert "pg_isready" in compose["services"]["postgres"]["healthcheck"]["test"][1]


def test_compose_image_tag_matches_pyproject_version():
    """حارس اتساق الإصدار: الافتراضي في compose يطابق pyproject.toml دائماً.

    كان الاختبار سابقاً يثبّت قيمة حرفية (0.17.0) فسَمح بانجراف pyproject
    (0.18.0) عن compose خلافاً لقاعدة P16 (مصدر وسم الصورة واحد) — الآن
    يُقارَن الافتراضي بمصدر الحقيقة نفسه فلا انجراف ممكن مستقبلاً.
    """
    import tomllib

    raw = (REPO / "docker-compose.yml").read_text(encoding="utf-8")
    assert "pharma-sdl:0.5.0" not in raw
    version = tomllib.loads(
        (REPO / "pyproject.toml").read_text(encoding="utf-8")
    )["project"]["version"]
    compose = yaml.safe_load(raw)
    for svc in ("api", "api-pg", "dashboard"):
        assert compose["services"][svc]["image"] == (
            f"pharma-sdl:${{PHARMA_SDL_IMAGE_TAG:-{version}}}"
        )


def test_dockerfile_runs_as_non_root():
    text = (REPO / "Dockerfile").read_text(encoding="utf-8")
    assert "USER appuser" in text
    assert "useradd" in text
    # وملكية مجلد البيانات قبل التبديل — الأحجام المركبة ترثها
    assert "chown -R appuser:appuser /app" in text


def test_ci_workflow_scopes_write_to_badge_job_only():
    wf = yaml.safe_load(
        (REPO / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8")
    )
    assert wf["permissions"] == {"contents": "read"}
    assert wf["jobs"]["badge"]["permissions"] == {"contents": "write"}
    assert "permissions" not in wf["jobs"]["test"]
    assert wf["jobs"]["badge"]["needs"] == "test"


def test_landing_page_badge_matches_pyproject_version():
    """شارة «الإصدار» في الصفحة الحية مقيدة بمصدر الحقيقة (pyproject.toml)."""
    import re
    import tomllib

    version = tomllib.loads(
        (REPO / "pyproject.toml").read_text(encoding="utf-8")
    )["project"]["version"]
    html = (REPO / "docs" / "index.html").read_text(encoding="utf-8")
    m = re.search(r"الإصدار v(\d+\.\d+\.\d+)", html)
    assert m, "شارة الإصدار مفقودة من الصفحة الحية docs/index.html"
    assert m.group(1) == version, (
        f"انجراف شارة الصفحة الحية: {m.group(1)} ≠ pyproject {version}"
    )


def test_readme_api_badge_matches_pyproject_version():
    """شارة API في README مقيدة بمصدر الحقيقة نفسه."""
    import re
    import tomllib

    version = tomllib.loads(
        (REPO / "pyproject.toml").read_text(encoding="utf-8")
    )["project"]["version"]
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    m = re.search(r"API-v(\d+\.\d+\.\d+)-", readme)
    assert m, "شارة API مفقودة من README.md"
    assert m.group(1) == version, f"انجراف شارة API: {m.group(1)} ≠ pyproject {version}"


def test_package_version_matches_pyproject():
    """إغلاق الانجراف الثالث: pharma_sdl.__version__ = مصدر الحقيقة (كان عالقاً على 0.14.0)."""
    import tomllib

    version = tomllib.loads(
        (REPO / "pyproject.toml").read_text(encoding="utf-8")
    )["project"]["version"]
    from pharma_sdl import __version__

    assert __version__ == version, (
        f"انجراف نسخة الحزمة: {__version__} ≠ pyproject {version}"
    )


def test_ryko_version_matches_pyproject():
    """نسخة Ryko مقيدة بمصدر الحقيقة نفسه — العقل لا يسبق جسمه."""
    import tomllib

    version = tomllib.loads(
        (REPO / "pyproject.toml").read_text(encoding="utf-8")
    )["project"]["version"]
    from pharma_sdl.ryko import RYKO_VERSION

    assert RYKO_VERSION == version, (
        f"انجراف نسخة Ryko: {RYKO_VERSION} ≠ pyproject {version}"
    )
