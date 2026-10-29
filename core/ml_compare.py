"""مقارنة نماذج pIC50 — RandomForest مقابل Gradient Boosting.

الهدف التعليمي: يرى الطالب أن اختيار الخوارزمية يغيّر الأداء على نفس
البيانات ونفس البصمات — بتحقق متقاطع K-Fold بدل تقسيم واحد عشوائي
(تقسيم واحد على 900 جزيء يعطي أرقام متقلبة).

المخرجات: قائمة ModelReport (R²، RMSE، MAE، زمن التدريب) لكل نموذج،
حتمية بثابت عشوائي معلن.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from sklearn.ensemble import (
    GradientBoostingRegressor,
    RandomForestRegressor,
)
from sklearn.metrics import r2_score
from sklearn.model_selection import KFold, cross_val_predict

from core.ml_potency import DEFAULT_DATA, featurize, load_dataset


@dataclass(frozen=True)
class ModelReport:
    """نتائج تحقق متقاطع لنموذج واحد على مجموعة بيانات موحدة."""

    name: str
    name_ar: str
    r2: float
    rmse: float
    mae: float
    fit_seconds: float
    n_folds: int
    n_samples: int


def _cv_report(
    name: str,
    name_ar: str,
    estimator: object,
    X: np.ndarray,
    y: np.ndarray,
    folds: int,
    seed: int,
) -> ModelReport:
    """تحقق متقاطع K-Fold → تنبؤ خارج الطية ثم مقاييس موحدة للنموذجين."""
    kf = KFold(n_splits=folds, shuffle=True, random_state=seed)
    t0 = time.perf_counter()
    pred = cross_val_predict(estimator, X, y, cv=kf, n_jobs=-1)
    elapsed = time.perf_counter() - t0
    return ModelReport(
        name=name,
        name_ar=name_ar,
        r2=round(float(r2_score(y, pred)), 3),
        rmse=round(float(np.sqrt(np.mean((y - pred) ** 2))), 3),
        mae=round(float(np.mean(np.abs(y - pred))), 3),
        fit_seconds=round(elapsed, 2),
        n_folds=folds,
        n_samples=len(y),
    )


def compare_models(
    path: Path | str = DEFAULT_DATA,
    folds: int = 5,
    n_estimators: int = 300,
    seed: int = 42,
) -> list[ModelReport]:
    """تدريب ومقارنة النموذجين على نفس البيانات ونفس الطيّات.

    GradientBoostingRegressor بدل xgboost: يغطي نفس الفكرة التعليمية
    (boosting مقابل bagging) بلا اعتمادية جديدة في بيئة مثبَّتة بدقة.
    """
    df = load_dataset(path)
    X, idx = featurize(df["smiles"].tolist())
    if len(X) < 20:
        raise ValueError(f"بيانات غير كافية للمقارنة: {len(X)} جزيء صالح فقط")
    y = df["pchembl_value"].to_numpy(dtype=float)[idx]

    rf = RandomForestRegressor(
        n_estimators=n_estimators, random_state=seed, n_jobs=-1
    )
    gb = GradientBoostingRegressor(
        n_estimators=n_estimators,
        learning_rate=0.05,
        max_depth=3,
        random_state=seed,
    )
    return [
        _cv_report("RandomForest", "غابة عشوائية (bagging)", rf, X, y, folds, seed),
        _cv_report("GradientBoosting", "تعزيز تدرّجي (boosting)", gb, X, y, folds, seed),
    ]
