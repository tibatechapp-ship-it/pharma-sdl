"""اختبارات P14 — محرك المقارنة ثلاثية الطبقات: عقود اللوحة والاتفاق.

تختبر السلوك بلا Vina ولا شبكة: طبقة ML على نموذج صغير مدرَّب حياً،
طبقة Vina بحقن وهمي موثّق، وطبقة Boltz-2 ببيان مؤقت — والدرس العربي.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from core.clients.boltz2_client import MANIFEST_SCHEMA, Boltz2Client
from core.ml_potency import train_potency_model
from core.three_tier import (
    TierPanelEntry,
    agreement_label,
    boltz2_reading,
    boltz2_unavailable_placeholder,
    build_panel,
    ml_reading,
    nearest_anchor_gap,
    trust_lesson,
)

ASPIRIN = "CC(=O)Oc1ccccc1C(=O)O"
IBUPROFEN = "CC(C)Cc1ccc(cc1)C(C)C(=O)O"


@pytest.fixture(scope="module")
def tiny_model():
    """نموذج صغير مدرَّب حياً — اختبار السلوك لا دقة المقياس."""
    smiles = [ASPIRIN, IBUPROFEN, "CCO", "c1ccccc1O", "CCN", "CCC"] * 5
    pic50 = [6.2, 6.8, 3.0, 5.0, 4.0, 3.5] * 5
    return train_potency_model(smiles, pic50, random_state=42, n_estimators=10)


def _fake_vina(smiles: str, receptor_id: str, exhaustiveness: int):
    """حقن وهمي بنفس عقد القراءة الحقيقي — بلا Vina."""
    return {
        "tier": 2,
        "engine": "fake-vina",
        "status": "ok",
        "dg_kcal": -6.0,
        "pic50": 4.4,
        "n_poses": 5,
        "unit": "pIC50 (جسر Cheng-Prusoff من ΔG)",
    }


def _boltz_client(tmp_path, smiles: str, value: float = -2.0):
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "generated_at": "2026-11-04T00:00:00+00:00",
        "model": {"name": "boltz-2", "version": "test"},
        "hardware": {"device": "T4"},
        "receptor": {"name": "Mpro", "pdb_reference": "7VH8"},
        "predictions": [{"smiles": smiles, "affinity_pred_value": value, "seed": 0}],
    }
    p = tmp_path / "m.json"
    p.write_text(json.dumps(manifest), encoding="utf-8")
    return Boltz2Client.load(p)


class TestAgreementBands:
    """شرائط الاتفاق — معلنة لا مخمّنة."""

    def test_quantitative(self):
        assert "كمّي" in agreement_label(7.2, 7.8)

    def test_rough(self):
        assert "تقريبي" in agreement_label(7.2, 8.5)

    def test_conflict(self):
        assert "تعارض" in agreement_label(5.0, 8.0)

    def test_missing_side(self):
        assert "غير قابل" in agreement_label(None, 7.0)


class TestReadings:
    def test_ml_reading_shape(self, tiny_model):
        reading = ml_reading(tiny_model, ASPIRIN)
        assert reading["tier"] == 1
        assert reading["status"] == "ok"
        assert "pic50" in reading and "ci95" in reading
        lo, hi = reading["ci95"]
        assert lo <= reading["pic50"] <= hi

    def test_boltz2_reading_none_client(self):
        assert boltz2_reading(None, ASPIRIN) is None

    def test_boltz2_placeholder_honest(self):
        ph = boltz2_unavailable_placeholder()
        assert ph["status"] == "unavailable_offline"
        assert "Colab" in ph["note"]
        assert "pic50" not in ph  # لا قيمة مختلقة

    def test_boltz2_reading_not_in_manifest(self, tmp_path):
        client = _boltz_client(tmp_path, IBUPROFEN)
        reading = boltz2_reading(client, ASPIRIN)
        assert reading["status"] == "not_in_manifest"

    def test_boltz2_reading_full(self, tmp_path):
        client = _boltz_client(tmp_path, ASPIRIN, value=-2.0)
        reading = boltz2_reading(client, ASPIRIN)
        assert reading["status"] == "ok"  # مفردات اللوحة الموحّدة
        assert reading["pic50"] == pytest.approx(8.0)
        assert reading["provenance"]["receptor"] == "Mpro (7VH8)"


class TestPanel:
    def test_build_panel_with_injected_vina(self, tiny_model, tmp_path):
        entries = [
            TierPanelEntry(
                smiles=ASPIRIN,
                name_ar="أسبرين",
                name_en="Aspirin",
                anchor={"pic50": 7.6, "ic50_nm": 2.5},
            )
        ]
        client = _boltz_client(tmp_path, ASPIRIN, value=-2.0)
        rows = build_panel(entries, tiny_model, client, dock_fn=_fake_vina)
        assert len(rows) == 1
        row = rows[0]
        assert row["tier1_ml"]["tier"] == 1
        assert row["tier2_vina"]["pic50"] == 4.4
        assert row["tier3_boltz2"]["pic50"] == pytest.approx(8.0)
        assert set(row["agreement_vs_anchor"]) == {"ml", "vina", "boltz2"}
        assert row["closest_to_anchor"]["closest_tier"] == 3

    def test_build_panel_without_boltz_uses_placeholder(self, tiny_model):
        entries = [
            TierPanelEntry(smiles=IBUPROFEN, name_ar="إيبوبروفين", name_en="Ibuprofen")
        ]
        rows = build_panel(entries, tiny_model, None, dock_fn=_fake_vina)
        assert rows[0]["tier3_boltz2"]["status"] == "unavailable_offline"

    def test_nearest_anchor_gap_without_anchor(self):
        out = nearest_anchor_gap(None, [])
        assert "بلا مرجع" in out["verdict"]


class TestTrustLesson:
    def test_all_rules_arabic_and_complete(self):
        lesson = trust_lesson()
        assert set(lesson) == {"tier1_ml", "tier2_vina", "tier3_boltz2", "funnel_rule", "disagreement_rule"}
        for text in lesson.values():
            assert len(text) > 60  # درس حقيقي لا شعار
        assert "Colab" in lesson["tier3_boltz2"] or "GPU" in lesson["tier3_boltz2"]
        assert "8.28" in lesson["tier2_vina"]  # مرجع إعادة الربط الذاتي مذكور
