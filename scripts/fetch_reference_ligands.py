"""جلب الليغاندات المرجعية البلورية من RCSB — أساس جناح إعادة الربط (P2).

الأمانة العلمية: اختبار redocking بلا إحداثيات بلورية حقيقية ليس redocking.
هذا السكربت (يُشغَّل مرة واحدة، ثم تُحفظ النواتج في المستودع):
    1) ينزّل بنية mmCIF من files.rcsb.org لكل هدف في receptors.json
    2) يستخرج الليغاند المشتبك (resname معروف) من السلسلة الأولى، نموذج أول
    3) يزيل البدائل (altloc) ويبني جزيئاً بترتيب روابط صحيح من SMILES المرجع
    4) يكتب SDF بالإحداثيات البلورية الأصلية إلى data/redocking/

الناتج ملف صغير (KB) لكل هدف — يُلتزم في المستودع فاختبارات RMSD تعمل
بلا شبكة إلى الأبد، ولا أحد يستطيع ادعاء نتيجة RMSD ضد مرجع مُولَّد.

الاستخدام:  python scripts/fetch_reference_ligands.py            # الأهداف كلها
            python scripts/fetch_reference_ligands.py 7VH8_A     # هدف واحد
"""

from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

import gemmi
from rdkit import Chem
from rdkit.Chem import AllChem

REPO = Path(__file__).resolve().parent.parent
RECEPTORS_JSON = REPO / "data" / "receptors" / "receptors.json"
OUT_DIR = REPO / "data" / "redocking"

RCSB_CIF = "https://files.rcsb.org/download/{pdb_id}.cif"


def _download(pdb_id: str, dest: Path) -> None:
    if dest.exists() and dest.stat().st_size > 0:
        return
    url = RCSB_CIF.format(pdb_id=pdb_id)
    print(f"  ⬇ {url}")
    req = urllib.request.Request(url, headers={"User-Agent": "pharma-sdl-redocking/0.3"})
    with urllib.request.urlopen(req, timeout=60) as resp, dest.open("wb") as fh:
        fh.write(resp.read())


def _ligand_block(structure: gemmi.Structure, resname: str) -> str | None:
    """أول نسخة من الليغاند المشتبك (نموذج أول، سلسلة أولى تملكه) ككتلة PDB."""
    structure.setup_entities()
    structure.remove_alternative_conformations()
    structure.remove_hydrogens()
    model = structure[0]
    for chain in model:
        for residue in chain:
            if residue.name == resname:
                lines = []
                serial = 1
                for atom in residue:
                    el = atom.element.name.capitalize()
                    name = f" {atom.name:<3}" if len(atom.name) < 4 else atom.name
                    pos = atom.pos
                    lines.append(
                        f"ATOM  {serial:5d} {name:4s} {resname:>3s} A"
                        f"{residue.seqid.num:4d}    "
                        f"{pos.x:8.3f}{pos.y:8.3f}{pos.z:8.3f}"
                        f"{1.00:6.2f}{0.00:6.2f}          {el:>2s}  "
                    )
                    serial += 1
                lines.append("END")
                return "\n".join(lines)
    return None


def _assign_from_template(pdb_block: str, template_smiles: str) -> Chem.Mol:
    r"""ترتيب روابط صحيح: قالب SMILES + إحداثيات PDB — لا روابط مُخمَّنة.

    الهيدروجين الصريح في SMILES المرجعي (مثل [H]/N=C\) يُزال قبل المطابقة —
    البلورة بلا هيدروجينات، والمطابقة تعمل على الهيكل الثقيل حصراً.
    """
    template = Chem.RemoveAllHs(Chem.MolFromSmiles(template_smiles))
    if template is None:
        raise SystemExit(f"SMILES المرجع غير صالح: {template_smiles}")
    raw = Chem.MolFromPDBBlock(pdb_block, removeHs=False, proximityBonding=True)
    if raw is None:
        raise SystemExit("فشل قراءة كتلة PDB لليغاند المرجعي")
    mol = AllChem.AssignBondOrdersFromTemplate(template, raw)
    Chem.AssignStereochemistry(mol, force=True, cleanIt=True)
    return mol


def fetch_target(target: dict) -> Path:
    """جلب ليغاند هدف واحد وحفظه SDF — يعيد مسار الملف."""
    target_id = target["id"]
    pdb_id = target["pdb_id"]
    resname = target["ligand_resname"]
    smiles = target["demo_smiles"]
    out = OUT_DIR / f"{target_id}_ligand.sdf"
    print(f"[{target_id}] {pdb_id} / {resname}")

    cif_path = OUT_DIR / f"{pdb_id}.cif"
    _download(pdb_id, cif_path)
    structure = gemmi.read_structure(str(cif_path))
    structure.setup_entities()

    block = _ligand_block(structure, resname)
    if block is None:
        raise SystemExit(f"لم يُعثر على الليغاند {resname} في {pdb_id}")
    mol = _assign_from_template(block, smiles)

    # مطابقة صادقة: عدد الذرات الثقيلة يقابل القالب — وإلا فالمرجع مكسور
    heavy_mol = Chem.RemoveHs(mol)
    heavy_tpl = Chem.RemoveAllHs(Chem.MolFromSmiles(smiles))
    if heavy_mol.GetNumAtoms() != heavy_tpl.GetNumAtoms():
        raise SystemExit(
            f"عدد الذرات الثقيلة {heavy_mol.GetNumAtoms()} لا يقابل القالب "
            f"{heavy_tpl.GetNumAtoms()} — المرجع غير مكتمل؛ لا يُكتب"
        )
    inchi_mol = Chem.MolToInchiKey(heavy_mol)
    inchi_tpl = Chem.MolToInchiKey(heavy_tpl)
    if inchi_mol != inchi_tpl:
        print("  ⚠ InChIKey مختلف (مقارنة هيكلية عبر SubstructureMatch):")
        match = heavy_mol.HasSubstructMatch(heavy_tpl) and heavy_tpl.HasSubstructMatch(heavy_mol)
        if not match:
            raise SystemExit("البنية المستخرجة لا تطابق SMILES المرجعي — لا يُكتب")
        print("    مطابقة بنيوية متبادلة ✔ (متزامرات مهمة — مقبولة كمرجع)")

    writer = Chem.SDWriter(str(out))
    writer.write(mol)
    writer.close()
    print(f"  ✔ {out.relative_to(REPO)} — {mol.GetNumAtoms()} ذرة ثقيلة بإحداثيات بلورية")
    return out


def main(argv: list[str]) -> int:
    targets = json.loads(RECEPTORS_JSON.read_text(encoding="utf-8"))
    only = set(argv[1:])
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    done = 0
    for target in targets:
        if only and target["id"] not in only:
            continue
        fetch_target(target)
        done += 1
    print(f"\nاكتمل — {done} مرجع بلوري جاهز في data/redocking/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
