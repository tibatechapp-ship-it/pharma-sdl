"""واجهة المختبر الذاتي — FRET محاكى الآن، دمج حقيقي لاحقاً."""

from pharma_sdl.lab.interface import AssayRequest, LabClient
from pharma_sdl.lab.simulation import SimulatedFretLab

__all__ = ["AssayRequest", "LabClient", "SimulatedFretLab"]
