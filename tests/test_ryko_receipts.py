"""اختبارات إيصالات Ryko — العقد الحتمي: نفس المدخل = نفس البصمة، والتلاعب يُكتشف."""

from __future__ import annotations

import pytest

from pharma_sdl.ryko import get_engine
from pharma_sdl.ryko.receipts import RykoReceipt


@pytest.fixture(scope="module")
def engine():
    return get_engine()


def _sample_receipt(engine) -> RykoReceipt:
    return engine.compute("math", "half_life", ke=0.231)


def test_same_inputs_same_digest(engine):
    """حتمية بالبايت — حسابان متطابقان ⇒ بصمة واحدة."""
    r1 = _sample_receipt(engine)
    r2 = _sample_receipt(engine)
    assert r1.digest == r2.digest
    assert len(r1.digest) == 64


def test_roundtrip_verify_stored(engine):
    """الإيصال المخزَّن يتحقق دون اتصال — إعادة حساب البصمة تطابق."""
    stored = _sample_receipt(engine).to_dict()
    assert RykoReceipt.verify_stored(stored) is True


def test_tampered_value_detected(engine):
    """تلاعب بالقيمة ⇒ التحقق يفشل (الإيصال قرار يُحسب لا وثيقة تُدَّعى)."""
    stored = _sample_receipt(engine).to_dict()
    stored["value"] = 9.999
    assert RykoReceipt.verify_stored(stored) is False


def test_tampered_source_detected(engine):
    """تلاعب بالمصدر ⇒ فشل — المصدر جزء من العقد."""
    stored = _sample_receipt(engine).to_dict()
    stored["source"] = "made up"
    assert RykoReceipt.verify_stored(stored) is False


def test_missing_digest_fails_closed():
    """إيصال بلا بصمة ⇒ فشل صريح (fail-closed) لا قبول صامت."""
    assert RykoReceipt.verify_stored({"module": "math", "op": "half_life"}) is False


def test_string_value_receipt_stable(engine):
    """النواتج النصية (كماولة/حكم) تدخل البصمة حتمياً."""
    r1 = engine.compute("chem", "validate_smiles", smiles="CCO")
    r2 = engine.compute("chem", "validate_smiles", smiles="CCO")
    assert r1.value == "CCO"
    assert r1.digest == r2.digest


def test_receipt_carries_formula_and_source(engine):
    """كل رقم معه معادلة ومصدر — العقد العلمي للمنصة."""
    r = _sample_receipt(engine)
    assert r.formula == "t½ = ln(2)/kₑ"
    assert r.source and r.source.strip()
    assert r.unit == "h"
