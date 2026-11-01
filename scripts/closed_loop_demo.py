"""عرض الحلقة المغلقة الموثقة — «حلقة واحدة مغلقة» قبل بناء أي طبقات إضافية.

    فرضية ← تنفيذ ← تقييم ← ذاكرة ← جولة تالية تقرأ ما سبق

الاستخدام:
    python3 scripts/closed_loop_demo.py                    # سجل مؤقت يتيم الحذف
    python3 scripts/closed_loop_demo.py --db data/experiments.sqlite3
    python3 scripts/closed_loop_demo.py --rounds-summary   # قراءة الذاكرة فقط

الصدق: كل النتائج UNVALIDATED — الحلقة لا ترفع حالة أي نتيجة تلقائياً؛
الترقية عبر بوابة الاعتماد (pharma_sdl.validation) بشرية وموثقة حصراً.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from pharma_sdl.experiments.registry import ExperimentRegistry  # noqa: E402
from pharma_sdl.loop.closed_loop import format_lineage, run_closed_loop  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="الحلقة المغلقة الموثقة — Pharma SDL")
    ap.add_argument("--db", help="مسار سجل التجارب الدائم (افتراضي: ملف مؤقت)")
    ap.add_argument("--target", default="7VH8_A")
    ap.add_argument("--top", type=int, default=5)
    ap.add_argument("--rounds-summary", action="store_true", help="قراءة الذاكرة فقط دون تشغيل")
    args = ap.parse_args()

    if args.rounds_summary:
        db = Path(args.db or REPO_ROOT / "data" / "experiments.sqlite3")
        if not db.exists():
            print(f"لا سجل عند {db} — شغّل بدون --rounds-summary أولاً.")
            return 1
        registry = ExperimentRegistry(db)
        records = registry.latest(limit=1)
        if not records:
            print("السجل فارغ.")
            return 1
        print(format_lineage(registry, records[0].experiment_id))
        return 0

    if args.db:
        db_path: Path = Path(args.db)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        registry = ExperimentRegistry(db_path)
        records = run_closed_loop(db_path, target_id=args.target, top_n=args.top)
        lineage = format_lineage(registry, records[-1].experiment_id)
        persistent = True
    else:
        with tempfile.TemporaryDirectory() as td:
            tmp_db = Path(td) / "loop.sqlite3"
            registry = ExperimentRegistry(tmp_db)
            records = run_closed_loop(tmp_db, target_id=args.target, top_n=args.top)
            lineage = format_lineage(registry, records[-1].experiment_id)
        persistent = False

    print("════════ الحلقة المغلقة الموثقة ════════")
    print()
    for rec in records:
        role = rec.parameters.get("role", "?")
        best = rec.top_hits[0] if rec.top_hits else None
        print(f"جولة {rec.parameters.get('round')} — {role}  [{rec.experiment_id}]")
        print(f"  الفرضية: {rec.hypothesis_ar}")
        if best:
            print(f"  الأفضل: {best['name'] or best['smiles'][:40]} @ {best['kcal']:.2f} kcal/mol ({best['method']})")
        print(f"  الحالة: {rec.validation_state} · code {rec.code_version} · data {rec.data_version}")
        if rec.lesson:
            print(f"  الدرس: {rec.lesson}")
        print()
    print("سلسلة الذاكرة (السجل الدائم — تُقرأ كما كُتبت):")
    print(lineage)
    if not persistent:
        print("(ملف مؤقت — استخدم --db للاحتفاظ بالذاكرة)")
    print()
    print("✔ لا ترقية تلقائية: كل النتائج UNVALIDATED حتى مراجعة بشرية موثقة عبر بوابة الاعتماد.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
