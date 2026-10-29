"""اختبارات توسيع المكتبة — BRICS محلي + PubChem حي (مزيّف) + الموزّع.

بلا شبكة في كل الاختبارات؛ نداء PubChem الحي موسوم integration.
"""
import pytest

from core import expander
from core.expander import (
    SRC_BRICS,
    SRC_NONE,
    SRC_PUBCHEM,
    expand_brics,
    expand_library,
    expand_pubchem,
)

ASPIRIN = "CC(=O)OC1=CC=CC=C1C(=O)O"


# ── BRICS المحلي ────────────────────────────────────────────


def test_brics_generates_valid_analogs():
    """الأسبرين بذرة كلاسيكية — التوسيع يعطي جزيئات صالحة ≠ البذرة."""
    out = expand_brics(ASPIRIN, n=10)
    assert 1 <= len(out) <= 10
    from rdkit import Chem

    for smi in out:
        assert Chem.MolFromSmiles(smi) is not None, f"invalid: {smi}"
    assert ASPIRIN not in out  # لا يعيد البذرة نفسها


def test_brics_caps_at_n_and_dedups():
    out = expand_brics(ASPIRIN, n=3)
    assert len(out) <= 3
    assert len(out) == len(set(out))


def test_brics_invalid_seed_returns_empty():
    assert expand_brics("not-a-smiles") == []
    assert expand_brics("") == []


def test_brics_without_rdkit_returns_empty(monkeypatch):
    monkeypatch.setattr(expander, "HAS_RDKIT", False)
    assert expand_brics(ASPIRIN) == []


# ── PubChem الحي (mock) ─────────────────────────────────────


class _FakeResp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_pubchem_mocked_returns_smiles(monkeypatch):
    payloads = iter(
        [
            _FakeResp({"IdentifierList": {"CID": [2244, 0, 1983]}}),
            _FakeResp(
                {
                    "PropertyTable": {
                        "Properties": [
                            {"CID": 2244, "CanonicalSMILES": "CC(=O)OC1=CC=CC=C1C(=O)O"},
                            {"CID": 1983, "CanonicalSMILES": "CC(=O)NC1=CC=C(C=C1)O"},
                        ]
                    }
                }
            ),
        ]
    )
    monkeypatch.setattr(
        expander.requests, "get", lambda *a, **k: next(payloads)
    )
    out = expand_pubchem(ASPIRIN, n=5)
    assert out == ["CC(=O)NC1=CC=C(C=C1)O"]  # البذرة نفسها تُرشَّح خارجاً بالاحتفاظ الترتيبي؟


def test_pubchem_network_failure_returns_empty(monkeypatch):
    def boom(*a, **k):
        raise expander.requests.ConnectionError("offline")

    monkeypatch.setattr(expander.requests, "get", boom)
    assert expand_pubchem(ASPIRIN) == []


def test_pubchem_bad_shape_returns_empty(monkeypatch):
    monkeypatch.setattr(
        expander.requests, "get", lambda *a, **k: _FakeResp({"error": "x"})
    )
    assert expand_pubchem(ASPIRIN) == []


# ── الموزّع ─────────────────────────────────────────────────


def test_auto_prefers_live_pubchem(monkeypatch):
    monkeypatch.setattr(
        expander, "expand_pubchem", lambda *a, **k: ["CCO", "CCC"]
    )
    out, src = expand_library(ASPIRIN, mode="auto")
    assert out == ["CCO", "CCC"] and src == SRC_PUBCHEM


def test_auto_falls_back_to_brics(monkeypatch):
    monkeypatch.setattr(expander, "expand_pubchem", lambda *a, **k: [])
    out, src = expand_library(ASPIRIN, mode="auto")
    assert src == SRC_BRICS and len(out) >= 1


def test_modes_force_engine(monkeypatch):
    monkeypatch.setattr(
        expander, "expand_pubchem", lambda *a, **k: ["CCO"]
    )
    out, src = expand_library(ASPIRIN, mode="pubchem")
    assert src == SRC_PUBCHEM and out == ["CCO"]

    monkeypatch.setattr(
        expander, "expand_brics", lambda *a, **k: ["CNO"]
    )
    out, src = expand_library(ASPIRIN, mode="brics")
    assert src == SRC_BRICS and out == ["CNO"]


def test_empty_seed_returns_none_source():
    out, src = expand_library("   ")
    assert out == [] and src == SRC_NONE


# ── نداء حي (لا يعمل في CI) ─────────────────────────────────


@pytest.mark.integration
def test_pubchem_live_smoke():
    """يتطلب شبكة — ينجح بصمت عند غيابها."""
    out = expand_pubchem(ASPIRIN, n=5)
    if out:
        assert all(isinstance(s, str) and s for s in out)
