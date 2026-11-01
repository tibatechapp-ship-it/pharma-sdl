"""اختبارات سجل المحركات — التوفر الصادق والتراجع المعلن."""

from __future__ import annotations

import pytest

import core.docking as core_docking
from pharma_sdl.engines.registry import get_engine, list_engines
from pharma_sdl.errors import ValidationError
from pharma_sdl.targets.registry import get_target


def test_simulation_always_available_and_deterministic():
    engine, note = get_engine("simulation")
    assert note is None
    target = get_target("7VH8_A")
    s1 = engine.score("O=C(N)c1ccccc1", target)
    s2 = engine.score("O=C(N)c1ccccc1", target)
    assert s1.kcal == s2.kcal
    assert -10.5 <= s1.kcal <= -5.2
    assert s1.method == "simulation"


def test_simulation_differentiates_molecules():
    engine, _ = get_engine("simulation")
    target = get_target("7VH8_A")
    scores = {engine.score(sm, target).kcal for sm in
              ["O=C(N)c1ccccc1", "Cn1cnc2c1c(=O)n(C)c(=O)n2C", "CC(=O)Nc1ccccc1"]}
    assert len(scores) >= 2, "الهاش الحتمي يجب أن يفرّق بين الجزيئات غالباً"


def test_registry_lists_three_engines_with_honest_status():
    statuses = {e.name: e for e in list_engines()}
    assert set(statuses) == {"simulation", "vina", "boltz2"}
    assert statuses["simulation"].available is True
    assert statuses["vina"].available == bool(
        core_docking.HAS_VINA and core_docking.HAS_MEEKO
    )
    # بلا بوابة مضبوطة في بيئة الاختبار: boltz2 غير متاح بصدق
    import os

    if not os.getenv("PHARMA_SDL_BOLTZ2_ENDPOINT"):
        assert statuses["boltz2"].available is False


def test_unknown_engine_raises_validation_error():
    with pytest.raises(ValidationError):
        get_engine("warp-drive")


def test_fallback_to_simulation_is_announced():
    engine, note = get_engine("boltz2")  # بلا بوابة → تراجع
    import os

    if os.getenv("PHARMA_SDL_BOLTZ2_ENDPOINT"):
        pytest.skip("بوابة Boltz-2 مضبوطة في هذه البيئة")
    assert engine.name == "simulation"
    assert note is not None and "boltz2" in note


def test_default_engine_is_simulation():
    engine, note = get_engine(None)
    assert engine.name == "simulation"
    assert note is None
