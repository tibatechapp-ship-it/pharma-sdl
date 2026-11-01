"""مسارات الدرجات الثلاثة — عقد صدق واحد تلتزم به كل الطبقات.

المبدأ (تدقيق علمي P0 — 2026-11):
    درجة الالتحام ≠ الفعالية المتنبأ بها ≠ النشاط التجريبي.
    ثلاثة أرقام بطبيعة مختلفة جوهرياً؛ دمجها برقم واحد — أو مقارنة درجات
    Vina بين بروتينين مختلفين — ادعاء لا يدعمه الدليل، وممنوع في هذه المنصة.

كل مسار يحمل: هويته، وطبيعة رقمه (فيزياء تقريبية / إحصاء تعميمي / قياس مخبري)،
ووحدته، ومصدره، وحدود تفسيره الصريحة. الطبقات الثلاث (API، التقارير، الواجهة)
تعرض الأرقام دائماً داخل مسارها المعلن — لا «درجة موحدة» في أي مخرج.

هذه الوحدة stdlib خالصة بلا أي تبعية — آمنة لـstlite وCI وكل مستهلك.
"""

from __future__ import annotations

from dataclasses import dataclass

# ─────────────────────────────────────────────────────────────
# التحذير العلمي/الطبي — يظهر في الواجهة والتقارير وكل استجابة فرز،
# وليس في التوثيق فقط (قرار تدقيق P0 — 2026-11).
# ─────────────────────────────────────────────────────────────

DISCLAIMER_AR = (
    "**تنبيه علمي وطبي:** هذه المنصة أداة بحثية حاسوبية لدعم استكشاف الفرضيات "
    "وتقييم المركبات. نتائج الالتحام الجزيئي والتنبؤات الحاسوبية لا تثبت "
    "الفعالية أو السلامة لدى البشر، ولا تُعد توصية علاجية أو بديلاً عن "
    "الاختبارات المخبرية والسمية والدراسات قبل السريرية والسريرية والمراجعة "
    "التنظيمية المناسبة. لا يجوز اتخاذ قرارات تشخيصية أو علاجية اعتماداً على "
    "هذه المخرجات وحدها."
)

DISCLAIMER_EN = (
    "**Scientific & medical notice:** this platform is a computational research "
    "tool for hypothesis exploration and compound triage. Docking results and "
    "computational predictions do not establish human efficacy or safety, are "
    "not a therapeutic recommendation, and are no substitute for wet-lab, "
    "toxicity, preclinical/clinical studies, and regulatory review. No "
    "diagnostic or treatment decision may rely on these outputs alone."
)


@dataclass(frozen=True)
class ScoreLane:
    """مسار درجة واحد — رقم بطبيعة معلنة وحدود تفسير صريحة."""

    id: str
    label_ar: str
    label_en: str
    nature_ar: str  # طبيعة الرقم: فيزياء تقريبية / إحصاء تعميمي / قياس مخبري
    nature_en: str
    unit: str
    source_ar: str
    source_en: str
    limit_ar: str  # حدود التفسير — ما لا يجوز استنتاجه من هذا الرقم
    limit_en: str


SCORE_LANES: dict[str, ScoreLane] = {
    "docking_score": ScoreLane(
        id="docking_score",
        label_ar="درجة الالتحام (Vina / محاكاة)",
        label_en="Docking score (Vina / simulation)",
        nature_ar="فيزياء تقريبية (تقدير طاقة على شبكة)",
        nature_en="approximate physics (grid energy estimate)",
        unit="kcal/mol",
        source_ar="محرك الالتحام المُستخدم في الجولة (`engine_used`)",
        source_en="the docking engine used this run (`engine_used`)",
        limit_ar=(
            "تُفسَّر داخل هدف واحد وبنية واحدة فقط — لا تُقارن درجات Vina "
            "بين بروتينين، والأكثر سالبية ليس «دواءً أقوى» بل «وضعية مفضلة تقديرياً»."
        ),
        limit_en=(
            "valid within one target and one structure only — never compare Vina "
            "scores across proteins; more negative means a preferred estimated "
            "pose, not a stronger drug."
        ),
    ),
    "predicted_potency": ScoreLane(
        id="predicted_potency",
        label_ar="الفعالية المتنبأ بها (نموذج ML)",
        label_en="Predicted potency (ML model)",
        nature_ar="إحصاء تعميمي (انحدار على بصمات)",
        nature_en="generalizing statistics (fingerprint regression)",
        unit="pIC50",
        source_ar="RandomForest على بصمات Morgan — مدرب على قياسات ChEMBL",
        source_en="RandomForest on Morgan fingerprints — trained on ChEMBL assays",
        limit_ar=(
            "صلاحيته محدودة بقدرة التعميم المقاسة في تقرير التقييم المستقل "
            "(docs/audit/MODEL-EVALUATION-REPORT.md)؛ فترة الثقة من تباين "
            "الأشجار ليست معايرة تجريبياً."
        ),
        limit_en=(
            "validity is bounded by the measured generalization in the independent "
            "evaluation report (docs/audit/MODEL-EVALUATION-REPORT.md); tree-variance "
            "confidence intervals are not experimentally calibrated."
        ),
    ),
    "experimental_activity": ScoreLane(
        id="experimental_activity",
        label_ar="النشاط التجريبي (المرجع)",
        label_en="Experimental activity (reference)",
        nature_ar="قياس مخبري موثق",
        nature_en="documented wet-lab measurement",
        unit="pChEMBL",
        source_ar="ChEMBL — مع نوع الاختبار (IC50/Ki/Kd) وشروطه عند توافرها",
        source_en="ChEMBL — with assay type (IC50/Ki/Kd) and conditions where available",
        limit_ar=(
            "المرجع الوحيد للحقيقة في هذه المنصة؛ يخضع لنوع الاختبار وشروطه، "
            "ولا يُدمج مع المسارين الآخرين ولا يُشتق منهما عكساً."
        ),
        limit_en=(
            "the only ground truth here; subject to assay type and conditions, "
            "never merged with the other lanes nor back-derived from them."
        ),
    ),
}

_LANES_TITLES = {
    "ar": ("مسارات الدرجات الثلاثة — لا تُدمج ولا تُقارن عبر الأهداف", "المسار", "طبيعة الرقم", "الوحدة", "حدود التفسير"),
    "en": ("The three score lanes — never merged, never compared across targets", "Lane", "Nature of the number", "Unit", "Interpretation limits"),
}


def lanes_legend_md(lang: str = "ar") -> str:
    """أسطورة المسارات الثلاثة كجدول Markdown — تُلحق بكل تقرير وعرض نتائج."""
    title, c1, c2, c3, c4 = _LANES_TITLES.get(lang, _LANES_TITLES["ar"])
    lines = [f"### {title}", "", f"| {c1} | {c2} | {c3} | {c4} |", "|---|---|---|---|"]
    for lane in SCORE_LANES.values():
        if lang == "en":
            lines.append(f"| **{lane.label_en}** | {lane.nature_en} | {lane.unit} | {lane.limit_en} |")
        else:
            lines.append(f"| **{lane.label_ar}** | {lane.nature_ar} | {lane.unit} | {lane.limit_ar} |")
    return "\n".join(lines)


_DISCLAIMER_TITLES = {
    "ar": "تنبيه علمي وطبي",
    "en": "Scientific & medical notice",
}


def disclaimer_md(lang: str = "ar") -> str:
    """التحذير العلمي/الطبي بصيغة Markdown — قسم كامل للتقارير وسترات الواجهة."""
    text = DISCLAIMER_EN if lang == "en" else DISCLAIMER_AR
    return f"> ⚠️ {text}"


__all__ = [
    "DISCLAIMER_AR",
    "DISCLAIMER_EN",
    "SCORE_LANES",
    "ScoreLane",
    "disclaimer_md",
    "lanes_legend_md",
]
