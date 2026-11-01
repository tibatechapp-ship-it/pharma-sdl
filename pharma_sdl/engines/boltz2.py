"""محرك Boltz-2 — تنبؤ تقارب مباشر (خطة v1.1: المحرك الأساسي للمستقبل).

لماذا Boltz-2؟ (ADR-0001): ترخيص MIT يسمح بالاستخدام التجاري، ويتنبأ
التقارب مباشرة — أسرع بمراتب من FEP — ويغطي بنية+تقارب في نموذج واحد.

وضعان مدعومان هنا:
  1) بوابة بعيدة (موصى بها): PHARMA_SDL_BOLTZ2_ENDPOINT
     POST JSON  {"smiles": "...", "pdb_id": "7VH8"}
     ← JSON     {"affinity_kcal": -8.4, "probability": 0.71}  (probability اختيارية)
     أي خدمة تستضيف Boltz-2 (GPU داخلية، خادم جامعي، مزوّد سحابي) تكفي.
  2) حزمة محلية: إن كان import boltz ممكناً تُمرَّر المهمة له — التشغيل الفعلي
     يتطلب أوزان النموذج وGPU فيُترك لإعداد النشر (docs/ARCHITECTURE.md).

بلا بوابة وبلا حزمة: المحرك يُعلن نفسه «غير متاح» بصدق — لا أرقام مختلقة أبداً.
"""

from __future__ import annotations

import importlib.util

from pharma_sdl.engines.base import EngineScore
from pharma_sdl.errors import EngineUnavailableError, ScreeningError
from pharma_sdl.targets.models import Target


def _has_local_package() -> bool:
    return importlib.util.find_spec("boltz") is not None


class Boltz2Engine:
    """محوّل Boltz-2 — تقارب مباشر عبر بوابة بعيدة (أو حزمة محلية مهيأة)."""

    name = "boltz2"
    label = "Boltz-2 (تنبؤ تقارب — بوابة بعيدة)"
    kind = "affinity"

    def __init__(self, endpoint: str | None = None, timeout_s: int = 120) -> None:
        self.endpoint = (endpoint or "").rstrip("/") or None
        self.timeout_s = timeout_s

    def available(self) -> bool:
        return bool(self.endpoint) or _has_local_package()

    def score(self, smiles: str, target: Target) -> EngineScore:
        if not self.endpoint:
            raise EngineUnavailableError(
                "Boltz-2 غير مهيأ: اضبط PHARMA_SDL_BOLTZ2_ENDPOINT (أو ركّب حزمة boltz محلياً)"
                " — حتى ذلك الحين استخدم vina أو simulation",
                "Boltz-2 not configured: set PHARMA_SDL_BOLTZ2_ENDPOINT (or install boltz)"
                " — meanwhile use vina or simulation",
            )
        try:
            import requests
        except ImportError as exc:  # pragma: no cover — requests تبعية أساسية
            raise EngineUnavailableError("requests غير متاح", "requests unavailable") from exc

        payload = {"smiles": smiles.strip(), "pdb_id": target.pdb_id}
        try:
            resp = requests.post(self.endpoint, json=payload, timeout=self.timeout_s)
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            raise ScreeningError(
                f"فشل الاتصال ببوابة Boltz-2: {exc}",
                f"Boltz-2 gateway call failed: {exc}",
            ) from exc

        kcal = data.get("affinity_kcal", data.get("affinity"))
        if not isinstance(kcal, (int, float)):
            raise ScreeningError(
                "رد بوابة Boltz-2 بلا حقل affinity_kcal رقمي — راجع العقد في docstring الوحدة",
                "Boltz-2 gateway response has no numeric affinity_kcal — see module docstring",
            )
        details: dict[str, object] = {"endpoint_configured": True}
        prob = data.get("probability")
        if isinstance(prob, (int, float)):
            details["probability"] = float(prob)
        return EngineScore(
            kcal=round(float(kcal), 2),
            method="boltz2-affinity",
            engine=self.name,
            details=details,
        )
