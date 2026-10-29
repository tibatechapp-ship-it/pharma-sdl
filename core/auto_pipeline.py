"""خط القراءة التلقائية — زر واحد من البذرة إلى التقرير (S8).

يجمع ما بُني في S5–S7 في خط واحد بلا أي مفتاح:
  مكتبة حول البذرة (PubChem حي → BRICS محلي احتياطاً)
  → فلتر ADME محلي (RDKit: Lipinski+Veber+hERG المحاكى)
  → ربط Vina (محركنا الدائم)
  → تقييم المحلل الداخلي للبوزات (S7-a — صنعناه)
  → فلتر ADMET خارجي اختياري (Ersilia إن توفّر خادم، وإلا المحلي)
  → أعلام PGx صادقة (لا اختراع أرقام) + تقرير PDF عربي (Tajawal)

القواعد الثابتة: أي فشل شبكة/خادم → fallback فوري للمحلي، والقمع يوثّق
ما استُخدم فعلاً. الملف نفسه بلا streamlit — دوال نقية قابلة للاختبار.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from core.contacts import PoseContacts, score_poses
from core.docking import ReceptorInfo, dock_ligand
from core.expander import expand_library

HAS_RDKIT = True
try:
    from rdkit import Chem
    from rdkit.Chem import Crippen, Descriptors, Lipinski, rdMolDescriptors
except ImportError:  # pragma: no cover - بيئة CI كاملة لديها rdkit
    HAS_RDKIT = False

# عتبة علم hERG المحاكى (core.oracle): IC50 < 10 µM = حاجب — قيمة القاعدة نفسها
HERG_FLAG_UM = 10.0


@dataclass
class AutoReport:
    """مخرجات الخط الآلي — كل ما يلزم للعرض والتقرير."""

    seed: str
    receptor_id: str
    source: str                       # pubchem | brics | none
    library: list[str]
    funnel: dict[str, int]
    results: list[dict]               # صفوف: smiles/vina/inhouse/hbonds/clashes
    admet_engine: str                 # ersilia | local | none
    admet_passed: int
    pgx_flags: list[str]
    best_smiles: str
    best_vina: float | None = None
    best_inhouse: float | None = None
    report_pdf: bytes | None = None


# ─────────────────────────────────────────────────────────────
# وصف الجزيء محلياً — بلا شبكة
# ─────────────────────────────────────────────────────────────

def mol_descriptors(smiles: str) -> tuple[float, float, int, int, float, int] | None:
    """(MW, LogP, HBD, HBA, TPSA, RotB) — None عند SMILES غير صالح."""
    if not HAS_RDKIT:
        return None
    mol = Chem.MolFromSmiles(smiles.strip()) if smiles.strip() else None
    if mol is None:
        return None
    return (
        float(Descriptors.MolWt(mol)),
        float(Crippen.MolLogP(mol)),
        int(Lipinski.NumHDonors(mol)),
        int(Lipinski.NumHAcceptors(mol)),
        float(rdMolDescriptors.CalcTPSA(mol)),
        int(Lipinski.NumRotatableBonds(mol)),
    )


def local_admet_verdict(smiles: str, oracle=None) -> tuple[bool, list[str]]:
    """حكم ADMET محلي صادق: Lipinski+Veber عبر RDKit + علم hERG من محاكاتنا.

    يُرجع (اجتاز؟, أعلام). الأعلام نصوص صريحة لا أرقام اختراعية — وhERG هنا
    محاكاة تعليمية (core.oracle) موسومة كذلك، لا تنبؤ حقيقي.
    """
    desc = mol_descriptors(smiles)
    if desc is None:
        return False, ["SMILES غير صالح"]
    mw, logp, hbd, hba, tpsa, rotb = desc
    flags: list[str] = []
    ok = True
    if mw > 500.0:
        flags.append(f"MW {mw:.0f} > 500 (Lipinski)")
        ok = False
    if logp > 5.0:
        flags.append(f"LogP {logp:.1f} > 5 (Lipinski)")
        ok = False
    if hbd > 5 or hba > 10:
        flags.append(f"HBD/HBA {hbd}/{hba} خارج الحد (5/10)")
        ok = False
    if tpsa > 140.0 or rotb > 10:
        flags.append(f"TPSA {tpsa:.0f}/روتاتمر {rotb} خارج Veber")
        ok = False
    if oracle is not None:
        try:
            herg = float(oracle.herg_toxicity(np.array([mw, logp, hbd, hba, tpsa, rotb])))
            if herg < HERG_FLAG_UM:
                flags.append(f"محاكاة hERG: {herg:.1f} µM < {HERG_FLAG_UM:.0f} — خطر محتمل")
                ok = False
            else:
                flags.append(f"محاكاة hERG: {herg:.1f} µM — مقبول تعليمياً")
        except Exception as exc:  # noqa: BLE001 — المحاكاة إضافية لا تعطّل الحكم
            print(f"hERG oracle skipped: {exc}")
    return ok, flags


# ─────────────────────────────────────────────────────────────
# فلتر ADMET الخارجي — Ersilia إن توفّر خادم، وإلا المحلي
# ─────────────────────────────────────────────────────────────

def _ersilia_pass(model_id: str, smiles_list: list[str]) -> dict[str, bool] | None:
    """حكم كل جزيء من Ersilia — None عند غياب الخادم (fallback للمحلي).

    hERG (eos2ta5): نجاز إذا ليست «خطر مرتفع» · logS (eos6oli): نجاز إذا ليست «ضعيف».
    """
    from core.clients.ersilia_client import predict_admet_batch

    rows = predict_admet_batch(smiles_list, model_id)
    if not rows:
        return None
    out: dict[str, bool] = {}
    for r in rows:
        bad = ("مرتفع" in r.verdict_ar) or ("ضعيف" in r.verdict_ar)
        out[r.smiles] = not bad
    return out


# ─────────────────────────────────────────────────────────────
# الخط الآلي نفسه
# ─────────────────────────────────────────────────────────────

def run_auto_pipeline(
    seed_smiles: str,
    receptor: ReceptorInfo,
    n_library: int = 8,
    dock_top: int = 3,
    n_poses: int = 3,
    exhaustiveness: int = 4,
    expand_mode: str = "auto",
    admet_model: str | None = None,
    use_ersilia: bool = True,
    model=None,
) -> AutoReport:
    """زر واحد: مكتبة → ADME → Vina → المحلل الداخلي → ADMET → أعلام → PDF.

    model: نموذج potency اختياري (نفس واجهة capstone) لتقرير PDF موحّد —
    غيابه لا يعطّل الخط؛ التقرير يُبنى فقط إن توفر.
    """
    seed = seed_smiles.strip()
    if not seed:
        raise ValueError("البذرة فارغة — أدخل SMILES صالحاً")

    # 1) المكتبة — حياً ثم محلياً (المصدر يُعلَن بصراحة)
    analogues, src = expand_library(seed, n=int(n_library), mode=expand_mode)
    library = [seed] + [s for s in analogues if s != seed]

    # 2) فلتر ADME محلي (يوفّر وقت Vina ويوثّق القمع)
    survivors: list[str] = []
    for smi in library:
        ok, _flags = local_admet_verdict(smi)
        if ok:
            survivors.append(smi)

    # 3) ربط Vina — حتى dock_top جزيء، فشل التجهيز يُحتسب ولا يُوقف الخط
    dock_rows: list[dict] = []
    dock_failures = 0
    for smi in survivors[: max(1, int(dock_top))]:
        try:
            res = dock_ligand(
                smi, receptor, n_poses=int(n_poses), exhaustiveness=int(exhaustiveness)
            )
        except Exception:  # noqa: BLE001 — جزيء فاشل لا يُسقط الخط كله
            dock_failures += 1
            continue
        dock_rows.append(
            {
                "smiles": smi,
                "vina": res.best,
                "energies": res.energies,
                "poses": res.poses_pdbqt,
            }
        )

    # 4) المحلل الداخلي — على أفضل بوز لكل جزيء
    poses = [r["poses"][0] for r in dock_rows]
    contacts: list[PoseContacts] = []
    if poses:
        try:
            contacts = score_poses(receptor.receptor_file_path, poses)
        except (ValueError, FileNotFoundError):
            contacts = []
    for row, pc in zip(dock_rows, contacts):
        row["inhouse"] = pc.score
        row["hbonds"] = pc.n_hbonds
        row["clashes"] = pc.n_clashes

    # 5) فلتر ADMET — Ersilia إن استجاب خادمها، وإلا المحلي
    admet_engine = "none"
    admet_passed = 0
    if dock_rows:
        smiles_docked = [r["smiles"] for r in dock_rows]
        verdicts: dict[str, bool] | None = None
        if use_ersilia and admet_model:
            try:
                verdicts = _ersilia_pass(admet_model, smiles_docked)
            except Exception:  # noqa: BLE001 — أي فشل خارجي → محلي
                verdicts = None
            if verdicts is not None:
                admet_engine = "ersilia"
        if verdicts is None:
            from core.oracle import MultiObjectiveOracle

            oracle = MultiObjectiveOracle(seed=42)
            verdicts = {}
            for smi in smiles_docked:
                ok, _flags = local_admet_verdict(smi, oracle=oracle)
                verdicts[smi] = ok
            admet_engine = "local"
        for r in dock_rows:
            r["admet_ok"] = verdicts.get(r["smiles"], False)
        admet_passed = sum(1 for r in dock_rows if r["admet_ok"])

    # 6) الأفضل — أدنى طاقة Vina بين المُربوطين (ADMET يُعرض، لا يُحذف)
    best_row = min(dock_rows, key=lambda r: r["vina"] if r["vina"] is not None else 0.0) \
        if dock_rows else None
    best_smiles = best_row["smiles"] if best_row else ""
    best_vina = best_row["vina"] if best_row else None
    best_inhouse = best_row.get("inhouse") if best_row else None

    # 7) أعلام PGx صادقة — محاكاة/إحالات، بلا أرقام اختراعية
    pgx_flags: list[str] = []
    if best_row:
        ok, flags = local_admet_verdict(best_row["smiles"])
        pgx_flags = list(flags)
    pgx_flags.append(
        "أيض المركّب غير مُقاس هنا — راجع CYP2D6/CYP2C19 في تبويب PGx قبل أي استنتاج"
    )

    funnel: dict[str, int] = {
        "المكتبة": len(library),
        "ADME المحلي": len(survivors),
        "أُربط بـVina": len(dock_rows),
        "اجتاز ADMET": admet_passed,
    }
    if dock_failures:
        funnel["فشل تجهيزه"] = dock_failures

    # 8) التقرير — يعيد استخدام قمع capstone وPDF العربي (Tajawal)
    report_pdf: bytes | None = None
    if best_row is not None:
        try:
            from core.capstone import build_pdf_report, score_potency

            if model is None:
                from core.capstone import _default_model

                model = _default_model()
            # pkpd_outlook يحتاج mw مع pic50 — نملأ الوصف إن توفر RDKit
            desc_rows = []
            for r in dock_rows:
                desc = mol_descriptors(r["smiles"])
                desc_rows.append(
                    {"smiles": r["smiles"], "mw": desc[0] if desc else 400.0}
                )
            ranked = score_potency(pd.DataFrame(desc_rows), model)
            from core.capstone import PipelineResult

            pres = PipelineResult(
                funnel=funnel,
                ranked=ranked,
                dose_mg=300.0,
                source=f"قراءة تلقائية ({'PubChem' if src == 'pubchem' else 'BRICS'})",
            )
            report_pdf = build_pdf_report(
                pres, target_name=f"SARS-CoV-2 Mpro ({receptor.pdb_id})"
            )
        except Exception:  # noqa: BLE001 — التقرير إضافي لا يُسقط الخط
            report_pdf = None

    return AutoReport(
        seed=seed,
        receptor_id=receptor.id,
        source=src,
        library=library,
        funnel=funnel,
        results=dock_rows,
        admet_engine=admet_engine,
        admet_passed=admet_passed,
        pgx_flags=pgx_flags,
        best_smiles=best_smiles,
        best_vina=best_vina,
        best_inhouse=best_inhouse,
        report_pdf=report_pdf,
    )
