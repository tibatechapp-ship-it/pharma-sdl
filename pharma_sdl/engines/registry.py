"""سجل المحركات — نقطة الحقيقة الوحيدة لما هو متاح في هذه البيئة.

سطر واحد لإضافة محرك: أدخله إلى _build_registry(). الفرز والتقارير
وواجهة الـAPI تكتشفه تلقائياً — بلا أي تعديل آخر.
"""

from __future__ import annotations

from pharma_sdl.config import get_settings
from pharma_sdl.engines.base import DockingEngine, EngineStatus
from pharma_sdl.engines.boltz2 import Boltz2Engine
from pharma_sdl.engines.simulation import SimulationEngine
from pharma_sdl.engines.vina_engine import VinaEngine
from pharma_sdl.errors import EngineUnavailableError, ValidationError

_registry: dict[str, DockingEngine] | None = None


def _build_registry() -> dict[str, DockingEngine]:
    settings = get_settings()
    engines: dict[str, DockingEngine] = {}
    sim = SimulationEngine()
    engines[sim.name] = sim
    vina = VinaEngine(exhaustiveness=settings.vina_exhaustiveness)
    engines[vina.name] = vina
    boltz2 = Boltz2Engine(endpoint=settings.boltz2_endpoint)
    engines[boltz2.name] = boltz2
    return engines


def _get_registry() -> dict[str, DockingEngine]:
    global _registry
    if _registry is None:
        _registry = _build_registry()
    return _registry


def list_engines() -> list[EngineStatus]:
    """حالة كل المحركات كما تُعرض للمستخدم — بلا تجميل."""
    notes = {
        "simulation": (
            "متاح دائماً — درجات حتمية للتطوير وCI والعرض الفوري.",
            "Always available — deterministic scores for dev, CI and instant demos.",
        ),
        "vina": (
            "يتطلب vina + meeko (مثبتان في requirements.txt).",
            "Requires vina + meeko (both pinned in requirements.txt).",
        ),
        "boltz2": (
            "يتطلب PHARMA_SDL_BOLTZ2_ENDPOINT أو حزمة boltz محلية.",
            "Requires PHARMA_SDL_BOLTZ2_ENDPOINT or a local boltz package.",
        ),
    }
    out: list[EngineStatus] = []
    for name, engine in _get_registry().items():
        note_ar, note_en = notes.get(name, ("", ""))
        out.append(
            EngineStatus(
                name=name,
                label=engine.label,
                kind=engine.kind,
                available=engine.available(),
                note_ar=note_ar,
                note_en=note_en,
            )
        )
    return out


def get_engine(name: str | None) -> tuple[DockingEngine, str | None]:
    """محرك بالاسم مع سياسة تراجع صادقة إلى المحاكاة عند التهيئة بذلك.

    يعيد (المحرك، ملاحظة التراجع أو None) — الملاحظة تُسجَّل في النتيجة
    النهائية حتى لا يظن أحد أن درجات المحاكاة هي Vina.
    """
    settings = get_settings()
    requested = (name or settings.default_engine).strip()
    engines = _get_registry()
    if requested not in engines:
        known = ", ".join(engines)
        raise ValidationError(
            f"محرك غير معروف: {requested!r} — المعروف: {known}",
            f"Unknown engine: {requested!r} — known: {known}",
        )
    engine = engines[requested]
    if engine.available():
        return engine, None

    if not settings.engine_fallback:
        available_names = [n for n, e in engines.items() if e.available()]
        raise EngineUnavailableError(
            f"المحرك {requested!r} غير متاح (التراجع معطَّل) — المتاح: {available_names}",
            f"Engine {requested!r} unavailable (fallback disabled) — available: {available_names}",
        )
    fallback = engines[settings.default_engine]
    if not fallback.available():  # pragma: no cover — المحاكاة متاحة دائماً
        raise EngineUnavailableError(
            "لا يوجد محرك متاح على الإطلاق", "No engine available at all"
        )
    note_ar = (
        f"المحرك المطلوب {requested!r} غير متاح في هذه البيئة — نُفِّذت الجولة "
        f"بالمحرك الاحتياطي {fallback.name!r} (سقوط مُعلَن)."
    )
    return fallback, note_ar
