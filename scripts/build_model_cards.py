"""بناء بطاقات النماذج الرسمية — مركز التحقق الخارجي (v0.18).

يجمع بين البروتوكول المجمَّد (scripts/evaluate_generalization.py — نفس
التقسيمات وبذورها، يُستورد لا يُعاد بناؤه) وبين البُعدين الجديدين من
core/model_cards.py: معايرة تنبؤ/ملاحظة + نطاق قابلية التطبيق.

المخرجات: docs/audit/model-cards-p18-results.json — تقرأه واجهة تبويب
«🛡️ التحقق الخارجي» وتستشهد به الوثائق. أرقام المقاييس يجب أن تطابق
المرجع المجمَّد model-evaluation-results.json حرفياً (نفس البروتوكول) —
إن اختلفت فهناك انحراف عن العقد ويجب التوقف لا النشر.

الاستخدام:
    python3 scripts/build_model_cards.py            # كامل (دقائق)
    python3 scripts/build_model_cards.py --quick    # RF=60 — فحص سريع
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import time
from pathlib import Path

import numpy as np
import sklearn

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from core.ml_potency import featurize, load_dataset
from core.model_cards import build_model_card

# استيراد البروتوكول المجمَّد من مكانه — مصدر واحد للحقيقة
_spec = importlib.util.spec_from_file_location(
    "evaluate_generalization", REPO_ROOT / "scripts" / "evaluate_generalization.py"
)
eg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(eg)

OUT_DEFAULT = REPO_ROOT / "docs" / "audit" / "model-cards-p18-results.json"
SCAFFOLD_SEEDS = (0, 1, 2, 3, 4)  # نفس بذور المرجع المجمَّد


def _tree_std(model, X) -> np.ndarray:
    """انحراف تنبؤات الأشجار — نفس تقدير عدم اليقين في الإنتاج."""
    preds = np.stack([est.predict(X) for est in model.estimators_])
    return preds.std(axis=0)


def main() -> None:
    ap = argparse.ArgumentParser(description="بطاقات النماذج — v0.18")
    ap.add_argument("--outdir", type=Path, default=None, help="مسار JSON الناتج")
    ap.add_argument("--n-estimators", type=int, default=300)
    ap.add_argument("--quick", action="store_true", help="RF=60 — فحص سريع فقط")
    args = ap.parse_args()
    if args.quick:
        args.n_estimators = 60
    outdir = args.outdir or OUT_DEFAULT
    outdir.parent.mkdir(parents=True, exist_ok=True)

    t0 = time.perf_counter()
    df = load_dataset(REPO_ROOT / "data" / "mpro_sample.csv")
    smiles_all = df["smiles"].tolist()
    y_all = df["pchembl_value"].to_numpy(dtype=float)
    X, valid_idx = featurize(smiles_all, count_based=eg.COUNT_BASED)
    y = y_all[valid_idx]
    print(f"[data] {len(y)} molecules · X{X.shape} · RF={args.n_estimators}")

    provenance_base = {
        "dataset": "data/mpro_sample.csv (ChEMBL4523582 — SARS-CoV-2 Mpro pChEMBL)",
        "n_total": len(y),
        "features": "Morgan count fingerprints radius=2, 2048 (count_based=True — التكوين المعتمد P11 في core/ml_potency حرفياً)",
        "model": f"RandomForestRegressor(n_estimators={args.n_estimators}, max_features={eg.PROD_MAX_FEATURES}) — نفس مواصفات الإنتاج المعتمد",
        "test_size": eg.TEST_SIZE,
        "bootstrap_resamples": eg.BOOTSTRAP_N,
        "ad_percentile": 5.0,
        "sklearn_version": sklearn.__version__,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S %Z"),
    }

    # ── 1) بطاقة التقسيم العشوائي — بروتوكول الإنتاج الحرفي (seed=42) ──
    print("[1/2] random split card (production protocol, seed=42)…")
    idx_tr, idx_te = eg.random_split_protocol(X, y, eg.RANDOM_SEED)
    rf = eg.fit_rf(X[idx_tr], y[idx_tr], eg.RANDOM_SEED, args.n_estimators)
    pred = rf.predict(X[idx_te])
    card_random = build_model_card(
        y_true=y[idx_te], y_pred=pred,
        train_X=X[idx_tr], test_X=X[idx_te],
        provenance={**provenance_base, "split": "random seed=42 (بروتوكول الإنتاج)"},
        tree_std=_tree_std(rf, X[idx_te]),
    )

    # ── 2) بطاقة التقسيم الهيكلي — 5 بذور كالمرجع المجمَّد ──
    print(f"[2/2] scaffold split cards × {len(SCAFFOLD_SEEDS)} seeds…")
    scaffolds = [eg.murcko_scaffold(s) for s in [smiles_all[i] for i in valid_idx]]
    per_seed = []
    card_scaffold_seed0 = None
    for seed in SCAFFOLD_SEEDS:
        i_tr, i_te = eg.scaffold_split_protocol(scaffolds, len(y), seed)
        rf_s = eg.fit_rf(X[i_tr], y[i_tr], seed, args.n_estimators)
        pred_s = rf_s.predict(X[i_te])
        m = eg.metrics_block(y[i_te], pred_s)
        m["seed"] = seed
        per_seed.append(m)
        print(f"      seed={seed}: R²={m['r2']} MAE={m['mae']}")
        if seed == 0:
            card_scaffold_seed0 = build_model_card(
                y_true=y[i_te], y_pred=pred_s,
                train_X=X[i_tr], test_X=X[i_te],
                provenance={**provenance_base, "split": "scaffold seed=0 (تفصيل البذرة الأولى)"},
                tree_std=_tree_std(rf_s, X[i_te]),
            )
    agg = {
        k: {
            "mean": round(float(np.mean([r[k] for r in per_seed])), 3),
            "std": round(float(np.std([r[k] for r in per_seed])), 3),
        }
        for k in ("r2", "mae", "rmse")
    }

    # ── الخلاصة الصادقة ──
    r2_random = card_random["metrics"]["r2"]["point"]
    r2_scaffold = agg["r2"]["mean"]
    ad_rand = card_random["applicability_domain"]
    results = {
        "protocol": {
            **provenance_base,
            "frozen_reference": "docs/audit/model-evaluation-results.json — المقاييس يجب أن تطابقه",
            "scaffold_seeds": list(SCAFFOLD_SEEDS),
            "runtime_seconds": None,
        },
        "model_card_random": card_random,
        "model_card_scaffold": {
            "aggregate": agg,
            "per_seed": per_seed,
            "seed0_detail": card_scaffold_seed0,
        },
        "honest_summary_ar": {
            "r2_random": r2_random,
            "r2_scaffold_mean": r2_scaffold,
            "generalization_gap": round(r2_random - r2_scaffold, 3),
            "ad_threshold_random": ad_rand["threshold"],
            "ad_inside_frac_random": ad_rand["inside"]["frac"],
            "reading_ar": (
                "اقرأ البطاقة هكذا: فجوة (العشوائي − الهيكلي) تقيس «التذكّر "
                "مقابل التعميم» مهما كان اتجاهها في بذور بعينها — قيمتها "
                "الحالية فوق، وفترات الثقة تمنع اقتباس نقطة بلا مجالها. "
                "داخل نطاق قابلية التطبيق النموذج يُستشهد به؛ خارجه استقراء "
                "يُعلَن خطره. ومعايرة الصناديق تكشف إن كانت القيم المتوقعة "
                "تعني ما تقول."
            ),
        },
    }
    results["protocol"]["runtime_seconds"] = round(time.perf_counter() - t0, 1)

    outdir.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[done] → {outdir}")
    print(f"  R² random={r2_random} (CI {card_random['metrics']['r2']['ci95']})")
    print(f"  R² scaffold={r2_scaffold} ± {agg['r2']['std']}")
    print(f"  AD(threshold={ad_rand['threshold']}) inside={ad_rand['inside']['frac']}"
          f" r2_in={ad_rand['inside']['r2']} r2_out={ad_rand['outside']['r2']}")


if __name__ == "__main__":
    main()
