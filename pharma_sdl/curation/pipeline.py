"""خط التنقية — أول مرحلة تشغيلية في المنصة (50–70% من جهد السنة الأولى
وفق الخطة v1.1، وهذا القسم هو بذرها).

المراحل بالترتيب:
  1) validate  — SMILES صالح؟ (أكبر جزء، تعقيم، وصف كامل)
  2) dedupe    — InChIKey (وعند غيابه SMILES القياسي) — أول ظهور يفوز
  3) covalent_gate — سياسة الهدف تحكم: غير تساهمي حصراً = رفض مسبَّب لكل رأس
  4) pains     — تنبيهات PAINS تُوثَّق (الرفض هنا اختياري لكل سياسة)

كل قرار مسبَّب بلغتين — التدقيق جزء من المخرجات وليس بعدها.
"""

from __future__ import annotations

from collections.abc import Iterable

from pharma_sdl.chemistry.filters import (
    classify_warhead_risk,
    detect_warheads,
    lipinski_flags,
    pains_alerts,
    sa_score,
    veber_flags,
)
from pharma_sdl.chemistry.molecules import (
    InvalidSmiles,
    canonicalize,
    largest_fragment,
    parse_smiles,
)
from pharma_sdl.errors import ValidationError
from pharma_sdl.models import (
    CuratedLigand,
    CurationReport,
    LigandInput,
    Rejection,
)
from pharma_sdl.targets.models import TargetPolicy

_MAX_INPUT_ROWS = 5000


def run_curation(
    rows: Iterable[LigandInput],
    policy: TargetPolicy,
    reject_pains: bool = False,
) -> CurationReport:
    """تنفيذ خط التنقية كاملاً — يعيد تقريراً موقّعاً بالأسباب."""
    inputs = list(rows)
    if not inputs:
        raise ValidationError("قائمة الليغاندات فارغة — لا شيء لتنقيته", "Empty ligand list")
    if len(inputs) > _MAX_INPUT_ROWS:
        raise ValidationError(
            f"عدد المدخلات {len(inputs)} يتجاوز السقف {_MAX_INPUT_ROWS}",
            f"Input count {len(inputs)} exceeds cap {_MAX_INPUT_ROWS}",
        )

    report = CurationReport()
    seen_keys: set[str] = set()

    for idx, item in enumerate(inputs, start=1):
        input_id = f"L{idx:04d}"
        try:
            mol = largest_fragment(parse_smiles(item.smiles))
            record = canonicalize(item.smiles)
        except InvalidSmiles as exc:
            report.rejected.append(
                Rejection(
                    input_id=input_id,
                    name=item.name,
                    smiles=item.smiles,
                    stage="validate",
                    reason_ar=f"SMILES غير صالح: {exc}",
                    reason_en=f"Invalid SMILES: {exc}",
                )
            )
            continue

        # ── إزالة التكرار ──
        dedupe_key = record.inchikey or record.canonical_smiles
        if dedupe_key in seen_keys:
            report.duplicates_removed += 1
            report.rejected.append(
                Rejection(
                    input_id=input_id,
                    name=item.name,
                    smiles=item.smiles,
                    stage="dedupe",
                    reason_ar="تكرار جزيئي (نفس InChIKey) — أول ظهور فقط يُفرز",
                    reason_en="Molecular duplicate (same InChIKey) — first occurrence wins",
                )
            )
            continue
        seen_keys.add(dedupe_key)

        # ── بوغة الرؤوس التساهمية (قرار السياسة) ──
        warheads = detect_warheads(mol)
        warhead_names = [w.name for w in warheads]
        risk = classify_warhead_risk(warheads)
        if policy.non_covalent_only and risk is not None:
            worst = next(w for w in warheads if w.category == risk)
            report.rejected.append(
                Rejection(
                    input_id=input_id,
                    name=item.name,
                    smiles=item.smiles,
                    stage="covalent_gate",
                    reason_ar=(
                        f"سياسة الهدف غير تساهمية: رأس تساهمي {worst.label_ar} "
                        f"— {policy.reason_ar}"
                    ),
                    reason_en=(
                        f"Target policy is non-covalent: warhead {worst.label_en} "
                        f"— {policy.reason_en}"
                    ),
                )
            )
            continue

        # ── PAINS ──
        alerts = pains_alerts(mol)
        if reject_pains and alerts:
            report.rejected.append(
                Rejection(
                    input_id=input_id,
                    name=item.name,
                    smiles=item.smiles,
                    stage="pains",
                    reason_ar=f"تنبيهات PAINS: {', '.join(alerts)}",
                    reason_en=f"PAINS alerts: {', '.join(alerts)}",
                )
            )
            continue

        # ── ناجٍ: بطاقة كيميائية كاملة ──
        report.kept.append(
            CuratedLigand(
                input_id=input_id,
                name=item.name,
                input_smiles=item.smiles.strip(),
                canonical_smiles=record.canonical_smiles,
                inchikey=record.inchikey,
                mol_weight=record.mol_weight,
                clogp=record.clogp,
                tpsa=record.tpsa,
                hbd=record.hbd,
                hba=record.hba,
                rotatable_bonds=record.rotatable_bonds,
                heavy_atoms=record.heavy_atoms,
                sa_score=sa_score(mol),
                pains_alerts=alerts,
                warhead_alerts=warhead_names,
                lipinski_flags=lipinski_flags(record),
                veber_flags=veber_flags(record),
            )
        )

    report.counts = {
        "input": len(inputs),
        "kept": len(report.kept),
        "rejected": len(report.rejected),
        "duplicates_removed": report.duplicates_removed,
    }
    return report
