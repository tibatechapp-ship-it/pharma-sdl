"""تقييم التعميم المستقل لنموذج الفعالية — التدقيق العلمي P0 (2026-11).

السؤال الذي يجيب عنه هذا السكربت:
    هل يتعلم النموذج التعميم على مركبات جديدة فعلاً، أم يكتفي بتذكّر
    التشابه الكيميائي الموجود في التدريب؟

البروتوكول (وفق مراجعة التدقيق العلمي):
    1. Random Split  — نفس بروتوكول الإنتاج (train_test_split, seed=42)
                       لإعادة إنتاج الرقم المُعلن كما هو.
    2. Scaffold Split— تقسيم حسب هياكل Bemis–Murcko: لا يمرّ هيكل واحد
                       بين التدريب والاختبار. 5 بذور → وسط ± انحراف.
                       فجوة (Random − Scaffold) هي مقياس «التذكّر مقابل التعميم».
    3. خطوط أساس     — متوسط التدريب (أرضية سطحية) + أقرب جار كيميائي
                       (Tanimoto على بصمات Morgan): هل يتفوق RF فعلاً على
                       «ابحث عن أنسب جزيء مقيس وأعد قياسه»؟
    4. المقاييس      — MAE / RMSE / R² مع فواصل ثقة 95% (Bootstrap 1000×)
                       + تحليل الخطأ حسب مدى النشاط + فحص معايرة عدم
                       اليقين (ارتباط |الخطأ| بانحراف أشجار RF).
    5. تدقيق تسرب    — عدد الهياكل المشتركة بين التدريب والاختبار في
                       التقسيم العشوائي (مصدر تضخم محتمل للرقم المعلن).

الصدق المنهجي:
    - نفس التمثيل ونفس النموذج المعتمد في الإنتاج حرفياً (P11):
      بصمة Morgan تكرارات + RF 300 مع max_features=0.3 — والمحاذاة
      تُتَتبع باختبار (COUNT_BASED/PROD_MAX_FEATURES مقابل الإنتاج).
    - كل المعالجة قبل التقسيم حتمية لكل جزيء (بصمة/هيكل) — لا معلومة
      من الاختبار تتسرب إلى التدريب.
    - كل الأرقام محسوبة فعلياً وتُكتب في docs/audit/ — لا افتراضات.

الاستخدام:
    python3 scripts/evaluate_generalization.py                # كامل (دقائق)
    python3 scripts/evaluate_generalization.py --quick        # RF=60 شجرة
    python3 scripts/evaluate_generalization.py --outdir DIR
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
from rdkit import Chem
from rdkit.Chem.Scaffolds import MurckoScaffold
from scipy import stats
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from core.ml_potency import featurize, load_dataset

RANDOM_SEED = 42          # نفس بذرة الإنتاج — مقارنة عادلة
TEST_SIZE = 0.2           # نفس نسبة الإنتاج
# ── مواءمة بروتوكول الإنتاج المعتمد (P11 / train_default_model) ──
# النموذج المعتمد v0.12.0: بصمة Morgan تكرارات (count_based=True) +
# RF 300 مع max_features=0.3. قبل هذه المواءمة كان البروتوكول يحسب
# بالتكوين التاريخي الثنائي — رقماً صادقاً يومها لكنه لم يعد «مواصفة
# الإنتاج». المحاذاة تُلزم بطاقات النماذج أن توثّق النموذج الذي يعمل فعلاً.
COUNT_BASED = True                 # featurize(count_based=True) — كالإنتاج
PROD_MAX_FEATURES = 0.3            # RandomForestRegressor(max_features=0.3) — كالإنتاج
BOOTSTRAP_N = 1000
CI_LEVEL = 0.95
ACTIVITY_BINS = [(0.0, 5.0, "ضعيف (<5)"), (5.0, 7.0, "متوسط (5–7)"), (7.0, 99.0, "قوي (>7)")]


# ────────────────────────────── helpers ──────────────────────────────

def murcko_scaffold(smiles: str) -> str | None:
    """هيكل Bemis–Murcko كسلسلة SMILES — None إذا فشل التحليل."""
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None
    try:
        return MurckoScaffold.MurckoScaffoldSmiles(mol=mol, includeChirality=False)
    except Exception:  # noqa: BLE001 — هيكل شاذ نادر
        return None


def bootstrap_ci(y_true: np.ndarray, y_pred: np.ndarray, metric: str) -> tuple[float, float]:
    """فاصل ثقة 95% بإعادة المعاينة على مجموعة الاختبار (1000×)."""
    rng = np.random.default_rng(RANDOM_SEED)
    n = len(y_true)
    vals = []
    for _ in range(BOOTSTRAP_N):
        idx = rng.integers(0, n, n)
        yt, yp = y_true[idx], y_pred[idx]
        if metric == "r2":
            vals.append(r2_score(yt, yp))
        elif metric == "mae":
            vals.append(mean_absolute_error(yt, yp))
        else:
            vals.append(float(np.sqrt(mean_squared_error(yt, yp))))
    lo, hi = np.percentile(vals, [(1 - CI_LEVEL) / 2 * 100, (1 + CI_LEVEL) / 2 * 100])
    return float(lo), float(hi)


def metrics_block(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    """MAE/RMSE/R² + فواصل الثقة + الخطأ حسب مدى النشاط."""
    out: dict = {
        "mae": round(float(mean_absolute_error(y_true, y_pred)), 3),
        "rmse": round(float(np.sqrt(mean_squared_error(y_true, y_pred))), 3),
        "r2": round(float(r2_score(y_true, y_pred)), 3),
        "n_test": len(y_true),
    }
    for name in ("mae", "rmse", "r2"):
        lo, hi = bootstrap_ci(y_true, y_pred, name)
        out[f"{name}_ci95"] = [round(lo, 3), round(hi, 3)]
    # الخطأ حسب مدى النشاط — أين يخفق النموذج؟
    bins = []
    for lo_v, hi_v, label in ACTIVITY_BINS:
        mask = (y_true >= lo_v) & (y_true < hi_v)
        if mask.sum() >= 3:
            bins.append(
                {
                    "bin": label,
                    "n": int(mask.sum()),
                    "mae": round(float(np.mean(np.abs(y_true[mask] - y_pred[mask]))), 3),
                }
            )
    out["mae_by_activity_bin"] = bins
    return out


def fit_rf(
    X_tr, y_tr, seed: int, n_estimators: int, max_features: float | None = PROD_MAX_FEATURES
) -> RandomForestRegressor:
    """نفس مواصفات الإنتاج المعتمد حرفياً: RF 300 + max_features=0.3 (P11)."""
    model = RandomForestRegressor(
        n_estimators=n_estimators,
        max_features=max_features,
        random_state=seed,
        n_jobs=-1,
        oob_score=False,
    )
    model.fit(X_tr, y_tr)
    return model


def tree_std(model: RandomForestRegressor, X_te) -> np.ndarray:
    """انحراف تنبؤات الأشجار الفردية — تقدير عدم اليقين المستخدم في الإنتاج."""
    preds = np.stack([est.predict(X_te) for est in model.estimators_])
    return preds.std(axis=0)


# ────────────────────────────── splits ──────────────────────────────

def random_split_protocol(X, y, seed: int) -> tuple[np.ndarray, np.ndarray]:
    """بروتوكول الإنتاج الحرفي — train_test_split على مستوى الجزيء."""
    idx_tr, idx_te = train_test_split(np.arange(len(y)), test_size=TEST_SIZE, random_state=seed)
    return idx_tr, idx_te


def scaffold_split_protocol(scaffolds: list[str | None], n: int, seed: int):
    """تقسيم حسب الهيكل (greedy bin-packing على نمط DeepChem):
    تُخلط الهياكل ببذرة ثم تُعبأ في التدريب حتى 80% — لا هيكل يعبر الحدود."""
    rng = np.random.default_rng(seed)
    by_scaffold: dict[str, list[int]] = {}
    for i, scf in enumerate(scaffolds):
        key = scf if scf is not None else f"__invalid__{i}"
        by_scaffold.setdefault(key, []).append(i)
    groups = sorted(by_scaffold.values(), key=len, reverse=True)
    order = rng.permutation(len(groups))
    n_train_target = int(n * (1 - TEST_SIZE))
    idx_tr: list[int] = []
    idx_te: list[int] = []
    for g_i in order:
        group = groups[g_i]
        if len(idx_tr) < n_train_target:
            idx_tr.extend(group)
        else:
            idx_te.extend(group)
    return np.array(idx_tr), np.array(idx_te)


def knn_baseline_predict(X_tr, y_tr, X_te) -> np.ndarray:
    """أقرب جار كيميائي — تانيروتو معمّم Σmin/Σmax على بصمات Morgan.

    بصمات الإنتاج تكرارات، فالصيغة الثنائية c/(a+b−c) مضللة هنا؛
    الصيغة المعمّمة تتفكك إلى الثنائية حرفياً على المتجهات 0/1
    (نفس دالة core.model_cards.generalized_tanimoto بلا استيراد دائري).
    """
    from scipy.spatial.distance import cdist as _cdist

    X_te = np.asarray(X_te, dtype=float)
    X_tr = np.asarray(X_tr, dtype=float)
    sums_te = X_te.sum(axis=1)[:, None]
    sums_tr = X_tr.sum(axis=1)[None, :]
    l1 = _cdist(X_te, X_tr, "cityblock")
    smin = (sums_te + sums_tr - l1) / 2.0
    smax = (sums_te + sums_tr + l1) / 2.0
    sims = smin / (smax + 1e-12)
    return y_tr[np.argmax(sims, axis=1)]


# ────────────────────────────── main ──────────────────────────────

def run(outdir: Path, n_estimators: int, n_scaffold_seeds: int) -> dict:
    t0 = time.perf_counter()
    outdir.mkdir(parents=True, exist_ok=True)

    df = load_dataset(REPO_ROOT / "data" / "mpro_sample.csv")
    smiles_all = df["smiles"].tolist()
    y_all = df["pchembl_value"].to_numpy(dtype=float)

    X, valid_idx = featurize(smiles_all, count_based=COUNT_BASED)
    y = y_all[valid_idx]
    valid_smiles = [smiles_all[i] for i in valid_idx]
    scaffolds = [murcko_scaffold(s) for s in valid_smiles]
    n_invalid = len(smiles_all) - len(valid_idx)
    n_scaffolds = len({s for s in scaffolds if s is not None})
    print(f"[data] {len(y)} molecules valid ({n_invalid} dropped) · {n_scaffolds} unique Murcko scaffolds")

    results: dict = {
        "protocol": {
            "dataset": "data/mpro_sample.csv (ChEMBL4523582 — SARS-CoV-2 Mpro pChEMBL)",
            "n_total": len(y),
            "n_invalid_dropped": int(n_invalid),
            "n_unique_scaffolds": int(n_scaffolds),
            "features": "Morgan count fingerprints radius=2, 2048 (count_based=True — التكوين المعتمد P11 في core/ml_potency حرفياً)",
            "model": f"RandomForestRegressor(n_estimators={n_estimators}, max_features={PROD_MAX_FEATURES}) — نفس مواصفات الإنتاج المعتمد",
            "test_size": TEST_SIZE,
            "bootstrap_resamples": BOOTSTRAP_N,
            "sklearn_version": __import__("sklearn").__version__,
            "rdkit_version": __import__("rdkit").__version__,
            "protocol_alignment": "2026-11-10: محاذاة البروتوكول إلى التكوين المعتمد P11 (counts + max_features=0.3) + تانيروتو معمّم — المرجع أعيد توليده على هذه البيئة",
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S %Z"),
            "runtime_seconds": None,
        },
        "random_split": {},
        "scaffold_split": {},
        "baselines": {},
        "leakage_audit": {},
        "uncertainty_calibration": {},
    }

    # 1) Random split — بروتوكول الإنتاج الحرفي (seed=42)
    print("[1/4] random split (production protocol, seed=42)…")
    idx_tr, idx_te = random_split_protocol(X, y, RANDOM_SEED)
    rf_rand = fit_rf(X[idx_tr], y[idx_tr], RANDOM_SEED, n_estimators)
    pred_rand = rf_rand.predict(X[idx_te])
    results["random_split"]["rf"] = metrics_block(y[idx_te], pred_rand)

    # تدقيق التسرب: هياكل مشتركة بين التدريب والاختبار في التقسيم العشوائي
    scf_tr = {scaffolds[i] for i in idx_tr if scaffolds[i] is not None}
    scf_te = {scaffolds[i] for i in idx_te if scaffolds[i] is not None}
    shared = scf_tr & scf_te
    n_shared_mols = sum(1 for i in idx_te if scaffolds[i] in shared)
    results["leakage_audit"] = {
        "random_split_shared_scaffolds": len(shared),
        "shared_scaffold_fraction_of_test": round(n_shared_mols / len(idx_te), 3),
        "note": (
            "هذه نسبة جزيئات الاختبار التي لهيكلها نظراء في التدريب "
            "في التقسيم العشوائي — مصدر تضخم محتمل لرقم R² المعلن."
        ),
    }

    # 2) Scaffold split — 5 بذور
    print(f"[2/4] scaffold split × {n_scaffold_seeds} seeds…")
    seed_runs = []
    for seed in range(n_scaffold_seeds):
        idx_tr, idx_te = scaffold_split_protocol(scaffolds, len(y), seed)
        rf_s = fit_rf(X[idx_tr], y[idx_tr], seed, n_estimators)
        pred_s = rf_s.predict(X[idx_te])
        m = metrics_block(y[idx_te], pred_s)
        m["seed"] = seed
        seed_runs.append(m)
        print(f"      seed={seed}: R²={m['r2']} MAE={m['mae']} (n_test={m['n_test']})")
    agg = {
        k: {
            "mean": round(float(np.mean([r[k] for r in seed_runs])), 3),
            "std": round(float(np.std([r[k] for r in seed_runs])), 3),
        }
        for k in ("r2", "mae", "rmse")
    }
    results["scaffold_split"] = {"per_seed": seed_runs, "aggregate": agg}

    # 3) خطوط الأساس — متوسط التدريب + أقرب جار (على التقسيمين)
    print("[3/4] baselines (mean + 1-NN Tanimoto)…")
    results["baselines"] = {}
    for split_name, (i_tr, i_te) in {
        "random": random_split_protocol(X, y, RANDOM_SEED),
        "scaffold": scaffold_split_protocol(scaffolds, len(y), 0),
    }.items():
        mean_pred = np.full(len(i_te), y[i_tr].mean())
        results["baselines"][f"train_mean_{split_name}"] = metrics_block(y[i_te], mean_pred)
        knn_pred = knn_baseline_predict(X[i_tr], y[i_tr], X[i_te])
        results["baselines"][f"1nn_tanimoto_{split_name}"] = metrics_block(y[i_te], knn_pred)

    # 4) معايرة عدم اليقين: هل يتنبأ انحراف الأشجار بالخطأ فعلاً؟
    print("[4/4] uncertainty calibration (|error| vs tree-std)…")
    rho_rand = stats.spearmanr(np.abs(y[idx_te] - pred_rand), tree_std(rf_rand, X[idx_te]))
    i_tr_s, i_te_s = scaffold_split_protocol(scaffolds, len(y), 0)
    rf_s0 = fit_rf(X[i_tr_s], y[i_tr_s], 0, n_estimators)
    rho_scaf = stats.spearmanr(
        np.abs(y[i_te_s] - rf_s0.predict(X[i_te_s])), tree_std(rf_s0, X[i_te_s])
    )
    results["uncertainty_calibration"] = {
        "spearman_rho_abserror_vs_treestd_random": {
            "rho": round(float(rho_rand.statistic), 3),
            "p_value": float(f"{rho_rand.pvalue:.2e}"),
        },
        "spearman_rho_abserror_vs_treestd_scaffold": {
            "rho": round(float(rho_scaf.statistic), 3),
            "p_value": float(f"{rho_scaf.pvalue:.2e}"),
        },
        "note": (
            "ارتباط موجب قوي = فترة الثقة من تباين الأشجار تحمل معلومة؛ "
            "ارتباط ضعيف = لا تُعرض كفاصل ثقة موثوق."
        ),
    }

    # الخلاصة الحاسمة: فجوة التذكّر/التعميم
    r2_random = results["random_split"]["rf"]["r2"]
    r2_scaffold = agg["r2"]["mean"]
    gap = round(r2_random - r2_scaffold, 3)
    results["generalization_gap"] = {
        "r2_random": r2_random,
        "r2_scaffold_mean": r2_scaffold,
        "gap": gap,
        "ratio_scaffold_to_random": round(r2_scaffold / r2_random, 3) if r2_random > 0 else None,
    }

    results["protocol"]["runtime_seconds"] = round(time.perf_counter() - t0, 1)

    # كتابة JSON + الطباعة
    json_path = outdir / "model-evaluation-results.json"
    json_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[done] JSON → {json_path}")
    print(f"       R² random={r2_random} · R² scaffold={r2_scaffold} ± {agg['r2']['std']} · gap={gap}")
    print(f"       baseline 1-NN(scaffold) R²={results['baselines']['1nn_tanimoto_scaffold']['r2']}")
    return results


def main() -> None:
    ap = argparse.ArgumentParser(description="تقييم التعميم المستقل — Random vs Scaffold")
    ap.add_argument("--outdir", type=Path, default=REPO_ROOT / "docs" / "audit")
    ap.add_argument("--n-estimators", type=int, default=300)
    ap.add_argument("--quick", action="store_true", help="RF=60 شجرة — فحص سريع فقط")
    args = ap.parse_args()
    if args.quick:
        args.n_estimators = 60
    run(args.outdir, args.n_estimators, n_scaffold_seeds=5)


if __name__ == "__main__":
    main()
