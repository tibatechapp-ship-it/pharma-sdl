"""حملة المقارنة المرجعية للتعلم النشط — حزمة Q4 وبوابة Go/No-Go (P4).

الخطة v1.1 (الربع الرابع): «ثلاث دورات مغلقة موثقة وتحسّن التعلم النشط على
الأساس العشوائي» — هذا السكربت ينتج الدليل:

    الاستراتيجيات (random / greedy / uncertainty / ucb) × البذور (0..S-1)
    → منحنى «أفضل فعالية مكتشفة» لكل حملة (على قيم الأوراكل الحقيقية)
    → متوسط ± انحراف لكل استراتيجية + الفرق المزاوج ضد random لكل بذرة
    → تغطية conformal الفعلية مقابل الاسمية في كل جولة
    → تقرير JSON + Markdown ثنائي اللغة في docs/audit/ — الخلاصة تُكتب
      من الأرقام المقاسة لا من الرغبة: ما تثبته الأرقام هو ما يُعلن.

الصدق المنهجي:
    - الأوراكل in-silico (قياسات pChEMBL من مجموعة البيانات نفسها) — لا مخبر.
    - القياس الصادق على اختبار scaffold ثابت — لا درجات عشوائية كأدلة.
    - كل الأرقام محسوبة فعلاً ومكتوبة — لا افتراضات ولا تجميل.
    - كل النتائج UNVALIDATED؛ خط pIC50 منفصل عن خطي Docking/المخبر.

الاستخدام:
    python3 scripts/learning_campaign.py                 # كامل (~دقائق)
    python3 scripts/learning_campaign.py --quick         # بذرتان وRF أخف
    python3 scripts/learning_campaign.py --outdir DIR
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from pharma_sdl import __version__
from pharma_sdl.active_learning import STRATEGIES
from pharma_sdl.campaign import DISCLAIMER_AR, DISCLAIMER_EN, run_campaign

DEFAULT_OUTDIR = REPO_ROOT / "docs" / "audit"


def _aggregate(reports: dict[str, list]) -> dict:
    """وسيط ± انحراف لكل استراتيجية + الفروق المزاوجة ضد random."""
    agg: dict = {}
    # كل الحملات تشترك في نفس عدد النقاط (rounds+1) — منحنيات قابلة للمحاذاة
    for strategy, reps in reports.items():
        curves = np.array([r.cumulative_best_curve for r in reps])
        finals = np.array([r.final_best_true for r in reps])
        aucs = np.array([r.curve_auc_normalized() for r in reps])
        agg[strategy] = {
            "curve_mean": [round(float(v), 3) for v in curves.mean(axis=0)],
            "curve_std": [round(float(v), 3) for v in curves.std(axis=0)],
            "final_best_mean": round(float(finals.mean()), 3),
            "final_best_std": round(float(finals.std()), 3),
            "curve_auc_mean": round(float(aucs.mean()), 3),
            "curve_auc_std": round(float(aucs.std()), 3),
            "per_seed_final": {str(r.seed): r.final_best_true for r in reps},
            "mean_conformal_coverage": round(
                float(
                    np.mean(
                        [x.conformal_coverage_empirical for r in reps for x in r.rounds]
                    )
                ),
                3,
            ),
        }
    for strategy, reps in reports.items():
        if strategy == "random":
            continue
        deltas_final = [
            r_final - b_final
            for r_final, b_final in zip(
                (r.final_best_true for r in reps),
                (r.final_best_true for r in reports["random"]),
                strict=True,
            )
        ]
        deltas_auc = [
            r_a - b_a
            for r_a, b_a in zip(
                (r.curve_auc_normalized() for r in reps),
                (r.curve_auc_normalized() for r in reports["random"]),
                strict=True,
            )
        ]
        agg[strategy]["vs_random"] = {
            "delta_final_per_seed": [round(d, 3) for d in deltas_final],
            "delta_final_mean": round(float(np.mean(deltas_final)), 3),
            "delta_auc_mean": round(float(np.mean(deltas_auc)), 3),
            "seeds_won_final": int(sum(1 for d in deltas_final if d > 0)),
            "n_seeds": len(deltas_final),
        }
    return agg


def _verdict(agg: dict, alpha: float) -> tuple[str, str]:
    """الخلاصة من الأرقام — ما تثبته هو ما يُعلن (بلا تجميل)."""
    candidates = [s for s in agg if s != "random"]
    best = max(candidates, key=lambda s: agg[s]["vs_random"]["delta_final_mean"])
    d = agg[best]["vs_random"]
    wins = d["seeds_won_final"]
    n = d["n_seeds"]
    cov = agg["uncertainty"]["mean_conformal_coverage"] if "uncertainty" in agg else None
    ar = (
        f"بوابة Go/No-Go (الربع الرابع): أفضل استراتيجية على خط الأساس العشوائي هي "
        f"«{best}» — الفرق المتوسط في أفضل فعالية مكتشفة {d['delta_final_mean']:+.2f} "
        f"pIC50، وفازت في {wins}/{n} بذور، وفرق متوسط منحنى التعلم "
        f"{d['delta_auc_mean']:+.3f}. "
        + (
            f"تغطية conformal الفعلية {cov:.2f} مقابل الاسمية {1 - alpha:.2f} — "
            f"{'الضمان يعمل عملياً' if cov and cov >= 1 - alpha - 0.05 else 'انحراف معلن يُراجع قبل أي استخدام'}."
            if cov is not None
            else ""
        )
        + " الأوراكل in-silico وكل النتائج UNVALIDATED — الدليل حاسوبي لا مخبري."
    )
    en = (
        f"Go/No-Go gate (Q4): the strongest strategy vs the random baseline is "
        f"'{best}' — mean delta in best-discovered activity {d['delta_final_mean']:+.2f} "
        f"pIC50, winning {wins}/{n} seeds, with learning-curve delta "
        f"{d['delta_auc_mean']:+.3f}. "
        + (
            f"Empirical conformal coverage {cov:.2f} vs nominal {1 - alpha:.2f} — "
            f"{'the guarantee holds in practice' if cov and cov >= 1 - alpha - 0.05 else 'a documented drift to review before any use'}."
            if cov is not None
            else ""
        )
        + " The oracle is in-silico and every result stays UNVALIDATED — "
        "the evidence is computational, not experimental."
    )
    return ar, en


def _write_markdown(out: Path, agg: dict, ar: str, en: str, protocol: dict) -> None:
    lines = [
        "# 📈 تقرير حملات التعلم النشط — حزمة Q4 (P4)",
        "",
        (
            f"> محسوب فعلياً {protocol['generated_at']} · pharma-sdl v{protocol['version']} · "
            f"{protocol['seeds']} بذور × {len(agg)} استراتيجيات × {protocol['rounds']} جولات"
        ),
        "",
        "## البروتوكول",
        "",
        f"- مجموعة البيانات: `{protocol['dataset']}` ({protocol['n_total']} جزيء صالح)",
        f"- الاختبار الثابت: scaffold (Bemis–Murcko) — {protocol['n_test_holdout']} جزيء لا تلمسه الاختيارات",
        "- الأوراكل: **in-silico** — يكشف قياسات pChEMBL من البيانات نفسها (لا مخبر)",
        f"- نموذج: RF {protocol['n_estimators']} شجرة على Morgan (radius=2, 2048 bit) — يُعاد ملاءمته كل جولة",
        f"- معايرة: split-conformal α={protocol['alpha']} (شريحة معايرة منفصلة عن الملاءمة)",
        "",
        "## قراءة صادقة قبل الأرقام",
        "",
        "الـR² على اختبار scaffold يبقى منخفضاً خلال الحملة **بالضرورة**: المُعنون",
        "يبدأ من عشرات الجزيئات فقط — قيمة حملة التعلم النشط هنا في **الاكتشاف**",
        "(إيجاد أعلى فعالية حقيقية بأقل عدد قياسات)، لا في التعميم العالمي الذي",
        "وثّقه تدقيق P0 ببيانات التدريب الكاملة.",
        "",
        "## النتائج الإجمالية (وسيط ± انحراف عبر البذور)",
        "",
        "| الاستراتيجية | أفضل مكتشف (نهائي) | متوسط المنحنى (AUC) | تغطية conformal الفعلية |",
        "|---|---|---|---|",
    ]
    label = {
        "random": "عشوائي (خط الأساس)",
        "greedy": "استغلال صرف",
        "uncertainty": "استكشاف صرف",
        "ucb": "توازن UCB",
    }
    for s, a in agg.items():
        lines.append(
            f"| {label.get(s, s)} | {a['final_best_mean']:.2f} ± {a['final_best_std']:.2f} "
            f"| {a['curve_auc_mean']:.3f} ± {a['curve_auc_std']:.3f} "
            f"| {a['mean_conformal_coverage']:.2f} |"
        )
    lines += [
        "",
        "## الفرق المزاوج ضد العشوائي (لكل بذرة)",
        "",
        "| الاستراتيجية | Δ نهائي (وسيط) | Δ منحنى (وسيط) | بذور فائزة |",
        "|---|---|---|---|",
    ]
    for s, a in agg.items():
        if s == "random":
            continue
        d = a["vs_random"]
        lines.append(
            f"| {label.get(s, s)} | {d['delta_final_mean']:+.2f} | {d['delta_auc_mean']:+.3f} "
            f"| {d['seeds_won_final']}/{d['n_seeds']} |"
        )
    lines += [
        "",
        "## الخلاصة",
        "",
        f"**عربي**: {ar}",
        "",
        f"**English**: {en}",
        "",
        "## المنحنيات (وسيط أفضل فعالية مكتشفة عبر البذور)",
        "",
        "| الجولة | " + " | ".join(label.get(s, s) for s in agg) + " |",
        "|---" * (len(agg) + 1) + "|",
    ]
    n_points = len(next(iter(agg.values()))["curve_mean"])
    for i in range(n_points):
        row = [str(i)]
        for s in agg:
            m, sd = agg[s]["curve_mean"][i], agg[s]["curve_std"][i]
            row.append(f"{m:.2f} ± {sd:.2f}")
        lines.append("| " + " | ".join(row) + " |")
    lines += [
        "",
        "## حدود الدليل",
        "",
        f"- {DISCLAIMER_AR}",
        "",
        f"- {DISCLAIMER_EN}",
        "",
        (
            "المصدر: `scripts/learning_campaign.py` — JSON الكامل: "
            "`docs/audit/active-learning-campaign.json` — حتمي بالبذور المعلمة."
        ),
    ]
    out.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(
        description="مقارنة استراتيجيات التعلم النشط — دليل بوابة Go/No-Go"
    )
    ap.add_argument("--outdir", type=Path, default=DEFAULT_OUTDIR)
    ap.add_argument("--seeds", type=int, default=3, help="عدد البذور (الافتراضي 3)")
    ap.add_argument("--rounds", type=int, default=8)
    ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--initial", type=int, default=40)
    ap.add_argument("--n-estimators", type=int, default=300)
    ap.add_argument("--alpha", type=float, default=0.10)
    ap.add_argument("--quick", action="store_true", help="بذرتان وRF أخف — فحص سريع")
    args = ap.parse_args()
    if args.quick:
        args.seeds = min(args.seeds, 2)
        args.n_estimators = min(args.n_estimators, 60)

    reports: dict[str, list] = {s: [] for s in STRATEGIES}
    t0 = time.perf_counter()
    for strategy in STRATEGIES:
        for seed in range(args.seeds):
            print(f"[campaign] {strategy} seed={seed} …", flush=True)
            reports[strategy].append(
                run_campaign(
                    strategy=strategy,
                    seed=seed,
                    initial_labeled=args.initial,
                    batch_size=args.batch,
                    rounds=args.rounds,
                    n_estimators=args.n_estimators,
                    alpha=args.alpha,
                )
            )
    runtime = round(time.perf_counter() - t0, 1)

    agg = _aggregate(reports)
    ar, en = _verdict(agg, args.alpha)

    first = reports["random"][0]
    protocol = {
        "dataset": str(first.dataset),
        "n_total": first.n_total,
        "n_test_holdout": first.n_test_holdout,
        "n_estimators": args.n_estimators,
        "alpha": args.alpha,
        "seeds": args.seeds,
        "rounds": args.rounds,
        "batch_size": args.batch,
        "initial_labeled": args.initial,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S %Z"),
        "runtime_seconds": runtime,
        "version": __version__,
        "disclaimer_ar": DISCLAIMER_AR,
        "disclaimer_en": DISCLAIMER_EN,
    }
    payload = {
        "protocol": protocol,
        "verdict_ar": ar,
        "verdict_en": en,
        "aggregate": agg,
        "campaigns": {
            s: [r.model_dump(mode="json") for r in reps] for s, reps in reports.items()
        },
    }
    args.outdir.mkdir(parents=True, exist_ok=True)
    json_path = args.outdir / "active-learning-campaign.json"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_markdown(
        args.outdir / "ACTIVE-LEARNING-CAMPAIGN.md", agg, ar, en, protocol
    )
    print(f"\n[done] {json_path}  ({runtime}s)")
    print(f"       {ar}")


if __name__ == "__main__":
    main()
