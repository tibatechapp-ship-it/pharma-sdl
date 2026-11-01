"""منسّق الفرز الظاهري — «الهيكل الهزّ» القابل للتشغيل من نقطة واحدة.

    مدخلات خام → تنقية (سياسة الهدف) → تسجيل بالمحرك → ترتيب → نتيجة موقّعة

كل جولة تحمل: مَن سجّل (engine_used)، هل حدث سقوط مُعلَن (fallback_note)،
كم رُفض ولماذا (rejected)، وكم استغرق الأمر (elapsed_seconds).
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Iterable

from pharma_sdl.curation.pipeline import run_curation
from pharma_sdl.engines.registry import get_engine
from pharma_sdl.errors import ScreeningError
from pharma_sdl.experiments.registry import code_version, ligands_fingerprint
from pharma_sdl.models import LigandInput, ScoredHit, ScreeningResult
from pharma_sdl.targets.registry import get_target
from pharma_sdl.validation.gate import default_card


def run_screening(
    target_id: str,
    ligands: Iterable[LigandInput],
    engine_name: str | None = None,
    top_n: int = 10,
    reject_pains: bool = False,
) -> ScreeningResult:
    """جولة فرز كاملة end-to-end — من SMILES خام إلى قائمة مرشحين مرتّبة."""
    started = time.perf_counter()
    target = get_target(target_id)
    engine, fallback_note = get_engine(engine_name)

    items = list(ligands)
    report = run_curation(items, target.policy, reject_pains=reject_pains)

    hits: list[ScoredHit] = []
    failures: list[str] = []
    for lig in report.kept:
        try:
            from rdkit import Chem

            mol = Chem.MolFromSmiles(lig.canonical_smiles)
            if mol is None:  # pragma: no cover — قادم من canonicalize صالح
                raise ScreeningError("فشل إعادة بناء الجزيء", "Molecule rebuild failed")
            score = engine.score(lig.canonical_smiles, target)
        except Exception as exc:  # noqa: BLE001 — خطأ جزيء واحد لا يُسقط الجولة
            failures.append(f"{lig.input_id} ({lig.name or lig.canonical_smiles[:40]}): {exc}")
            continue
        hits.append(
            ScoredHit(
                rank=0,  # يُعيَّن بعد الترتيب
                input_id=lig.input_id,
                name=lig.name,
                canonical_smiles=lig.canonical_smiles,
                inchikey=lig.inchikey,
                docking_kcal=score.kcal,
                method=score.method,
                mol_weight=lig.mol_weight,
                clogp=lig.clogp,
                tpsa=lig.tpsa,
                pains_alerts=lig.pains_alerts,
                warhead_alerts=lig.warhead_alerts,
                lipinski_flags=lig.lipinski_flags,
            )
        )

    hits.sort(key=lambda h: h.docking_kcal)
    top = top_n if top_n and top_n > 0 else len(hits)
    ranked = hits[:top]
    for i, hit in enumerate(ranked, start=1):
        hit.rank = i

    warnings = [f"فشل تسجيل: {f}" for f in failures]
    if fallback_note:
        warnings.append(fallback_note)
    if engine.name == "simulation":
        warnings.append(
            "درجات هذه الجولة من محرك المحاكاة الحتمي (تطوير/عرض) — ليست فيزياء ولا تنبؤاً."
        )

    elapsed = round(time.perf_counter() - started, 3)
    run_id = uuid.uuid4().hex[:12]
    # بوابة الاعتماد (تدقيق P1): كل جولة تولد UNVALIDATED — بطاقة تُحمل
    # مع النتيجة في الـAPI والتقارير؛ الترقية بشرية صريحة حصراً.
    validation = default_card(
        subject=f"screening_run:{run_id}",
        result_id=run_id,
        engine=engine.name,
        method=ranked[0].method if ranked else None,
        data_version=ligands_fingerprint([l.canonical_smiles for l in report.kept]),
        code_version=code_version(),
        limits=(
            "درجات التحام/تنبؤات حاسوبية — لا تثبت فعالية أو سلامة؛ "
            "الترقية تتطلب أدلة تجريبية موثقة عبر بوابة الاعتماد."
        ),
    )
    return ScreeningResult(
        run_id=run_id,
        target_id=target.id,
        target_label_ar=target.label_ar,
        target_label_en=target.label_en,
        engine_requested=engine_name or "default",
        engine_used=engine.name,
        fallback_note=fallback_note,
        validation=validation,
        counts={
            "input": report.counts.get("input", len(items)),
            "kept": report.counts.get("kept", 0),
            "rejected": report.counts.get("rejected", 0),
            "duplicates_removed": report.counts.get("duplicates_removed", 0),
            "scored": len(hits),
            "failed": len(failures),
            "returned": len(ranked),
        },
        hits=ranked,
        rejected=report.rejected,
        warnings=warnings,
        elapsed_seconds=elapsed,
    )
