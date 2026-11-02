#!/usr/bin/env python3
"""قياس جودة نماذج الأهداف الثلاثة ونشر الأرشيف — مصدر الحقيقة الوحيد.

السكربت الذي تعِد به وثائق P7/ADR-0012 (وكان مفقوداً من الشجرة رغم
ذكره في رسالة الالتزام — فجوة أصلحها P9): يقيس كل هدف من `TARGETS`
ببروتوكول الصدق المعلن (scaffold مزدوج بلا تسريب، معمارية الإنتاج
حرفياً) ويكتب `data/tibb-quality.json` — الأرقام تُقاس مرة واحدة
وتُنشر أرشيفاً، والـAPI يقرأها كما هي بلا حساب حي.

الاستخدام:
    python scripts/measure_tibb_quality.py               # 300 شجرة، بذرة 0
    python scripts/measure_tibb_quality.py --n-estimators 100   # تجربة سريعة
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from pharma_sdl.experiments.registry import code_version
from pharma_sdl.quality import (
    NOTE_AR,
    NOTE_EN,
    QUALITY_ARTIFACT,
    TARGETS,
    measure_target_quality,
)

_SPLIT_LABEL = "bemis-murcko scaffold x2 (test ثم fit/calib)"
_FEATURIZER_LABEL = "active_learning.featurize (Morgan 2048) — نفس الإنتاج"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="قياس ونشر مقاييس جودة الأهداف")
    parser.add_argument("--n-estimators", type=int, default=300)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args(argv)

    targets: list[dict] = []
    for tid in sorted(TARGETS):
        q = measure_target_quality(
            tid, n_estimators=args.n_estimators, seed=args.seed
        )
        targets.append(q.model_dump())
        print(
            f"{tid}: R2={q.r2:.3f} MAE={q.mae:.3f} "
            f"coverage {q.nominal_coverage:.2f}->{q.measured_coverage:.3f} "
            f"(n_test={q.n_test}, code={q.code_version})"
        )

    first = targets[0]
    artifact = {
        "protocol": {
            "n_estimators": first["n_estimators"],
            "seed": first["seed"],
            "test_size": first["test_size"],
            "calib_size": first["calib_size"],
            "alpha": first["alpha"],
            "split": _SPLIT_LABEL,
            "featurizer": _FEATURIZER_LABEL,
        },
        "note_ar": NOTE_AR,
        "note_en": NOTE_EN,
        "measured_on": date.today().isoformat(),
        "code_version": code_version(),
        "targets": targets,
    }
    QUALITY_ARTIFACT.write_text(
        json.dumps(artifact, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    print(f"archived -> {QUALITY_ARTIFACT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
