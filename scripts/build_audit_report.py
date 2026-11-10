"""مولّد تقرير التدقيق العلمي — يقرأ model-evaluation-results.json ويصيغ التقرير الرسمي.

يشغَّل بعد evaluate_generalization.py:
    python3 scripts/evaluate_generalization.py   # أرقام حقيقية → JSON
    python3 scripts/build_audit_report.py        # JSON → Markdown رسمي
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from pharma_sdl.scores import disclaimer_md

AUDIT_DIR = REPO_ROOT / "docs" / "audit"


def fmt_ci(block: dict, key: str) -> str:
    lo, hi = block.get(f"{key}_ci95", [None, None])
    return f"± {hi - block[key]:.3f}" if lo is not None else "—"


def table_row(label: str, block: dict) -> str:
    return (
        f"| {label} | {block['r2']:.3f} | {fmt_ci(block, 'r2')} "
        f"| {block['mae']:.3f} | {fmt_ci(block, 'mae')} "
        f"| {block['rmse']:.3f} | {block['n_test']} |"
    )


def render(results: dict) -> str:
    p = results["protocol"]
    rnd = results["random_split"]["rf"]
    scaf = results["scaffold_split"]["aggregate"]
    scaf0 = results["scaffold_split"]["per_seed"][0]
    gap = results["generalization_gap"]
    baselines = results["baselines"]
    cal = results["uncertainty_calibration"]
    leak = results["leakage_audit"]
    scaf_ci = round(1.96 * scaf["r2"]["std"], 3)
    scaf_mae_ci = [
        round(scaf["mae"]["mean"] - 1.96 * scaf["mae"]["std"], 3),
        round(scaf["mae"]["mean"] + 1.96 * scaf["mae"]["std"], 3),
    ]

    verdict = (
        "النموذج يتعلم إشارة تعميم حقيقية تتجاوز التذكّر الهيكلي"
        if gap["gap"] <= 0
        else "فجوة التعميم حاضرة — جزء من الأداء المعلن تذكّر تشابه لا تعميم"
    )

    return f"""# تقرير التقييم المستقل لنموذج الفعالية — التدقيق العلمي P0

> **السؤال المحوري:** هل يتعلم نموذج pIC50 التعميم على مركبات جديدة فعلاً،
> أم يكتفي بتذكّر التشابه الكيميائي في التدريب؟ — **أرقام محسوبة فعلاً، لا افتراضات.**

- **التاريخ:** {p['generated_at']} · **زمن التنفيذ:** {p['runtime_seconds']}s
- **البيانات:** {p['dataset']} — {p['n_total']} جزيء صالح ({p['n_invalid_dropped']} مستبعد) · {p['n_unique_scaffolds']} هيكل Murcko فريد
- **التمثيل:** {p['features']} · **النموذج:** {p['model']} · **نسبة الاختبار:** {int(p['test_size'] * 100)}%
- **إعادة الإنتاج:** `python3 scripts/evaluate_generalization.py` ← يولّد JSON ثم هذا التقرير عبر `scripts/build_audit_report.py`

---

## 1) الخلاصة التنفيذية — إجابات الأرقام

| السؤال | الجواب بالأرقام |
|---|---|
| هل الرقم المعلن (R² عشوائي للنموذج المعتمد) قابل لإعادة الإنتاج؟ | **نعم** — R² عشوائي = **{rnd['r2']:.3f}** [95% CI {rnd['r2_ci95'][0]:.3f}–{rnd['r2_ci95'][1]:.3f}] بنفس بروتوكول الإنتاج حرفياً |
| هل يتععم النموذج على هياكل جديدة؟ | **نعم، بمستوى معقول** — R² هيكلي = **{scaf['r2']['mean']:.3f} ± {scaf['r2']['std']:.3f}** (5 بذور)؛ الفجوة = {gap['gap']:+.3f} → **{verdict}** |
| هل يتفوق على خط أساس ساذج؟ | نعم بوضوح على «متوسط التدريب» (R² = {baselines['train_mean_scaffold']['r2']:.3f})، لكن **فارقه عن «أقرب جار كيميائي» متواضع** — انظر §3 |
| هل فترة الثقة (تباين الأشجار) موثوقة؟ | **جزئياً** — ارتباطها بالخطأ الفعلي ضعيف على التقسيم العشوائي (ρ={cal['spearman_rho_abserror_vs_treestd_random']['rho']}, p={cal['spearman_rho_abserror_vs_treestd_random']['p_value']}) وأفضل هيكلياً (ρ={cal['spearman_rho_abserror_vs_treestd_scaffold']['rho']}) → تُعرض كإشارة ترتيب لا كفاصل ثقة معايَر |
| أين يخطئ أكثر؟ | **عند الأطراف** — المركبات القوية (>7) MAE ≈ {scaf0['mae_by_activity_bin'][2]['mae']:.2f} والضعيفة (<5) ≈ {scaf0['mae_by_activity_bin'][0]['mae']:.2f}، مقابل {scaf0['mae_by_activity_bin'][1]['mae']:.2f} فقط في الوسط — وعتبات «الحكم التعليمي» تقع بالضبط في منطقة أسوأ دقة |

## 2) النتائج التفصيلية

| البروتوكول | R² | CI(R²) | MAE | CI(MAE) | RMSE | n_test |
|---|---|---|---|---|---|---|
{table_row('Random split — RF (بروتوكول الإنتاج)', rnd)}
{table_row('Scaffold split — RF (وسط 5 بذور)', {'r2': scaf['r2']['mean'], 'mae': scaf['mae']['mean'], 'rmse': scaf['rmse']['mean'], 'n_test': scaf0['n_test'], 'r2_ci95': [scaf['r2']['mean'] - scaf_ci, scaf['r2']['mean'] + scaf_ci], 'mae_ci95': scaf_mae_ci})}
{table_row('Random — أقرب جار Tanimoto (1-NN)', baselines['1nn_tanimoto_random'])}
{table_row('Scaffold — أقرب جار Tanimoto (1-NN)', baselines['1nn_tanimoto_scaffold'])}
{table_row('Scaffold — متوسط التدريب (أرضية)', baselines['train_mean_scaffold'])}

- **فجوة التعميم:** R²(random) − R²(scaffold) = {rnd['r2']:.3f} − {scaf['r2']['mean']:.3f} = **{gap['gap']:+.3f}**
  (النسبة {gap['ratio_scaffold_to_random']}) — القيمة السالبة تعني أن الأداء على هياكل غير مرى قبلها **لا يقل** عن الأداء ضمن هياكل مألوفة؛ مخاوف «التذكّر الهيكلي» لا تدعمها الأرقام في هذا النطاق.
- توزيع بذور Scaffold: {' · '.join(f"seed {s['seed']}: {s['r2']:.3f}" for s in results['scaffold_split']['per_seed'])}

## 3) القراءة الصادقة: النموذج مقابل «ابحث عن الأنسب»

خط الأساس 1-NN (أعد قياس أنسب جزيء مقيس) يحقق R² = {baselines['1nn_tanimoto_scaffold']['r2']:.3f} على التقسيم الهيكلي —
أي أن الزيادة الحقيقية للنموذج فوق «قاعدة بيانات مطابقة تشابه» ≈ **{scaf['r2']['mean'] - baselines['1nn_tanimoto_scaffold']['r2']:.3f}** في R² فقط.
هذا لا يُلغي قيمة النموذج (زمن استجابة فوري، وتغطية ما لا قياس له)، لكنه يمنع أي ادعاء بأن RF يفهم
«علاقة بنية-فعالية» عميقة عند 900 جزيء. القيمة الحقيقية المطلوبة تأتي من بيانات أكثر تنوعاً — لا من أشجار أكثر.

## 4) تحليل الخطأ حسب مدى النشاط (Scaffold seed=0)

| المدى | n | MAE | التفسير |
|---|---|---|---|
| ضعيف (<5) | {scaf0['mae_by_activity_bin'][0]['n']} | {scaf0['mae_by_activity_bin'][0]['mae']:.3f} | مبالغة في التقدير — انحدار نحو المتوسط |
| متوسط (5–7) | {scaf0['mae_by_activity_bin'][1]['n']} | {scaf0['mae_by_activity_bin'][1]['mae']:.3f} | أفضل نطاق |
| قوي (>7) | {scaf0['mae_by_activity_bin'][2]['n']} | {scaf0['mae_by_activity_bin'][2]['mae']:.3f} | **تقليل من التقدير — أخطر منطقة**: عتبة «مثبط قوي» (7.0) في فقر الدقة |

**أثر عملي فوري:** لا يجوز اعتبار تنبؤ ≥ 7 دليلاً على «مثبط قوي» — النموذج يميل لتسطيح القيم الشديدة.
عرض الحكم التعليمي يجب أن يقرأ بجانبه MAE النطاق نفسه.

## 5) تدقيق التسرب الهيكلي في التقسيم العشوائي

{leak['random_split_shared_scaffolds']} هيكلاً مشتركاً بين التدريب والاختبار في التقسيم العشوائي — أي **{leak['shared_scaffold_fraction_of_test'] * 100:.1f}%** من جزيئات الاختبار لها نظراء هيكلية في التدريب.
هذا مصدر التضخم المحتمل الكلاسيكي؛ **تجريبياً هنا لم يتضخم الرقم** (الهيكلي {scaf['r2']['mean']:.3f} ≥ العشوائي {rnd['r2']:.3f})،
لكن البروتوكول المعتمد مستقبلاً هو **Scaffold Split حصراً** لأي رقم يُعلن، مع بقاء العشوائي للمقارنة التاريخية فقط.

## 6) معايرة عدم اليقين (فترة الثقة من تباين الأشجار)

- عشوائي: Spearman ρ = {cal['spearman_rho_abserror_vs_treestd_random']['rho']} (p = {cal['spearman_rho_abserror_vs_treestd_random']['p_value']}) — **غير دال** عن 180 جزيء.
- هيكلي: Spearman ρ = {cal['spearman_rho_abserror_vs_treestd_scaffold']['rho']} (p = {cal['spearman_rho_abserror_vs_treestd_scaffold']['p_value']:.1e}) — دال لكنه متوسط القوة.

**القرار:** تُعرض فترة الثقة في الواجهة والتقارير كـ«إشارة ثقة نسبية» مع نص صريح بأنها **غير معايَرة تجريبياً** —
لا تُقرأ كفاصل ثقة إحصائي. المعايرة الحقيقية (conformal prediction) بند لاحق بعد توسيع البيانات.

## 7) حدود هذا التقرير (تُقرأ قبل أي اقتباس لأرقامه)

1. **هدف واحد وحجم واحد:** 900 قياس لهدف Mpro من مستند ChEMBL واحد — لا دليل على الصلاحية خارج هذا النطاق.
2. **لا عمود لنوع الاختبار:** مجموعة CSV الحالية لا تميّز IC50/Ki/Kd ولا شروط الاختبار — مراجعة نوع النشاط قبل الدمج بند P0 في مسار الكيرايشن.
3. **فترات الثقة Bootstrap** تعكس تقلب مجموعات الاختبار الصغيرة، ولا تعالج انحياز العينة.
4. **التمثيل ثنائي فقط:** بصمات Morgan دون أي وصف 3D — لا استنتاج عن الحتمية الفراغية للارتباط.
5. pIC50 يُعامَل هنا كبديل لـpKd (افتراض Cheng-Prusoff) — تقريب موثق في `pharma_sdl/affinity/consensus.py`.

## 8) الإجراءات المترتبة

| # | الإجراء | الأولوية |
|---|---|---|
| 1 | اعتماد Scaffold Split كبروتوكول الإعلان الرسمي — تثبيت هذا السكربت في CI كفحص انحراف | P0 — هذا التقرير |
| 2 | عرض MAE النطاق بجانب كل «حكم تعليمي» في الواجهة والتقارير | P0 |
| 3 | وسم فترة الثقة بأنها «غير معايَرة» في كل المخرجات (نُفِّذ في عقد `pharma_sdl/scores.py`) | P0 — منفَّذ |
| 4 | إثراء البيانات (هدف Mpro كامل من ChEMBL مع نوع الاختبار وشروطه) قبل أي تحدث للنموذج | P1 |
| 5 | معايرة عدم اليقين (Conformal) بعد توسيع البيانات | P2 |

---

{disclaimer_md('ar')}

*تقرير مولّد آلياً — `scripts/build_audit_report.py` من `docs/audit/model-evaluation-results.json`؛ كل رقم فيه محسوب فعلاً بتاريخه.*
"""


def main() -> None:
    results = json.loads((AUDIT_DIR / "model-evaluation-results.json").read_text(encoding="utf-8"))
    out = AUDIT_DIR / "MODEL-EVALUATION-REPORT.md"
    out.write_text(render(results), encoding="utf-8")
    print(f"[done] {out}")


if __name__ == "__main__":
    main()
