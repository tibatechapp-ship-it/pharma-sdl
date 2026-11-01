"""الحلقة المغلقة — الفلسفة منفَّذة: فرضية ← تنفيذ ← تقييم ← ذاكرة ← جولة تالية.

هذه هي «الحلقة الواحدة المغلقة» من خطة التدقيق: المنظومة تستقبل سؤالاً
علمياً، تنفذ التجربة الحاسوبية ضمن حدود آمنة (محرك حتمي للتطوير)، تسجل
الإعدادات والنتائج في سجل دائم، ثم **تقرأ سجل الجولة السابقة قبل أن
تقرر التالية** — تبدأ من حيث انتهت، لا من الصفر.

الصدق بنيوياً:
    - كل تجربة تبدأ UNVALIDATED — الحلقة لا ترفع حالة أي نتيجة تلقائياً أبداً
      (الترقية عبر pharma_sdl.validation.promote بشرية وموثقة حصراً).
    - محرك المحاكاة الحتمي يُستخدم للعرض والتطوير — method="simulation"
      ظاهر في كل نتيجة، فلا يمكن خلطه بفيزياء حقيقية.
    - ثلاث أدوار للجولات: exploit (خط أساس) → explore (استكشاف ما لم يُختبر)
      → exploit (توظيف ما تعلمناه) — كل دور له فرضية معلنة.
"""

from __future__ import annotations

import time
from pathlib import Path

from rdkit import Chem

from pharma_sdl.curation.loader import load_ligands_csv
from pharma_sdl.errors import ScreeningError
from pharma_sdl.experiments.registry import (
    ExperimentRecord,
    ExperimentRegistry,
    code_version,
    ligands_fingerprint,
)
from pharma_sdl.models import LigandInput
from pharma_sdl.screening.runner import run_screening
from pharma_sdl.validation.gate import ValidationState

DEMO_CSV = Path(__file__).resolve().parent.parent.parent / "data" / "demo_ligands.csv"


def _canonical(smiles: str) -> str | None:
    mol = Chem.MolFromSmiles(smiles)
    return Chem.MolToSmiles(mol) if mol is not None else None


def _record_base(
    *,
    hypothesis_ar: str,
    hypothesis_en: str,
    question: str,
    role: str,
    target_id: str,
    parent_id: str | None,
    smiles_pool: list[str],
    parameters: dict,
) -> ExperimentRecord:
    return ExperimentRecord(
        hypothesis_ar=hypothesis_ar,
        hypothesis_en=hypothesis_en,
        question=question,
        target_id=target_id,
        data_version=ligands_fingerprint(smiles_pool),
        code_version=code_version(),
        parameters={"role": role, "pool_size": len(smiles_pool), **parameters},
        parent_experiment_id=parent_id,
    )


def _screen_and_complete(
    registry: ExperimentRegistry,
    record: ExperimentRecord,
    ligands: list[LigandInput],
    target_id: str,
    engine_name: str | None,
    top_n: int,
) -> ExperimentRecord:
    started = time.perf_counter()
    try:
        result = run_screening(
            target_id=target_id, ligands=ligands, engine_name=engine_name, top_n=top_n
        )
    except Exception as exc:
        registry.fail(record.experiment_id, error=f"{type(exc).__name__}: {exc}")
        raise ScreeningError(
            f"فشلت جولة الحلقة ({record.parameters.get('role')}): {exc}",
            f"Closed-loop round failed ({record.parameters.get('role')}): {exc}",
        ) from exc
    elapsed = round(time.perf_counter() - started, 3)
    rows = [
        {
            "rank": h.rank,
            "name": h.name,
            "smiles": h.canonical_smiles,
            "inchikey": h.inchikey,
            "kcal": h.docking_kcal,
            "method": h.method,
        }
        for h in result.hits[:top_n]
    ]
    return registry.complete(
        record.experiment_id,
        counts=result.counts,
        top_hits=rows,
        warnings=result.warnings,
        elapsed_seconds=elapsed,
        engine_used=result.engine_used,
        method=result.hits[0].method if result.hits else None,
    )


def run_closed_loop(
    db_path: str | Path,
    target_id: str = "7VH8_A",
    ligands_csv: str | Path | None = None,
    top_n: int = 5,
    engine_name: str | None = None,
) -> list[ExperimentRecord]:
    """حلقة واحدة مغلقة بثلاث جولات — كل جولة تقرأ ذاكرة سابقتها.

    الجولة 1 (exploit): فرز المكتبة كاملة — خط الأساس، أفضل top_n.
    الجولة 2 (explore): استبعاد مرشحي الجولة 1 (من الذاكرة!) وتجريب البقية.
    الجولة 3 (exploit): توظيف التعلم — إعادة فرز دمج الأفضل من الجولتين.

    تُرجع السجلات بترتيب الجولات؛ سلسلة parent_experiment_id تكتب القصة.
    """
    registry = ExperimentRegistry(db_path)
    csv_path = Path(ligands_csv) if ligands_csv else DEMO_CSV
    all_ligands = load_ligands_csv(csv_path)
    all_smiles = [l.smiles for l in all_ligands]

    # ── الجولة 1: خط الأساس ──────────────────────────────────
    r1 = _record_base(
        hypothesis_ar="أفضل مرشحي المكتبة عبر خط الفرز الحالي هم نقطة الانطلاق المعتدة.",
        hypothesis_en="Current pipeline top candidates are the trusted starting set.",
        question="ما ترتيب المكتبة كاملة وفق خط الفرز الحالي؟",
        role="exploit_baseline",
        target_id=target_id,
        parent_id=None,
        smiles_pool=all_smiles,
        parameters={"round": 1, "top_n": top_n},
    )
    registry.begin(r1)
    r1 = _screen_and_complete(
        registry, r1, all_ligands, target_id, engine_name, top_n=top_n
    )
    r1 = registry.complete(
        r1.experiment_id,
        counts=r1.counts,
        top_hits=r1.top_hits,
        warnings=r1.warnings,
        elapsed_seconds=r1.elapsed_seconds,
        engine_used=r1.engine_used,
        method=r1.method,
        lesson=(
            f"خط الأساس: أفضل {len(r1.top_hits)} مرشح موثق أعلاه — "
            "درجات محرك التطوير الحتمي (ليست فيزياء)؛ الحالة UNVALIDATED بلا ترقية تلقائية."
        ),
    )

    # ── الجولة 2: استكشاف — تقرأ الذاكرة وتستبعد ما اختُبر ────
    tested = {h["smiles"] for h in r1.top_hits}
    explore_pool = [
        l for l in all_ligands if _canonical(l.smiles) not in tested
    ]
    r2 = _record_base(
        hypothesis_ar="ما لم يُختبر في الجولة الأولى قد يحمل بدائل أفضل — الذاكرة تمنع إعادة العمل.",
        hypothesis_en="Untested molecules may hold better alternatives — memory avoids rework.",
        question="هل يوجد مرشح أفضل خارج قائمة الجولة الأولى؟",
        role="explore",
        target_id=target_id,
        parent_id=r1.experiment_id,
        smiles_pool=[l.smiles for l in explore_pool],
        parameters={"round": 2, "excluded_from_round1": len(r1.top_hits)},
    )
    registry.begin(r2)
    r2 = _screen_and_complete(
        registry, r2, explore_pool, target_id, engine_name, top_n=top_n
    )
    best1 = r1.top_hits[0]["kcal"] if r1.top_hits else None
    best2 = r2.top_hits[0]["kcal"] if r2.top_hits else None
    verdict2 = (
        "لا مرشح أفضل خارج قائمة الجولة 1 — الفرضية لم تُدعم في هذه المكتبة."
        if best1 is not None and best2 is not None and best2 > best1
        else "وُجد مرشح خارجي يضاهي أو يتفوق على خط الأساس — الفرضية مدعومة."
    )
    r2 = registry.complete(
        r2.experiment_id,
        counts=r2.counts,
        top_hits=r2.top_hits,
        warnings=r2.warnings,
        elapsed_seconds=r2.elapsed_seconds,
        engine_used=r2.engine_used,
        method=r2.method,
        lesson=verdict2,
    )

    # ── الجولة 3: توظيف — أفضل ما تعلمناه من السجل كاملاً ────
    pool_smiles = [h["smiles"] for h in (r1.top_hits + r2.top_hits)]
    combined = [LigandInput(name=h["name"], smiles=h["smiles"]) for h in (r1.top_hits + r2.top_hits)]
    r3 = _record_base(
        hypothesis_ar="دمج أفضل الجولتين وإعادة ترتيبهما يعطي القائمة النهائية الأقوى.",
        hypothesis_en="Re-ranking the union of both rounds yields the strongest final list.",
        question="ما القائمة النهائية بعد توظيف كل الأدلة؟",
        role="exploit_final",
        target_id=target_id,
        parent_id=r2.experiment_id,
        smiles_pool=pool_smiles,
        parameters={"round": 3, "union_of": [r1.experiment_id, r2.experiment_id]},
    )
    registry.begin(r3)
    r3 = _screen_and_complete(
        registry, r3, combined, target_id, engine_name, top_n=top_n
    )
    r3 = registry.complete(
        r3.experiment_id,
        counts=r3.counts,
        top_hits=r3.top_hits,
        warnings=r3.warnings,
        elapsed_seconds=r3.elapsed_seconds,
        engine_used=r3.engine_used,
        method=r3.method,
        lesson=(
            "القائمة النهائية موثقة أعلاه — الخطوة التالية المعلنة: "
            "فحص تجريبي تأكيدي قبل أي ترقية لحالة الاعتماد (لا ترقية آلية)."
        ),
    )

    return [r1, r2, r3]


def format_lineage(registry: ExperimentRegistry, last_id: str, lang: str = "ar") -> str:
    """سرد سلسلة الحلقة من السجل — إثبات أن الذاكرة تُقرأ كما كُتبت."""
    chain = registry.lineage(last_id)
    lines = []
    for i, rec in enumerate(chain, 1):
        role = rec.parameters.get("role", "?")
        best = rec.top_hits[0] if rec.top_hits else None
        best_txt = f"{best['name'] or best['smiles'][:24]} @ {best['kcal']:.2f}" if best else "—"
        if lang == "en":
            lines.append(
                f"{i}. [{rec.experiment_id}] {role} — best: {best_txt} — "
                f"{rec.validation_state} — {rec.lesson or ''}"
            )
        else:
            lines.append(
                f"{i}. [{rec.experiment_id}] {role} — الأفضل: {best_txt} — "
                f"{rec.validation_state} — {rec.lesson or ''}"
            )
    return "\n".join(lines)


__all__ = [
    "DEMO_CSV",
    "ValidationState",
    "format_lineage",
    "run_closed_loop",
]
