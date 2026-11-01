"""التقسيمات التقييمية — بروتوكول القياس الصادق (من تدقيق P0 إلى محرك P4).

القاعدة الملزمة من الخطة v1.1 (القسم 9): «لا تُعرض درجات التقسيم العشوائي
كأدلة أداء» — أي منحنى تعلّم أو مقياس تعميم في هذه المنصة يُقاس على تقسيم
هياكل (Bemis–Murcko) لا يمرّ هيكل واحد بين التدريب والاختبار.

هذه النسخة الحزمية هي المرجع المضيّ قدَماً؛ سكربت التدقيق التاريخي
(scripts/evaluate_generalization.py) يحفظ أرقامه المنشورة كما هي.
"""

from __future__ import annotations

import numpy as np
from rdkit import Chem
from rdkit.Chem.Scaffolds import MurckoScaffold


def murcko_scaffold(smiles: str) -> str | None:
    """هيكل Bemis–Murcko كسلسلة SMILES — None إذا فشل التحليل."""
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None
    try:
        return MurckoScaffold.MurckoScaffoldSmiles(mol=mol, includeChirality=False)
    except Exception:  # noqa: BLE001 — هيكل شاذ نادر، يُعامل كجroup مستقل
        return None


def scaffold_groups(smiles_list: list[str]) -> list[list[int]]:
    """تجميع فهارس الجزيئات حسب الهيكل — الفهارس غير الصالحة مجموعات فردية.

    الترتيب داخل كل مجموعة محفوظ (حتمية كاملة)؛ وترتيب المجموعات لا يهم لأن
    التقسيم نفسه يخلطها ببذرة معلنة.
    """
    by_scaffold: dict[str, list[int]] = {}
    for i, smi in enumerate(smiles_list):
        scf = murcko_scaffold(smi)
        key = scf if scf is not None else f"__invalid__{i}"
        by_scaffold.setdefault(key, []).append(i)
    return sorted(by_scaffold.values(), key=len, reverse=True)


def scaffold_split_indices(
    smiles_list: list[str], seed: int = 0, test_size: float = 0.2
) -> tuple[np.ndarray, np.ndarray]:
    """تقسيم حسب الهيكل (greedy bin-packing على نمط DeepChem).

    تُخلط المجموعات الهيكلية ببذرة معلنة ثم تُعبأ في التدريب حتى (1−test_size)
    — لا هيكل واحد يعبر الحدود، فرقم الاختبار رقم تعميم حقيقي.
    تُرجع (فهارس التدريب، فهارس الاختبار).
    """
    rng = np.random.default_rng(seed)
    groups = scaffold_groups(smiles_list)
    order = rng.permutation(len(groups))
    n_total = len(smiles_list)
    n_train_target = int(n_total * (1 - test_size))
    idx_tr: list[int] = []
    idx_te: list[int] = []
    for g_i in order:
        group = groups[g_i]
        if len(idx_tr) < n_train_target:
            idx_tr.extend(group)
        else:
            idx_te.extend(group)
    return np.array(idx_tr, dtype=int), np.array(idx_te, dtype=int)


__all__ = ["murcko_scaffold", "scaffold_groups", "scaffold_split_indices"]
