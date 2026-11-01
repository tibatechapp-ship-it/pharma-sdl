"""إعدادات المنصة — قراءة من متغيرات البيئة بقيم افتراضية آمنة.

كل ما يخص التشغيل (المنفذ، المحرك الافتراضي، السقوف، البوابات الخارجية)
يمر عبر Settings — لا أرقام سحرية مبعثرة في الكود.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw.strip())
    except ValueError:
        return default


def _env_str(name: str, default: str) -> str:
    raw = os.getenv(name)
    return default if raw is None or not raw.strip() else raw.strip()


@dataclass(frozen=True)
class Settings:
    """إعدادات تشغيل المنصة (تُجمد بعد الإنشاء)."""

    host: str = "0.0.0.0"
    port: int = 8000
    # المحرك المستخدم حين لا يحدد الطلب محركاً — المحاكاة دائماً متاحة.
    default_engine: str = "simulation"
    # عند طلب محرك غير متاح: التراجع إلى المحاكاة مع تسجيل تنبيه صادق.
    engine_fallback: bool = True
    # سقوف حماية واجهة الـAPI من الطلبات العملاقة.
    max_ligands_per_run: int = 250
    default_top_n: int = 25
    cors_origins: str = "*"
    # بوابة Boltz-2 (تنبؤ تقارب حقيقي) — لا مفتاح مخزَّن هنا أبداً (SECURITY.md).
    boltz2_endpoint: str | None = None
    # مجلد الأصول المشتركة (المستقبلات، بيانات العرض) — جذر المستودع افتراضياً.
    data_dir: Path = REPO_ROOT / "data"
    # عمر المهمة في الطابور الداخلي قبل التنظيف.
    job_ttl_seconds: int = 3600
    # سجل التجارب الدائم (تدقيق P1) — الذاكرة التجريبية لا تضيع بعد إعادة التشغيل.
    experiments_db: Path = REPO_ROOT / "data" / "experiments.sqlite3"
    # طابور المهام الدائم (ADR-0007) — النتائج تُستعاد والمقاطعة تُوثَّق لا تُخفى.
    jobs_db: Path = REPO_ROOT / "data" / "jobs.sqlite3"
    # المصادقة وRBAC (P2): مفاتيح API بصيغة id:key:role مفصولة بفواصل — فارغ = وضع مفتوح.
    api_keys: str = ""
    # وضع العرض العام المحدود (P2): سقوف أدنى + قفل المحركات + حد معدل.
    demo_mode: bool = False
    demo_max_ligands: int = 25
    demo_max_top_n: int = 10
    demo_allowed_engines: str = "simulation"
    # حد المعدل لكل IP (طلبات/دقيقة) — 0 يعطّله؛ وضع العرض يفرض قيمة افتراضية.
    rate_limit_per_min: int = 0
    # عمق البحث في Vina (exhaustiveness) عند تشغيل محرك الربط الفعلي.
    vina_exhaustiveness: int = 8
    # ── P3: التخزين الحي — خلفية السجل التجريبي وطابور المهام ──
    # sqlite (الافتراضي) أو postgres — العقود نفسها حرفياً (ADR-0008)؛
    # postgres يستوجب psycopg + DSN صريحاً — لا ترقية صامتة ولا ادعاء بلا خدمة.
    store_backend: str = "sqlite"
    pg_dsn: str | None = None

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            host=_env_str("PHARMA_SDL_HOST", "0.0.0.0"),
            port=_env_int("PHARMA_SDL_PORT", 8000),
            default_engine=_env_str("PHARMA_SDL_DEFAULT_ENGINE", "simulation"),
            engine_fallback=_env_bool("PHARMA_SDL_ENGINE_FALLBACK", True),
            max_ligands_per_run=_env_int("PHARMA_SDL_MAX_LIGANDS", 250),
            default_top_n=_env_int("PHARMA_SDL_TOP_N", 25),
            cors_origins=_env_str("PHARMA_SDL_CORS", "*"),
            boltz2_endpoint=os.getenv("PHARMA_SDL_BOLTZ2_ENDPOINT") or None,
            data_dir=Path(_env_str("PHARMA_SDL_DATA_DIR", str(REPO_ROOT / "data"))),
            experiments_db=Path(
                _env_str(
                    "PHARMA_SDL_EXPERIMENTS_DB",
                    str(Path(_env_str("PHARMA_SDL_DATA_DIR", str(REPO_ROOT / "data"))) / "experiments.sqlite3"),
                )
            ),
            job_ttl_seconds=_env_int("PHARMA_SDL_JOB_TTL", 3600),
            jobs_db=Path(
                _env_str(
                    "PHARMA_SDL_JOBS_DB",
                    str(Path(_env_str("PHARMA_SDL_DATA_DIR", str(REPO_ROOT / "data"))) / "jobs.sqlite3"),
                )
            ),
            api_keys=_env_str("PHARMA_SDL_API_KEYS", ""),
            demo_mode=_env_bool("PHARMA_SDL_DEMO_MODE", False),
            demo_max_ligands=_env_int("PHARMA_SDL_DEMO_MAX_LIGANDS", 25),
            demo_max_top_n=_env_int("PHARMA_SDL_DEMO_MAX_TOP_N", 10),
            demo_allowed_engines=_env_str("PHARMA_SDL_DEMO_ENGINES", "simulation"),
            rate_limit_per_min=_env_int("PHARMA_SDL_RATE_LIMIT", 0),
            vina_exhaustiveness=_env_int("PHARMA_SDL_VINA_EXHAUSTIVENESS", 8),
            store_backend=_env_str("PHARMA_SDL_STORE", "sqlite").lower(),
            pg_dsn=os.getenv("PHARMA_SDL_PG_DSN") or None,
        )


_settings: Settings | None = None


def get_settings() -> Settings:
    """نسخة وحيدة من الإعدادات (تُقرأ مرة واحدة عند أول استدعاء)."""
    global _settings
    if _settings is None:
        _settings = Settings.from_env()
    return _settings


def reset_settings() -> None:
    """لاختبارات فقط — إعادة قراءة البيئة من جديد."""
    global _settings
    _settings = None
