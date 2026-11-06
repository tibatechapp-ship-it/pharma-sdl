"""إعدادات المنصة — قراءة من متغيرات البيئة بقيم افتراضية آمنة.

كل ما يخص التشغيل (المنفذ، المحرك الافتراضي، السقوف، البوابات الخارجية)
يمر عبر Settings — لا أرقام سحرية مبعثرة في الكود.

التحصين (P16): قيمة بيئة غير صالحة **توقف الإقلاع برسالة واضحة تسمّي
المتغير** — التخمين الصامت في الإعدادات الحرجة أخطر من الفشل نفسه
(مشغّل يظن الحد 100 وهو يعمل بـ30 = حادثة بلا سجل). و`validate()`
يفحص الحدود المنطقية بعد القراءة — بما فيها: postgres بلا DSN = رفض
(لا ترقية صامتة)، والإنتاج بلا مفاتيح يُرفض في بوابة التطبيق (app.py).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from pharma_sdl.errors import ConfigError

REPO_ROOT = Path(__file__).resolve().parent.parent

# قيم البيئة المقبولة لـ PHARMA_SDL_ENV — أي شيء آخر يوقف الإقلاع.
KNOWN_ENVS = frozenset({"development", "production"})
# قيم الثنائيات المقبولة — خارجها خطأ نشر لا صمت ("1"/"0" وحدها كانت تكفي سابقاً).
_TRUTHY = frozenset({"1", "true", "yes", "on"})
_FALSY = frozenset({"0", "false", "no", "off"})


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    value = raw.strip().lower()
    if value in _TRUTHY:
        return True
    if value in _FALSY:
        return False
    raise ValueError(
        f"قيمة غير مقبولة لـ {name}: {raw!r} — المقبول: 1/true/yes/on أو 0/false/no/off",
        f"Invalid value for {name}: {raw!r} — accepted: 1/true/yes/on or 0/false/no/off",
    )


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw.strip())
    except ValueError as exc:
        raise ValueError(
            f"قيمة غير رقمية لـ {name}: {raw!r} — أصلحها أو احذف المتغير كلياً "
            f"لتطابق الافتراضي {default}",
            f"Non-numeric value for {name}: {raw!r} — fix it or unset it "
            f"to use the default {default}",
        ) from exc


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return float(raw.strip())
    except ValueError as exc:
        raise ValueError(
            f"قيمة غير رقمية لـ {name}: {raw!r} — أصلحها أو احذف المتغير كلياً "
            f"لتطابق الافتراضي {default}",
            f"Non-numeric value for {name}: {raw!r} — fix it or unset it "
            f"to use the default {default}",
        ) from exc


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
    # ── P8: جسر الفيزياء — بوابة LIMS حقيقية عبر عقد REST (ADR-0013) ──
    # رابط فارغ = المختبر المحاكى (الافتراضي التوثيقي). ضبط الرابط يبدّل
    # نفس الواجهة إلى البوابة الحقيقية — ولا عودة صامتة إلى المحاكاة أبداً.
    lims_url: str | None = None
    lims_token: str | None = None
    lims_timeout_s: float = 10.0
    lims_poll_interval_s: float = 2.0
    lims_max_polls: int = 60
    lims_outbox: Path | None = REPO_ROOT / "data" / "lab-outbox.jsonl"
    # البوابة المرجعية لـLIMS (P9) — أوامر العمل تنجو من إعادة التشغيل (sqlite).
    gateway_db: Path = REPO_ROOT / "data" / "lims-gateway.sqlite3"
    # ── P10: جهة الميدان — سواقة الجهاز خلف نقطة رفع البوابة (ADR-0015) ──
    # مضيف فارغ = لا سواقة مهيأة (المصنع يعيد None صريحاً — لا محاكاة صامتة).
    # علم simulated الافتراضي True: الجهاز الحقيقي قرار بشري موثق يتطلب
    # PHARMA_SDL_INSTRUMENT_SIMULATED=false + رمز موافقة بشرية عند القياس.
    instrument_host: str | None = None
    instrument_port: int = 10001
    instrument_simulated: bool = True
    instrument_timeout_s: float = 30.0
    # ── P16: تحصين النشر ──
    # بيئة التشغيل: development (الافتراضي) أو production — الإنتاج يفرض
    # مفاتيح API (البوابة ترفض الإقلاع بلاها، app.py) ويُعلن في /health.
    env: str = "development"
    # هل نقف خلف بروكسي موثوق يعيد كتابة X-Forwarded-For؟ صادق افتراضياً:
    # False يقرأ IP المباشر فقط — الترويسة المزوّرة لا تتحايل على حد المعدل.
    trust_proxy: bool = False

    @classmethod
    def from_env(cls) -> Settings:
        settings = cls(
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
            lims_url=os.getenv("PHARMA_SDL_LIMS_URL") or None,
            lims_token=os.getenv("PHARMA_SDL_LIMS_TOKEN") or None,
            lims_timeout_s=_env_float("PHARMA_SDL_LIMS_TIMEOUT", 10.0),
            lims_poll_interval_s=_env_float("PHARMA_SDL_LIMS_POLL_INTERVAL", 2.0),
            lims_max_polls=_env_int("PHARMA_SDL_LIMS_MAX_POLLS", 60),
            lims_outbox=Path(
                _env_str(
                    "PHARMA_SDL_LIMS_OUTBOX",
                    str(REPO_ROOT / "data" / "lab-outbox.jsonl"),
                )
            ),
            gateway_db=Path(
                _env_str(
                    "PHARMA_SDL_GATEWAY_DB",
                    str(REPO_ROOT / "data" / "lims-gateway.sqlite3"),
                )
            ),
            instrument_host=os.getenv("PHARMA_SDL_INSTRUMENT_HOST") or None,
            instrument_port=_env_int("PHARMA_SDL_INSTRUMENT_PORT", 10001),
            instrument_simulated=_env_bool("PHARMA_SDL_INSTRUMENT_SIMULATED", True),
            instrument_timeout_s=_env_float("PHARMA_SDL_INSTRUMENT_TIMEOUT", 30.0),
            env=_env_str("PHARMA_SDL_ENV", "development").lower(),
            trust_proxy=_env_bool("PHARMA_SDL_TRUST_PROXY", False),
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        """حدود منطقية بعد القراءة — خطأ النشر يظهر عند الإقلاع لا في الإنتاج.

        تُرفع ConfigError (PlatformError ⋂ ValueError): الاختبارات وطبقة
        الإعداد تتعامل معها كـ ValueError، وطبقة النشر كـ PlatformError
        تُترجم إلى رمز HTTP صادق (ADR-0016).
        """
        if self.env not in KNOWN_ENVS:
            raise ConfigError(
                f"PHARMA_SDL_ENV غير معروف: {self.env!r} — المقبول: development/production"
            )
        if not 1 <= self.port <= 65535:
            raise ConfigError(f"PHARMA_SDL_PORT خارج المجال (1..65535): {self.port}")
        if self.max_ligands_per_run < 1:
            raise ConfigError(f"PHARMA_SDL_MAX_LIGANDS يجب أن يكون ≥ 1: {self.max_ligands_per_run}")
        if self.default_top_n < 1:
            raise ConfigError(f"PHARMA_SDL_TOP_N يجب أن يكون ≥ 1: {self.default_top_n}")
        if self.rate_limit_per_min < 0:
            raise ConfigError(f"PHARMA_SDL_RATE_LIMIT لا يقبل سالباً: {self.rate_limit_per_min}")
        if self.job_ttl_seconds < 1:
            raise ConfigError(f"PHARMA_SDL_JOB_TTL يجب أن يكون ≥ 1 ثانية: {self.job_ttl_seconds}")
        if self.vina_exhaustiveness < 1:
            raise ConfigError(f"PHARMA_SDL_VINA_EXHAUSTIVENESS يجب أن يكون ≥ 1: {self.vina_exhaustiveness}")
        if self.demo_max_ligands < 1 or self.demo_max_top_n < 1:
            raise ConfigError(
                "سقوف وضع العرض يجب أن تكون ≥ 1 "
                f"(ligands={self.demo_max_ligands}, top_n={self.demo_max_top_n})"
            )
        if self.store_backend not in {"sqlite", "postgres"}:
            raise ConfigError(
                f"PHARMA_SDL_STORE غير معروف: {self.store_backend!r} — المقبول: sqlite/postgres"
            )
        if self.store_backend == "postgres" and not self.pg_dsn:
            raise ConfigError(
                "PHARMA_SDL_STORE=postgres يستوجب PHARMA_SDL_PG_DSN صريحاً — "
                "لا ترقية صامتة ولا ادعاء تخزين بلا خدمة (ADR-0008)",
                "PHARMA_SDL_STORE=postgres requires an explicit PHARMA_SDL_PG_DSN — "
                "no silent upgrade, no claimed storage without a service (ADR-0008)",
            )
        if self.lims_timeout_s <= 0 or self.lims_poll_interval_s <= 0 or self.lims_max_polls < 1:
            raise ConfigError(
                "إعدادات LIMS يجب أن تكون موجبة "
                f"(timeout={self.lims_timeout_s}, poll={self.lims_poll_interval_s}, max_polls={self.lims_max_polls})"
            )
        if not 1 <= self.instrument_port <= 65535:
            raise ConfigError(f"PHARMA_SDL_INSTRUMENT_PORT خارج المجال (1..65535): {self.instrument_port}")
        if self.instrument_timeout_s <= 0:
            raise ConfigError(f"PHARMA_SDL_INSTRUMENT_TIMEOUT يجب أن يكون موجباً: {self.instrument_timeout_s}")


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
