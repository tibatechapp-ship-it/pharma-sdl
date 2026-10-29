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
