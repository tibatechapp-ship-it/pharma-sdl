"""واجهة سطر الأوامر — المنصة بلا متصفح: engines/targets/screen/assay/serve.

أمثلة:
    pharma-sdl engines
    pharma-sdl targets
    pharma-sdl screen --target 7VH8_A --ligands data/demo_ligands.csv --top 10
    pharma-sdl assay --smiles "O=C(N)c1ccccc1" --dg -8.2
    pharma-sdl serve --port 8000
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pharma_sdl import __version__
from pharma_sdl.config import get_settings


def _cmd_engines(_args: argparse.Namespace) -> int:
    from pharma_sdl.engines.registry import list_engines

    print(f"محركات Pharma SDL v{__version__}:")
    for e in list_engines():
        state = "✅ متاح" if e.available else "⛔ غير متاح"
        print(f"  - {e.name:<12} [{e.kind}] {e.label} — {state}")
        if e.note_ar:
            print(f"      {e.note_ar}")
    return 0


def _cmd_targets(_args: argparse.Namespace) -> int:
    from pharma_sdl.targets.registry import list_targets

    print("الأهداف الجاهزة:")
    for t in list_targets():
        policy = "غير تساهمي حصراً" if t.policy.non_covalent_only else "مفتوح"
        print(f"  - {t.id:<8} {t.label_ar}")
        print(f"      الصندوق: center={t.center} size={t.box_size} — السياسة: {policy}")
        if t.self_dock_reference_kcal is not None:
            print(f"      مرجع self-dock: {t.self_dock_reference_kcal} kcal/mol")
    return 0


def _cmd_screen(args: argparse.Namespace) -> int:
    from pharma_sdl.curation.loader import load_ligands_csv
    from pharma_sdl.models import LigandInput
    from pharma_sdl.reporting.report import build_json, build_markdown
    from pharma_sdl.screening.runner import run_screening

    if args.ligands:
        ligands = load_ligands_csv(args.ligands)
    else:
        ligands = [
            LigandInput(name="demo", smiles="O=C(N)c1ccccc1"),
        ]
    result = run_screening(
        target_id=args.target,
        ligands=ligands,
        engine_name=args.engine,
        top_n=args.top,
        reject_pains=args.reject_pains,
    )
    print(f"الجولة {result.run_id} — {result.target_label_ar}")
    print(f"المحرك: {result.engine_used} | العدّادات: {result.counts}")
    print()
    print(f"{'#':>3}  {'ΔG kcal/mol':>11}  الاسم")
    for h in result.hits:
        print(f"{h.rank:>3}  {h.docking_kcal:>11.2f}  {h.name or h.canonical_smiles[:40]}")
    if result.rejected:
        print(f"\nمرفوضون في التنقية: {len(result.rejected)} — الأسباب في التقرير.")
    if args.out:
        out_path = Path(args.out)
        out_path.write_text(build_json(result), encoding="utf-8")
        out_path.with_suffix(".md").write_text(
            build_markdown(result, lang=args.lang), encoding="utf-8"
        )
        print(f"\nحُفظ التقرير: {out_path} (+ .md)")
    return 0


def _cmd_assay(args: argparse.Namespace) -> int:
    from pharma_sdl.lab.simulation import SimulatedFretLab

    result = SimulatedFretLab().run_assay(
        type("Req", (), {"smiles": args.smiles, "dg_kcal": args.dg})()
    )
    print(json.dumps(result.model_dump(), ensure_ascii=False, indent=2))
    return 0


def _cmd_loop(args: argparse.Namespace) -> int:
    """الحلقة المغلقة — فرضية ← تنفيذ ← تقييم ← ذاكرة ← جولة تالية."""
    from pharma_sdl.experiments.registry import ExperimentRegistry
    from pharma_sdl.loop.closed_loop import format_lineage, run_closed_loop

    records = run_closed_loop(
        db_path=args.db,
        target_id=args.target,
        ligands_csv=args.ligands,
        top_n=args.top,
    )
    registry = ExperimentRegistry(args.db)
    print(f"اكتملت الحلقة — {len(records)} تجارب موثقة في {args.db}")
    for rec in records:
        role = rec.parameters.get("role", "?")
        best = rec.top_hits[0] if rec.top_hits else None
        best_txt = (
            f"{best['name'] or best['smiles'][:24]} @ {best['kcal']:.2f} kcal/mol"
            if best
            else "—"
        )
        print(f"  [{rec.experiment_id}] {role:<16} {best_txt} — {rec.validation_state}")
    print()
    print("سلسلة الذاكرة (كما ستُقرأ في الجولة التالية):")
    print(format_lineage(registry, records[-1].experiment_id))
    print()
    print("لا ترقية تلقائية — كل النتائج UNVALIDATED حتى مراجعة بشرية موثقة.")
    return 0


def _cmd_experiments(args: argparse.Namespace) -> int:
    """عرض أحدث التجارب من السجل الدائم — الذاكرة التجريبية."""
    from pharma_sdl.experiments.registry import ExperimentRegistry

    registry = ExperimentRegistry(args.db)
    records = registry.latest(limit=args.limit)
    if not records:
        print("السجل فارغ — شغّل: pharma-sdl loop")
        return 0
    stats = registry.stats()
    print(f"السجل: {args.db} — {sum(stats.values())} تجربة {stats}")
    for rec in records:
        best = rec.top_hits[0] if rec.top_hits else None
        best_txt = (
            f"{best['name'] or best['smiles'][:24]} @ {best['kcal']:.2f}"
            if best
            else (rec.error or "—")
        )
        print(
            f"  [{rec.experiment_id}] {rec.status:<9} {rec.target_id or '—':<8} "
            f"{rec.engine_used or '—':<12} {best_txt}"
        )
        print(f"      الفرضية: {rec.hypothesis_ar[:80]}")
        if rec.lesson:
            print(f"      الدرس: {rec.lesson[:90]}")
    return 0


def _cmd_export_experiments(args: argparse.Namespace) -> int:
    """تصدير السجل التجريبي إلى JSONL — طريق الترقية إلى PostgreSQL (ADR-0007)."""
    from pharma_sdl.experiments.portability import export_jsonl
    from pharma_sdl.experiments.registry import ExperimentRegistry

    registry = ExperimentRegistry(args.db)
    count = export_jsonl(registry, args.out)
    print(f"صُدّرت {count} تجربة إلى {args.out}")
    print("الخطوة التالية: psql -f deploy/postgres/schema.sql ثم الاستيراد")
    return 0


def _cmd_import_experiments(args: argparse.Namespace) -> int:
    """استيراد تجارب من JSONL — المعرّفات وسلاسل الأسلاف محفوظة حرفياً."""
    from pharma_sdl.experiments.portability import import_jsonl
    from pharma_sdl.experiments.registry import ExperimentRegistry

    registry = ExperimentRegistry(args.db)
    count = import_jsonl(registry, args.input, overwrite=args.overwrite)
    print(f"استُوردت {count} تجربة إلى {args.db}")
    return 0


def _cmd_serve(args: argparse.Namespace) -> int:
    try:
        import uvicorn
    except ImportError:
        print("uvicorn غير متاح — ثبّته: pip install uvicorn", file=sys.stderr)
        return 1
    uvicorn.run(
        "pharma_sdl.api.app:create_app",
        factory=True,
        host=args.host,
        port=args.port,
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pharma-sdl",
        description=f"Pharma SDL Platform CLI v{__version__} — منصة اكتشاف الأدوية API-First",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("engines", help="عرض المحركات وحالتها").set_defaults(func=_cmd_engines)
    sub.add_parser("targets", help="عرض الأهداف وسياساتها").set_defaults(func=_cmd_targets)

    p_screen = sub.add_parser("screen", help="جولة فرز كاملة من سطر الأوامر")
    p_screen.add_argument("--target", default="7VH8_A", help="معرّف الهدف (افتراضي 7VH8_A)")
    p_screen.add_argument("--ligands", help="ملف CSV بعمود smiles")
    p_screen.add_argument("--engine", default="simulation", help="simulation | vina | boltz2")
    p_screen.add_argument("--top", type=int, default=10, help="عدد المرشحين")
    p_screen.add_argument("--reject-pains", action="store_true", help="رفض PAINS بدل التوثيق")
    p_screen.add_argument("--out", help="حفظ JSON (+ .md) في هذا المسار")
    p_screen.add_argument("--lang", default="ar", choices=["ar", "en"], help="لغة التقرير")
    p_screen.set_defaults(func=_cmd_screen)

    p_assay = sub.add_parser("assay", help="فحص FRET محاكى لجزيء واحد")
    p_assay.add_argument("--smiles", required=True)
    p_assay.add_argument("--dg", type=float, required=True, help="ΔG kcal/mol من جولة الفرز")
    p_assay.set_defaults(func=_cmd_assay)

    p_loop = sub.add_parser(
        "loop",
        help="الحلقة المغلقة الموثقة: فرضية ← تنفيذ ← تقييم ← ذاكرة ← جولة تالية",
    )
    p_loop.add_argument("--db", default=str(get_settings().experiments_db), help="مسار سجل التجارب")
    p_loop.add_argument("--target", default="7VH8_A")
    p_loop.add_argument("--ligands", help="CSV البليغاندات (افتراضي مكتبة العرض)")
    p_loop.add_argument("--top", type=int, default=5)
    p_loop.set_defaults(func=_cmd_loop)

    p_exp = sub.add_parser("experiments", help="عرض أحدث التجارب من السجل الدائم")
    p_exp.add_argument("--db", default=str(get_settings().experiments_db), help="مسار سجل التجارب")
    p_exp.add_argument("--limit", type=int, default=10)
    p_exp.set_defaults(func=_cmd_experiments)

    p_export = sub.add_parser(
        "export-experiments", help="تصدير السجل التجريبي إلى JSONL (طريق PostgreSQL)"
    )
    p_export.add_argument("--db", default=str(get_settings().experiments_db))
    p_export.add_argument("--out", required=True, help="ملف JSONL الهدف")
    p_export.set_defaults(func=_cmd_export_experiments)

    p_import = sub.add_parser(
        "import-experiments", help="استيراد تجارب من JSONL — المعرّفات محفوظة"
    )
    p_import.add_argument("--db", default=str(get_settings().experiments_db))
    p_import.add_argument("--in", dest="input", required=True, help="ملف JSONL المصدر")
    p_import.add_argument(
        "--overwrite", action="store_true", help="الكتابة فوق المكرر (الافتراضي: التخطي)"
    )
    p_import.set_defaults(func=_cmd_import_experiments)

    p_serve = sub.add_parser("serve", help="تشغيل بوابة الـAPI")
    p_serve.add_argument("--host", default="0.0.0.0")
    p_serve.add_argument("--port", type=int, default=8000)
    p_serve.set_defaults(func=_cmd_serve)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args) or 0)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
