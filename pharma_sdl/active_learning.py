"""استراتيجيات التعلم النشط — اختيار الدفعة التالية من المخزون (P4).

القرار المعماري (ADR-0009): أربعة معايير اختيار شفافة فوق نموذج الإنتاج
الحالي حرفياً (RF على بصمات Morgan) — بلا نموذج جديد وبلا خدمة خارجية:

    random      — خط الأساس العشوائي؛ بوابة Go/No-Go في الخطة v1.1 تُقاس ضده
                  («تحسّن التعلم النشط على الأساس العشوائي»)
    greedy      — استغلال صرف: أعلى فعالية متنبأ بها
    uncertainty — استكشاف صرف: أكبر انحراف بين تنبؤات الأشجار
    ucb         — توازن: pred + κ·std (الاستغلال بمكافأة استكشاف)

التمثيل نفسه (featurize) موافق حرفياً لمواصفات الإنتاج core.ml_potency
(Morgan radius=2, 2048 bit عبر rdFingerprintGenerator) — واختبار وحدة
يقاطع التطابق بين التطبيقين على جزيئات ثابتة، فأي انحراف يُكشف آلياً.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from rdkit import Chem, DataStructs
from rdkit.Chem import rdFingerprintGenerator

STRATEGIES: tuple[str, ...] = ("random", "greedy", "uncertainty", "ucb")

STRATEGY_RATIONALE: dict[str, tuple[str, str]] = {
    "random": (
        "اختيار عشوائي ببذرة معلنة — خط الأساس الذي يُقاس عليه كل تحسّن.",
        "Seeded random choice — the baseline every strategy must beat.",
    ),
    "greedy": (
        "استغلال صرف: الجزيئات ذات أعلى فعالية متنبأ بها أولاً.",
        "Pure exploitation: molecules with highest predicted activity first.",
    ),
    "uncertainty": (
        "استكشاف صرف: الجزيئات التي تختلف أشجار النموذج حولها أكثر أولاً.",
        "Pure exploration: molecules where the model's trees disagree most.",
    ),
    "ucb": (
        "توازن استغلال/استكشاف: التنبؤ زائد κ×انحراف الأشجار.",
        "Exploit/explore balance: prediction plus kappa times tree-std.",
    ),
}


def mol_from_smiles(smiles: str):
    """تحليل SMILES بأمان — None عند الفشل."""
    try:
        return Chem.MolFromSmiles(smiles) if smiles else None
    except Exception:  # noqa: BLE001
        return None


def morgan_fp(smiles: str, radius: int = 2, nbits: int = 2048) -> np.ndarray | None:
    """بصمة Morgan ثنائية — نفس مواصفات core.ml_potency حرفياً."""
    m = mol_from_smiles(smiles)
    if m is None:
        return None
    gen = rdFingerprintGenerator.GetMorganGenerator(radius=radius, fpSize=nbits)
    arr = np.zeros((nbits,), dtype=np.int8)
    DataStructs.ConvertToNumpyArray(gen.GetFingerprint(m), arr)
    return arr


def featurize(
    smiles_list: list[str], radius: int = 2, nbits: int = 2048
) -> tuple[np.ndarray, list[int]]:
    """قائمة SMILES → مصفوفة بصمات + فهارس الصالحة فقط (نفس عقد core.ml_potency)."""
    X: list[np.ndarray] = []
    idx: list[int] = []
    for i, smi in enumerate(smiles_list):
        fp = morgan_fp(smi, radius, nbits)
        if fp is not None:
            X.append(fp)
            idx.append(i)
    if not X:
        return np.empty((0, nbits)), []
    return np.array(X, dtype=np.int8), idx


def tree_std(model: Any, X: np.ndarray) -> np.ndarray:
    """انحراف تنبؤات الأشجار الفردية — تقدير عدم اليقين (تعريف تدقيق P0 نفسه)."""
    preds = np.stack([est.predict(X) for est in model.estimators_])
    return preds.std(axis=0)


def acquisition_scores(
    model: Any,
    X: np.ndarray,
    strategy: str,
    kappa: float = 1.0,
) -> np.ndarray:
    """درجة الجاذبية لكل جزيء في المخزون — الأعلى يُختبر أولاً (عدا random).

    random بلا درجة معنوية (العشوائية هي الاستراتيجية) فيُعاد ترتيب حيادي.
    """
    if strategy not in STRATEGIES:
        raise ValueError(
            f"استراتيجية غير معروفة: {strategy} — المسموح: {', '.join(STRATEGIES)}"
        )
    if strategy == "random":
        return np.zeros(len(X), dtype=float)
    if strategy == "greedy":
        return model.predict(X)
    std = tree_std(model, X)
    if strategy == "uncertainty":
        return std
    # ucb — الاستغلال بمكافأة استكشاف
    return model.predict(X) + float(kappa) * std


def select_batch(
    model: Any,
    X_pool: np.ndarray,
    strategy: str,
    k: int,
    *,
    rng: np.random.Generator | None = None,
    kappa: float = 1.0,
) -> list[int]:
    """اختيار دفعة من مخزون غير المُعنون — حتمية بالبذرة، بلا تكرار فهارس.

    تُرجع فهارس داخل المخزون (ليست معرّفات عالمية). k الأكبر من المخزون
    يُختار المخزون كله — لا اختيار وهمي من فراغ.
    """
    if k <= 0:
        return []
    n_pool = len(X_pool)
    k = min(k, n_pool)
    if strategy == "random":
        gen = rng if rng is not None else np.random.default_rng()
        return sorted(gen.choice(n_pool, size=k, replace=False).tolist())
    scores = acquisition_scores(model, X_pool, strategy, kappa=kappa)
    # فرز مستقر على الدرجات المعكوسة — التعادلات حتمية بترتيب المخزون
    order = np.argsort(-scores, kind="stable")
    return sorted(order[:k].tolist())


__all__ = [
    "STRATEGIES",
    "STRATEGY_RATIONALE",
    "acquisition_scores",
    "featurize",
    "morgan_fp",
    "select_batch",
    "tree_std",
]
