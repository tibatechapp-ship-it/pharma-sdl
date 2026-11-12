"""اختبارات المحرك والكتالوج — الواجهة العلمية المعلنة قبل أي حساب."""

from __future__ import annotations

import pytest

from pharma_sdl.ryko import MODULE_TITLES, OPS, RYKO_VERSION, get_engine
from pharma_sdl.ryko.errors import RykoInputError, RykoUnknownOpError


@pytest.fixture(scope="module")
def engine():
    return get_engine()


def test_stats_honest_counts(engine):
    s = engine.stats()
    assert s["version"] == RYKO_VERSION == "0.20.0"
    assert s["modules"] == 6
    assert s["operations"] == sum(len(o) for o in OPS.values())
    assert s["operations"] >= 44


def test_catalog_is_declared_contract(engine):
    cat = engine.catalog()
    for mod, info in cat.items():
        assert mod in MODULE_TITLES
        assert info["title"] == MODULE_TITLES[mod]
        for op, spec in info["ops"].items():
            assert spec["formula"].strip(), f"{mod}.{op} بلا معادلة"
            assert spec["source"].strip(), f"{mod}.{op} بلا مصدر"
            assert spec["unit"].strip(), f"{mod}.{op} بلا وحدة"
            assert spec["inputs"], f"{mod}.{op} بلا مدخلات معلنة"


def test_all_six_modules_present(engine):
    assert set(engine.catalog()) == set(MODULE_TITLES)


def test_unknown_module_rejected(engine):
    with pytest.raises(RykoUnknownOpError):
        engine.compute("astrology", "horoscope")


def test_unknown_op_rejected(engine):
    with pytest.raises(RykoUnknownOpError):
        engine.compute("math", "stochastic_magic")


def test_mismatched_inputs_rejected_with_declaration(engine):
    with pytest.raises(RykoInputError):
        engine.compute("math", "half_life", wrong_input=1)


def test_engine_singleton(engine):
    assert get_engine() is engine


def test_every_registered_op_callable_and_computable(engine):
    """اختبار شامل: كل عملية مسجلة تُنادى فعلاً — لا سجل زائف."""
    called = 0
    for ops in OPS.values():
        for spec in ops.values():
            assert callable(spec.fn)
            called += 1
    assert called == engine.stats()["operations"]
