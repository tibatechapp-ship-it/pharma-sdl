"""اختبارات استراتيجيات التعلم النشط — الحتمية والترتيب والعقد (P4)."""

from __future__ import annotations

import numpy as np
import pytest

from pharma_sdl.active_learning import (
    STRATEGIES,
    featurize,
    morgan_fp,
    select_batch,
    tree_std,
)


class _FakeTree:
    """شجرة وهمية بإنحرافات لكل صف — لبناء نموذج وهمي بترتيب معلوم تماماً."""

    def __init__(self, offsets: np.ndarray) -> None:
        self.offsets = np.asarray(offsets, dtype=float)

    def predict(self, X: np.ndarray) -> np.ndarray:
        return np.arange(len(X), dtype=float) + self.offsets


class _FakeModel:
    """نموذج وهمي: الوسط والانحراف مضبوطان لكل صف يدوياً."""

    def __init__(self, tree_offsets: tuple[np.ndarray, ...]) -> None:
        self.estimators_ = [_FakeTree(o) for o in tree_offsets]

    def predict(self, X: np.ndarray) -> np.ndarray:
        return np.mean([t.predict(X) for t in self.estimators_], axis=0)


# صفوف: وسط = [1, 2, 3, 4, 5] وانحراف = [0.9, 0.5, 0.1, 0.7, 0.3]
_MEANS = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
_STDS = np.array([0.9, 0.5, 0.1, 0.7, 0.3])


def _designed_model() -> _FakeModel:
    offsets = np.stack([_MEANS - _STDS, _MEANS, _MEANS + _STDS])
    return _FakeModel(tuple(offsets))


@pytest.fixture
def fake_model() -> _FakeModel:
    return _designed_model()


def test_strategies_registry_complete():
    assert set(STRATEGIES) == {"random", "greedy", "uncertainty", "ucb"}


def test_greedy_picks_highest_predicted(fake_model):
    X = np.zeros((5, 1))
    assert select_batch(fake_model, X, "greedy", 2) == [3, 4]  # أعلى وسط


def test_uncertainty_picks_largest_tree_disagreement(fake_model):
    X = np.zeros((5, 1))
    assert select_batch(fake_model, X, "uncertainty", 2) == [0, 3]  # أكبر انحراف


def test_ucb_balances_mean_and_std(fake_model):
    X = np.zeros((5, 1))
    # mean+k·std: [1.9, 2.5, 3.1, 4.7, 5.3] → الأعلى {4, 3} (الدفعة ترجع مفروزة)
    assert select_batch(fake_model, X, "ucb", 2, kappa=1.0) == [3, 4]
    # κ=0 يحوّل ucb إلى استغلال صرف — نفس الأعلى هنا لكن بعقد مختلف
    assert select_batch(fake_model, X, "ucb", 2, kappa=0.0) == [3, 4]
    # κ كبير يقلب الترتيب لصالح الانحراف: أعلى std = {0, 3}
    assert select_batch(fake_model, X, "ucb", 2, kappa=100.0) == [0, 3]


def test_random_respects_seed_and_batch_size(fake_model):
    X = np.zeros((20, 1))
    b1 = select_batch(fake_model, X, "random", 5, rng=np.random.default_rng(42))
    b2 = select_batch(fake_model, X, "random", 5, rng=np.random.default_rng(42))
    b3 = select_batch(fake_model, X, "random", 5, rng=np.random.default_rng(43))
    assert b1 == b2  # نفس البذرة → نفس الدفعة
    assert b1 != b3  # بذور مختلفة → اختلاف متوقع
    assert len(set(b1)) == 5  # بلا تكرار


def test_k_larger_than_pool_returns_whole_pool(fake_model):
    X = np.zeros((5, 1))
    assert len(select_batch(fake_model, X, "greedy", 10)) == 5
    assert select_batch(fake_model, X, "greedy", 0) == []


def test_unknown_strategy_raises(fake_model):
    with pytest.raises(ValueError):
        select_batch(fake_model, np.zeros((3, 1)), "magic", 1)


def test_tree_std_matches_manual_computation(fake_model):
    X = np.zeros((5, 1))
    stds = tree_std(fake_model, X)
    # الحساب اليدوي على مصفوفة الإزاحات نفسها (std بـddof=0 كما في tree_std)
    offsets = np.stack([_MEANS - _STDS, _MEANS, _MEANS + _STDS])
    expected = offsets.std(axis=0)
    assert np.allclose(stds, expected)
    # ترتيب الاستكشاف يحافظ على ترتيب الانحرافات المصمّم: {0.9, 0.7} الأعلى
    assert select_batch(fake_model, X, "uncertainty", 2) == [0, 3]


def test_featurize_matches_core_production_featurizer():
    """العقد الحاكم: التمثيل هنا = تمثيل الإنتاج core.ml_potency حرفياً.

    أي انحراف بين التطبيقين يُكشف بهذا الاختبار قبل أن يفسد أي رقم.
    """
    from core.ml_potency import morgan_fp as core_morgan_fp

    samples = [
        "CC(=O)Oc1ccccc1C(=O)O",  # أسبرين
        "CN1CCC[C@H]1c1cccnc1",  # نيكوتين
        "Cn1cnc2c1c(=O)n(C)c(=O)n2C",  # كافيين
        "not-a-smiles",  # غير صالح → None في الطرفين
    ]
    for smi in samples:
        ours = morgan_fp(smi)
        theirs = core_morgan_fp(smi)
        if ours is None:
            assert theirs is None
        else:
            assert theirs is not None
            assert np.array_equal(ours, theirs)


def test_featurize_skips_invalid_and_keeps_index_alignment():
    X, idx = featurize(["CCO", "bad", "c1ccccc1"])
    assert idx == [0, 2]
    assert X.shape == (2, 2048)
