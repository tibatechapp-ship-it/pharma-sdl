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
from sklearn.ensemble import (
    HistGradientBoostingRegressor,
    RandomForestRegressor,
)
from sklearn.model_selection import train_test_split

from core.physchem import DESCRIPTOR_NAMES, physchem_vector

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


def morgan_fp(
    smiles: str, radius: int = 2, nbits: int = 2048, count_based: bool = False
) -> np.ndarray | None:
    """بصمة Morgan كمتجه numpy — None إذا فشل التحليل.

    P11: `count_based=True` يعيد متجه التكرارات (عدديات) بدلاً من الثنائي —
    التمثيل المعتمد في ترقية P11 (R² هيكلي 0.489 → 0.509 على البروتوكول
    المنشور). تستخدم rdFingerprintGenerator (الواجهة الحديثة).
    """
    m = mol_from_smiles(smiles)
    if m is None:
        return None
    gen = rdFingerprintGenerator.GetMorganGenerator(radius=radius, fpSize=nbits)
    if count_based:
        return np.asarray(gen.GetCountFingerprintAsNumPy(m), dtype=np.float64)
    fp = gen.GetFingerprint(m)
    arr = np.zeros((nbits,), dtype=np.int8)
    DataStructs.ConvertToNumpyArray(fp, arr)
    return arr


def featurize(
    smiles_list: list[str],
    radius: int = 2,
    nbits: int = 2048,
    include_descriptors: bool = False,
    count_based: bool = False,
) -> tuple[np.ndarray, list[int]]:
    """تحويل قائمة SMILES إلى مصفوفة بصمات مع فهرس الصالحة فقط.

    P11: `count_based=True` بصمة تكرارات (الافتراضي المعتمد للإنتاج)،
    و`include_descriptors=True` تدمج كتلة فيزيوكيميائية (20 عموداً —
    متاحة لكنها ليست الافتراضي: نتيجة A/B عليها سلبية على بيانات Mpro).
    """
    X: list[np.ndarray] = []
    idx: list[int] = []
    for i, smi in enumerate(smiles_list):
        fp = morgan_fp(smi, radius, nbits, count_based=count_based)
        if fp is None:
            continue
        if include_descriptors:
            vec = physchem_vector(smi)
            if vec is None:  # الجزيء صالح للبصمة لا للوصف → يُستبعد لتوحيد الصفوف
                continue
            X.append(np.concatenate([fp.astype(np.float64), vec]))
        else:
            X.append(fp)
        idx.append(i)
    if not X:
        width = nbits + len(DESCRIPTOR_NAMES) if include_descriptors else nbits
        return np.empty((0, width)), []
    return np.array(X), idx


def verdict_for(pic50: float) -> tuple[str, str]:
    """حكم تعليمي على سلم pIC50 → (النص, الرمز)."""
    for threshold, label, icon in VERDICT_BANDS:
        if pic50 >= threshold:
            return label, icon
    return "خامل تقريباً في هذا الفحص", "⚪"


@dataclass
class PotencyModel:
    """غلاف تنبؤي فوق نموذج فعالية مع فترة ثقة.

    P11 — خيارا معمارية معلنان:
        model_kind="rf"      : RandomForest + CI من تباين الأشجار (الافتراضي التاريخي).
        model_kind="histgb"  : HistGradientBoosting + CI من انحدار كمّي مزدوج
                               (quantile 0.159/0.841 — فترة تنبؤ فعلية لا تقدير تباين).
    """

    model: RandomForestRegressor | HistGradientBoostingRegressor
    metrics: dict[str, float | int]
    radius: int = 2
    nbits: int = 2048
    model_kind: str = "rf"
    include_descriptors: bool = False
    count_based: bool = False
    ci_low: HistGradientBoostingRegressor | None = None
    ci_high: HistGradientBoostingRegressor | None = None

    def _features_one(self, smiles: str) -> np.ndarray:
        """متجه سمات جزيء واحد بنفس تمثيل التدريب — ValueError عند الفشل."""
        X, idx = featurize(
            [smiles],
            self.radius,
            self.nbits,
            include_descriptors=self.include_descriptors,
            count_based=self.count_based,
        )
        if not idx:
            raise ValueError(f"SMILES غير صالح: {smiles!r}")
        return X[0]

    def predict(self, smiles: str) -> dict:
        """تنبؤ لجزيء واحد → pIC50 ± CI95 + IC50 (nM) + حكم تعليمي."""
        x = self._features_one(smiles).reshape(1, -1)
        if self.model_kind == "histgb":
            mean = float(self.model.predict(x)[0])
            lo = float(self.ci_low.predict(x)[0]) if self.ci_low is not None else mean
            hi = float(self.ci_high.predict(x)[0]) if self.ci_high is not None else mean
            lo, hi = min(lo, mean), max(hi, mean)
            std = (hi - lo) / (2 * 1.96)  # مكافئ عرضي فقط للعرض
        else:
            tree_preds = np.array(
                [est.predict(x)[0] for est in self.model.estimators_]
            )
            mean = float(tree_preds.mean())
            std = float(tree_preds.std())
            ci95 = 1.96 * std
            lo, hi = mean - ci95, mean + ci95
        ic50_nm = 10 ** (-mean) * 1e9
        label, icon = verdict_for(mean)
        return {
            "pic50": round(mean, 2),
            "pic50_std": round(std, 3),
            "ci95": (round(lo, 2), round(hi, 2)),
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
    model_kind: str = "rf",
    include_descriptors: bool = False,
    count_based: bool = False,
    max_features: float | None = None,
) -> PotencyModel:
    """تدريب نموذج pIC50 من قائمة SMILES وقيمها + تقرير مقاييس الاختبار.

    P11: `model_kind="histgb"` يدرّب HistGradientBoosting (نقطة) مع
    نموذجي انحدار كمّي (0.159/0.841) لفترة تنبؤ فعلية، و
    `include_descriptors=True` يوسّع التمثيل بكتلة فيزيوكيميائية، و
    `count_based=True` بصمة تكرارات، و`max_features` لمجموعات فرعية من
    السمات لكل تقسيم (0.3 = المعتمد في ترقية P11). الافتراضي المطلق
    (rf / بلا وصف / ثنائي) = المواصفة التاريخية حرفياً — لا كسر للعقد.
    """
    if model_kind not in {"rf", "histgb"}:
        raise ValueError(f"model_kind غير معروف: {model_kind!r} (المسموح: rf, histgb)")
    X, idx = featurize(
        smiles,
        radius,
        nbits,
        include_descriptors=include_descriptors,
        count_based=count_based,
    )
    if len(X) < 20:
        raise ValueError(f"بيانات غير كافية للتدريب: {len(X)} جزيء صالح فقط")
    y = np.asarray(pic50, dtype=float)[idx]

    X_tr, X_te, y_tr, y_te = train_test_split(
        X, y, test_size=test_size, random_state=random_state
    )

    ci_low: HistGradientBoostingRegressor | None = None
    ci_high: HistGradientBoostingRegressor | None = None
    if model_kind == "rf":
        model: RandomForestRegressor | HistGradientBoostingRegressor = RandomForestRegressor(
            n_estimators=n_estimators,
            max_features=max_features,
            random_state=random_state,
            n_jobs=-1,
            oob_score=False,
        )
        model.fit(X_tr, y_tr)
    else:
        model = HistGradientBoostingRegressor(
            max_iter=n_estimators,
            random_state=random_state,
            early_stopping=False,  # حتمية كاملة — لا توقف مبكر اعتمادياً على val
        )
        model.fit(X_tr, y_tr)
        # فترة تنبؤ كمّية ≈ 68% مركزية (0.159/0.841) — نفس السمات
        ci_low = HistGradientBoostingRegressor(
            loss="quantile", quantile=0.159, max_iter=n_estimators,
            random_state=random_state, early_stopping=False,
        )
        ci_high = HistGradientBoostingRegressor(
            loss="quantile", quantile=0.841, max_iter=n_estimators,
            random_state=random_state, early_stopping=False,
        )
        ci_low.fit(X_tr, y_tr)
        ci_high.fit(X_tr, y_tr)

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
    metrics["model_kind"] = model_kind
    metrics["include_descriptors"] = include_descriptors
    metrics["count_based"] = count_based
    metrics["max_features"] = max_features
    return PotencyModel(
        model=model,
        metrics=metrics,
        radius=radius,
        nbits=nbits,
        model_kind=model_kind,
        include_descriptors=include_descriptors,
        count_based=count_based,
        ci_low=ci_low,
        ci_high=ci_high,
    )


def train_default_model(random_state: int = 42) -> PotencyModel:
    """تدريب على مجموعة Mpro المرفقة — مدخل المنصة والاختبارات.

    P11 (v0.12.0): التكوين المعتمد بعد A/B على البروتوكول المنشور —
    بصمة تكرارات + max_features=0.3 (R² هيكلي 0.489 → 0.509، خمسة بذور).
    تفاصيل المقارنة: docs/audit/MODEL-UPGRADE-P11.md.
    """
    df = load_dataset()
    return train_potency_model(
        df["smiles"].tolist(),
        df["pchembl_value"].tolist(),
        random_state=random_state,
        count_based=True,
        max_features=0.3,
    )
