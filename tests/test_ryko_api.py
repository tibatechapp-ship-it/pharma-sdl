"""اختبارات بوابة Ryko API — نفس العقد عبر HTTP (بلا شبكة)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from pharma_sdl.api.app import create_app
from pharma_sdl.ryko import RYKO_VERSION


@pytest.fixture(scope="module")
def client():
    return TestClient(create_app())


def test_catalog_exposes_declared_contract(client):
    resp = client.get("/api/v1/ryko/catalog")
    assert resp.status_code == 200
    body = resp.json()
    assert body["version"] == RYKO_VERSION
    assert body["modules"] == 6
    assert body["operations"] >= 40
    for info in body["catalog"].values():
        assert info["title"]
        for spec in info["ops"].values():
            assert spec["formula"] and spec["source"]


def test_compute_returns_verifiable_receipt(client):
    resp = client.post("/api/v1/ryko/compute", json={
        "module": "math", "op": "half_life", "inputs": {"ke": 0.231},
    })
    assert resp.status_code == 200
    body = resp.json()
    assert abs(body["value"] - 3.0006) < 1e-3
    assert body["formula"] == "t½ = ln(2)/kₑ"
    assert len(body["digest"]) == 64


def test_compute_deterministic_over_http(client):
    body = {"module": "physics", "op": "binding_dg",
            "inputs": {"kd_um": 1.0, "temp_c": 25.0}}
    d1 = client.post("/api/v1/ryko/compute", json=body).json()["digest"]
    d2 = client.post("/api/v1/ryko/compute", json=body).json()["digest"]
    assert d1 == d2


def test_unknown_operation_is_404_bilingual(client):
    resp = client.post("/api/v1/ryko/compute", json={
        "module": "math", "op": "does_not_exist", "inputs": {},
    })
    assert resp.status_code == 404
    detail = resp.json()["detail"]
    assert detail["ar"] and detail["en"]


def test_domain_violation_is_422_bilingual(client):
    resp = client.post("/api/v1/ryko/compute", json={
        "module": "math", "op": "half_life", "inputs": {"ke": 0},
    })
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert detail["ar"] and detail["en"]


def test_invalid_smiles_is_422(client):
    resp = client.post("/api/v1/ryko/compute", json={
        "module": "chem", "op": "validate_smiles", "inputs": {"smiles": "!!bad!!"},
    })
    assert resp.status_code == 422


def test_compute_accepts_lists_and_booleans(client):
    resp = client.post("/api/v1/ryko/compute", json={
        "module": "pharmaceutics", "op": "bcs_class",
        "inputs": {"dose_number": 0.8, "permeability_high": True},
    })
    assert resp.status_code == 200
    assert resp.json()["value"] == "I"


def test_diagnostics_seed_over_http(client):
    resp = client.post("/api/v1/ryko/compute", json={
        "module": "diagnostics", "op": "ppv_npv",
        "inputs": {"sensitivity": 0.9, "specificity": 0.9, "prevalence": 0.1},
    })
    assert resp.status_code == 200
    assert abs(resp.json()["value"] - 0.5) < 1e-9
