"""A/B/C/D لتقنية النموذج — P11 (ترقية تمثيل النموذج وفق خطة التطوير §5.2).

السؤال الذي يجيب عنه هذا السكربت:
    هل يرفع دمج الوصف الفيزيوكيميائي / بديل HistGB / بصمة التكرارات
    الأداء الهيكلي المعلن (R² = 0.489 ± 0.097)؟ وما الذي يُعتمد إنتاجياً؟

البروتوكول — حرفياً بروتوكول P0 المنشور (evaluate_generalization.py):
    1. Random Split  — بروتوكول الإنتاج (train_test_split, seed=42).
    2. Scaffold Split— Bemis–Murcko greedy bin-packing، 5 بذور (0..4)
                       → وسط ± انحراف. لا هيكل يعبر الحدود.
    3. المقاييس      — MAE / RMSE / R² مع Bootstrap CI 95% (1000×).
    4. الأساس المرجعي— 1-NN Tanimoto على التمثيل الأصلي (نفس P0).
    5. معايرة عدم اليقين — RF: انحراف الأشجار · HistGB: عرض الفترة الكمّية
                       (Spearman |الخطأ| × الإشارة) + تغطية الفترة 0.159/0.841.

الأذرع:
    A  Morgan ثنائي (2048) + RF 300                 — المرتكز (يجب أن يعيد أرقام P0)
    B  Morgan ثنائي ⊕ physchem (20) + RF 300        — فرضية الخطة: أثر الوصف وحده
    C  Morgan ثنائي ⊕ physchem (20) + HistGB 150    — فرضية الخطة: نموذج بديل
    D  Morgan تكرارات (2048) + RF 300 (max_features=0.3) — الفائز من المسح الاستكشافي

إجراء الاختيار (معلن بصدق):
    المسح الاستكشافي للضبط جرى على بذور هيكلية (0–2) ثم قُيّمت الأذرع
    النهائية على البذور الخمس الكاملة (0–4) — الذراع D (max_features)
    والضبط المعلن لـ C اختيرا على (0–2)، وأرقامها المعلنة أدناه على (0–4)
    تحمل انحياز اختيار معلناً ومحدوداً (مساحة الضبط صغيرة وثابتة في JSON).

الصدق المنهجي:
    - نفس دوال التقسيم والمقاييس مستوردة من السكربت المنشور P0 — لا إعادة كتابة.
    - كل الأذرع تُقيَّم على نفس التقسيمات بالضبط (مقارنة مقترنة عادلة).
    - الحكم المعتمد: وسط R² هيكلي للتقسيمات الخمس (المقياس الأول المعتمد
      منذ P0) — مع اشتراط عدم تدهور العشوائي بقيمة جوهرية.

الاستخدام:
    python3 scripts/evaluate_ab_p11.py                    # كامل (دقائق)
    python3 scripts/evaluate_ab_p11.py --outdir DIR
    python3 scripts/evaluate_ab_p11.py --quick            # فحص سريع فقط
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
from scipy import stats
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

# نفس دوال البروتوكول المنشور — مصدر حقيقة واحد، لا نسخ
from core.ml_potency import featurize, load_dataset
from scripts.evaluate_generalization import (
    RANDOM_SEED,
    TEST_SIZE,
    knn_baseline_predict,
    metrics_block,
    murcko_scaffold,
    random_split_protocol,
    scaffold_split_protocol,
    tree_std,
)

BOOTSTRAP_N = 1000
TARGET_SCAFFOLD_R2 = 0.55  # هدف خطة التطوير P11
RANDOM_REGRESSION_TOLERANCE = 0.02  # أقصى تدهور مقبول في العشوائي مقابل A

GB_PARAMS = {  # الضبط المعلن لذراع C — من المسح الاستكشافي (بذور 0–2)
    "max_iter": 150,
    "learning_rate": 0.08,
    "max_leaf_nodes": 31,
    "l2_regularization": 1.0,
}


def fit_arm(kind: str, X_tr, y_tr, seed: int, rf_trees: int, mf: float | None, gb_params: dict):
    """تدريب ذراع واحدة — RF بضبط الإنتاج أو HistGB بضبط معلن."""
    if kind == "rf":
        m = RandomForestRegressor(
            n_estimators=rf_trees, max_features=mf, random_state=seed, n_jobs=-1, oob_score=False
        )
        m.fit(X_tr, y_tr)
        return m, None, None
    point = HistGradientBoostingRegressor(
        loss="squared_error", early_stopping=False, random_state=seed, **gb_params
    )
    lo = HistGradientBoostingRegressor(
        loss="quantile", quantile=0.159, early_stopping=False, random_state=seed, **gb_params
    )
    hi = HistGradientBoostingRegressor(
        loss="quantile", quantile=0.841, early_stopping=False, random_state=seed, **gb_params
    )
    point.fit(X_tr, y_tr)
    lo.fit(X_tr, y_tr)
    hi.fit(X_tr, y_tr)
    return point, lo, hi


def arm_predict(kind: str, model, lo, hi, X_te) -> tuple[np.ndarray, np.ndarray]:
    """تنبؤات النقطة وعرض فترة عدم اليقين (RF: انحراف أشجار × 1.96×2)."""
    pred = model.predict(X_te)
    if kind == "rf":
        span = tree_std(model, X_te) * 2 * 1.96
    else:
        span = hi.predict(X_te) - lo.predict(X_te)
    return pred, span


def spearman_abs_error(y_true, y_pred, signal) -> dict:
    rho = stats.spearmanr(np.abs(y_true - y_pred), signal)
    return {"rho": round(float(rho.statistic), 3), "p_value": float(f"{rho.pvalue:.2e}")}


def run(outdir: Path, rf_trees: int, gb_params: dict, n_scaffold_seeds: int) -> dict:
    t0 = time.perf_counter()
    outdir.mkdir(parents=True, exist_ok=True)

    df = load_dataset(REPO_ROOT / "data" / "mpro_sample.csv")
    smiles_all = df["smiles"].tolist()
    y_all = df["pchembl_value"].to_numpy(dtype=float)

    # التمثيلات الثلاثة على نفس جزيئات P0 الصالحة حصراً (مقارنة مقترنة)
    X_bin, valid_idx = featurize(smiles_all)  # تمثيل P0 الأصلي — نفس فهارس P0
    y = y_all[valid_idx]
    valid_smiles = [smiles_all[i] for i in valid_idx]
    scaffolds = [murcko_scaffold(s) for s in valid_smiles]
    n_scaffolds = len({s for s in scaffolds if s is not None})

    X_bin_desc, desc_idx = featurize(smiles_all, include_descriptors=True)
    X_count, _ = featurize(smiles_all, count_based=True)
    assert desc_idx == valid_idx, "فهارس التمثيلات غير متطابقة — يجب أن تكون مقترنة"

    arms_spec = {
        "A_morgan_bin_rf": {"X": X_bin, "kind": "rf", "mf": None,
                            "label": "Morgan ثنائي + RF300 — مرتكز P0"},
        "B_morgan_physchem_rf": {"X": X_bin_desc, "kind": "rf", "mf": None,
                                 "label": "Morgan ⊕ physchem(20) + RF300 — فرضية الوصف"},
        "C_morgan_physchem_histgb": {"X": X_bin_desc, "kind": "histgb", "mf": None,
                                     "label": "Morgan ⊕ physchem(20) + HistGB — فرضية النموذج البديل"},
        "D_morgan_count_rf_mf03": {"X": X_count, "kind": "rf", "mf": 0.3,
                                   "label": "Morgan تكرارات + RF300(max_features=0.3) — المعتمد"},
    }
    n = len(y)
    print(f"[data] {n} molecules · {n_scaffolds} scaffolds · dims: bin={X_bin.shape[1]} +desc={X_bin_desc.shape[1]} count={X_count.shape[1]}")

    results: dict = {
        "protocol": {
            "dataset": "data/mpro_sample.csv (ChEMBL4523582 — SARS-CoV-2 Mpro pChEMBL)",
            "n_total": n,
            "n_unique_scaffolds": int(n_scaffolds),
            "arms": {k: v["label"] for k, v in arms_spec.items()},
            "rf_n_estimators": rf_trees,
            "histgb_params": {"early_stopping": False, **gb_params},
            "random_seed": RANDOM_SEED,
            "scaffold_seeds": list(range(n_scaffold_seeds)),
            "test_size": TEST_SIZE,
            "bootstrap_resamples": BOOTSTRAP_N,
            "target_scaffold_r2": TARGET_SCAFFOLD_R2,
            "random_regression_tolerance": RANDOM_REGRESSION_TOLERANCE,
            "selection_note": (
                "المسح الاستكشافي للضبط على بذور هيكلية (0–2)؛ الأرقام المعلنة "
                "هنا على البذور الخمس (0–4) وتحمل انحياز اختيار معلناً ومحدوداً."
            ),
            "protocol_source": "scripts/evaluate_generalization.py (P0) — نفس الدوال مستوردة",
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S %Z"),
            "runtime_seconds": None,
        },
        "arms": {},
        "baselines_reference": {},
    }

    # خط الأساس المرجعي — 1-NN Tanimoto على تمثيل P0 (نفس P0)
    print("[baseline] 1-NN Tanimoto (morgan bin)…")
    for split_name, (i_tr, i_te) in {
        "random": random_split_protocol(X_bin, y, RANDOM_SEED),
        "scaffold": scaffold_split_protocol(scaffolds, n, 0),
    }.items():
        knn_pred = knn_baseline_predict(X_bin[i_tr], y[i_tr], X_bin[i_te])
        results["baselines_reference"][f"1nn_tanimoto_{split_name}"] = metrics_block(y[i_te], knn_pred)

    # التحقق من المرتكز مقابل P0
    published = REPO_ROOT / "docs" / "audit" / "model-evaluation-results.json"
    anchor_pub = json.loads(published.read_text(encoding="utf-8")) if published.exists() else None

    for arm_name, spec in arms_spec.items():
        X, kind, mf = spec["X"], spec["kind"], spec["mf"]
        print(f"\n[arm] {arm_name} ({kind}, mf={mf})…")
        arm_res: dict = {}

        # 1) Random split — seed 42
        i_tr, i_te = random_split_protocol(X, y, RANDOM_SEED)
        model, lo, hi = fit_arm(kind, X[i_tr], y[i_tr], RANDOM_SEED, rf_trees, mf, gb_params)
        pred, span = arm_predict(kind, model, lo, hi, X[i_te])
        arm_res["random_split"] = metrics_block(y[i_te], pred)
        arm_res["uncertainty_calibration"] = {"random": spearman_abs_error(y[i_te], pred, span)}
        if kind == "histgb":
            lo_v, hi_v = lo.predict(X[i_te]), hi.predict(X[i_te])
            arm_res["quantile_coverage"] = {
                "random": {
                    "coverage_68": round(float(np.mean((y[i_te] >= lo_v) & (y[i_te] <= hi_v))), 3),
                    "mean_span": round(float(np.mean(hi_v - lo_v)), 3),
                }
            }

        # 2) Scaffold split × 5 بذور — نفس بذور P0 حرفياً
        seed_runs = []
        for seed in range(n_scaffold_seeds):
            i_tr_s, i_te_s = scaffold_split_protocol(scaffolds, n, seed)
            model_s, lo_s, hi_s = fit_arm(kind, X[i_tr_s], y[i_tr_s], seed, rf_trees, mf, gb_params)
            pred_s, span_s = arm_predict(kind, model_s, lo_s, hi_s, X[i_te_s])
            m = metrics_block(y[i_te_s], pred_s)
            m["seed"] = seed
            seed_runs.append(m)
            if kind == "histgb" and seed == 0:
                lo_v, hi_v = lo_s.predict(X[i_te_s]), hi_s.predict(X[i_te_s])
                arm_res["quantile_coverage"]["scaffold_seed0"] = {
                    "coverage_68": round(float(np.mean((y[i_te_s] >= lo_v) & (y[i_te_s] <= hi_v))), 3),
                    "mean_span": round(float(np.mean(hi_v - lo_v)), 3),
                }
                arm_res["uncertainty_calibration"]["scaffold"] = spearman_abs_error(
                    y[i_te_s], pred_s, span_s
                )
            print(f"      seed={seed}: R²={m['r2']} MAE={m['mae']} (n_test={m['n_test']})")
        agg = {
            k: {
                "mean": round(float(np.mean([r[k] for r in seed_runs])), 3),
                "std": round(float(np.std([r[k] for r in seed_runs])), 3),
            }
            for k in ("r2", "mae", "rmse")
        }
        arm_res["scaffold_split"] = {"per_seed": seed_runs, "aggregate": agg}
        arm_res["generalization_gap"] = {
            "r2_random": arm_res["random_split"]["r2"],
            "r2_scaffold_mean": agg["r2"]["mean"],
            "gap": round(arm_res["random_split"]["r2"] - agg["r2"]["mean"], 3),
        }
        results["arms"][arm_name] = arm_res

    # التحقق من المرتكز مقابل P0
    if anchor_pub is not None:
        a = results["arms"]["A_morgan_bin_rf"]
        match = (
            a["random_split"]["r2"] == anchor_pub["random_split"]["rf"]["r2"]
            and a["scaffold_split"]["aggregate"]["r2"]["mean"]
            == anchor_pub["scaffold_split"]["aggregate"]["r2"]["mean"]
        )
        results["anchor_check"] = {
            "published_random_r2": anchor_pub["random_split"]["rf"]["r2"],
            "reproduced_random_r2": a["random_split"]["r2"],
            "published_scaffold_r2_mean": anchor_pub["scaffold_split"]["aggregate"]["r2"]["mean"],
            "reproduced_scaffold_r2_mean": a["scaffold_split"]["aggregate"]["r2"]["mean"],
            "match": match,
        }

    # المقارنة والحكم
    scaffold_r2 = {k: v["scaffold_split"]["aggregate"]["r2"] for k, v in results["arms"].items()}
    random_r2 = {k: v["random_split"]["r2"] for k, v in results["arms"].items()}
    base_mean = scaffold_r2["A_morgan_bin_rf"]["mean"]
    base_rand = random_r2["A_morgan_bin_rf"]
    # الترشح: تفوق هيكلي + عدم تدهور عشوائي جوهري
    eligible = {
        k for k in scaffold_r2
        if k != "A_morgan_bin_rf"
        and scaffold_r2[k]["mean"] > base_mean
        and random_r2[k] >= base_rand - RANDOM_REGRESSION_TOLERANCE
    }
    best_arm = max(eligible, key=lambda k: scaffold_r2[k]["mean"]) if eligible else "A_morgan_bin_rf"
    results["comparison"] = {
        "scaffold_r2_mean": {k: v["mean"] for k, v in scaffold_r2.items()},
        "scaffold_r2_std": {k: v["std"] for k, v in scaffold_r2.items()},
        "scaffold_mae_mean": {
            k: results["arms"][k]["scaffold_split"]["aggregate"]["mae"]["mean"]
            for k in results["arms"]
        },
        "random_r2": random_r2,
        "delta_scaffold_vs_A": {k: round(scaffold_r2[k]["mean"] - base_mean, 3) for k in scaffold_r2},
        "eligible_for_adoption": sorted(eligible),
        "winner_by_scaffold_r2": best_arm,
        "adoption_target": TARGET_SCAFFOLD_R2,
        "adoption_verdict": (
            "ADOPT" if best_arm != "A_morgan_bin_rf" and scaffold_r2[best_arm]["mean"] >= TARGET_SCAFFOLD_R2
            else ("ADOPT_PARTIAL" if best_arm != "A_morgan_bin_rf" else "KEEP_BASELINE")
        ),
    }

    results["protocol"]["runtime_seconds"] = round(time.perf_counter() - t0, 1)

    json_path = outdir / "model-ab-p11-results.json"
    json_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n" + "═" * 78)
    print(f"{'الذراع':<30}{'R² عشوائي':>10}{'R² هيكلي (وسط±σ)':>20}{'Δ هيكلي':>9}{'MAE هيكلي':>10}")
    for k in arms_spec:
        s = scaffold_r2[k]
        print(
            f"{k:<30}{random_r2[k]:>10}{s['mean']:>10} ± {s['std']:<8}"
            f"{results['comparison']['delta_scaffold_vs_A'][k]:>9}"
            f"{results['comparison']['scaffold_mae_mean'][k]:>10}"
        )
    print("═" * 78)
    print(f"[anchor] A يعيد أرقام P0 حرفياً: {results.get('anchor_check', {}).get('match')}")
    print(f"[verdict] الفائز: {best_arm} → {results['comparison']['adoption_verdict']} (هدف الخطة ≥ {TARGET_SCAFFOLD_R2})")
    print(f"[done] JSON → {json_path}")
    return results


def main() -> None:
    ap = argparse.ArgumentParser(description="A/B/C/D لترقية نموذج الفعالية — P11")
    ap.add_argument("--outdir", type=Path, default=REPO_ROOT / "docs" / "audit")
    ap.add_argument("--rf-trees", type=int, default=300)
    ap.add_argument("--quick", action="store_true", help="فحص سريع (RF=60، HistGB=60) — لا يُنشر")
    args = ap.parse_args()
    if args.quick:
        args.rf_trees = 60
        gb_params = {**GB_PARAMS, "max_iter": 60}
    else:
        gb_params = dict(GB_PARAMS)
    run(args.outdir, args.rf_trees, gb_params, n_scaffold_seeds=5)


if __name__ == "__main__":
    main()
