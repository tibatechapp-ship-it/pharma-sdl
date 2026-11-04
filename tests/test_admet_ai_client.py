"""اختبارات عميل ADMET-AI — عقود mock بلا torch تعمل في كل بيئة.

الاختبار الحي (يحتاج admet-ai مثبّتة) موسوم ويتخطى تلقائياً في CI.
"""
import sys
from types import ModuleType, SimpleNamespace

import pytest

from core.clients import admet_ai_client as ai
from core.clients.admet_ai_client import (
    ADMET_AI_LESSON,
    INSTALL_HINT_AR,
    INSTALL_HINT_EN,
    ML_TASKS,
    TASKS,
    AdmetAIResult,
    is_available,
    percentile_task_id,
    predict_admet_ai_batch,
    reset_model,
    verdict,
)

# ── الكتالوج — عقود الأعداد المعلَنة ─────────────────────────


def test_catalog_counts_match_published_contract():
    """41 مهمة ML + 3 إنذارات بنيوية + 8 وصفات = 52 عمود إخراج موثّق."""
    kinds = [t.kind for t in TASKS.values()]
    assert kinds.count("classification") == 31
    assert kinds.count("regression") == 10
    assert kinds.count("structural_alert") == 3
    assert kinds.count("physchem") == 8
    assert len(TASKS) == 52
    assert len(ML_TASKS) == 41
    assert len(set(TASKS)) == len(TASKS)  # لا تكرار في المعرفات


def test_flagship_tasks_present():
    """نقاط النهاية الرائدة — التي يذكرها التقرير والدروس."""
    required = {
        "hERG", "AMES", "DILI", "ClinTox", "Carcinogens_Lagunin",
        "BBB_Martins", "Bioavailability_Ma", "HIA_Hou", "Solubility_AqSolDB",
        "Caco2_Wang", "PPBR_AZ", "VDss_Lombardo", "Half_Life_Obach",
        "CYP3A4_Veith", "Pgp_Broccatelli", "Skin_Reaction",
        "PAINS_alert", "BRENK_alert", "NIH_alert",
    }
    assert required <= set(TASKS)
    # مهام CYP الثماني: تثبيط 5 (Veith: 1A2/2C19/2C9/2D6/3A4) + ركيزة 3 (CarbonMangels)
    cyp = {t for t in TASKS if t.startswith("CYP")}
    assert len(cyp) == 8
    assert {"CYP1A2_Veith", "CYP2C19_Veith", "CYP2C9_Veith", "CYP2D6_Veith", "CYP3A4_Veith"} <= cyp


def test_task_cards_complete_bilingual():
    """كل بطاقة مكتملة الحقول ثنائية اللغة — لا نص فارغ."""
    for t in TASKS.values():
        assert t.name_ar and t.name_en
        assert t.unit_ar and t.unit_en
        assert t.family_ar and t.family_en
        assert t.kind in {"classification", "regression", "structural_alert", "physchem"}


def test_percentile_suffix_mapping():
    """كل مهمة ML لها عمود مئين موافق باللاحقة الثابتة."""
    assert percentile_task_id("hERG") == "hERG_drugbank_approved_percentile"
    for tid in ML_TASKS:
        assert percentile_task_id(tid).endswith("_drugbank_approved_percentile")


def test_herg_thresholds_consistent_with_ersilia_client():
    """توحيد عتبات hERG مع عميل Ersilia — قرار تصميمي موثّق."""
    from core.clients import ersilia_client as ec

    assert ai.HERG_LOW == ec.HERG_LOW
    assert ai.HERG_HIGH == ec.HERG_HIGH


# ── الأحكام التعليمية ────────────────────────────────────────


def test_verdict_herg_scale():
    assert verdict("hERG", 0.02, "ar") == "خطر منخفض"
    assert verdict("hERG", 0.2, "ar") == "منطقة رمادية — مراقبة"
    assert verdict("hERG", 0.97, "ar") == "خطر مرتفع — فحوص QT"
    assert verdict("hERG", 0.97, "en") == "High risk — QT follow-up"


def test_verdict_toxicity_family():
    for tid in ("AMES", "DILI", "ClinTox", "Carcinogens_Lagunin", "Skin_Reaction"):
        assert verdict(tid, 0.05) == "خطر منخفض"
        assert verdict(tid, 0.99) == "خطر مرتفع"


def test_verdict_absorption_family():
    assert verdict("Bioavailability_Ma", 0.9) == "جيد"
    assert verdict("HIA_Hou", 0.5) == "متوسط"
    assert verdict("HIA_Hou", 0.1) == "ضعيف"
    assert verdict("Solubility_AqSolDB", -1.0) == "ذوبان جيد"
    assert verdict("Solubility_AqSolDB", -3.0) == "ذوبان متوسط"
    assert verdict("Solubility_AqSolDB", -5.0) == "ذوبان ضعيف — عقبة تطوير"


def test_verdict_bbb_direction_not_good_not_bad():
    """BBB معلوماتية — الاتجاه يصف النفاذ لا الجودة."""
    assert verdict("BBB_Martins", 0.9) == "يتجاوز الحاجز على الأرجح"
    assert verdict("BBB_Martins", 0.05) == "لا يتجاوز غالباً"
    assert verdict("BBB_Martins", 0.5) == "منطقة رمادية"


def test_verdict_alerts_and_unknown():
    assert verdict("PAINS_alert", 0) == "بلا إنذار"
    assert "⚠️" in verdict("PAINS_alert", 2)
    assert verdict("hERG_unknown_task", 0.5) == "—"
    # مهام انحدار بلا حكم مصطنَع → عرض القيمة + المئين هو العرض الصادق
    assert verdict("PPBR_AZ", 76.5) == "—"
    assert verdict("VDss_Lombardo", 1.2, "en") == "—"


def test_verdict_regression_no_fake_judgment():
    """لا أحكام مصطنعة على الانحدار — القيمة والمئين تكفيان (صدق العرض)."""
    for tid in ("Caco2_Wang", "Clearance_Microsome_AZ", "Half_Life_Obach",
                "Lipophilicity_AstraZeneca", "LD50_Zhu", "PPBR_AZ"):
        assert verdict(tid, 123.0) == "—"


# ── صف النتيجة ───────────────────────────────────────────────


def test_result_get_missing_is_none():
    r = AdmetAIResult(smiles="CCO", values={"hERG": 0.2})
    assert r.get("hERG") == 0.2
    assert r.get("AMES") is None  # نقص صادق لا تزييف
    assert r.get_percentile("hERG") is None


# ── الحقن الوهمي — عقود الاستدلال بلا torch ─────────────────


class _FakeFrame:
    """أدنى بديل عن DataFrame — يكفي عقد to_dict(orient='records')."""

    def __init__(self, rows):
        self._rows = rows

    def to_dict(self, orient):
        assert orient == "records"
        return self._rows


class _FakeModel:
    def __init__(self, rows=None, raise_on_predict=False):
        self.rows = rows if rows is not None else [
            {
                "hERG": 0.42,
                "Solubility_AqSolDB": -2.5,
                "molecular_weight": 180.159,
                "hERG_drugbank_approved_percentile": 77.5,
                "valid": True,
            }
        ]
        self.raise_on_predict = raise_on_predict
        self.calls: list[list[str]] = []

    def predict(self, smiles):
        self.calls.append(list(smiles))
        if self.raise_on_predict:
            raise RuntimeError("boom")
        if len(smiles) == 1:
            # مسار الجزيء الواحد: الحزمة تُرجع dict
            return dict(self.rows[0])
        # الدُفعة: صف لكل جزيء
        return _FakeFrame([dict(r) for _ in smiles for r in self.rows])


def _inject(monkeypatch, model):
    """حقن وحدة admet_ai وهمية + إعادة ضبط الكاسول."""
    fake_mod = ModuleType("admet_ai")
    fake_mod.ADMETModel = lambda: model
    monkeypatch.setitem(sys.modules, "admet_ai", fake_mod)
    reset_model()
    return model


@pytest.fixture()
def _clean_state(monkeypatch):
    reset_model()
    yield
    reset_model()


def test_available_with_injected_module(monkeypatch, _clean_state):
    _inject(monkeypatch, _FakeModel())
    assert is_available() is True


def test_unavailable_when_import_fails(monkeypatch, _clean_state):
    monkeypatch.setitem(
        sys.modules, "admet_ai",
        None,  # استيراد None يرمي ImportError في بايثون
    )
    # ملاحظة: sys.modules[name] = None يجعل import يرمي ImportError
    assert is_available() is False
    assert predict_admet_ai_batch(["CCO"]) == []


def test_batch_prediction_rows_and_percentiles(monkeypatch, _clean_state):
    _inject(monkeypatch, _FakeModel())
    results = predict_admet_ai_batch(["CCO", "c1ccccc1O"])
    assert len(results) == 2
    r0 = results[0]
    assert r0.smiles == "CCO"
    assert r0.get("hERG") == 0.42
    assert r0.get("molecular_weight") == 180.159
    assert r0.get_percentile("hERG") == 77.5
    # عمود valid لا يُحتسب قيمة
    assert "valid" not in r0.values
    # المئين في dict مستقل بلا اللاحقة
    assert "hERG_drugbank_approved_percentile" not in r0.percentiles


def test_single_molecule_dict_path(monkeypatch, _clean_state):
    """الجزيء الواحد تُرجعه الحزمة dict — يُوحَّد دائماً."""
    _inject(monkeypatch, _FakeModel())
    results = predict_admet_ai_batch(["CCO"])
    assert len(results) == 1
    assert results[0].get("hERG") == 0.42


def test_invalid_row_excluded(monkeypatch, _clean_state):
    """عمود valid=False يستبعد الجزيء — نجاح جزئي مقبول."""
    model = _FakeModel(rows=[
        {"hERG": 0.1, "valid": True},
        {"hERG": 0.9, "valid": False},
        {"hERG": 0.3},  # بلا عمود valid → يُقبل
    ])
    _inject(monkeypatch, model)
    results = predict_admet_ai_batch(["CCO", "CCC", "CCN"])
    assert len(results) == 2
    assert results[0].get("hERG") == 0.1
    assert results[1].get("hERG") == 0.3


def test_nan_cells_skipped(monkeypatch, _clean_state):
    """NaN → نقص صادق في ذلك العمود لا انهيار."""
    nan = float("nan")
    _inject(monkeypatch, _FakeModel(rows=[
        {"hERG": 0.2, "AMES": nan, "hERG_drugbank_approved_percentile": nan},
    ]))
    results = predict_admet_ai_batch(["CCO"])
    assert results[0].get("hERG") == 0.2
    assert results[0].get("AMES") is None
    assert results[0].get_percentile("hERG") is None


def test_predict_failure_returns_empty_not_raise(monkeypatch, _clean_state):
    """فشل الاستدلال → [] بلا استثناء — عقد الواجهة."""
    _inject(monkeypatch, _FakeModel(raise_on_predict=True))
    assert predict_admet_ai_batch(["CCO"]) == []


def test_empty_input_short_circuits(monkeypatch, _clean_state):
    _inject(monkeypatch, _FakeModel())
    assert predict_admet_ai_batch([]) == []
    assert predict_admet_ai_batch(["", "   "]) == []


def test_whitespace_stripped(monkeypatch, _clean_state):
    model = _inject(monkeypatch, _FakeModel())
    predict_admet_ai_batch(["  CCO  "])
    assert model.calls[0] == ["CCO"]


def test_singleton_reused(monkeypatch, _clean_state):
    """الكاسول: نفس كائن النموذج عبر النداءات — بلا إعادة تحميل."""
    model = _inject(monkeypatch, _FakeModel())
    predict_admet_ai_batch(["CCO"])
    predict_admet_ai_batch(["CCC"])
    # get_model يعيد نفس الكائن
    assert ai.get_model() is model
    assert len(model.calls) == 2


# ── نصوص الدرس والتلميح ─────────────────────────────────────


def test_lesson_bilingual_mentions_count_and_families():
    for lang in ("ar", "en"):
        text = ADMET_AI_LESSON[lang].format(n=41)
        assert "41" in text
        assert "DrugBank" in text
        assert "hERG" in text


def test_install_hints_are_actionable():
    assert "pip install admet-ai" in INSTALL_HINT_AR
    assert "pip install admet-ai" in INSTALL_HINT_EN
    assert "cpu" in INSTALL_HINT_EN.lower()


# ── الاختبار الحي (يتخطى في CI حيث الحزمة غير مثبّتة) ────────


def test_live_aspirin_predictions():
    """قياس حي على أسبرين — مرجعية فيزيائية معروفة (المصدر: JSON المجمّد)."""
    pytest.importorskip("admet_ai")
    reset_model()
    try:
        results = predict_admet_ai_batch(["CC(=O)Oc1ccccc1C(=O)O"])
        assert len(results) == 1
        r = results[0]
        mw = r.get("molecular_weight")
        assert mw is not None and abs(mw - 180.16) <= 0.5
        herg = r.get("hERG")
        assert herg is not None and 0.0 <= herg <= 1.0
        # تيرفينادين (المسحوب بسبب hERG) أعلى من الأسبرين — المرجعية الدوائية
        ter = predict_admet_ai_batch([
            "CC(C)(C)C1=CC=C(C=C1)C(CCCN2CCC(CC2)C(C3=CC=CC=C3)"
            "(C4=CC=CC=C4)O)O"
        ])
        assert ter and (ter[0].get("hERG") or 0.0) > herg
    finally:
        reset_model()
