#!/usr/bin/env python3
"""P13 — قياس حي مجمّد لعميل ADMET-AI على لوحة أدوية مرجعية موثّقة.

يعمل محلياً بلا شبكة (النماذج مضمّنة في حزمة admet-ai) ويُنتج:
    docs/audit/model-admet-ai-p13-results.json

يضم الملف: كتالوج المهام الـ41 + 3 إنذارات + 8 وصفات، نتائج اللوحة الكاملة
(قيم + مئينات DrugBank)، فحوص صدق على مرجعيات فيزيائية معروفة، وبيئة القياس.
"""
from __future__ import annotations

import json
import platform
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from core.clients import admet_ai_client as ai

OUT = REPO / "docs" / "audit" / "model-admet-ai-p13-results.json"

# لوحة مرجعية — كل جزيء بخصائص موثّقة من الأدبيات لفحص الصدق
PANEL: dict[str, dict] = {
    "aspirin": {
        "smiles": "CC(=O)Oc1ccccc1C(=O)O",
        "note_ar": "مسكن كلاسيكي — مرجعية فيزيائية معروفة",
        "anchors": {"molecular_weight": 180.16, "logP": 1.31, "tpsa": 63.6},
    },
    "paracetamol": {
        "smiles": "CC(=O)NC1=CC=C(C=C1)O",
        "note_ar": "تحلل حي بـ CYP — مرجعية توافر جيد",
        "anchors": {"molecular_weight": 151.16},
    },
    "metformin": {
        "smiles": "CN(C)C(=N)N=C(N)N",
        "note_ar": "ثنائي غوانيد شديد القطبية — امتصاص معوي منخفض متوقع",
        "anchors": {"molecular_weight": 129.16, "tpsa": 91.49},
    },
    "terfenadine": {
        "smiles": (
            "CC(C)(C)C1=CC=C(C=C1)C(CCCN2CCC(CC2)C(C3=CC=CC=C3)"
            "(C4=CC=CC=C4)O)O"
        ),
        "note_ar": "سُحب 1997/1998 بسبب إطالة QT عبر hERG — مرجعية خطر القلب",
        "anchors": {"molecular_weight": 471.67},
    },
    "warfarin": {
        "smiles": "CC(=O)CC(c1ccccc1)c1c(O)c2ccccc2oc1=O",
        "note_ar": "ارتباط شبه كامل ببروتينات البلازما (~99%) — مرجعية PPBR",
        "anchors": {"molecular_weight": 308.33},
    },
    "itraconazole": {
        "smiles": (
            "CCC(C)N1C(=O)N(C=N1)C2=CC=C(C=C2)N3CCN(CC3)C4=CC=C(C=C4)"
            "OCC5COC(O5)(CN6C=NC=N6)C7=C(C=C(C=C7)Cl)Cl"
        ),
        "note_ar": "عملياً غير ذائب — مرجعية ذوبان ضعيف ومثبط CYP3A4 قوي",
        "anchors": {"molecular_weight": 705.63},
    },
}


def main() -> int:
    if not ai.is_available():
        print("admet-ai غير متاح في هذه البيئة — لا تجميد بلا قياس حقيقي.")
        return 1

    model_pkg = _pkg_version("admet_ai") or "؟"
    torch_pkg = _pkg_version("torch") or "؟"
    chemprop_pkg = _pkg_version("chemprop") or "؟"
    rdkit_pkg = _pkg_version("rdkit") or "؟"
    print(
        f"admet-ai {model_pkg} · torch {torch_pkg} · chemprop {chemprop_pkg} "
        f"· rdkit {rdkit_pkg}"
    )

    names = list(PANEL)
    smiles = [PANEL[n]["smiles"] for n in names]
    print(f"predicting {len(smiles)} molecules × all outputs …", flush=True)
    results = ai.predict_admet_ai_batch(smiles)
    if not results:
        print("فشل الاستدلال — لا تجميد.")
        return 1
    print(f"got {len(results)} result rows", flush=True)

    # فحوص الصدق — مرجعيات فيزيائية لا تسامح فيها
    anchors_report: dict[str, dict] = {}
    all_ok = True
    for name, spec in PANEL.items():
        row = next((r for r in results if r.smiles == spec["smiles"]), None)
        checks = {}
        for task_id, expected in spec["anchors"].items():
            got = row.get(task_id) if row else None
            ok = got is not None and abs(got - expected) <= max(0.5, 0.02 * expected)
            checks[task_id] = {"expected": expected, "measured": got, "ok": ok}
            all_ok = all_ok and ok
            if not ok:
                print(f"  anchor FAIL: {name}.{task_id} expected={expected} measured={got}")
        anchors_report[name] = checks
    print("sanity anchors:", "PASS" if all_ok else "FAIL", flush=True)

    # حجب نموذج إضافي: تيرفينادين يجب أن يظهر خطر hERG أعلى من الأسبرين
    asp = next(r for r in results if r.smiles == PANEL["aspirin"]["smiles"])
    ter = next(r for r in results if r.smiles == PANEL["terfenadine"]["smiles"])
    asp_herg, ter_herg = asp.get("hERG"), ter.get("hERG")
    herg_ok = (
        asp_herg is not None
        and ter_herg is not None
        and ter_herg > asp_herg
    )
    print(
        f"pharmacology anchor (terfenadine hERG={ter_herg} > aspirin hERG={asp_herg}): "
        f"{'PASS' if herg_ok else 'FAIL'}"
    )

    catalog = {
        t.task_id: {
            "name_ar": t.name_ar,
            "name_en": t.name_en,
            "unit_ar": t.unit_ar,
            "unit_en": t.unit_en,
            "kind": t.kind,
            "family_ar": t.family_ar,
            "family_en": t.family_en,
        }
        for t in ai.TASKS.values()
    }

    panel_out = {}
    for name, spec in PANEL.items():
        row = next((r for r in results if r.smiles == spec["smiles"]), None)
        if row is None:
            panel_out[name] = {"smiles": spec["smiles"], "measured": False}
            continue
        panel_out[name] = {
            "smiles": spec["smiles"],
            "note_ar": spec["note_ar"],
            "values": {k: round(v, 4) for k, v in sorted(row.values.items())},
            "percentiles_drugbank": {
                k: round(v, 2) for k, v in sorted(row.percentiles.items())
            },
            "verdicts_curated": {
                tid: ai.verdict(tid, row.get(tid), lang="ar")
                for tid in ("hERG", "AMES", "DILI", "ClinTox", "Carcinogens_Lagunin",
                            "BBB_Martins", "Bioavailability_Ma", "HIA_Hou",
                            "Solubility_AqSolDB")
                if row.get(tid) is not None
            },
        }

    payload = {
        "phase": "P13",
        "title": "قياس حي مجمّد — عميل ADMET-AI على لوحة أدوية مرجعية",
        "measured_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "admet_ai": model_pkg,
            "torch": torch_pkg,
            "chemprop": chemprop_pkg,
            "rdkit": rdkit_pkg,
            "rdkit_note": (
                "إصدار rdkit هنا كما حلّته سلسلة تبعيات admet-ai الاختيارية "
                "(cuik_molmaker مرتبط ببناء rdkit المحدد) — ليس إصدار تثبيت "
                "المشروع الأساسي المثبَّت في pyproject."
            ),
            "device": "cpu",
        },
        "task_catalog": catalog,
        "counts": {
            "ml_tasks": ai.N_ML_TASKS,
            "structural_alerts": len(ai._ALERT_TASKS),
            "physchem": len(ai._PHYSCHEM_TASKS),
            "total_output_columns": len(ai.TASKS),
        },
        "panel": panel_out,
        "sanity_anchors": anchors_report,
        "sanity_anchors_all_ok": all_ok,
        "pharmacology_anchor_herg": {
            "description": "تيرفينادين (مسحوب بسبب hERG) > أسبرين في احتمال الحجب",
            "aspirin_hERG": asp.get("hERG"),
            "terfenadine_hERG": ter.get("hERG"),
            "ok": herg_ok,
        },
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1))
    print(f"frozen -> {OUT}")

    # ملخّص قابل للطباعة في التقرير
    print("\n== ملخّص اللوحة (قيم مختارة) ==")
    hdr = ["molecule", "hERG", "AMES", "DILI", "Solubility", "PPBR%", "BBB"]
    print("  ".join(f"{h:>12s}" for h in hdr))
    for name in names:
        row = next((r for r in results if r.smiles == PANEL[name]["smiles"]), None)
        if row is None:
            continue
        vals = [
            name,
            _fmt(row.get("hERG")),
            _fmt(row.get("AMES")),
            _fmt(row.get("DILI")),
            _fmt(row.get("Solubility_AqSolDB")),
            _fmt(row.get("PPBR_AZ")),
            _fmt(row.get("BBB_Martins")),
        ]
        print("  ".join(f"{v:>12s}" for v in vals))

    return 0 if (all_ok and herg_ok) else 2


def _fmt(v: float | None) -> str:
    return "—" if v is None else f"{v:.3f}"


def _pkg_version(mod_name: str) -> str | None:
    try:
        from importlib.metadata import version

        return version(mod_name)
    except Exception:  # noqa: BLE001
        return None


if __name__ == "__main__":
    raise SystemExit(main())
