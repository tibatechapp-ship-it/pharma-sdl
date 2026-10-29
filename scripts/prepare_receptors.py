#!/usr/bin/env python3
"""تجهيز مستقبلات Docking (PDBQT) من RCSB — Mpro 7VH8 و PLpro 7CMD.

سلسلة التجهيز (teaching-grade):
  1. تنزيل PDB من RCSB.
  2. استخراج سلسلة البروتين (ATOM، سلسلة A) — بلا ماء أو هيتاتم.
  3. استخراج الليغاند المشتبك (HETATM) وحساب مركز صندوق الربط منه.
  4. تحويل الليغاند إلى SMILES (مثال جاهز للاستخدام في التطبيق).
  5. إضافة هيدروجينات (obabel -h) ثم تحويل للمستقبل الصلب (obabel -xr → PDBQT).
  6. تحقق: self-dock للليغاند المشتبك في موقعه الأصلي (يجب أن يكون الناتج سالباً بوضوح).
  7. حفظ data/receptors/*.pdbqt + receptors.json (ميتاداتا عربي/إنجليزي).

التشغيل: python scripts/prepare_receptors.py
يعتمد على: requests, openbabel-wheel (CLI obabel), vina, meeko, rdkit.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import requests

REPO = Path(__file__).resolve().parent.parent
OUT_DIR = REPO / "data" / "receptors"

RCSB = "https://files.rcsb.org/download/{pdb_id}.pdb"

# (pdb_id, ligand_resname, chain, أسماء عربي/إنجليزي، ملاحظة تعليمية عربية)
# ملاحظة: أسماء الليغاندات بعد إصلاح RCSB — 4WI = PF-00835231 (مركّب نيرماتريلڤير الأصلي)،
# TTT = 5-amino-2-methyl-N-(1-naphthalen-1-ylethyl)benzamide — مثبط بنزاميد مشتبك في PLpro.
TARGETS = [
    {
        "pdb_id": "7VH8",
        "ligand_resname": "4WI",
        "chain": "A",
        "name_ar": "البروتييز الرئيسي لسارس-كوف-2 (Mpro)",
        "name_en": "SARS-CoV-2 Main Protease (Mpro)",
        "note_ar": "نفس هدف نموذج Predict وCapstone — الليغاند المشتبك PF-00835231 هو المركّب الأصلي لنيرماتريلڤير.",
    },
    {
        "pdb_id": "7CMD",
        "ligand_resname": "TTT",
        "chain": "A",
        "name_ar": "البروتييز الشبيه بالبابايين (PLpro)",
        "name_en": "SARS-CoV-2 Papain-like Protease (PLpro)",
        "note_ar": "إنزيم ثانٍ من نفس الفيروس — مثبط بنزاميد-نافثيل مشتبك في جيب التشكل النشط.",
    },
]

BOX_PADDING = 9.0   # هامش حول امتداد الليغاند في كل بُعد
BOX_MIN = 18.0
BOX_MAX = 26.0


def ligand_box(coords: list[tuple[float, float, float]]) -> tuple[float, float, float]:
    """صندوق تكيفي: امتداد الليغاند + هامش، مقصوص على [18, 26] أنغستروم."""
    size = []
    for i in range(3):
        extent = max(c[i] for c in coords) - min(c[i] for c in coords)
        size.append(round(min(max(extent + BOX_PADDING, BOX_MIN), BOX_MAX), 1))
    return tuple(size)  # type: ignore[return-value]


def fetch_pdb(pdb_id: str) -> str:
    r = requests.get(RCSB.format(pdb_id=pdb_id), timeout=60)
    r.raise_for_status()
    return r.text


def split_receptor_ligand(pdb_text: str, lig_res: str, chain: str):
    """يفصل ATOM (بروتين السلسلة) عن HETATM (الليغاند) ويرجع إحداثيات الليغاند."""
    rec_lines: list[str] = []
    lig_lines: list[str] = []
    for line in pdb_text.splitlines():
        if line.startswith("ATOM") and len(line) > 21 and line[21] == chain:
            alt = line[16] if len(line) > 16 else " "
            if alt not in (" ", "A"):
                continue  # نُبقي المطابق الأول فقط
            rec_lines.append(line)
        elif line.startswith("HETATM") and len(line) > 21 and line[21] == chain:
            res = line[17:20].strip()
            if res == lig_res:
                lig_lines.append(line)
    return rec_lines, lig_lines


def coords_from_lines(lines: list[str]) -> list[tuple[float, float, float]]:
    return [
        (float(l[30:38]), float(l[38:46]), float(l[46:54]))
        for l in lines
        if len(l) >= 54
    ]


def obabel(*args: str) -> str:
    """تشغيل obabel وإرجاع النص الناتج (يرمي عند فشل)."""
    cmd = ["obabel", *args]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"obabel فشل: {' '.join(cmd)}\n{proc.stderr}")
    return proc.stdout


def run_target(t: dict, tmp: Path) -> dict:
    pdb_id, lig_res, chain = t["pdb_id"], t["ligand_resname"], t["chain"]
    print(f"\n══ {pdb_id} — {t['name_en']} ══")
    pdb_text = fetch_pdb(pdb_id)

    rec_lines, lig_lines = split_receptor_ligand(pdb_text, lig_res, chain)
    assert len(rec_lines) > 1500, f"{pdb_id}: بروتين قصير جداً ({len(rec_lines)})"
    assert len(lig_lines) >= 8, f"{pdb_id}: لم يُعثر على ليغاند {lig_res}"
    print(f"بروتين: {len(rec_lines)} ذرة — ليغاند: {len(lig_lines)} ذرة")

    # 1) المستقبل الخام
    rec_pdb = tmp / f"{pdb_id}_raw.pdb"
    rec_pdb.write_text("\n".join(rec_lines) + "\nEND\n")

    # 2) الليغاند → SMILES (بإضافة H)
    lig_pdb = tmp / f"{pdb_id}_{lig_res}.pdb"
    lig_pdb.write_text("\n".join(lig_lines) + "\nEND\n")
    lig_sdf = tmp / f"{pdb_id}_{lig_res}.sdf"
    obabel(str(lig_pdb), "-O", str(lig_sdf), "-h")
    import rdkit
    from rdkit import Chem

    mol = next(iter(Chem.SDMolSupplier(str(lig_sdf), removeHs=False)), None)
    assert mol is not None, f"{pdb_id}: RDKit لم يقرأ الليغاند من SDF"
    smiles = Chem.MolToSmiles(Chem.RemoveHs(mol))
    print(f"SMILES المشتبك: {smiles}")

    # 3) المستقبل: H إضافي ثم PDBQT صلب
    rec_h = tmp / f"{pdb_id}_h.pdb"
    rec_pdbqt = OUT_DIR / f"{pdb_id}_{chain}.pdbqt"
    obabel(str(rec_pdb), "-O", str(rec_h), "-h")
    obabel(str(rec_h), "-O", str(rec_pdbqt), "-xr")
    n_atoms = sum(1 for l in rec_pdbqt.read_text().splitlines() if l.startswith(("ATOM", "HETATM")))
    n_hd = sum(1 for l in rec_pdbqt.read_text().splitlines() if l[77:79].strip() == "HD")
    print(f"PDBQT: {n_atoms} ذرة (منها {n_hd} هيدروجين قطبي HD)")
    assert n_atoms > 1500 and n_hd > 100, f"{pdb_id}: مخرجات PDBQT غير متوقعة"

    # 4) صندوق الربط من مركز الليغاند وامتداده
    cs = coords_from_lines(lig_lines)
    cx = sum(c[0] for c in cs) / len(cs)
    cy = sum(c[1] for c in cs) / len(cs)
    cz = sum(c[2] for c in cs) / len(cs)
    box = ligand_box(cs)
    print(f"مركز الصندوق: ({cx:.2f}, {cy:.2f}, {cz:.2f}) — حجم {box}")

    # 5) تحقق: self-dock
    from meeko import MoleculePreparation, PDBQTWriterLegacy
    from rdkit.Chem import AllChem
    from vina import Vina

    mol_h = Chem.AddHs(Chem.MolFromSmiles(smiles))
    AllChem.EmbedMolecule(mol_h, randomSeed=42)
    setup = MoleculePreparation()(mol_h)[0]
    lig_pdbqt_str, ok, _err = PDBQTWriterLegacy.write_string(setup)
    assert ok and lig_pdbqt_str

    v = Vina(sf_name="vina")
    v.set_receptor(str(rec_pdbqt))
    v.compute_vina_maps(center=[cx, cy, cz], box_size=list(box))
    v.set_ligand_from_string(lig_pdbqt_str)
    v.dock(exhaustiveness=8, n_poses=3)
    best = float(v.energies(n_poses=1)[0][0])
    print(f"Self-dock أفضل طاقة: {best:.2f} kcal/mol")
    assert best < -5.0, f"{pdb_id}: طاقة self-dock غير منطقية ({best})"

    return {
        "id": f"{pdb_id}_{chain}",
        "pdb_id": pdb_id,
        "ligand_resname": lig_res,
        "name_ar": t["name_ar"],
        "name_en": t["name_en"],
        "note_ar": t["note_ar"],
        "center": [round(cx, 2), round(cy, 2), round(cz, 2)],
        "box_size": list(box),
        "demo_smiles": smiles,
        "demo_name_ar": f"{lig_res} — الليغاند المشتبك الأصلي",
        "demo_name_en": f"{lig_res} — co-crystallized ligand",
        "self_dock_best_kcal": round(best, 2),
        "receptor_file": rec_pdbqt.name,
        "meeko": rdkit.__version__,
    }


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    entries: list[dict] = []
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        for t in TARGETS:
            try:
                entries.append(run_target(t, tmp))
            except Exception as exc:  # noqa: BLE001
                print(f"⚠️ تجاهُل {t['pdb_id']}: {exc}", file=sys.stderr)
    if not entries:
        print("❌ لم ينجح أي هدف", file=sys.stderr)
        return 1
    meta_path = OUT_DIR / "receptors.json"
    meta_path.write_text(json.dumps(entries, ensure_ascii=False, indent=2) + "\n")
    print(f"\n✅ {len(entries)} مستقبل جاهز — الميتاداتا: {meta_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
