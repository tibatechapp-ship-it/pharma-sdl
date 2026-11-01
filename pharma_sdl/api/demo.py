"""وضع العرض العام المحدود — عدالة الحساب المشترك (P2، تقييم #6).

النشر العام بلا حواجز = vina على نفقة المشغّل وإغراق بلا أثر. الوضع هنا:

    PHARMA_SDL_DEMO_MODE=1
    ├─ حد معدل لكل IP (token bucket) — الافتراضي 30 طلب/دقيقة، 429 صادق
    │  مع ترويسات X-RateLimit-* وRetry-After
    ├─ قفل المحركات على القائمة المسموحة (افتراضياً simulation حصراً)
    ├─ سقوف أدنى: 25 ليغاند/طلب وtop_n ≤ 10
    └─ /health يصرّح demo_mode: true — لا وضع محدود خفي

الحد ليس مصادقة ولا بديلاً عنها — هو حزام أمان للحساب المشترك، والمصادقة
تسبقه منطقياً (مفاتيح API في auth.py).
"""

from __future__ import annotations

import threading

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from pharma_sdl.api.deps import app_settings
from pharma_sdl.errors import RateLimitError


class TokenBucketLimiter:
    """دلو رموز لكل هوية (IP) — معدل ثابت، ذاكرة خفيفة، قفل واحد صادق.

    الساعة قابلة للحقن (clock) — للاختبارات الحتمية بلا انتظار حقيقي.
    """

    def __init__(self, rate_per_min: int, clock=None) -> None:
        import time as _time

        self.rate = max(1, int(rate_per_min))
        self.capacity = float(self.rate)
        self.refill_per_sec = self.rate / 60.0
        self._clock = clock or _time.monotonic
        self._tokens: dict[str, float] = {}
        self._updated: dict[str, float] = {}
        self._lock = threading.Lock()

    def allow(self, identity: str) -> tuple[bool, int, int]:
        """(مسموح؟، رموز متبقية، ثوانٍ حتى إعادة ملء كاملة)."""
        now = self._clock()
        with self._lock:
            tokens = self._tokens.get(identity, self.capacity)
            last = self._updated.get(identity, now)
            tokens = min(self.capacity, tokens + (now - last) * self.refill_per_sec)
            if tokens >= 1.0:
                tokens -= 1.0
                allowed = True
            else:
                allowed = False
            self._tokens[identity] = tokens
            self._updated[identity] = now
            remaining = int(tokens)
            deficit = 1.0 - tokens
            reset_s = int(deficit / self.refill_per_sec) if not allowed else 0
        return allowed, remaining, reset_s


_limiter: TokenBucketLimiter | None = None


def get_limiter() -> TokenBucketLimiter:
    """نسخة وحيدة — حد المعدل من الإعدادات (وضع العرض يفرض قيمة افتراضية)."""
    global _limiter
    if _limiter is None:
        settings = app_settings()
        rate = settings.rate_limit_per_min
        if settings.demo_mode and rate <= 0:
            rate = 30
        _limiter = TokenBucketLimiter(rate)
    return _limiter


def reset_limiter() -> None:
    """لاختبارات فقط."""
    global _limiter
    _limiter = None


def _identity(request: Request) -> str:
    """هوية المتصل — IP المباشر (خلف بروكسي معروف يُقرأ X-Forwarded-For الأول)."""
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def install_rate_limit(app: FastAPI) -> None:
    """تركيب وسيط حد المعدل — يعمل فقط حين حدّه الإعداد (أو وضع العرض)."""

    @app.middleware("http")
    async def _rate_limit_middleware(request: Request, call_next):
        settings = app_settings()
        active = settings.demo_mode or settings.rate_limit_per_min > 0
        if not active:
            return await call_next(request)
        limiter = get_limiter()
        allowed, remaining, reset_s = limiter.allow(_identity(request))
        headers = {
            "X-RateLimit-Limit": str(limiter.rate),
            "X-RateLimit-Remaining": str(remaining),
            "X-RateLimit-Reset": str(reset_s),
        }
        if not allowed:
            exc = RateLimitError(
                "تجاوزت حد المعدل المسموح — انتظر قليلاً قبل إعادة المحاولة "
                "(وضع العرض العام يشترك في حسابه الجميع)",
                "Rate limit exceeded — wait a moment and retry "
                "(the public demo shares its compute with everyone)",
            )
            return JSONResponse(
                status_code=exc.http_status,
                headers={**headers, "Retry-After": str(max(1, reset_s))},
                content={
                    "code": exc.code,
                    "message_ar": exc.message_ar,
                    "message_en": exc.message_en,
                },
            )
        response = await call_next(request)
        for key, value in headers.items():
            response.headers[key] = value
        return response


def demo_engine_allowed(engine: str | None) -> bool:
    """هل يُسمح بهذا المحرك في وضع العرض؟ القائمة من الإعدادات."""
    settings = app_settings()
    if not settings.demo_mode:
        return True
    allowed = {e.strip() for e in settings.demo_allowed_engines.split(",") if e.strip()}
    return (engine or "simulation") in allowed


def demo_caps() -> tuple[int, int]:
    """سقوف وضع العرض (ليغاندات، top_n) — أدنى السقفين العام والعرضي."""
    settings = app_settings()
    return (
        min(settings.max_ligands_per_run, settings.demo_max_ligands),
        min(settings.default_top_n, settings.demo_max_top_n),
    )


__all__ = [
    "TokenBucketLimiter",
    "demo_caps",
    "demo_engine_allowed",
    "get_limiter",
    "install_rate_limit",
    "reset_limiter",
]
