"""اختبارات التدهور الصادق للمحركات — مسارات الفشل بلا شبكة ولا أرقام مختلقة.

تقفل الفراغات المعلنة في تقييم 2026-11-13: pharma_sdl/engines/boltz2.py (47٪ —
مسارات التدهور/الغياب غير مختبرة) و pharma_sdl/engines/vina_engine.py (55٪ —
النمط نفسه). كل الاستدعاءات الخارجية تُستبدل بـmonkeypatch داخلياً — الاختبار
أوفلاين بالكامل وسريع، والرسائل الصادقة جزء من العقد (لا انهيار صامت).
"""

from __future__ import annotations

import pytest

import core.docking as core_docking
from pharma_sdl.engines.boltz2 import Boltz2Engine
from pharma_sdl.engines.vina_engine import VinaEngine
from pharma_sdl.errors import EngineUnavailableError, ScreeningError
from pharma_sdl.targets.models import Target, TargetPolicy
from pharma_sdl.targets.registry import get_target

TARGET = get_target("7VH8_A")


class _FakeResult:
    def __init__(self, best, scores):
        self.best = best
        self.scores = scores


class _FakeReceptor:
    def __init__(self, rid):
        self.id = rid


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


# ── Boltz-2: العقد الصادق — بلا بوابة بلا درجة ──────────────

def test_boltz2_without_endpoint_raises_honest_unavailable():
    engine = Boltz2Engine(endpoint=None)
    with pytest.raises(EngineUnavailableError):
        engine.score("CCO", TARGET)


def test_boltz2_endpoint_normalization_and_payload(monkeypatch):
    """الشريطة الأخيرة من الendpoint تُقص، والحمولة تُبنى من SMILES المُنظَّف."""
    engine = Boltz2Engine(endpoint="http://boltz.local/")
    seen = {}

    def _post(url, json=None, timeout=None):
        seen["url"], seen["json"], seen["timeout"] = url, json, timeout
        return _FakeResponse({"affinity_kcal": -8.4123, "probability": 0.71})

    monkeypatch.setattr("requests.post", _post)
    score = engine.score("  CCO  ", TARGET)
    assert engine.available() is True
    assert score.kcal == -8.41
    assert score.method == "boltz2-affinity"
    assert score.engine == "boltz2"
    assert score.details["probability"] == 0.71
    assert score.details["endpoint_configured"] is True
    assert seen["url"] == "http://boltz.local"
    assert seen["json"] == {"smiles": "CCO", "pdb_id": TARGET.pdb_id}
    assert seen["timeout"] == engine.timeout_s


def test_boltz2_accepts_affinity_alias_and_omits_missing_probability(monkeypatch):
    engine = Boltz2Engine(endpoint="http://boltz.local")
    monkeypatch.setattr(
        "requests.post",
        lambda url, json=None, timeout=None: _FakeResponse({"affinity": -7.9}),
    )
    score = engine.score("CCO", TARGET)
    assert score.kcal == -7.9
    assert "probability" not in score.details


def test_boltz2_rejects_non_numeric_affinity_honestly(monkeypatch):
    engine = Boltz2Engine(endpoint="http://boltz.local")
    monkeypatch.setattr(
        "requests.post",
        lambda url, json=None, timeout=None: _FakeResponse({"affinity_kcal": "very strong"}),
    )
    with pytest.raises(ScreeningError) as exc:
        engine.score("CCO", TARGET)
    assert any("affinity_kcal" in str(a) for a in exc.value.args)


def test_boltz2_wraps_gateway_connection_failure(monkeypatch):
    engine = Boltz2Engine(endpoint="http://boltz.local")

    def _boom(url, json=None, timeout=None):
        raise ConnectionError("boom")

    monkeypatch.setattr("requests.post", _boom)
    with pytest.raises(ScreeningError) as exc:
        engine.score("CCO", TARGET)
    assert "بوابة" in exc.value.message_ar
    assert "gateway" in exc.value.message_en


def test_boltz2_wraps_http_error_status(monkeypatch):
    import requests as requests_mod

    engine = Boltz2Engine(endpoint="http://boltz.local")

    class _BadResponse(_FakeResponse):
        def raise_for_status(self):
            raise requests_mod.HTTPError("500 server error")

    monkeypatch.setattr(
        "requests.post",
        lambda url, json=None, timeout=None: _BadResponse({"affinity_kcal": -8.0}),
    )
    with pytest.raises(ScreeningError) as exc:
        engine.score("CCO", TARGET)
    assert "بوابة" in exc.value.message_ar
    assert "gateway" in exc.value.message_en


# ── Vina: التدهور عند غياب البيئة أو المستقبل ───────────────

def _vina_ready(monkeypatch):
    monkeypatch.setattr(core_docking, "HAS_VINA", True)
    monkeypatch.setattr(core_docking, "HAS_MEEKO", True)


def test_vina_unavailable_raises_honest_error(monkeypatch):
    monkeypatch.setattr(core_docking, "HAS_VINA", False)
    monkeypatch.setattr(core_docking, "HAS_MEEKO", True)
    engine = VinaEngine()
    assert engine.available() is False
    with pytest.raises(EngineUnavailableError):
        engine.score("CCO", TARGET)


def test_vina_available_when_core_flags_are_set(monkeypatch):
    _vina_ready(monkeypatch)
    assert VinaEngine().available() is True


def test_vina_target_without_prepared_receptor_raises(monkeypatch):
    """هدف بلا مستقبل PDBQT جاهز = رفض صادق لا ادعاء ربط."""
    _vina_ready(monkeypatch)
    fake = Target(
        id="FAKE_NO_RECEPTOR",
        pdb_id="9XXX",
        name_ar="وهمي بلا مستقبل",
        name_en="fake without receptor",
        receptor_file="none.pdbqt",
        center=(0.0, 0.0, 0.0),
        box_size=(10.0, 10.0, 10.0),
        policy=TargetPolicy(),
    )
    with pytest.raises(ScreeningError) as exc:
        VinaEngine().score("CCO", fake)
    assert any("FAKE_NO_RECEPTOR" in str(a) for a in exc.value.args)


def test_vina_wraps_docking_runtime_failure(monkeypatch):
    _vina_ready(monkeypatch)
    monkeypatch.setattr(core_docking, "load_receptors", lambda: [_FakeReceptor(TARGET.id)])

    def _boom(*args, **kwargs):
        raise RuntimeError("grid exploded")

    monkeypatch.setattr(core_docking, "dock_ligand", _boom)
    with pytest.raises(ScreeningError) as exc:
        VinaEngine().score("CCO", TARGET)
    assert any("Vina" in str(a) for a in exc.value.args)


def test_vina_success_returns_rounded_scores_and_details(monkeypatch):
    _vina_ready(monkeypatch)
    monkeypatch.setattr(core_docking, "load_receptors", lambda: [_FakeReceptor(TARGET.id)])
    monkeypatch.setattr(
        core_docking,
        "dock_ligand",
        lambda smiles, receptor, n_poses, exhaustiveness: _FakeResult(
            -8.1234, [-8.1234, -7.5]
        ),
    )
    score = VinaEngine(exhaustiveness=16, n_poses=2).score("CCO", TARGET)
    assert score.kcal == -8.12
    assert score.method == "vina-docking"
    assert score.engine == "vina"
    assert score.details["exhaustiveness"] == 16
    assert score.details["n_poses"] == 2
    assert score.details["all_scores"] == [-8.12, -7.5]
    assert score.details["receptor_id"] == TARGET.id
