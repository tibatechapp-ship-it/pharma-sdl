#!/usr/bin/env python3
"""التجميد الحي — P14: اللوحة ثلاثية الطبقات على أمثلة مرجعية (خطة التطوير P14).

المعيار: جدول مقارنة ثلاثي منشور على مثالين على الأقل — نيرماتريلڤير و
PF-00835231 (الليغاند المشتبك في 7VH8 نفسه) مقابل Mpro:

- الطبقة 1: النموذج الافتراضي المعتمد v0.12.0 (بصمة تكرارات + RF mf=0.3)
- الطبقة 2: Vina على المستقبل الجاهز 7VH8_A → جسر Cheng-Prusoff العكسي
- الطبقة 3: بيان Boltz-2 المجمّد من دفتر Lab08 (Colab GPU) إن وُجد —
  وإلا فحالة «unavailable_offline» صادقة تُنشر كما هي (لا قيم مختلقة).

المراسِ التجريبية: سجلات ChEMBL حقيقية (استعلام 2026-11-04) — كل سجل
بمعرّف اختباره، ولمرجل نيرماتريلڤير يُتّبع قاعدة «وسيط سجلات IC50
الإنزيمية» المعلنة. لا يُجمَّد شيء بلا قياس حقيقي.

المخرجات: docs/audit/model-three-tier-p14-results.json
الإعادة:  python3 scripts/evaluate_three_tier_p14.py [--boltz-manifest PATH]
"""
from __future__ import annotations

import argparse
import json
import math
import platform
import statistics
import sys
import time
from pathlib import Path

import rdkit
import sklearn

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from rdkit import Chem, DataStructs, RDLogger
from rdkit.Chem import AllChem

from core.clients.boltz2_client import MANIFEST_SCHEMA, Boltz2Client
from core.docking import HAS_MEEKO, HAS_VINA
from core.ml_potency import train_default_model
from core.three_tier import TierPanelEntry, build_panel

RDLogger.DisableLog("rdApp.*")

DEFAULT_MANIFEST = REPO / "data" / "boltz2" / "lab08-manifest.json"
OUT_JSON = REPO / "docs" / "audit" / "model-three-tier-p14-results.json"
TARGET_CHEMBL = "CHEMBL4523582"  # نفس هدف بيانات التدريب (P0/P11)

# ── المرجع التجريبي: سجلات ChEMBL حقيقية (استعلام حي 2026-11-04) ──
CHEMBL_RECORDS = {
    "nirmatrelvir": {
        "molecule_chembl_id": "CHEMBL4802135",
        "rule": "وسيط سجلات IC50 الإنزيمية على CHEMBL4523582 — قاعدة معلنة",
        "ic50_nm_records": [
            {"assay_chembl_id": "CHEMBL5106611", "value_nm": 75.0},
            {"assay_chembl_id": "CHEMBL5112747", "value_nm": 0.79},
            {"assay_chembl_id": "CHEMBL5118373", "value_nm": 66.0},
            {"assay_chembl_id": "CHEMBL5142713", "value_nm": 31.0},
            {"assay_chembl_id": "CHEMBL5145885", "value_nm": 11.2},
        ],
        "ki_context_nm": [
            {"assay_chembl_id": "CHEMBL5140442", "value_nm": 3.0},
            {"assay_chembl_id": "CHEMBL5140699", "value_nm": 3.11},
        ],
    },
    "pf00835231": {
        "molecule_chembl_id": "CHEMBL4777223",
        "rule": "سجل IC50 واحد مباشر على CHEMBL4523582",
        "ic50_nm_records": [
            {"assay_chembl_id": "CHEMBL4810314", "value_nm": 8.0},
        ],
        "ki_context_nm": [],
    },
}


def anchor_from_records(key: str) -> dict:
    """بناء المرجع التجريبي من سجلات ChEMBL — بوسيط معلن لا قيمة مفبركة."""
    spec = CHEMBL_RECORDS[key]
    values = [rec["value_nm"] for rec in spec["ic50_nm_records"]]
    median_nm = statistics.median(values)
    return {
        "molecule_chembl_id": spec["molecule_chembl_id"],
        "target_chembl_id": TARGET_CHEMBL,
        "rule": spec["rule"],
        "ic50_nm": median_nm,
        "pic50": round(-math.log10(median_nm * 1e-9), 2),
        "ic50_spread_nm": [min(values), max(values)],
        "records": spec["ic50_nm_records"],
        "ki_context": spec["ki_context_nm"],
        "queried_at": "2026-11-04",
        "source": "ChEMBL REST API (www.ebi.ac.uk/chembl)",
    }


PANEL = [
    TierPanelEntry(
        smiles=(
            "CC(C)(C)[C@H](NC(=O)[C@H](CC(C)C)NC(=O)[C@H](CC1=CN=CS1)"
            "NC(=O)C(F)(F)F)C(=O)N1CC[C@@H](C1)C#N"
        ),
        name_ar="نيرماتريلڤير (PF-07321332)",
        name_en="Nirmatrelvir (Paxlovid)",
        anchor=anchor_from_records("nirmatrelvir"),
    ),
    TierPanelEntry(
        smiles=(
            "NC(=N)N[C@@H]1[C@H]2CC[C@@H](CN2C1=O)NC(=O)[C@@H](NC(=O)"
            "[C@@H](NC(=O)C(F)(F)F)CC2CCCCC2)C(C)C"
        ),
        name_ar="PF-00835231 (الليغاند المشتبك في 7VH8)",
        name_en="PF-00835231 (7VH8 co-crystal ligand)",
        anchor=anchor_from_records("pf00835231"),
    ),
]


def nearest_tanimoto(smiles: str) -> tuple[float, str]:
    """أقرب جار في بيانات التدريب — إفصاح «خارج العينة» بالأرقام."""
    query = Chem.MolFromSmiles(smiles)
    query_fp = AllChem.GetMorganFingerprintAsBitVect(query, 2, nBits=2048)
    import pandas as pd

    df = pd.read_csv(REPO / "data" / "mpro_sample.csv")
    best_sim, best_row = 0.0, ""
    for s in df["smiles"]:
        mol = Chem.MolFromSmiles(s)
        if mol is None:
            continue
        fp = AllChem.GetMorganFingerprintAsBitVect(mol, 2, nBits=2048)
        sim = DataStructs.TanimotoSimilarity(query_fp, fp)
        if sim > best_sim:
            best_sim, best_row = sim, s
    return round(best_sim, 3), best_row


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--boltz-manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
        help="مسار بيان Boltz-2 المجمّد (افتراضيًا data/boltz2/lab08-manifest.json)",
    )
    args = parser.parse_args()

    t0 = time.time()
    print("── P14: اللوحة ثلاثية الطبقات (ML ← Vina ← Boltz-2) ──")

    # الطبقة 1: النموذج الافتراضي المعتمد (بذرة ثابتة)
    model = train_default_model(random_state=42)
    print("[1/3] نموذج ML v0.12.0 مدرَّب (n=900، بذرة 42)")

    # الطبقة 3: بيان Boltz-2 إن وُجد
    client = Boltz2Client.load(args.boltz_manifest)
    if client is None:
        print(f"[3/3] بيان Boltz-2 غائب أو غير صالح: {args.boltz_manifest} → حالة صادقة")
        boltz_status = "unavailable_offline"
    else:
        print(f"[3/3] بيان Boltz-2 محمّل: {len(client._records)} قراءة، نموذج {client.meta.model_version}")
        boltz_status = client.status

    # إفصاح خارج العينة + بناء اللوحة
    entries: list[TierPanelEntry] = []
    for entry in PANEL:
        sim, row = nearest_tanimoto(entry.smiles)
        entry.nearest_train_tanimoto = sim
        entries.append(entry)
        print(f"    {entry.name_en}: أقرب جار تدريب Tanimoto={sim} → خارج العينة")

    print("[2/3] طبقة Vina تعمل الآن (7VH8_A، exhaustiveness=8، بذرة 42) …")
    rows = build_panel(entries, model, client)
    print(f"    اكتملت اللوحة: {len(rows)} صفوف")

    results = {
        "schema": "pharma-sdl.three-tier-p14.v1",
        "protocol": {
            "date_utc": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()),
            "target": {
                "chembl_id": TARGET_CHEMBL,
                "pdb_reference": "7VH8",
                "receptor_id": "7VH8_A",
                "self_dock_reference_kcal": -8.28,
            },
            "tiers": {
                "tier1": "ML — train_default_model() v0.12.0 (Morgan counts 2048 r=2, RF 300, max_features=0.3, seed 42)",
                "tier2": "Vina — dock_ligand() على 7VH8_A (exhaustiveness=8, random_seed=42) → pIC50 عبر Cheng-Prusoff العكسي (ΔG=−1.3642·pIC50)",
                "tier3": "Boltz-2 — بيان مجمّد من labs/lab08_boltz2_co_folding.ipynb (Colab GPU) عبر core/clients/boltz2_client.py",
            },
            "agreement_bands": "≤1.0 اتفاق كمّي · 1–2 اتفاق تقريبي · >2 تعارض (pIC50)",
            "anchor_rule": "سجلات ChEMBL حقيقية بمعرّفاتها — وسيط IC50 الإنزيمية لمرجل متعدد السجلات",
            "boltz_manifest": {
                "path": str(args.boltz_manifest.relative_to(REPO)) if str(args.boltz_manifest).startswith(str(REPO)) else str(args.boltz_manifest),
                "schema": MANIFEST_SCHEMA,
                "status": boltz_status,
            },
        },
        "environment": {
            "python": platform.python_version(),
            "rdkit": rdkit.__version__,
            "sklearn": sklearn.__version__,
            "vina_available": HAS_VINA,
            "meeko_available": HAS_MEEKO,
            "platform": platform.platform(),
        },
        "rows": rows,
        "lesson": {
            "trust_rules_ar": {
                "tier1_ml": "ترتيب آلاف المرشحين داخل السلالة — لا قيم مطلقة خارجها (قياس P12 الخارجي)",
                "tier2_vina": "موضع الربط وطاقة خشنة، بمرجع إعادة ربط ذاتي −8.28 kcal/mol",
                "tier3_boltz2": "الحكم المرجعي على العشرات الناجية — بنية + قرابة في ~20 ثانية GPU (MIT)",
                "funnel_rule": "الآلاف ← المئات ← العشرات ← التجربة؛ كل طبقة تسبق أغلى منها ولا تتجاوز حكمها",
            },
        },
        "runtime_seconds": round(time.time() - t0, 1),
    }

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"→ المجمّد: {OUT_JSON}")

    # طباعة الجدول العربي للمراجعة البشرية
    print("\n── الجدول ──")
    for row in rows:
        ml, vina, boltz = row["tier1_ml"], row["tier2_vina"], row["tier3_boltz2"]
        anchor = row["anchor"]
        print(f"\n● {row['name_en']} — المرجع: IC50 {anchor['ic50_nm']} nM (pIC50 {anchor['pic50']})")
        print(f"  طبقة1 ML   : pIC50 {ml['pic50']} (CI {ml['ci95'][0]}–{ml['ci95'][1]})")
        if vina.get("status") == "ok":
            print(f"  طبقة2 Vina : ΔG {vina['dg_kcal']} kcal/mol → pIC50 {vina['pic50']}")
        b = boltz or {}
        print(f"  طبقة3 Boltz: {b.get('status', 'غير متاح offline')}"
              + (f" → pIC50 {b['pic50']}" if b.get("status") == "ok" else ""))
        for tier, verdict in row["agreement_vs_anchor"].items():
            print(f"  {tier} مقابل المرجع: {verdict}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
