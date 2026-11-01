"""اختبارات سجل الأهداف وسياساتها — القرار D2 من الخطة v1.1."""

from __future__ import annotations

import pytest

from pharma_sdl.errors import NotFoundError
from pharma_sdl.targets.registry import get_target, list_targets


def test_targets_registry_has_mpro_and_plpro():
    targets = {t.id: t for t in list_targets()}
    assert "7VH8_A" in targets, "Mpro 7VH8 جاهز في المستودع"
    assert "7CMD_A" in targets, "PLpro 7CMD جاهز في المستودع"


def test_mpro_policy_is_non_covalent_only():
    mpro = get_target("7VH8_A")
    assert mpro.policy.non_covalent_only is True
    assert "v1.1" in mpro.policy.reason_ar
    assert "covalent" in mpro.policy.reason_en.lower()


def test_target_pocket_is_defined():
    mpro = get_target("7VH8_A")
    assert len(mpro.center) == 3 and all(v != 0 for v in mpro.center)
    assert all(v > 0 for v in mpro.box_size)
    assert mpro.receptor_file.endswith(".pdbqt")


def test_self_dock_reference_present():
    mpro = get_target("7VH8_A")
    assert mpro.self_dock_reference_kcal is not None
    assert -12.0 < mpro.self_dock_reference_kcal < 0.0


def test_unknown_target_raises_not_found():
    with pytest.raises(NotFoundError):
        get_target("9999_X")
