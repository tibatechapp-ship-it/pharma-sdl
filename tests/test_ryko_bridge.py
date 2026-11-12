"""اختبارات جسر Ryko إلى سلسلة القرار — P20.

الجسر لا يحسب بنفسه: كل إيصال يخرج عبر عملية معلنة في الكتالوج، والبصمة
تتحقق دون اتصال (`RykoReceipt.verify_stored`). الذهبية محسوبة يدوياً:
pIC50=7 ⇒ IC50=100nM · Ki=IC50/(1+[L]/Kd)=100/1.5 · C90 عند γ=1 ⇒ Hill=0.90.
"""

from __future__ import annotations

import pytest

from pharma_sdl.ryko import RykoInputError, RykoReceipt, get_engine
from pharma_sdl.ryko.decision_bridge import (
    receipts_for_candidate,
    receipts_for_reading,
    stored,
)


@pytest.fixture(scope="module")
def model():
    from core.ml_potency import load_dataset, train_potency_model

    df = load_dataset()
    return train_potency_model(
        df["smiles"].tolist(), df["pchembl_value"].tolist(), n_estimators=40
    )


@pytest.fixture(scope="module")
def library():
    from core.capstone import offline_library

    return offline_library(n=60, seed=7)


# ── العملية الجديدة في الكتالوج ──────────────────────────────


def test_pic50_to_ic50_registered_in_catalog():
    spec = get_engine().catalog()["math"]["ops"]["pic50_to_ic50"]
    assert spec["formula"] == "IC50[nM] = 10^(9−pIC50)"
    assert spec["source"].strip()
    assert spec["inputs"] == {"pic50": "pIC50"}


def test_stats_count_grows_honestly():
    s = get_engine().stats()
    assert s["modules"] == 6
    assert s["operations"] == sum(len(o) for o in __import__(
        "pharma_sdl.ryko", fromlist=["OPS"]
    ).OPS.values())
    assert s["operations"] >= 44  # 43 (P19) + pic50_to_ic50 (P20)


# ── receipts_for_reading ────────────────────────────────────


def test_pic50_golden_receipt():
    recs = receipts_for_reading({"status": "ok", "tier": 1, "pic50": 7.0})
    assert len(recs) == 1
    rec = recs[0]
    assert (rec.module, rec.op) == ("math", "pic50_to_ic50")
    assert abs(float(rec.value) - 100.0) < 1e-9
    assert rec.unit == "nM"
    assert rec.extra["ic50_um"] == pytest.approx(0.1)


def test_reading_receipts_verify_offline():
    for doc in stored(receipts_for_reading({"status": "ok", "pic50": 8.5})):
        assert RykoReceipt.verify_stored(doc)


def test_cheng_prusoff_receipt_from_reading():
    recs = receipts_for_reading(
        {"status": "ok", "pic50": 7.0}, ligand_nm=50.0, kd_nm=100.0
    )
    assert [r.op for r in recs] == ["pic50_to_ic50", "cheng_prusoff_ki"]
    ki = recs[-1]
    assert ki.source.startswith("Cheng & Prusoff")
    assert abs(float(ki.value) - 100.0 / 1.5) < 1e-9  # 66.67 nM


def test_kd_from_dg_receipt_and_roundtrip():
    recs = receipts_for_reading(
        {"status": "ok", "tier": 2, "dg_kcal": -10.0}, temp_c=25.0
    )
    kd = recs[-1]
    assert (kd.module, kd.op) == ("physics", "kd_from_dg")
    assert kd.unit == "uM"
    assert kd.extra["T_K"] == pytest.approx(298.15)
    # قراءة عكسية عبر عملية معلنة أخرى: ΔG من Kd يعيد −10 بالضبط
    dg_back = get_engine().compute(
        "physics", "binding_dg", kd_um=float(kd.value), temp_c=25.0
    )
    assert float(dg_back.value) == pytest.approx(-10.0, abs=1e-9)


def test_failed_or_empty_reading_is_honest_absence():
    """قراءة فاشلة/غائبة ⇒ قائمة فارغة — غياب صادق، لا إيصال مختلق."""
    assert receipts_for_reading(None) == []
    assert receipts_for_reading({}) == []
    assert receipts_for_reading({"status": "not_in_manifest", "pic50": 7.0}) == []
    assert receipts_for_reading({"status": "unavailable_no_poses"}) == []


def test_out_of_range_pic50_rejected_with_bilingual_error():
    with pytest.raises(RykoInputError, match="pIC50"):
        receipts_for_reading({"status": "ok", "pic50": 99.0})


# ── receipts_for_candidate (سلسلة القرار في capstone) ───────


def test_candidate_receipts_occupancy_proof():
    """C90 من capstone عند γ=1 ⇒ إيصال Hill يُظهر أثراً = 0.90 بالضبط."""
    recs = receipts_for_candidate(pic50=7.0, conc_nm=900.0, hill_coeff=1.0)
    assert [r.op for r in recs] == ["pic50_to_ic50", "hill_effect"]
    assert abs(float(recs[1].value) - 0.90) < 1e-9
    assert recs[1].extra["fraction_of_emax"] == pytest.approx(0.90)
    for doc in stored(recs):
        assert RykoReceipt.verify_stored(doc)


def test_candidate_receipts_honour_hill_coeff():
    """γ ≠ 1 يعمل حتمياً: C90 = IC50·9^(1/γ) يحقق 0.90 عند أي γ."""
    gamma = 1.7
    c90 = 100.0 * (9.0 ** (1.0 / gamma))  # IC50=100nM (pIC50=7)
    recs = receipts_for_candidate(pic50=7.0, conc_nm=c90, hill_coeff=gamma)
    assert float(recs[1].value) == pytest.approx(0.90, abs=1e-9)


# ── الجسر في التقارير (Markdown) ────────────────────────────


def test_markdown_report_embeds_receipts_section(library, model):
    """تقرير capstone يحمل إيصالات Ryko — العملية والقيمة والبصمة."""
    from core.capstone import build_markdown_report, c90_nm, run_pipeline

    res = run_pipeline(library, dose_mg=300, source="اختبار", model=model)
    valid = res.top.dropna(subset=["pic50"])
    recs = receipts_for_candidate(
        pic50=float(valid.iloc[0].pic50),
        conc_nm=float(c90_nm(float(valid.iloc[0].pic50))),
    )
    md = build_markdown_report(res, ryko_receipts=stored(recs))
    assert "إيصالات Ryko" in md
    assert "math.pic50_to_ic50" in md
    assert "pharma.hill_effect" in md
    assert "RykoReceipt.verify_stored" in md
    # البصمة كاملة الظهور (12 حرفاً + …)
    for doc in stored(recs):
        assert doc["digest"][:12] in md


def test_markdown_report_without_receipts_unchanged(library, model):
    """بلا إيصالات: التقرير كما في P19 حرفياً — لا قسم فارغ زائف."""
    from core.capstone import build_markdown_report, run_pipeline

    res = run_pipeline(library, dose_mg=300, source="اختبار", model=model)
    md = build_markdown_report(res)
    assert "إيصالات Ryko" not in md
