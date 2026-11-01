"""تقارير الفرز — Markdown ثنائي اللغة + JSON، جاهزان للعرض والتنزيل والتسليم.

التقرير يحمل دائماً: هوية الهدف، المحرك المستخدم وملاحظات الصدق،
عدّادات التنقية، جدول المرشحين، جدول المرفوضين بأسبابهم، والخطوة التالية.
"""

from __future__ import annotations

from pharma_sdl.models import ScreeningResult
from pharma_sdl.scores import disclaimer_md, lanes_legend_md

_LABELS = {
    "ar": {
        "title": "تقرير فرز ظاهري — Pharma SDL",
        "target": "الهدف",
        "engine": "المحرك",
        "created": "التوقيت",
        "counts": "العدّادات",
        "hits": "قائمة المرشحين (Top {n})",
        "hits_table": ["#", "الاسم", "SMILES", "ΔG kcal/mol", "الطريقة", "أعلام"],
        "rejected": "المرفوضون في التنقية (بالأسباب)",
        "rejected_table": ["المعرّف", "الاسم", "المرحلة", "السبب"],
        "warnings": "تنبيهات",
        "policy": "السياسة",
        "next": "الخطوة التالية",
        "next_text": (
            "تمرير أفضل المرشحين إلى فحص FRET تأكيدي (محاكى حالياً عبر "
            "`POST /api/v1/lab/assays`)، ثم مراجعة بشرية قبل أي التزام مختبري."
        ),
        "lanes": "مسارات الدرجات",
        "disclaimer": "التحذير العلمي والطبي",
        "none": "لا يوجد",
    },
    "en": {
        "title": "Virtual Screening Report — Pharma SDL",
        "target": "Target",
        "engine": "Engine",
        "created": "Created",
        "counts": "Counts",
        "hits": "Hit list (Top {n})",
        "hits_table": ["#", "Name", "SMILES", "ΔG kcal/mol", "Method", "Flags"],
        "rejected": "Curation rejections (with reasons)",
        "rejected_table": ["ID", "Name", "Stage", "Reason"],
        "warnings": "Warnings",
        "policy": "Policy",
        "next": "Next step",
        "next_text": (
            "Send top hits to confirmatory FRET (currently simulated via "
            "`POST /api/v1/lab/assays`), then human review before any lab commitment."
        ),
        "lanes": "Score lanes",
        "disclaimer": "Scientific & medical notice",
        "none": "none",
    },
}


def _short(smiles: str, limit: int = 60) -> str:
    return smiles if len(smiles) <= limit else smiles[: limit - 1] + "…"


def build_markdown(result: ScreeningResult, lang: str = "ar") -> str:
    """تقرير Markdown كامل لجولة فرز — عربي (افتراضي) أو إنجليزي."""
    t = _LABELS.get(lang, _LABELS["ar"])
    lines: list[str] = []
    lines.append(f"# {t['title']} — `{result.run_id}`")
    lines.append("")
    lines.append(f"- **{t['target']}:** {result.target_label_ar} / {result.target_label_en}")
    lines.append(f"- **{t['engine']}:** `{result.engine_used}` (طلب: `{result.engine_requested}`)")
    lines.append(f"- **{t['created']}:** {result.created_at}")
    lines.append(f"- **{t['counts']}:** {result.counts}")
    lines.append("")

    lines.append(f"## {t['hits'].format(n=len(result.hits))}")
    if result.hits:
        header = " | ".join(t["hits_table"])
        lines.append(f"| {header} |")
        lines.append("|" + "---|" * len(t["hits_table"]))
        for h in result.hits:
            flags = ", ".join(
                [f"PAINS:{a}" for a in h.pains_alerts] + h.lipinski_flags + h.warhead_alerts
            ) or t["none"]
            lines.append(
                f"| {h.rank} | {h.name or '—'} | `{_short(h.canonical_smiles)}` "
                f"| **{h.docking_kcal:.2f}** | {h.method} | {flags} |"
            )
    else:
        lines.append(f"_{t['none']}_")
    lines.append("")

    lines.append(f"## {t['rejected']}")
    if result.rejected:
        header = " | ".join(t["rejected_table"])
        lines.append(f"| {header} |")
        lines.append("|" + "---|" * len(t["rejected_table"]))
        for r in result.rejected:
            reason = r.reason_ar if lang == "ar" else r.reason_en
            lines.append(f"| {r.input_id} | {r.name or '—'} | {r.stage} | {reason} |")
    else:
        lines.append(f"_{t['none']}_")
    lines.append("")

    if result.warnings:
        lines.append(f"## {t['warnings']}")
        for w in result.warnings:
            lines.append(f"- {w}")
        lines.append("")

    lines.append("")

    lines.append(f"## {t['lanes']}")
    lines.append(lanes_legend_md(lang))
    lines.append("")

    lines.append(f"## {t['next']}")
    lines.append(t["next_text"])
    lines.append("")

    lines.append(f"## {t['disclaimer']}")
    lines.append(disclaimer_md(lang))
    return "\n".join(lines) + "\n"


def build_json(result: ScreeningResult) -> str:
    """JSON كامل للنتيجة — للأنابيب الآلية والتخزين."""
    return result.model_dump_json(indent=2)
