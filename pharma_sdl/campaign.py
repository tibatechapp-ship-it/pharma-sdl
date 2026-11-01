"""حملة التعلم المغلقة — حزمة Q4 من الخطة v1.1 أصبحت كوداً (P4).

الخطة (خارطة Go/No-Go، الربع الرابع): «دورات التعلم المغلقة (ثلاث على
الأقل) بمقارنة الحقيقي بالمتوقع؛ تحديث النماذج من النتائج» — ومعيار Go:
«تحسّن التعلم النشط على الأساس العشوائي». هذه الوحدة هي المحرك الذي يجعل
كل جولة **تُحدّث النموذج من نتائجها** وتُقاس بصدق.

دورة واحدة (Round):
    1. نموذج RF يُملاء على المُعنون (مع شريحة معايرة conformal منفصلة عن
       الملاءمة — لا ذاتية معايرة على بيانات التدريب).
    2. قياس صادق على مجموعة اختبار scaffold ثابتة لا تلمسها الاختيارات
       أبداً: R²/MAE/RMSE + تغطية conformal الفعلية مقابل الاسمية.
    3. اختيار دفعة من المخزون بالاستراتيجية (random/greedy/uncertainty/ucb).
    4. «الأوراكل» يكشف القياس الحقيقي للدفعة — قيم pChEMBL من مجموعة
       البيانات نفسها (أوراكل in-silico معلن؛ لا مخبر ولا أدوية).
    5. المُعنون يكبر؛ والذاكرة (registry اختياري) تكتب الجولة بسلسلة
       أسلاف — الحلقة تبدأ من حيث انتهت.

الصدق بنيوياً:
    - كل سجل جولة يبدأ UNVALIDATED — لا ترقية آلية (بوابة P1 حصراً).
    - منحنى «أفضل مكتشف» على قيم حقيقية من الأوراكل لا على تنبؤات.
    - بصمة البيانات + بذرة + إعدادات في كل تقرير — قابلية إعادة إنتاج كاملة.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from pharma_sdl.active_learning import (
    STRATEGIES,
    STRATEGY_RATIONALE,
    featurize,
    select_batch,
    tree_std,
)
from pharma_sdl.experiments.registry import (
    ExperimentRecord,
    code_version,
    dataset_fingerprint,
)
from pharma_sdl.splits import scaffold_split_indices
from pharma_sdl.uncertainty import ConformalCalibrator

if TYPE_CHECKING:  # pragma: no cover — العقد المضاعف (sqlite | postgres) موثّق نمطياً
    from pharma_sdl.experiments.pg_store import PostgresExperimentStore
    from pharma_sdl.experiments.registry import ExperimentRegistry

DATASET_CSV = Path(__file__).resolve().parent.parent / "data" / "mpro_sample.csv"

DISCLAIMER_AR = (
    "تنبيه علمي/طبي: حملة تعلم نشط حاسوبية بالكامل — «الأوراكل» يكشف قياسات "
    "pChEMBL محفوظة في مجموعة البيانات (لا مخبر هنا)، وكل النتائج UNVALIDATED "
    "حتى ترقية بشرية موثقة، ودرجات pIC50 خط درجة مستقل لا يُقارن أبداً بدرجات "
    "الإرساء أو القياسات المخبرية."
)
DISCLAIMER_EN = (
    "Scientific/medical disclaimer: fully computational active-learning campaign — "
    "the oracle is in-silico and reveals pChEMBL values stored in the dataset (no "
    "wet lab here), every result stays UNVALIDATED until documented human promotion, "
    "and pIC50 is a separate score lane never compared to docking scores or assay "
    "measurements."
)


class RoundLog(BaseModel):
    """سجل جولة واحدة — ما اختير، ما كُشف، وما تعلمنا فعلاً."""

    round: int
    n_labeled: int
    n_pool: int
    strategy: str
    # الدفعة المختارة: smiles + تنبؤ + انحراف أشجار + فترة conformal + الحقيقة
    batch: list[dict] = Field(default_factory=list)
    best_true_cumulative: float
    round_best_true: float | None = None
    test_metrics: dict[str, float] = Field(default_factory=dict)
    conformal_q: float
    conformal_coverage_empirical: float


class CampaignReport(BaseModel):
    """تقرير حملة كاملة — قابل للتسلسل JSON وحاسم بالبذرة."""

    strategy: str
    seed: int
    dataset: str
    dataset_fingerprint: str
    n_total: int
    n_invalid_dropped: int
    n_test_holdout: int
    config: dict[str, float | int | str] = Field(default_factory=dict)
    rounds: list[RoundLog] = Field(default_factory=list)
    cumulative_best_curve: list[float] = Field(default_factory=list)
    final_best_true: float
    runtime_seconds: float = 0.0
    disclaimer_ar: str = DISCLAIMER_AR
    disclaimer_en: str = DISCLAIMER_EN

    def curve_auc_normalized(self) -> float:
        """متوسط «أفضل مكتشف» عبر الجولات — مقاييس واحد للمنحنى كله.

        كلما صعد المنحنى أبكر كان أعلى هذا المتوسط — ومقارنة الاستراتيجيات
        عليه أعدل من المقارنة عند الجولة الأخيرة وحدها.
        """
        if not self.cumulative_best_curve:
            return 0.0
        return float(np.mean(self.cumulative_best_curve))


def _display_path(p: Path) -> str:
    """مسار عرض نسبي لمجلد المستودع — لا مسارات بيئة في التقارير المنشورة."""
    try:
        return str(p.resolve().relative_to(Path(__file__).resolve().parent.parent))
    except ValueError:
        return str(p)


def _load(dataset_csv: str | Path) -> tuple[list[str], np.ndarray, np.ndarray, str, int]:
    """تحميل البيانات وتضمينها — (smiles الصالحة، y، X، بصمة الملف، عدد المهمل)."""
    df = pd.read_csv(dataset_csv)
    required = {"smiles", "pchembl_value"}
    if not required.issubset(df.columns):
        raise ValueError(f"الملف ينقصه الأعمدة {required - set(df.columns)}")
    df = df.dropna(subset=["smiles", "pchembl_value"]).reset_index(drop=True)
    smiles_all = df["smiles"].astype(str).tolist()
    y_all = df["pchembl_value"].to_numpy(dtype=float)
    X, valid_idx = featurize(smiles_all)
    y = y_all[valid_idx]
    valid_smiles = [smiles_all[i] for i in valid_idx]
    fp = dataset_fingerprint(dataset_csv)
    return valid_smiles, y, X, fp, len(smiles_all) - len(valid_idx)


def _fit_and_calibrate(
    X_labeled: np.ndarray,
    y_labeled: np.ndarray,
    seed: int,
    n_estimators: int,
    alpha: float,
    calib_fraction: float = 0.2,
) -> tuple[RandomForestRegressor, ConformalCalibrator]:
    """ملاءمة على شريحة ومعايرة conformal على شريحة منفصلة — لا ذاتية معايرة."""
    n_calib = max(2, int(len(y_labeled) * calib_fraction))
    n_fit = len(y_labeled) - n_calib
    if n_fit < 5:
        # مجموعة صغيرة جداً: الملاءمة على الكل والمعايرة على بواقي التدريب —
        # انحياز تفاؤلي معلوم ويُعلن في التقرير عبر finite_sample_guarantee.
        model = RandomForestRegressor(
            n_estimators=n_estimators, random_state=seed, n_jobs=-1
        )
        model.fit(X_labeled, y_labeled)
        pred = model.predict(X_labeled)
        return model, ConformalCalibrator(pred, y_labeled, alpha=alpha)
    rng = np.random.default_rng(seed)
    perm = rng.permutation(len(y_labeled))
    calib_idx, fit_idx = perm[:n_calib], perm[n_calib:]
    model = RandomForestRegressor(n_estimators=n_estimators, random_state=seed, n_jobs=-1)
    model.fit(X_labeled[fit_idx], y_labeled[fit_idx])
    # الملاءمة المتوازية حتمية (الأشجار مستقلة ومبذورة) لكن تجميع تنبؤات
    # predict المتوازي (out += pred تحت قفل) يعتمد على ترتيب الخيوط — فآخر
    # منزلة عشرية تتأرجح مع توقيت الجدولة (انكشف تحت coverage في CI).
    # التنبؤ أحادي الخيط يعيد النظام الحتمي بلا ثمن يُذكر.
    model.n_jobs = 1
    calib_pred = model.predict(X_labeled[calib_idx])
    return model, ConformalCalibrator(calib_pred, y_labeled[calib_idx], alpha=alpha)


def _test_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    return {
        "r2": round(float(r2_score(y_true, y_pred)), 3),
        "mae": round(float(mean_absolute_error(y_true, y_pred)), 3),
        "rmse": round(float(np.sqrt(mean_squared_error(y_true, y_pred))), 3),
    }


def run_campaign(
    dataset_csv: str | Path | None = None,
    *,
    strategy: str = "uncertainty",
    seed: int = 0,
    initial_labeled: int = 40,
    batch_size: int = 8,
    rounds: int = 8,
    n_estimators: int = 300,
    kappa: float = 1.0,
    alpha: float = 0.10,
    test_size: float = 0.2,
    registry: ExperimentRegistry | PostgresExperimentStore | None = None,
    target_id: str = "CHEMBL4523582",
) -> CampaignReport:
    """حملة تعلم مغلقة كاملة — N جولات، النموذج يُحدَّث من نتائج كل جولة.

    الاستراتيجية واحدة لكل حملة؛ مقارنة الاستراتيجيات تتم بين حملات بنفس
    البذرة عبر scripts/learning_campaign.py — المقارنة على مستوى التقارير
    لا داخل الحملة الواحدة.
    """
    if strategy not in STRATEGIES:
        raise ValueError(
            f"استراتيجية غير معروفة: {strategy} — المسموح: {', '.join(STRATEGIES)}"
        )
    if rounds < 1:
        raise ValueError("rounds must be >= 1")
    if initial_labeled < 10:
        raise ValueError("initial_labeled must be >= 10 — لا تعلم من فراغ")
    if batch_size < 1:
        raise ValueError("batch_size must be >= 1")

    csv_path = Path(dataset_csv) if dataset_csv else DATASET_CSV
    t0 = time.perf_counter()
    smiles, y, X, data_fp, n_invalid = _load(csv_path)

    # الاختبار الثابت (scaffold) لا يلمسه الاختيار أبداً — قياس صادق للتعلم
    idx_tr, idx_te = scaffold_split_indices(smiles, seed=seed, test_size=test_size)
    pool: list[int] = idx_tr.tolist()
    rng_init = np.random.default_rng([seed, 7919])
    init_local = rng_init.choice(
        len(pool), size=min(initial_labeled, len(pool)), replace=False
    )
    labeled_global: list[int] = sorted(pool[i] for i in init_local)
    init_set = set(labeled_global)
    pool = [i for i in pool if i not in init_set]

    hyp_ar, hyp_en = STRATEGY_RATIONALE[strategy]
    best_true = float(np.max(y[labeled_global]))
    curve: list[float] = [best_true]
    round_logs: list[RoundLog] = []
    parent_id: str | None = None

    for rnd in range(1, rounds + 1):
        model, calib = _fit_and_calibrate(
            X[labeled_global], y[labeled_global], seed + rnd, n_estimators, alpha
        )

        # 1) قياس صادق على الاختبار الثابت (scaffold — لا تسرب هياكل)
        pred_test = model.predict(X[idx_te])
        metrics = _test_metrics(y[idx_te], pred_test)
        coverage = calib.coverage(pred_test, y[idx_te])

        # 2) اختيار الدفعة من المخزون
        X_pool = X[pool]
        rng_round = np.random.default_rng([seed, rnd])
        batch_local = select_batch(
            model, X_pool, strategy, batch_size, rng=rng_round, kappa=kappa
        )
        chosen = [pool[i] for i in batch_local]
        pred_pool = model.predict(X_pool)
        std_pool = tree_std(model, X_pool)
        batch_rows = []
        for i_local, i_global in zip(batch_local, chosen, strict=True):
            lo, hi = calib.interval(float(pred_pool[i_local]))
            batch_rows.append(
                {
                    "smiles": smiles[i_global],
                    "predicted_pic50": round(float(pred_pool[i_local]), 3),
                    "tree_std": round(float(std_pool[i_local]), 4),
                    "interval_lo": round(lo, 3),
                    "interval_hi": round(hi, 3),
                    "true_pic50": round(float(y[i_global]), 3),
                }
            )

        # 3) الأوراكل يكشف الحقيقة (in-silico) والمُعنون يكبر
        round_best = float(np.max(y[chosen]))
        best_true = max(best_true, round_best)
        curve.append(best_true)
        labeled_global.extend(chosen)
        chosen_set = set(chosen)
        pool = [i for i in pool if i not in chosen_set]

        round_logs.append(
            RoundLog(
                round=rnd,
                n_labeled=len(labeled_global),
                n_pool=len(pool),
                strategy=strategy,
                batch=batch_rows,
                best_true_cumulative=round(best_true, 3),
                round_best_true=round(round_best, 3),
                test_metrics=metrics,
                conformal_q=round(calib.q, 4),
                conformal_coverage_empirical=round(coverage, 3),
            )
        )

        # 4) الذاكرة: الجولة تُكتب بسلسلة أسلاف — الحلقة تقرأ سابقتها
        if registry is not None:
            record = registry.begin(
                ExperimentRecord(
                    kind="learning_round",
                    hypothesis_ar=hyp_ar,
                    hypothesis_en=hyp_en,
                    question=(
                        f"الجولة {rnd}/{rounds}: أي دفعة يختارها معيار «{strategy}» "
                        "ومن يكتشف أعلى فعالية حقيقية؟"
                    ),
                    target_id=target_id,
                    engine_used="sklearn-rf",
                    method=f"active_learning/{strategy}",
                    data_version=data_fp,
                    code_version=code_version(),
                    parameters={
                        "strategy": strategy,
                        "round": rnd,
                        "rounds_total": rounds,
                        "seed": seed,
                        "batch_size": batch_size,
                        "n_labeled": len(labeled_global),
                        "n_estimators": n_estimators,
                        "kappa": kappa,
                        "alpha": alpha,
                        "oracle": "in_silico_dataset_truth",
                    },
                    parent_experiment_id=parent_id,
                )
            )
            registry.complete(
                record.experiment_id,
                counts={"batch": len(batch_rows), "labeled": len(labeled_global)},
                top_hits=batch_rows,
                elapsed_seconds=round(time.perf_counter() - t0, 3),
                engine_used="sklearn-rf",
                method=f"active_learning/{strategy}",
                lesson=(
                    f"أفضل فعالية حقيقية هذه الجولة {round_best:.2f} pIC50 "
                    f"والتراكمي {best_true:.2f} — الأوراكل in-silico؛ "
                    "UNVALIDATED بلا ترقية آلية."
                ),
            )
            parent_id = record.experiment_id

    return CampaignReport(
        strategy=strategy,
        seed=seed,
        dataset=_display_path(csv_path),
        dataset_fingerprint=data_fp,
        n_total=len(smiles),
        n_invalid_dropped=n_invalid,
        n_test_holdout=len(idx_te),
        config={
            "initial_labeled": initial_labeled,
            "batch_size": batch_size,
            "rounds": rounds,
            "n_estimators": n_estimators,
            "kappa": kappa,
            "alpha": alpha,
            "test_size": test_size,
            "test_split": "scaffold_bemis_murcko",
        },
        rounds=round_logs,
        cumulative_best_curve=[round(v, 3) for v in curve],
        final_best_true=round(best_true, 3),
        runtime_seconds=round(time.perf_counter() - t0, 1),
    )


__all__ = [
    "DATASET_CSV",
    "DISCLAIMER_AR",
    "DISCLAIMER_EN",
    "CampaignReport",
    "RoundLog",
    "run_campaign",
]
