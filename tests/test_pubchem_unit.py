"""
Unit tests for PubChemClient with mocked HTTP.
لا تحتاج إنترنت — تعمل بسرعة < 0.1s.
تُغطي جميع فروع الكود (نجاح، فشل، cache، fallback).
"""
from unittest.mock import patch

import requests

from core.pubchem_client import PubChemClient


class MockResponse:
    def __init__(self, status_code=200, json_data=None):
        self.status_code = status_code
        self._json = json_data or {}

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


# ═══════════════════════════════════════════════════════════════
# get_cid
# ═══════════════════════════════════════════════════════════════

@patch("core.pubchem_client.time.sleep", return_value=None)
@patch("core.pubchem_client.requests.Session.get")
def test_get_cid_success(mock_get, mock_sleep):
    mock_get.return_value = MockResponse(200, {"IdentifierList": {"CID": [2244]}})
    client = PubChemClient()
    assert client.get_cid("aspirin") == 2244


@patch("core.pubchem_client.time.sleep", return_value=None)
@patch("core.pubchem_client.requests.Session.get")
def test_get_cid_not_found(mock_get, mock_sleep):
    mock_get.return_value = MockResponse(404)
    client = PubChemClient()
    assert client.get_cid("unknown") is None


@patch("core.pubchem_client.time.sleep", return_value=None)
@patch("core.pubchem_client.requests.Session.get")
def test_get_cid_network_error(mock_get, mock_sleep):
    mock_get.side_effect = requests.RequestException("timeout")
    client = PubChemClient()
    assert client.get_cid("aspirin") is None


# ═══════════════════════════════════════════════════════════════
# get_properties
# ═══════════════════════════════════════════════════════════════

@patch("core.pubchem_client.time.sleep", return_value=None)
@patch("core.pubchem_client.requests.Session.get")
def test_get_properties_success(mock_get, mock_sleep):
    mock_get.return_value = MockResponse(200, {
        "PropertyTable": {"Properties": [{
            "MolecularWeight": "180.16",
            "SMILES": "CC(=O)OC1=CC=CC=C1C(=O)O",
            "XLogP": "1.2",
        }]}
    })
    client = PubChemClient()
    props = client.get_properties(2244)
    assert props["MolecularWeight"] == "180.16"


@patch("core.pubchem_client.time.sleep", return_value=None)
@patch("core.pubchem_client.requests.Session.get")
def test_get_properties_cached(mock_get, mock_sleep):
    mock_get.return_value = MockResponse(200, {
        "PropertyTable": {"Properties": [{"MolecularWeight": "180.16"}]}
    })
    client = PubChemClient()
    client.get_properties(2244)
    client.get_properties(2244)
    assert mock_get.call_count == 1


@patch("core.pubchem_client.time.sleep", return_value=None)
@patch("core.pubchem_client.requests.Session.get")
def test_get_properties_404(mock_get, mock_sleep):
    mock_get.return_value = MockResponse(404)
    client = PubChemClient()
    assert client.get_properties(999) is None


# ═══════════════════════════════════════════════════════════════
# _extract_smiles (fallback logic)
# ═══════════════════════════════════════════════════════════════

def test_extract_smiles_primary():
    smiles = PubChemClient._extract_smiles({"SMILES": "CCO"})
    assert smiles == "CCO"


def test_extract_smiles_fallback_canonical():
    smiles = PubChemClient._extract_smiles({"CanonicalSMILES": "CCO"})
    assert smiles == "CCO"


def test_extract_smiles_fallback_isomeric():
    smiles = PubChemClient._extract_smiles({"IsomericSMILES": "CCO"})
    assert smiles == "CCO"


def test_extract_smiles_none():
    smiles = PubChemClient._extract_smiles({})
    assert smiles is None


def test_extract_smiles_empty_string():
    smiles = PubChemClient._extract_smiles({"SMILES": "   "})
    assert smiles is None


# ═══════════════════════════════════════════════════════════════
# fetch_drug (full flow)
# ═══════════════════════════════════════════════════════════════

@patch("core.pubchem_client.time.sleep", return_value=None)
@patch("core.pubchem_client.requests.Session.get")
def test_fetch_drug_success(mock_get, mock_sleep):
    def side_effect(url, **kwargs):
        if "cids" in url:
            return MockResponse(200, {"IdentifierList": {"CID": [2244]}})
        return MockResponse(200, {
            "PropertyTable": {"Properties": [{
                "SMILES": "CC(=O)OC1=CC=CC=C1C(=O)O",
                "MolecularWeight": "180.16",
                "MolecularFormula": "C9H8O4",
                "XLogP": "1.2",
            }]}
        })
    mock_get.side_effect = side_effect
    client = PubChemClient()
    data = client.fetch_drug("aspirin")
    assert data["cid"] == 2244
    assert data["name"] == "aspirin"
    assert data["smiles"] == "CC(=O)OC1=CC=CC=C1C(=O)O"
    assert data["mw"] == "180.16"


@patch("core.pubchem_client.time.sleep", return_value=None)
@patch("core.pubchem_client.requests.Session.get")
def test_fetch_drug_not_found(mock_get, mock_sleep):
    mock_get.return_value = MockResponse(404)
    client = PubChemClient()
    assert client.fetch_drug("not_a_drug") is None


# ═══════════════════════════════════════════════════════════════
# get_cid_from_smiles
# ═══════════════════════════════════════════════════════════════

@patch("core.pubchem_client.time.sleep", return_value=None)
@patch("core.pubchem_client.requests.Session.get")
def test_get_cid_from_smiles(mock_get, mock_sleep):
    mock_get.return_value = MockResponse(200, {"IdentifierList": {"CID": [2244]}})
    client = PubChemClient()
    assert client.get_cid_from_smiles("CC(=O)OC1=CC=CC=C1C(=O)O") == 2244
