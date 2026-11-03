"""اختبارات ml_potency — سريعة ومحلية بالكامل (لا شبكة).

تستخدم data/mpro_sample.csv المرفقة (900 جزيء Mpro حقيقي من ChEMBL)
لتدريب نموذج مصغّر والتحقق من سلوك التنبؤ وفترات الثقة.
"""
import pytest

from core.ml_potency import (
    DEFAULT_DATA,
    featurize,
    load_dataset,
    morgan_fp,
    train_potency_model,
    verdict_for,
)

NIRMATRELVIR = (
    "CC1([C@@H]2[C@H]1[C@H](N(C2)C(=O)[C@H](C(C)(C)C)NC(=O)C(F)(F)F)"
    "C(=O)N[C@@H](C[C@@H]3CCNC3=O)C#N)C"
)
ASPIRIN = "CC(=O)OC1=CC=CC=C1C(=O)O"
BAD_SMILES = "this_is_not_a_smiles"


@pytest.fixture(scope="module")
def model():
    df = load_dataset()
    return train_potency_model(
        df["smiles"].tolist(), df["pchembl_value"].tolist(), n_estimators=60
    )


def test_default_data_exists():
    assert DEFAULT_DATA.exists(), "data/mpro_sample.csv مفقود من المستودع"


def test_morgan_fp_shapes():
    fp = morgan_fp(ASPIRIN)
    assert fp is not None
    assert fp.shape == (2048,)
    assert fp.sum() > 0  # الأسبرين يجب أن يضيء بتات فعلياً
    assert morgan_fp(BAD_SMILES) is None
    assert morgan_fp("") is None


def test_featurize_drops_invalid():
    X, idx = featurize([ASPIRIN, BAD_SMILES, NIRMATRELVIR])
    assert X.shape == (2, 2048)
    assert idx == [0, 2]


def test_load_dataset_columns():
    df = load_dataset()
    assert {"smiles", "pchembl_value"} <= set(df.columns)
    assert len(df) >= 500
    assert df["pchembl_value"].between(3.0, 12.0).all()


def test_train_metrics_sane(model):
    m = model.metrics
    assert 0.2 <= m["r2"] <= 1.0  # نموذج حقيقي، ليس مثالياً وليس عشوائياً
    assert 0.3 <= m["rmse"] <= 1.5
    assert m["n_train"] + m["n_test"] == m["n_total"]
    assert m["n_total"] >= 500


def test_predict_known_inhibitor(model):
    """نيرماتريلڤير مثبط معروف — يجب أن يخرج من النموذج ضمن السلم المعقول."""
    res = model.predict(NIRMATRELVIR)
    assert 5.0 <= res["pic50"] <= 10.0
    assert res["ci95"][0] < res["pic50"] < res["ci95"][1]
    assert res["ic50_nm"] > 0
    assert res["verdict"] in {
        "مثبط قوي جداً",
        "مثبط قوي",
        "مثبط متوسط",
        "مثبط ضعيف",
        "خامل تقريباً في هذا الفحص",
    }
    assert res["icon"] in {"🏆", "✅", "🟡", "🟠", "⚪"}


def test_decoy_has_wider_uncertainty(model):
    """الأسبرين خارج منطقة التدريب → عدم يقين أوسع (إبيستيمي عملي)."""
    decoy = model.predict(ASPIRIN)
    active = model.predict(NIRMATRELVIR)
    decoy_span = decoy["ci95"][1] - decoy["ci95"][0]
    active_span = active["ci95"][1] - active["ci95"][0]
    assert decoy["pic50_std"] > 0
    assert decoy_span > active_span


def test_predict_invalid_raises(model):
    with pytest.raises(ValueError, match="SMILES غير صالح"):
        model.predict(BAD_SMILES)


def test_predict_many_mixed(model):
    out = model.predict_many([NIRMATRELVIR, BAD_SMILES])
    assert out[0] is not None
    assert out[1] is None


def test_verdict_bands():
    assert verdict_for(9.0)[0] == "مثبط قوي جداً"
    assert verdict_for(7.4)[0] == "مثبط قوي"
    assert verdict_for(6.5)[0] == "مثبط متوسط"
    assert verdict_for(5.5)[0] == "مثبط ضعيف"
    assert verdict_for(4.0)[0] == "خامل تقريباً في هذا الفحص"


# ═══ P11 — ترقية التمثيل والنموذج ═══

@pytest.fixture(scope="module")
def upgraded_model():
    """التكوين المعتمد P11: بصمة تكرارات + max_features=0.3 (عقد train_default_model)."""
    df = load_dataset()
    return train_potency_model(
        df["smiles"].tolist(),
        df["pchembl_value"].tolist(),
        n_estimators=60,
        count_based=True,
        max_features=0.3,
    )


@pytest.fixture(scope="module")
def histgb_model():
    df = load_dataset()
    return train_potency_model(
        df["smiles"].tolist(),
        df["pchembl_value"].tolist(),
        n_estimators=40,
        model_kind="histgb",
        include_descriptors=True,
    )


def test_featurize_count_based():
    """بصمة التكرارات: نفس الشكل، قيم عددية ≥ الثنائي ببت-ببت."""
    X_bin, idx_b = featurize([ASPIRIN, NIRMATRELVIR])
    X_cnt, idx_c = featurize([ASPIRIN, NIRMATRELVIR], count_based=True)
    assert idx_b == idx_c == [0, 1]
    assert X_cnt.shape == X_bin.shape == (2, 2048)
    assert (X_cnt >= 0).all()
    assert (X_cnt.astype(int) >= X_bin.astype(int)).all()  # التكرار يشمل الوجود
    assert X_cnt.sum() > X_bin.sum()  # التكرارات تحمل معلومة إضافية


def test_featurize_descriptors_contract():
    X, idx = featurize([ASPIRIN, BAD_SMILES, NIRMATRELVIR], include_descriptors=True)
    assert X.shape == (2, 2048 + 20)
    assert idx == [0, 2]


def test_featurize_empty_with_flags():
    X, idx = featurize([BAD_SMILES], include_descriptors=True, count_based=True)
    assert X.shape == (0, 2048 + 20)
    assert idx == []


def test_upgraded_model_contract(upgraded_model):
    """النموذج المعتمد v0.12.0: نفس عقد التنبؤ + بصمة معلنة في المقاييس."""
    assert upgraded_model.count_based is True
    assert upgraded_model.metrics["count_based"] is True
    assert upgraded_model.metrics["max_features"] == 0.3
    res = upgraded_model.predict(NIRMATRELVIR)
    assert 5.0 <= res["pic50"] <= 10.0
    assert res["ci95"][0] < res["pic50"] < res["ci95"][1]
    assert res["ic50_nm"] > 0


def test_upgraded_model_drops_invalid(upgraded_model):
    assert upgraded_model.predict_many([NIRMATRELVIR, BAD_SMILES])[1] is None
    with pytest.raises(ValueError, match="SMILES غير صالح"):
        upgraded_model.predict(BAD_SMILES)


def test_histgb_smoke_contract(histgb_model):
    """HistGB + الوصف: عقد تنبؤ سليم — النقطة داخل الفترة الكمّية."""
    assert histgb_model.model_kind == "histgb"
    assert histgb_model.ci_low is not None and histgb_model.ci_high is not None
    m = histgb_model.metrics
    assert m["n_train"] + m["n_test"] == m["n_total"]
    res = histgb_model.predict(NIRMATRELVIR)
    assert 4.0 <= res["pic50"] <= 11.0
    assert res["ci95"][0] <= res["pic50"] <= res["ci95"][1]
    assert res["ci95"][1] > res["ci95"][0]


def test_unknown_model_kind_raises():
    df = load_dataset()
    with pytest.raises(ValueError, match="model_kind غير معروف"):
        train_potency_model(
            df["smiles"].tolist()[:50], df["pchembl_value"].tolist()[:50], model_kind="xgboost"
        )
