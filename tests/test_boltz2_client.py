"""اختبارات P14 — عميل Boltz-2: عقد البيان المجمّد والتدهور الصادق.

تختبر السلوك المحلي فقط (لا شبكة، لا GPU، لا boltz): الغياب الصادق،
رفض المخططات الفاسدة، التحويل الموثق للوحدات، وسمعة النسب الكاملة.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from core.clients.boltz2_client import (
    MANIFEST_SCHEMA,
    Boltz2Client,
    affinity_to_ic50_um,
    affinity_to_pic50,
)

SMI = "CC(=O)Oc1ccccc1C(=O)O"  # أسبرين


def _valid_manifest() -> dict:
    return {
        "schema": MANIFEST_SCHEMA,
        "generated_at": "2026-11-04T00:00:00+00:00",
        "model": {
            "name": "boltz-2",
            "version": "test-0.4.3",
            "license": "MIT",
            "source_url": "https://github.com/jwohlwend/boltz",
        },
        "hardware": {"device": "NVIDIA T4", "colab": True},
        "receptor": {
            "name": "SARS-CoV-2 Mpro",
            "pdb_reference": "7VH8",
            "sequence_sha256": "a" * 64,
        },
        "predictions": [
            {
                "smiles": "CC(=O)OC1=CC=CC=C1C(=O)O",  # أسبرين بصيغة مختلفة التكتب
                "affinity_pred_value": -2.0,
                "affinity_probability_binary": 0.9,
                "iptm": 0.8,
                "ptm": 0.75,
                "seed": 0,
                "source": "boltz predict test.yaml --seed 0",
            }
        ],
    }


class TestUnitContract:
    """عقد الوحدات الرسمي — log10(IC50[μM]) كما وثّقه المستودع الرسمي."""

    def test_value_minus_two_is_ten_nanomolar(self):
        # −2.0 → 0.01 μM = 10 nM → pIC50 = 8.0
        assert affinity_to_ic50_um(-2.0) == pytest.approx(0.01)
        assert affinity_to_ic50_um(-2.0) * 1000.0 == pytest.approx(10.0)
        assert affinity_to_pic50(-2.0) == pytest.approx(8.0)

    def test_zero_value_is_micromolar(self):
        # 0.0 → 1 μM → pIC50 = 6.0
        assert affinity_to_ic50_um(0.0) == pytest.approx(1.0)
        assert affinity_to_pic50(0.0) == pytest.approx(6.0)

    def test_monotonic(self):
        # قيمة أصغر = تقارب أقوى = pIC50 أعلى
        assert affinity_to_pic50(-3.0) > affinity_to_pic50(-2.0)


class TestHonestDegradation:
    """الغياب والفساد → حالة صادقة بلا قيم مختلقة (المبدأ الحاكم)."""

    def test_missing_manifest_returns_none(self, tmp_path):
        assert Boltz2Client.load(tmp_path / "غير-موجود.json") is None

    def test_invalid_schema_rejected(self, tmp_path):
        p = tmp_path / "m.json"
        p.write_text(json.dumps({"schema": "مخطط-غريب", "predictions": []}), encoding="utf-8")
        assert Boltz2Client.load(p) is None

    def test_corrupt_json_rejected(self, tmp_path):
        p = tmp_path / "m.json"
        p.write_text("{这不是json", encoding="utf-8")
        assert Boltz2Client.load(p) is None

    def test_predictions_not_a_list_rejected(self, tmp_path):
        p = tmp_path / "m.json"
        p.write_text(json.dumps({"schema": MANIFEST_SCHEMA, "predictions": "x"}), encoding="utf-8")
        assert Boltz2Client.load(p) is None

    def test_bad_entries_excluded_individually(self, tmp_path):
        manifest = _valid_manifest()
        manifest["predictions"] += [
            {"smiles": SMI},  # بلا affinity_pred_value
            {"affinity_pred_value": -2.0},  # بلا smiles
            {"smiles": "SMILES-غير-صالح(", "affinity_pred_value": -2.0},
            {"smiles": SMI, "affinity_pred_value": "not-a-number"},
            "سطر نصي لا قاموس",
        ]
        p = tmp_path / "m.json"
        p.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
        client = Boltz2Client.load(p)
        assert client is not None
        assert client.status == "available"
        # المقياس الصالح الوحيد (أسبرين) نجا والباقي استُبعد دون انهيار
        assert client.lookup(SMI) is not None


class TestValidManifest:
    """البيان الصالح — قراءات كاملة وسمعة نسب لا تنقطع."""

    @pytest.fixture
    def client(self, tmp_path):
        p = tmp_path / "m.json"
        p.write_text(json.dumps(_valid_manifest(), ensure_ascii=False), encoding="utf-8")
        return Boltz2Client.load(p)

    def test_lookup_by_canonical_smiles(self, client):
        # الإدخال في البيان بتكتب مختلفة — البحث بالتقنين يجده
        rec = client.lookup(SMI)
        assert rec is not None
        assert rec.affinity_pred_value == pytest.approx(-2.0)

    def test_missing_molecule_returns_none(self, client):
        assert client.lookup("CCO") is None

    def test_reading_structure(self, client):
        reading = client.reading_for(SMI)
        assert reading["tier"] == 3
        assert reading["status"] == "available"
        assert reading["unit"] == "log10(IC50[μM])"
        assert reading["pic50"] == pytest.approx(8.0)
        assert reading["ic50_nm"] == pytest.approx(10.0, rel=1e-3)
        prov = reading["provenance"]
        assert prov["model"] == "boltz-2 test-0.4.3"
        assert prov["hardware"] == "NVIDIA T4"
        assert len(prov["manifest_sha256"]) == 64
        assert "boltz predict" in prov["source"]

    def test_reading_for_unknown_is_none(self, client):
        assert client.reading_for("CCO") is None

    def test_confidence_fields_optional(self, tmp_path):
        manifest = _valid_manifest()
        del manifest["predictions"][0]["iptm"]
        p = tmp_path / "m.json"
        p.write_text(json.dumps(manifest), encoding="utf-8")
        client = Boltz2Client.load(p)
        conf = client.reading_for(SMI)["confidence"]
        assert "iptm" not in conf          # المحذوف غائب
        assert conf.get("ptm") == 0.75     # الموجود نُقل كما هو
