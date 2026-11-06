#!/usr/bin/env python3
"""P12 — Lab07: القياس الخارجي الرسمي على TDC admet_group (خطة التطوير §3، P12).

أول مرة يقاس فيها المشروع على مرجع لا نملكه: مهمتا انحدار قياسيتان من
المجموعة المرجعية الرسمية ADMET Group في Therapeutics Data Commons،
بتقسيمها الرسمي ومقياسها الرسمي (MAE عبر `BenchmarkGroup.evaluate_many`)
وعلى البذور الرسمية [1..5] نفسها التي تُبنى عليها لوحة الصدارة.

ما يُقاس بالضبط: خط أنابيب v0.12.0 **المعتمد** (بصمة Morgan بالتكرارات
2048bit + RandomForest 300 شجرة، max_features=0.3) بوصفه فئة خطوط
أنابيب انحدار SMILES→قيمة — وليس نموذج Mpro الفعالية نفسه (لا مهمة
pIC50 لـ Mpro في TDC؛ توثيق الفجوة في تقرير التدقيق).

البروتوكول الرسمي الحرفي (من مصدر TDC):
  * الاختبار: تقسيم Scaffold مثبّت مسبقاً (20%) لا يمسّه أحد.
  * train/valid لكل بذرة: create_scaffold_split من train_val بنسبة
    (0.875/0.125) — الدالة الرسمية في TDC نفسها.
  * النتيجة: متوسط ± انحراف معياري لـ MAE الاختبار عبر البذور الخمس
    كما تحسبه `group.evaluate_many` — لا حسبة يدوية.

الاستخدام:
    pip install PyTDC --no-deps   # بلا سحب تبعيات — بيئة المشروع محفوظة
    python3 scripts/evaluate_tdc_p12.py            # المهمتان الرسميتان
    python3 scripts/evaluate_tdc_p12.py --tasks lipophilicity_astrazeneca
    python3 scripts/evaluate_tdc_p12.py --outdir docs/audit

المخرجات: docs/audit/model-tdc-p12-results.json
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata as im
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from core.ml_potency import featurize  # خط v0.12.0 المعتمد حرفياً

# ---------------------------------------------------------------------------
# الثوابت — تكوين v0.12.0 المعتمد (ذراع D) + البروتوكول الرسمي
# ---------------------------------------------------------------------------

SEEDS = [1, 2, 3, 4, 5]          # البذور الرسمية للوحة TDC
RF_TREES = 300                    # نفس P0/P11
RF_MAX_FEATURES = 0.3             # المعتمد في P11
RF_SEED = 42                      # بذرة النموذج ثابتة — يتغير تقسيم train/valid فقط
COUNT_BASED = True                # بصمة التكرارات (المعتمدة)
NBITS = 2048
RADIUS = 2

TASKS = {
    "lipophilicity_astrazeneca": {
        "label": "Lipophilicity_AstraZeneca (TDC.Lipophilicity_AstraZeneca)",
        "unit": "log-ratio", "n_total": 4200, "metric": "MAE", "split": "Scaffold",
        "leaderboard_url": "https://tdcommons.ai/benchmark/admet_group/05lipo",
        "leaderboard": {  # اللوحة الرسمية كاملة — مقدَّرة عند 2026-11-04
            "MiniMol": [0.456, 0.008], "Chemprop-RDKit": [0.467, 0.006],
            "Chemprop": [0.470, 0.009], "BaseBoosting (Huang)": [0.479, 0.007],
            "ADMETrix": [0.512, 0.010], "CMPNN": [0.515, 0.008],
            "MapLight + GNN": [0.525, 0.003], "ContextPred": [0.535, 0.012],
            "StackingRegressor (DeepMol)": [0.538, 0.001], "MapLight": [0.539, 0.002],
            "GCN": [0.541, 0.011], "AttrMasking": [0.547, 0.024],
            "NeuralFP": [0.563, 0.023], "AttentiveFP": [0.572, 0.007],
            "RDKit2D + MLP (DeepPurpose)": [0.574, 0.017],
            "Basic ML (Boral)": [0.617, 0.003], "Euclia ML model": [0.621, 0.005],
            "CFA": [0.626, 0.013], "DeepMol (AutoML)": [0.656, 0.012],
        },
    },
    "solubility_aqsoldb": {
        "label": "Solubility_AqSolDB (TDC.Solubility_AqSolDB)",
        "unit": "log mol/L", "n_total": 9982, "metric": "MAE", "split": "Scaffold",
        "leaderboard_url": "https://tdcommons.ai/benchmark/admet_group/06aqsol",
        "leaderboard": {
            "MiniMol": [0.741, 0.013], "Chemprop-RDKit": [0.761, 0.025],
            "DeepMol (AutoML)": [0.775, 0.006], "AttentiveFP": [0.776, 0.008],
            "MapLight + GNN": [0.789, 0.003], "MapLight": [0.792, 0.002],
            "CMPNN": [0.796, 0.038], "RDKit2D + MLP (DeepPurpose)": [0.827, 0.047],
            "Basic ML (Boral)": [0.828, 0.002], "Chemprop": [0.829, 0.022],
            "GCN": [0.907, 0.020], "CFA": [0.939, 0.030],
            "NeuralFP": [0.947, 0.016], "CNN (DeepPurpose)": [1.023, 0.023],
            "AttrMasking": [1.026, 0.020], "ContextPred": [1.040, 0.045],
            "Euclia ML model": [1.076, 0.016],
            "Morgan + MLP (DeepPurpose)": [1.203, 0.019],
        },
    },
}

# النسخة المجمدة من التقسيم الرسمي تحت data/external/admet_group/
# (تصميم ذاكرة TDC الأصلي بالبايت — يعمل السكربت دون شبكة)
FROZEN_DIR = REPO / "data" / "external" / "admet_group"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def env_report() -> dict:
    """بيئة التشغيل الفعلية — كما تُعرض في تقارير التدقيق دائماً."""
    pkgs = ["PyTDC", "numpy", "scikit-learn", "rdkit", "pandas"]
    versions = {}
    for p in pkgs:
        try:
            versions[p] = im.version(p)
        except Exception:  # noqa: BLE001 — البيانات الوصفية تتسامح مع حزم غير متاحة
            versions[p] = "غير متوفر"
    return {"python": sys.version.split()[0], **versions}


ARMS = {
    "adopted": {
        "label": "المعتمد v0.12.0 (mf=0.3)",
        "max_features": RF_MAX_FEATURES,
    },
    "sqrt_diagnostic": {
        "label": "تشخيصي sqrt (الافتراضي القياسي للبصمات)",
        "max_features": "sqrt",
    },
}


def fit_adopted_pipeline(smiles: list[str], y: list[float],
                         max_features: float | str = RF_MAX_FEATURES) -> tuple:
    """تدريب تكوين v0.12.0 المعتمد حرفياً على تقسيم خارجي (بلا تقسيم داخلي).

    يعيد (النموذج، عدد الجزيئات المستبعدة في التدريب).
    """
    from sklearn.ensemble import RandomForestRegressor

    X, idx = featurize(smiles, RADIUS, NBITS, count_based=COUNT_BASED)
    y_arr = np.asarray(y, dtype=float)[idx]
    model = RandomForestRegressor(
        n_estimators=RF_TREES,
        max_features=max_features,
        random_state=RF_SEED,
        n_jobs=-1,
    )
    model.fit(X, y_arr)
    return model, len(smiles) - len(idx)


def predict_adopted_pipeline(model, smiles: list[str]) -> tuple[np.ndarray, int]:
    """تنبؤ على مجموعة اختبار خارجية؛ الفاشل تحليله يُنعَّم بمتوسط التدريب."""
    X, idx = featurize(smiles, RADIUS, NBITS, count_based=COUNT_BASED)
    pred = np.full(len(smiles), np.nan)
    if len(idx):
        pred[np.asarray(idx)] = model.predict(X)
    n_fail = len(smiles) - len(idx)
    if n_fail:  # تعويض موثّق — عادة صفر في مجموعات TDC المنقّاة
        pred[np.isnan(pred)] = float(np.nanmean(pred[np.asarray(idx)])) if len(idx) else 0.0
    return pred, n_fail


def run_task(group, task: str, spec: dict, arm: str) -> dict:
    mf = ARMS[arm]["max_features"]
    print(f"\n=== {task} — بروتوكول TDC الرسمي (بذور {SEEDS}) — ذراع {ARMS[arm]['label']} ===",
          flush=True)
    benchmark = group.get(task)
    name = benchmark["name"]
    train_val, test = benchmark["train_val"], benchmark["test"]
    assert len(train_val) + len(test) == spec["n_total"], "حجم المجموعة غير مطابق"
    test_smiles = test["Drug"].tolist()
    test_y = test["Y"].to_numpy(dtype=float)

    predictions_list = []
    per_seed = []
    for seed in SEEDS:
        t0 = time.time()
        train, _valid = group.get_train_valid_split(seed=seed, benchmark=task)
        model, n_tr_fail = fit_adopted_pipeline(
            train["Drug"].tolist(), train["Y"].tolist(), max_features=mf
        )
        pred, n_te_fail = predict_adopted_pipeline(model, test_smiles)
        assert not np.isnan(pred).any(), "تنبؤات اختبار ناقصة بعد التعويض"
        predictions_list.append({name: pred.tolist()})
        mae = float(np.mean(np.abs(test_y - pred)))
        ss_res = float(np.sum((test_y - pred) ** 2))
        ss_tot = float(np.sum((test_y - test_y.mean()) ** 2))
        per_seed.append({
            "seed": seed,
            "n_train": len(train) - n_tr_fail,
            "n_train_dropped_unparseable": int(n_tr_fail),
            "n_test": len(test),
            "n_test_dropped_unparseable_imputed": int(n_te_fail),
            "mae": round(mae, 4),
            "r2": round(1.0 - ss_res / ss_tot, 4),
            "seconds": round(time.time() - t0, 1),
        })
        print(f"  seed {seed}: MAE={mae:.4f} R2={per_seed[-1]['r2']:.4f} "
              f"({per_seed[-1]['seconds']}s)", flush=True)

    # الحكم الرسمي بمقياس TDC نفسه — لا حسبة يدوية
    official = group.evaluate_many(predictions_list)
    official_mae = float(official[name][0])
    official_std = float(official[name][1])
    print(f"  ★ الرسمي (evaluate_many): MAE = {official_mae:.4f} ± {official_std:.4f}",
          flush=True)

    # موقعنا في اللوحة الرسمية
    entries = sorted(
        [{"model": k, "mae": v[0], "std": v[1]} for k, v in spec["leaderboard"].items()],
        key=lambda e: e["mae"],
    )
    better = [e for e in entries if e["mae"] < official_mae]
    rank = len(better) + 1
    best = entries[0]
    fingerprint_baseline = [e for e in entries if "Morgan" in e["model"]]
    fp_note = fingerprint_baseline[0] if fingerprint_baseline else None

    return {
        "task": task,
        "arm": arm,
        "arm_label": ARMS[arm]["label"],
        "max_features": mf,
        "label": spec["label"],
        "unit": spec["unit"],
        "n_total": spec["n_total"],
        "n_train_val": len(train_val),
        "n_test": len(test),
        "metric": "MAE",
        "our_mae_mean": round(official_mae, 4),
        "our_mae_std": round(official_std, 4),
        "per_seed": per_seed,
        "our_r2_mean": round(float(np.mean([s["r2"] for s in per_seed])), 4),
        "leaderboard_rank_of_ours": rank,
        "n_leaderboard_entries": len(entries),
        "leaderboard_best": best,
        "gap_to_best": round(official_mae - best["mae"], 4),
        "fingerprint_baseline_note": fp_note,
        "leaderboard_url": spec["leaderboard_url"],
        "leaderboard_reference": spec["leaderboard"],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--tasks", nargs="*", default=list(TASKS),
                    choices=list(TASKS))
    ap.add_argument("--arms", nargs="*", default=list(ARMS), choices=list(ARMS))
    ap.add_argument("--outdir", default=str(REPO / "docs" / "audit"))
    args = ap.parse_args()

    try:
        from tdc.benchmark_group import admet_group
    except ImportError as e:
        print("PyTDC غير مثبت. ثبّته بلا سحب تبعيات لحماية بيئة المشروع:")
        print("    pip install PyTDC --no-deps && pip install 'setuptools<81'")
        print(f"  ({e})")
        return 2

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    out_path = outdir / "model-tdc-p12-results.json"

    group = admet_group(path=str(REPO / "data" / "external"))

    # دمج مع نتائج سابقة (التشغيل على دفعات مهمة×ذراع)
    out = {}
    if out_path.exists():
        try:
            out = json.loads(out_path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001 — استئناف تقييم متسامح: ملف تالف يعني البدء من جديد
            out = {}
    out.setdefault("tasks", {})
    out["phase"] = "P12 — Lab07: القياس الخارجي الرسمي (TDC admet_group)"
    out["generated_utc"] = datetime.now(UTC).isoformat(timespec="seconds")
    out["what_is_measured"] = (
        "خط أنابيب v0.12.0 المعتمد (Morgan تكرارات 2048 + RF300, "
        "max_features=0.3) بوصفه فئة خطوط انحدار SMILES→قيمة على مرجع "
        "لا نملكه — وليس نموذج Mpro الفعالية (لا مهمة pIC50-Mpro في TDC)"
    )
    out["protocol"] = {
        "group": "TDC admet_group (المرجعية الرسمية للوحة الصدارة)",
        "test_set": "Scaffold split رسمي مثبت 20% (يأتي من TDC ولا يُلمس)",
        "train_valid": "create_scaffold_split الرسمية على train_val بنسبة 0.875/0.125 لكل بذرة",
        "seeds": SEEDS,
        "metric": "MAE كما تحسبه group.evaluate_many الرسمية (متوسط ± انحراف)",
        "model_seed_fixed": RF_SEED,
        "arms": {k: {"max_features": v["max_features"], "label": v["label"]}
                 for k, v in ARMS.items()},
        "pipeline": {
            "featurizer": f"Morgan count-based r={RADIUS}, {NBITS}bit (v0.12.0 المعتمد)",
            "model": f"RandomForest {RF_TREES} trees",
        },
    }
    out["environment"] = env_report()
    out["frozen_data"] = {
        "dir": "data/external/admet_group/ (تصميم ذاكرة TDC الأصلي — يعمل دون شبكة)",
        "sha256": {
            str(p.relative_to(FROZEN_DIR)): sha256(p)
            for p in sorted(FROZEN_DIR.rglob("*.csv"))
        } if FROZEN_DIR.exists() else {},
    }
    out["leaderboard_reference_accessed"] = "2026-11-04"

    for task in args.tasks:
        slot = out["tasks"].setdefault(task, {
            "task": task, "label": TASKS[task]["label"],
            "unit": TASKS[task]["unit"], "n_total": TASKS[task]["n_total"],
            "metric": "MAE", "official_split": "Scaffold 20% test (TDC)",
            "leaderboard_url": TASKS[task]["leaderboard_url"],
            "leaderboard_reference": TASKS[task]["leaderboard"],
            "arms": {},
        })
        for arm in args.arms:
            slot["arms"][arm] = run_task(group, task, TASKS[task], arm)

    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n✍️  كُتب: {out_path}", flush=True)

    # خلاصة قابلة للقراءة
    print("\n=== الخلاصة مقابل اللوحة الرسمية ===", flush=True)
    for task, slot in out["tasks"].items():
        print(f"{slot['label']}", flush=True)
        for arm, r in slot["arms"].items():
            print(f"  [{arm}] نحن: MAE = {r['our_mae_mean']} ± {r['our_mae_std']} "
                  f"(المرتبة {r['leaderboard_rank_of_ours']}/{r['n_leaderboard_entries']})",
                  flush=True)
            print(f"      الأفضل ({r['leaderboard_best']['model']}): "
                  f"{r['leaderboard_best']['mae']} — الفجوة: +{r['gap_to_best']}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
