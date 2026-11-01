"""جناح إعادة الربط — تشغيل مستقل يوثق النتائج في docs/audit (P2).

الاستخدام:
    python scripts/redocking_suite.py                    # الأهداف كلها (ex=8)
    python scripts/redocking_suite.py --exhaustiveness 4 # أسرع للتجارب المحلية
    python scripts/redocking_suite.py --out custom.json  # مسار ناتج مختلف

الناتج: جدول نصي + JSON (docs/audit/redocking-results.json) يلتزم في
المستودع — أرقام RMSD/ΔΔG حقيقية ضد بلورات RCSB، لا ادعاءات بلا قياس.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from pharma_sdl.engines.redocking import (
    RedockingResult,
    has_redocking_stack,
    redock_reference,
    targets_with_references,
)

DEFAULT_OUT = REPO / "docs" / "audit" / "redocking-results.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="جناح إعادة الربط — قبول هندسي صادق")
    parser.add_argument("--exhaustiveness", type=int, default=8)
    parser.add_argument("--n-poses", type=int, default=9)
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--targets", nargs="*", help="معرّفات محددة (افتراضي: كل المراجع)")
    args = parser.parse_args(argv)

    if not has_redocking_stack():
        print("⛔ vina/meeko غير متاحين — الجناح لا يعمل بلا ربط فعلي (بلا ادعاء).")
        return 1
    target_ids = args.targets or [t["id"] for t in targets_with_references()]
    if not target_ids:
        print("⛔ لا مراجع بلورية — شغّل: python scripts/fetch_reference_ligands.py")
        return 1

    results: list[RedockingResult] = []
    print(f"جناح إعادة الربط — {len(target_ids)} هدف (exhaustiveness={args.exhaustiveness})\n")
    for target_id in target_ids:
        print(f"▶ {target_id} ...", flush=True)
        res = redock_reference(
            target_id, exhaustiveness=args.exhaustiveness, n_poses=args.n_poses
        )
        results.append(res)
        status = "✅ مقبول" if res.accepted else "⛔ مرفوض"
        print(
            f"  {status} — best={res.best_kcal:.2f} kcal | RMSD={res.rmsd_best:.2f} Å "
            f"(top3={res.rmsd_top3:.2f}) | |ΔΔG|={res.ddg_error:.2f} kcal"
        )
        for failure in res.failures:
            print(f"    ⚠ {failure}")
        print()

    all_ok = all(r.accepted for r in results)
    print("الخلاصة:", "القبول الهندسي ناجح لكل الأهداف ✅" if all_ok else "فشل قبول هدف واحد على الأقل ⛔")

    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "acceptance": {"rmsd_max_angstrom": 2.0, "ddg_max_kcal": 2.5},
        "all_accepted": all_ok,
        "results": [asdict(r) for r in results],
    }
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"حُفظت النتائج: {out_path.relative_to(REPO)}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
