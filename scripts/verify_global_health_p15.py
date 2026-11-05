#!/usr/bin/env python3
"""P15 — خطوة التحقق والتجميد الحي لتكامل الصحة العالمية (Ersilia: الملاريا والسل).

يُنتج: docs/audit/model-global-health-p15-results.json

يضم الملف:
- أدلة التحقق من مستودعات ersilia-os الرسمية (عقد المخرجات + الرخص + التواريخ)
- العبء العالمي WHO الموثّق لكل ممرض بمرجعه
- فحوص صدق اللوحة المرجعية (SMILES صالحة + أوزان جزيئية مطابقة للأدبيات)
- حالة النداء الحي لخادم Ersilia كما هي — غير متاح → تُجمَّد الحالة صادقة
  (`unavailable_offline`) ولا يُخترع رقم واحد (نمط P14 للطبقة الثالثة).

إعادة الإنتاج:
    python3 scripts/verify_global_health_p15.py
مع خادم محلي حي (اختياري):
    ersilia serve eos4zfy   # و/أو eos8d8a ثم أعد السكربت
"""
from __future__ import annotations

import json
import platform
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from core import global_health as gh
from core.clients import ersilia_client as ec

OUT = REPO / "docs" / "audit" / "model-global-health-p15-results.json"

# أدلة التحقق — من مستودعات ersilia-os الرسمية على GitHub (2026-11-05)
VERIFICATION_EVIDENCE = {
    "eos4zfy": {
        "title": "maip-malaria",
        "source": "https://github.com/ersilia-os/eos4zfy",
        "verified_at": "2026-11-05",
        "output_columns": [
            {
                "name": "maip_score",
                "type": "float",
                "direction": "high",
                "description": (
                    "Score of the antimalarial potential of small molecules "
                    "against the blood stage of Plasmodium falciparum"
                ),
            }
        ],
        "license": {"package": "GPL-3.0", "model": "MIT"},
        "provenance": "surrogate of MAIP (Bosc et al. 2021) — blood-stage antimalarial activity",
        "our_endpoint": "maip_score",
        "our_verdict_thresholds": {
            "MAIP_STRONG": ec.MAIP_STRONG,
            "MAIP_ACTIVE": ec.MAIP_ACTIVE,
            "note": "educational convention declared by us — the platform is best used for ranking",
        },
    },
    "eos8d8a": {
        "title": "Mycobacterium tuberculosis membrane permeability of drugs",
        "source": "https://github.com/ersilia-os/eos8d8a",
        "verified_at": "2026-11-05",
        "output_columns": [
            {
                "name": "mycpermcheck",
                "type": "float",
                "direction": "high",
                "description": "Probability of permeability in Mtb",
            }
        ],
        "license": {"package": "GPL-3.0", "model": "MIT"},
        "provenance": (
            "MycPermCheck — trained on compounds active against M.tb "
            "(MIC < 10 uM, MW < 500 Da)"
        ),
        "our_endpoint": "mtb_permeability_prob",
        "our_verdict_thresholds": {
            "PERM_GOOD": ec.PERM_GOOD,
            "PERM_BAD": ec.PERM_BAD,
            "note": "probability in [0,1]; grey zone declares generalization limits",
        },
    },
    "eos2ta5": {
        "title": "CardioToxNet-hERG",
        "source": "https://github.com/ersilia-os/eos2ta5",
        "verified_at": "2026-10-29 (original P5 verification)",
        "output_columns": [{"name": "score", "type": "float", "direction": "high"}],
        "license": {"package": "GPL-3.0", "model": "MIT"},
        "provenance": "hERG blockade probability (12,620 compounds)",
        "our_endpoint": "hERG_blockade_prob",
    },
    "eos6oli": {
        "title": "SolTranNet",
        "source": "https://github.com/ersilia-os/eos6oli",
        "verified_at": "2026-10-29 (original P5 verification)",
        "output_columns": [{"name": "value", "type": "float", "direction": "high"}],
        "license": {"package": "GPL-3.0", "model": "MIT"},
        "provenance": "aqueous solubility logS (AqSolDB)",
        "our_endpoint": "logS_mol_per_L",
    },
}


def validate_panel() -> list[dict]:
    """فحص صدق اللوحة: SMILES صالحة بالتحليل + الوزن مطابق للأدبيات (±0.5)."""
    try:
        from rdkit import Chem
        from rdkit.Chem import Descriptors
    except ImportError:
        return [
            {
                "check": "rdkit_available",
                "ok": False,
                "note": "RDKit missing — panel validation not executed here",
            }
        ]
    checks: list[dict] = []
    for label, smi in gh.GLOBAL_PRESETS.items():
        mol = Chem.MolFromSmiles(smi)
        mw = Descriptors.MolWt(mol) if mol is not None else None
        ref = gh.GLOBAL_PRESET_MW[smi]
        checks.append(
            {
                "label": label,
                "smiles": smi,
                "parses": mol is not None,
                "mw_computed": None if mw is None else round(mw, 2),
                "mw_reference": ref,
                "ok": mol is not None and abs(mw - ref) < 0.5,
            }
        )
    return checks


def try_live_panel() -> dict[str, dict]:
    """نداء حي صادق لكل ممرض — أي غياب يُسجَّل كما هو بلا قيم مختلقة."""
    out: dict[str, dict] = {}
    for pid, card in gh.PATHOGENS.items():
        rows = gh.assess_panel(pid)
        out[pid] = {
            "model_id": card.model_id,
            "status": (
                "live"
                if any(r.status == "live" for r in rows)
                else "unavailable_offline"
            ),
            "rows": [
                {
                    "smiles": r.smiles,
                    "value": r.value,
                    "status": r.status,
                    "verdict_ar": r.verdict_ar,
                    "verdict_en": r.verdict_en,
                }
                for r in rows
            ],
        }
    return out


def build_freeze() -> dict:
    """التجميد الكامل — أدلة + فحوص + حالة حية صادقة + بيئة القياس."""
    panel_checks = validate_panel()
    all_ok = bool(panel_checks) and all(c.get("ok") for c in panel_checks)
    live = try_live_panel()
    return {
        "phase": "P15 — global health integration (Ersilia: malaria + tuberculosis)",
        "frozen_at_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "protocol": {
            "client_contract": "POST {base}/run body=[{input: <smiles>}] — ersilia/serve/standard_api.py",
            "degradation": "network/server failure → None → status unavailable_offline (never fabricated)",
            "funnel": "stage1 pathogen score → stage2 ADMET gate (hERG + logS) → stage3 wet lab (MIC/PK-PD)",
        },
        "verification_evidence": VERIFICATION_EVIDENCE,
        "who_burden": {
            pid: {
                "cases": c.who_cases,
                "deaths": c.who_deaths,
                "year": c.who_year,
                "source_ar": c.who_source_ar,
                "source_en": c.who_source_en,
                "note_ar": c.burden_note_ar,
                "note_en": c.burden_note_en,
            }
            for pid, c in gh.PATHOGENS.items()
        },
        "panel_checks": {
            "tolerance_mw": 0.5,
            "all_pass": all_ok,
            "checks": panel_checks,
        },
        "live_status": live,
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "ersilia_base": ec.ERSILIA_BASE,
        },
    }


def main() -> int:
    freeze = build_freeze()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(freeze, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"فحوص اللوحة: {'كلها PASS' if freeze['panel_checks']['all_pass'] else 'فشل فحص — راجع الملف'}")
    for pid, ls in freeze["live_status"].items():
        n_live = sum(1 for r in ls["rows"] if r["status"] == "live")
        print(f"{pid} ({ls['model_id']}): {ls['status']} — {n_live}/{len(ls['rows'])} قيمة حية")
    print(f"التجميد: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
