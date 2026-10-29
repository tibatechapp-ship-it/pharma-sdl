"""
ml_potency — التنبؤ بالفعالية (pIC50) من البصمات الجزيئية.

النموذج: RandomForest على بصمات Morgan (radius=2, 2048 bit).
فترة الثقة: تباين تنبؤات الأشجار الفردية — تقدير عملي لعدم اليقين
(أشجار متشابهة = واثق، أشجار متفرقة = الجزيء بعيد عن منطقة التدريب).
البيانات: قياسات IC50 الحقيقية لـ SARS-CoV-2 Mpro (CHEMBL4523582)
المضغوطة في data/mpro_sample.csv.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from rdkit import Chem, DataStructs
from rdkit.Chem import rdFingerprintGenerator
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA = REPO_ROOT / "data" / "mpro_sample.csv"

# عتبات الحكم التعليمية على سلم pIC50 (كلما زادت كان المثبط أقوى)
VERDICT_BANDS = [
    (8.0, "مثبط قوي جداً", "🏆"),
    (7.0, "مثبط قوي", "✅"),
    (6.0, "مثبط متوسط", "🟡"),
    (5.0, "مثبط ضعيف", "🟠"),
]


def mol_from_smiles(smiles: str) -> Chem.Mol | None:
    """تحليل SMILES بأمان — يرجع None عند الفشل."""
    try:
        return Chem.MolFromSmiles(smiles) if smiles else None
    except Exception:  # noqa: BLE001
        return None


def morgan_fp(smiles: str, radius: int = 2, nbits: int = 2048) -> np.ndarray | None:
    """بصمة Morgan ثنائية كمتجه numpy — None إذا فشل التحليل.

    تستخدم rdFingerprintGenerator (الواجهة الحديثة) لتجنب تحذيرات
    الإهمال التي تغرق سجلات Streamlit في الإصدارات الحديثة.
    """
    m = mol_from_smiles(smiles)
    if m is None:
        return None
    gen = rdFingerprintGenerator.GetMorganGenerator(radius=radius, fpSize=nbits)
    fp = gen.GetFingerprint(m)
    arr = np.zeros((nbits,), dtype=np.int8)
    DataStructs.ConvertToNumpyArray(fp, arr)
    return arr


def featurize(
    smiles_list: list[str], radius: int = 2, nbits: int = 2048
) -> tuple[np.ndarray, list[int]]:
    """تحويل قائمة SMILES إلى مصفوفة بصمات مع فهرس الصالحة فقط."""
    X: list[np.ndarray] = []
    idx: list[int] = []
    for i, smi in enumerate(smiles_list):
        fp = morgan_fp(smi, radius, nbits)
        if fp is not None:
            X.append(fp)
            idx.append(i)
    if not X:
        return np.empty((0, nbits)), []
    return np.array(X), idx


def verdict_for(pic50: float) -> tuple[str, str]:
    """حكم تعليمي على سلم pIC50 → (النص, الرمز)."""
    for threshold, label, icon in VERDICT_BANDS:
        if pic50 >= threshold:
            return label, icon
    return "خامل تقريباً في هذا الفحص", "⚪"


@dataclass
class PotencyModel:
    """غلاف تنبؤي فوق RandomForest مع فترة ثقة من تباين الأشجار."""

    model: RandomForestRegressor
    metrics: dict[str, float | int]
    radius: int = 2
    nbits: int = 2048

    def predict(self, smiles: str) -> dict:
        """تنبؤ لجزيء واحد → pIC50 ± CI95 + IC50 (nM) + حكم تعليمي."""
        fp = morgan_fp(smiles, self.radius, self.nbits)
        if fp is None:
            raise ValueError(f"SMILES غير صالح: {smiles!r}")
        fp2 = fp.reshape(1, -1)
        tree_preds = np.array(
            [est.predict(fp2)[0] for est in self.model.estimators_]
        )
        mean = float(tree_preds.mean())
        std = float(tree_preds.std())
        ci95 = 1.96 * std
        ic50_nm = 10 ** (-mean) * 1e9
        label, icon = verdict_for(mean)
        return {
            "pic50": round(mean, 2),
            "pic50_std": round(std, 3),
            "ci95": (round(mean - ci95, 2), round(mean + ci95, 2)),
            "ic50_nm": float(f"{ic50_nm:.3g}"),
            "verdict": label,
            "icon": icon,
        }

    def predict_many(self, smiles_list: list[str]) -> list[dict | None]:
        """تنبؤ لعدة جزيئات — None لغير الصالحة."""
        out: list[dict | None] = []
        for smi in smiles_list:
            try:
                out.append(self.predict(smi))
            except ValueError:
                out.append(None)
        return out


def load_dataset(path: Path | str = DEFAULT_DATA) -> pd.DataFrame:
    """تحميل مجموعة بيانات Mpro مع التحقق من الأعمدة."""
    df = pd.read_csv(path)
    required = {"smiles", "pchembl_value"}
    if not required.issubset(df.columns):
        raise ValueError(f"الملف ينقصه الأعمدة {required - set(df.columns)}")
    return df.dropna(subset=["smiles", "pchembl_value"]).reset_index(drop=True)


def train_potency_model(
    smiles: list[str],
    pic50: list[float],
    n_estimators: int = 300,
    test_size: float = 0.2,
    random_state: int = 42,
    radius: int = 2,
    nbits: int = 2048,
) -> PotencyModel:
    """تدريب نموذج pIC50 من قائمة SMILES وقيمها + تقرير مقاييس الاختبار."""
    X, idx = featurize(smiles, radius, nbits)
    if len(X) < 20:
        raise ValueError(f"بيانات غير كافية للتدريب: {len(X)} جزيء صالح فقط")
    y = np.asarray(pic50, dtype=float)[idx]

    X_tr, X_te, y_tr, y_te = train_test_split(
        X, y, test_size=test_size, random_state=random_state
    )
    model = RandomForestRegressor(
        n_estimators=n_estimators,
        random_state=random_state,
        n_jobs=-1,
        oob_score=False,
    )
    model.fit(X_tr, y_tr)

    pred = model.predict(X_te)
    rmse = float(np.sqrt(np.mean((y_te - pred) ** 2)))
    metrics: dict[str, float | int] = {
        "r2": float(model.score(X_te, y_te)),
        "rmse": round(rmse, 3),
        "mae": round(float(np.mean(np.abs(y_te - pred))), 3),
        "n_train": len(X_tr),
        "n_test": len(X_te),
        "n_total": len(X),
    }
    return PotencyModel(model=model, metrics=metrics, radius=radius, nbits=nbits)


def train_default_model(random_state: int = 42) -> PotencyModel:
    """تدريب على مجموعة Mpro المرفقة — مدخل المنصة والاختبارات."""
    df = load_dataset()
    return train_potency_model(
        df["smiles"].tolist(),
        df["pchembl_value"].tolist(),
        random_state=random_state,
    )
