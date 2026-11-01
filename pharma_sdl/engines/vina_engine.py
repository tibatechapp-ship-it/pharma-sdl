"""محرك AutoDock Vina — يجسر فوق خط core.docking المُتحقق منه في هذا المستودع.

نفس المستقبلات المُجهَّزة (data/receptors/*.pdbqt)، نفس تحضير Meeko،
نفس صناديق الربط المشتقة من الليغاند المشتبك — لكن خلف عقد محرك موحّد.
المتطلبات: pip install vina meeko (موجودان في requirements.txt).
"""

from __future__ import annotations

import core.docking as core_docking
from pharma_sdl.engines.base import EngineScore
from pharma_sdl.errors import EngineUnavailableError, ScreeningError
from pharma_sdl.targets.models import Target


class VinaEngine:
    """ربط جزيئي فعلي بـVina 1.2 — الربط مع مستقبلات المُستودع الجاهزة."""

    name = "vina"
    label = "AutoDock Vina 1.2 (ربط فعلي)"
    kind = "docking"

    def __init__(self, exhaustiveness: int = 8, n_poses: int = 3) -> None:
        self.exhaustiveness = exhaustiveness
        self.n_poses = n_poses

    def available(self) -> bool:
        return bool(core_docking.HAS_VINA and core_docking.HAS_MEEKO)

    def _receptor_for(self, target: Target):
        for rec in core_docking.load_receptors():
            if rec.id == target.id:
                return rec
        raise ScreeningError(
            f"لا يوجد مستقبل PDBQT جاهز للهدف {target.id}",
            f"No prepared PDBQT receptor for target {target.id}",
        )

    def score(self, smiles: str, target: Target) -> EngineScore:
        if not self.available():
            raise EngineUnavailableError(
                "vina/meeko غير متاحين في هذه البيئة — ركّبهما أو استخدم محرك المحاكاة",
                "vina/meeko unavailable here — install them or use the simulation engine",
            )
        receptor = self._receptor_for(target)
        try:
            result = core_docking.dock_ligand(
                smiles,
                receptor,
                n_poses=self.n_poses,
                exhaustiveness=self.exhaustiveness,
            )
        except (ValueError, RuntimeError) as exc:
            raise ScreeningError(
                f"فشل الربط بـVina: {exc}",
                f"Vina docking failed: {exc}",
            ) from exc
        best = result.best
        if best is None:  # pragma: no cover — Vina يعيد بوزات دائماً عند النجاح
            raise ScreeningError("Vina لم يُرجع أي بوز", "Vina returned no poses")
        return EngineScore(
            kcal=round(float(best), 2),
            method="vina-docking",
            engine=self.name,
            details={
                "exhaustiveness": self.exhaustiveness,
                "n_poses": self.n_poses,
                "all_scores": [round(float(s), 2) for s in result.scores],
                "receptor_id": receptor.id,
            },
        )
