"""اختبارات الصحة العالمية (P15) — كلها بلا شبكة (نمط test_ersilia.py).

النداء الحي لخادم محلي موسوم integration ولا يعمل في CI.
"""
import pytest

from core import global_health as gh
from core.clients import ersilia_client as ec
from core.clients.ersilia_client import AdmetRow

# ── كتالوج الممرضين وعقد النماذج ────────────────────────────


def test_pathogen_catalog_complete():
    """ممرضان موثّقان، وكلاهما مربوط بنموذج Ersilia مُتحقَّق منه."""
    assert set(gh.PATHOGENS) == {"malaria", "tuberculosis"}
    for card in gh.PATHOGENS.values():
        assert card.model_id in ec.MODELS
        assert card.endpoint == ec.MODELS[card.model_id].endpoint
        assert card.who_cases and card.who_deaths and card.who_year == "2023"
        assert card.who_source_ar and card.who_source_en


def test_new_models_in_ersilia_catalog_with_verified_columns():
    """عقد المخرجات كما وثّقه مستودعا ersilia-os الرسميان."""
    assert ec.MODELS["eos4zfy"].column_hint == "maip_score"
    assert ec.MODELS["eos8d8a"].column_hint == "mycpermcheck"
    assert ec.MODELS["eos4zfy"].endpoint == "maip_score"
    assert ec.MODELS["eos8d8a"].endpoint == "mtb_permeability_prob"
    assert not ec.MODELS["eos4zfy"].low_good  # الاتجاه: high = أفضل
    assert not ec.MODELS["eos8d8a"].low_good


def test_who_burden_matches_verified_figures():
    """أرقام WHO كما نشرتها التقاريران 2024 (بيانات 2023) — لا تغيير بلا مرجع."""
    m, t = gh.PATHOGENS["malaria"], gh.PATHOGENS["tuberculosis"]
    assert m.who_cases == "263 مليون" and m.who_deaths == "597 ألف"
    assert "World Malaria Report 2024" in m.who_source_en
    assert t.who_cases == "10.8 مليون" and t.who_deaths == "1.25 مليون"
    assert "Global Tuberculosis Report 2024" in t.who_source_en


# ── الأحكام التعليمية للنموذجين الجديدين ─────────────────────


def test_maip_verdict_scale_bilingual():
    assert ec.verdict("eos4zfy", 3.0, "ar").startswith("مرشح قوي")
    assert ec.verdict("eos4zfy", 1.0, "ar").startswith("منطقة رمادية")
    assert ec.verdict("eos4zfy", -1.0, "ar") == "نشاط متوقع ضعيف"
    assert ec.verdict("eos4zfy", -1.0, "en") == "Weak predicted activity"


def test_mycperm_verdict_scale_bilingual():
    assert ec.verdict("eos8d8a", 0.9, "ar") == "نفاذية متوقعة"
    assert ec.verdict("eos8d8a", 0.5, "ar").startswith("منطقة رمادية")
    assert ec.verdict("eos8d8a", 0.1, "en") == "Weak permeability predicted"


# ── اللوحة المرجعية — SMILES موثّقة من PubChem ───────────────


def test_panel_five_molecules_valid_and_mw_matches():
    from rdkit import Chem
    from rdkit.Chem import Descriptors

    assert len(gh.GLOBAL_PRESETS) == 5
    for label, smi in gh.GLOBAL_PRESETS.items():
        mol = Chem.MolFromSmiles(smi)
        assert mol is not None, label
        assert abs(Descriptors.MolWt(mol) - gh.GLOBAL_PRESET_MW[smi]) < 0.5


def test_panel_covers_both_diseases_with_negative_control():
    """أرتيميسينين/كلوروكين للملاريا، إيزونيازيد/بيرازيناميد للسل، باراسيتامول سالبة."""
    labels = " ".join(gh.GLOBAL_PRESETS)
    assert "أرتيميسينين" in labels and "كلوروكين" in labels
    assert "إيزونيازيد" in labels and "بيرازيناميد" in labels
    assert "باراسيتامول" in labels


# ── assess_candidate — حقن كامل بلا شبكة ────────────────────


def _fake_client(value: float):
    def fn(smiles, model_id, timeout=None, base_url=None):
        return AdmetRow(
            model_id=model_id,
            smiles=smiles,
            endpoint=ec.MODELS[model_id].endpoint,
            value=value,
            verdict_ar=ec.verdict(model_id, value, "ar"),
            verdict_en=ec.verdict(model_id, value, "en"),
        )

    return fn


def test_assess_candidate_live_with_injected_client():
    row = gh.assess_candidate(
        "C[C@@H]1CC[C@H]2[C@H](C(=O)O[C@H]3[C@@]24[C@H]1CC[C@](O3)(OO4)C)C",
        "malaria",
        client_fn=_fake_client(3.5),
    )
    assert row.status == "live"
    assert row.value == 3.5
    assert row.verdict_en.startswith("Strong candidate")
    assert row.endpoint == "maip_score"


def test_assess_candidate_offline_is_honest():
    def dead(smiles, model_id, timeout=None, base_url=None):
        return None

    row = gh.assess_candidate("CCO", "tuberculosis", client_fn=dead)
    assert row.status == "unavailable_offline"
    assert row.value is None
    assert "مختلقة" in row.verdict_ar


def test_assess_candidate_invalid_smiles_skips_client():
    def fail(*a, **k):
        raise AssertionError("invalid input must not reach the server")

    row = gh.assess_candidate("not-a-smiles", "malaria", client_fn=fail)
    assert row.status == "invalid_input"
    assert row.value is None


def test_assess_candidate_unknown_pathogen_raises():
    with pytest.raises(ValueError, match="unknown pathogen_id"):
        gh.assess_candidate("CCO", "ebola")


def test_assess_panel_partial_success_counts():
    calls = {"n": 0}

    def flaky(smiles, model_id, timeout=None, base_url=None):
        calls["n"] += 1
        return None if calls["n"] == 2 else _fake_client(0.9)(smiles, model_id)

    rows = gh.assess_panel("tuberculosis", client_fn=flaky)
    assert len(rows) == 5
    statuses = [r.status for r in rows]
    assert statuses.count("live") == 4
    assert statuses.count("unavailable_offline") == 1


# ── قرار القمع — القواعد الخمس ──────────────────────────────


def test_funnel_honest_stop_on_missing_value():
    v = gh.funnel_decision("malaria", None, herg_value=0.9, logs_value=-6.0)
    assert v.stage_reached == 0
    assert v.decision_en == "Honest stop"


@pytest.mark.parametrize("pathogen", ["malaria", "tuberculosis"])
def test_funnel_stops_stage1_on_weak_activity(pathogen):
    v = gh.funnel_decision(pathogen, -5.0 if pathogen == "malaria" else 0.1)
    assert v.stage_reached == 1
    assert "Stop" in v.decision_en


def test_funnel_stops_stage2_on_herg_risk():
    v = gh.funnel_decision("malaria", 5.0, herg_value=0.9, logs_value=-1.0)
    assert v.stage_reached == 2
    assert "cardiotoxicity" in v.decision_en


def test_funnel_stops_stage2_on_poor_solubility():
    v = gh.funnel_decision("tuberculosis", 0.9, herg_value=0.05, logs_value=-6.0)
    assert v.stage_reached == 2
    assert "solubility" in v.decision_en


def test_funnel_passes_to_wet_lab_when_clean():
    v = gh.funnel_decision("malaria", 5.0, herg_value=0.05, logs_value=-1.0)
    assert v.stage_reached == 3
    assert v.decision_ar == "مرشح للمختبر الرطب"


def test_funnel_missing_admet_values_still_reaches_wet_lab():
    """بوابة ADMET الغائبة لا توقف المرشح النشط — لكن دون شهادة سمية."""
    v = gh.funnel_decision("tuberculosis", 0.9, herg_value=None, logs_value=None)
    assert v.stage_reached == 3


def test_funnel_unknown_pathogen_raises():
    with pytest.raises(ValueError, match="unknown pathogen_id"):
        gh.funnel_decision("malariax", 1.0)


# ── الدرس والعرض ────────────────────────────────────────────


def test_lesson_bilingual_mentions_both_diseases_and_numbers():
    ar, en = gh.trust_lesson("ar"), gh.trust_lesson("en")
    assert "263" in ar and "10.8" in ar and "الملاريا" in ar and "السل" in ar
    assert "263" in en and "10.8" in en and "malaria" in en.lower()
    assert gh.GLOBAL_LESSON["ar"] != gh.GLOBAL_LESSON["en"]


def test_panel_df_bilingual_columns():
    rows = gh.assess_panel("malaria", client_fn=_fake_client(1.5))
    df = gh.panel_df(rows, "ar")
    assert set(df[0]) == {"SMILES", "القيمة", "الحالة", "الحكم"}
    df_en = gh.panel_df(rows, "en")
    assert set(df_en[0]) == {"SMILES", "Value", "Status", "Verdict"}


def test_funnel_df_bilingual_columns():
    df = gh.funnel_df([gh.funnel_decision("malaria", None)], "ar")
    assert set(df[0]) == {"المرحلة", "القرار", "السبب"}
    df_en = gh.funnel_df([gh.funnel_decision("malaria", None)], "en")
    assert set(df_en[0]) == {"Stage", "Decision", "Reason"}


def test_fallback_reference_covers_new_models():
    for model_id in ("eos4zfy", "eos8d8a"):
        rows = ec.FALLBACK_REFERENCE[model_id]
        assert len(rows) >= 4
        for r in rows:
            assert r.example_ar and r.example_en and r.note_ar and r.note_en
    # درسان محوريان يجب أن يظلا في المرجعية
    assert any(r.example_en == "Artemisinin" for r in ec.FALLBACK_REFERENCE["eos4zfy"])
    assert any(
        r.example_en == "Isoniazid" for r in ec.FALLBACK_REFERENCE["eos8d8a"]
    )


def test_funnel_stages_documented():
    assert [s.stage_id for s in gh.PATHOGEN_FUNNEL] == [1, 2, 3]


# ── التجميد — عقد الملف (بلا شبكة) ──────────────────────────


def test_freeze_builder_schema_and_honest_live_status():
    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location(
        "verify_p15",
        str(Path(__file__).parents[1] / "scripts" / "verify_global_health_p15.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    freeze = mod.build_freeze()
    assert set(freeze) >= {
        "phase",
        "frozen_at_utc",
        "verification_evidence",
        "who_burden",
        "panel_checks",
        "live_status",
        "environment",
    }
    assert freeze["panel_checks"]["all_pass"] is True
    for ls in freeze["live_status"].values():
        assert ls["status"] in {"live", "unavailable_offline"}
        for r in ls["rows"]:
            # بلا خادم حي: إما قيمة حية أو حالة صادقة — لا قيم وهمية أبداً
            assert (r["value"] is None) == (r["status"] != "live")


# ── نداء حي (لا يعمل في CI) ──────────────────────────────────


@pytest.mark.integration
def test_global_health_live_local_server_smoke():
    """يتطلب خادماً محلياً: ersilia serve eos4zfy / eos8d8a — ينجح بصمت إن غاب."""
    for pid in gh.PATHOGENS:
        row = gh.assess_candidate("CCO", pid, timeout=5.0)
        if row.status == "live":
            assert row.value is not None
            assert row.verdict_ar
