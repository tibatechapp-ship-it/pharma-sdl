"""مقاييس الصدق لكل هدف — الجودة تُقاس وتُنشر ولا تُدَّعى (بند 60/90 يوماً).

بند «60/90 يوماً» في خطة التطوير الموثقة: «نسخة بيانات موسعة + إعادة نشر
مقاييس الصدق». ADR-0011 أجّل إعلان جودة كل نموذج على هدفه إلى هنا.

البروتوكول الصادق (بلا تسريب هياكل في أي خطوة):
    1. تقسيم scaffold أول (بذرة معلنة) يفصل اختباراً ثابتاً لا يمرّ هيكل
       واحد بينه وبين التدريب — نفس عقود splits.py المعمول بها منذ تدقيق P0.
    2. تقسيم scaffold ثانٍ داخل بِركة التدريب حصراً يفصل الملاءمة عن معايرة
       conformal — بذرة مستقلة (seed+1).
    3. الملاءمة بنفس معمارية الإنتاج حرفياً (RandomForest بنفس عدد الأشجار
       والبذرة، ونفس التمثيل active_learning.featurize المُختبر تقاطعياً).
    4. المقاييس تُقاس على الاختبار المحجوز مرة واحدة: R² وMAE وRMSE +
       التغطية الفعلية لفترة conformal بجانب الاسمية — الوعد بلا قياس ممنوع.

الحدود الصادقة (لا تُخلَّط أبداً):
    - هذه مقاييس جودة النموذج على هياكل محجوزة من سكان بيانات التدريب —
      **لا تُصحّح تنبؤات المكتبة النبوية الـ17**: فرز المنتجات الطبيعية
      استقراء خارج نطاق التدريب، ويبقى UNVALIDATED في خط predicted_potency
      حصراً (ADR-0010) بغض النظر عن جودة النموذج.
    - المقياس واحد لكل هدف (بذرة واحدة) — لا ادعاء بفترات ثقة عبر بذور.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
from pydantic import BaseModel
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from pharma_sdl.active_learning import featurize
from pharma_sdl.experiments.registry import (
    ExperimentRecord,
    code_version,
    dataset_fingerprint,
)

# prophetic يستورد late في الدوال لتجنب دورة استيراد محتملة في المستقبل؛
# اليوم لا دورة (prophetic لا يستورد quality) — استيراد مباشر أوضح.
from pharma_sdl.prophetic import MIN_DATASET_ROWS, TARGETS
from pharma_sdl.splits import scaffold_groups, scaffold_split_indices
from pharma_sdl.uncertainty import ConformalCalibrator

DEFAULT_N_ESTIMATORS = 300
DEFAULT_SEED = 0
DEFAULT_TEST_SIZE = 0.2
DEFAULT_CALIB_SIZE = 0.25
DEFAULT_ALPHA = 0.10

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
QUALITY_ARTIFACT = DATA_DIR / "tibb-quality.json"

NOTE_AR = (
    "مقاييس جودة نموذج كل هدف على هياكل Bemis–Murcko محجوزة لا يمرّ هيكل "
    "واحد بين التدريب والاختبار — بمعمارية الإنتاج نفسها وبذرة معلنة. "
    "هذه أرقام جودة النموذج ولا تُصحّح تنبؤات المكتبة النبوية: فرز "
    "المنتجات الطبيعية استقراء خارج نطاق التدريب ويبقى UNVALIDATED في خط "
    "predicted_potency حصراً (ADR-0010). المقياس ببذرة واحدة لكل هدف — "
    "لا ادعاء بفترات ثقة عبر بذور متعددة."
)
NOTE_EN = (
    "Per-target model quality on held-out Bemis-Murcko scaffolds (no "
    "scaffold crosses the train/test boundary) with the production "
    "architecture and a declared seed. These are model-quality numbers and "
    "do NOT validate the Prophetic-library screen predictions: screening "
    "natural products is extrapolation beyond the training domain and "
    "remains UNVALIDATED in the predicted_potency lane only (ADR-0010). "
    "One seed per target - no across-seed confidence intervals claimed."
)


class TargetQuality(BaseModel):
    """قياس جودة واحد لهدف واحد — بروتوكول معلن وأرقام مقاسة كما هي."""

    target_id: str
    name_ar: str
    name_en: str
    dataset: str  # "data/xxx.csv" — عرض فقط (المسار الحقيقي داخلي)
    dataset_fingerprint: str
    measured_on: str  # تاريخ القياس UTC
    code_version: str

    # بروتوكول القياس — كل معاملات الإعادة كاملة
    n_estimators: int
    seed: int
    test_size: float
    calib_size: float
    alpha: float

    # أحجام فعلية بعد الإسقاط والتقسيم
    n_rows: int
    n_scaffolds: int
    n_fit: int
    n_calib: int
    n_test: int

    # مقاييس الاختبار المحجوز (scaffold — لا تسريب هياكل)
    r2: float
    mae: float
    rmse: float

    # conformal — الاسمية بجانب الفعلية دائماً
    nominal_coverage: float
    measured_coverage: float
    q_hat: float
    finite_sample_guarantee: bool


def measure_target_quality(
    target_id: str,
    *,
    n_estimators: int = DEFAULT_N_ESTIMATORS,
    seed: int = DEFAULT_SEED,
    test_size: float = DEFAULT_TEST_SIZE,
    calib_size: float = DEFAULT_CALIB_SIZE,
    alpha: float = DEFAULT_ALPHA,
    registry: object | None = None,
) -> TargetQuality:
    """قياس جودة نموذج هدف واحد ببروتوكول الصدق المعلن أعلاه.

    نفس معمارية الفرز الإنتاجي حرفياً (RF بنفس الأشجار والبذرة ونفس
    featurize) — الفرق الوحيد: تقييم على هياكل محجوزة بدل فرز المكتبة.
    """
    if target_id not in TARGETS:
        raise ValueError(
            f"هدف غير مُدرّب: {target_id} — المدرّب: {', '.join(sorted(TARGETS))}"
        )
    if n_estimators < 10:
        raise ValueError("n_estimators must be >= 10")
    spec = TARGETS[target_id]
    csv_path = spec.dataset_path
    if not csv_path.exists():
        raise FileNotFoundError(f"بيانات الهدف مفقودة: {csv_path}")

    t0 = time.perf_counter()
    df = pd.read_csv(csv_path)
    df = df.dropna(subset=["smiles", "pchembl_value"]).reset_index(drop=True)
    if len(df) < MIN_DATASET_ROWS:
        raise ValueError(
            f"بيانات {spec.target_id} شحّة ({len(df)} صفاً) — الحد الأدنى "
            f"{MIN_DATASET_ROWS}؛ لا قياس جودة فوق بيانات شحّة"
        )

    smiles_all = df["smiles"].astype(str).tolist()
    y_all = df["pchembl_value"].to_numpy(dtype=float)

    # التمثيل مرة واحدة — نفس featurize المشتركة مع core.ml_potency
    X_all, valid_idx = featurize(smiles_all)
    y = y_all[valid_idx]
    smiles = [smiles_all[i] for i in valid_idx]

    # 1) تقسيم scaffold أول — اختبار محجوز لا يعبره هيكل واحد
    idx_pool, idx_test = scaffold_split_indices(smiles, seed=seed, test_size=test_size)
    # 2) تقسيم scaffold ثانٍ داخل بِركة التدريب حصراً — ملاءمة/معايرة
    pool_smiles = [smiles[i] for i in idx_pool]
    idx_fit_local, idx_calib_local = scaffold_split_indices(
        pool_smiles, seed=seed + 1, test_size=calib_size
    )
    idx_fit = idx_pool[idx_fit_local]
    idx_calib = idx_pool[idx_calib_local]

    model = RandomForestRegressor(
        n_estimators=n_estimators, random_state=seed, n_jobs=-1
    )
    model.fit(X_all[idx_fit], y[idx_fit])

    pred_test = model.predict(X_all[idx_test])  # تنبؤ أحادي الخيط — درس ADR-0009
    pred_calib = model.predict(X_all[idx_calib])

    calibrator = ConformalCalibrator(pred_calib, y[idx_calib], alpha=alpha)
    cov = calibrator.coverage(pred_test, y[idx_test])

    quality = TargetQuality(
        target_id=spec.target_id,
        name_ar=spec.name_ar,
        name_en=spec.name_en,
        dataset=f"data/{spec.dataset}",
        dataset_fingerprint=dataset_fingerprint(csv_path),
        measured_on=datetime.now(UTC).date().isoformat(),
        code_version=code_version(),
        n_estimators=n_estimators,
        seed=seed,
        test_size=test_size,
        calib_size=calib_size,
        alpha=alpha,
        n_rows=len(smiles),
        n_scaffolds=len(scaffold_groups(smiles)),
        n_fit=len(idx_fit),
        n_calib=len(idx_calib),
        n_test=len(idx_test),
        r2=round(float(r2_score(y[idx_test], pred_test)), 3),
        mae=round(float(mean_absolute_error(y[idx_test], pred_test)), 3),
        rmse=round(float(np.sqrt(mean_squared_error(y[idx_test], pred_test))), 3),
        nominal_coverage=round(calibrator.nominal_coverage, 3),
        measured_coverage=round(cov, 3),
        q_hat=round(calibrator.q, 4),
        finite_sample_guarantee=calibrator.finite_sample_guarantee,
    )

    if registry is not None:
        registry.add(
            ExperimentRecord(
                kind="target_quality_measurement",
                hypothesis_ar=(
                    f"جودة نموذج {spec.name_ar} على هياكل محجوزة معلنة بجانب "
                    "الهدف نفسه — بلا وعود بلا قياس؟"
                ),
                hypothesis_en=(
                    f"{spec.name_en} model quality on held-out scaffolds "
                    "published beside the target — no promise without a "
                    "measurement?"
                ),
                question=(
                    f"ما R²/MAE/RMSE والتغطية conformal المقاسة على اختبار "
                    f"scaffold ثابت ({n_estimators} شجرة، بذرة {seed}، α={alpha})؟"
                ),
                target_id=spec.target_id,
                engine_used="sklearn-rf",
                method="target_quality_measurement",
                data_version=quality.dataset_fingerprint,
                parameters={
                    "n_estimators": n_estimators,
                    "seed": seed,
                    "test_size": test_size,
                    "calib_size": calib_size,
                    "alpha": alpha,
                    "lane": "model_quality",
                    "oracle": "heldout_scaffold_measurement",
                    "code_version": quality.code_version,
                },
                counts={
                    "n_rows": quality.n_rows,
                    "n_scaffolds": quality.n_scaffolds,
                    "n_fit": quality.n_fit,
                    "n_calib": quality.n_calib,
                    "n_test": quality.n_test,
                },
                warnings=[
                    (
                        "مقاييس جودة النموذج لا تُصحّح تنبؤات المكتبة النبوية — "
                        "الفرز يبقى UNVALIDATED (ADR-0010)."
                    )
                ],
                elapsed_seconds=round(time.perf_counter() - t0, 3),
            )
        )
    return quality


def load_published_quality() -> dict:
    """قراءة الأرشيف المنشور — يفشل صراحة إن لم يُنشأ بعد (لا اختراع أرقام)."""
    if not QUALITY_ARTIFACT.exists():
        raise FileNotFoundError(
            f"أرشيف مقاييس الجودة غير منشور بعد: {QUALITY_ARTIFACT} — "
            f"شغّل scripts/measure_tibb_quality.py أولاً"
        )
    import json

    return json.loads(QUALITY_ARTIFACT.read_text(encoding="utf-8"))


__all__ = [
    "DEFAULT_ALPHA",
    "DEFAULT_CALIB_SIZE",
    "DEFAULT_N_ESTIMATORS",
    "DEFAULT_SEED",
    "DEFAULT_TEST_SIZE",
    "NOTE_AR",
    "NOTE_EN",
    "QUALITY_ARTIFACT",
    "TargetQuality",
    "load_published_quality",
    "measure_target_quality",
]
