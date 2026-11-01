"""جناح إعادة الربط (Redocking) — القبول الهندسي الصادق (P2، تقييم #7).

«الربط يعمل» ≠ «الوضع صحيح». المعيار المقبول في المجال: إعادة ربط الليغاند
المشتبك في مستقبله ثم قياس RMSD بين أفضل وضع مُتنبأ والوضع البلوري
(تناظرياً — الذرات المتماثلة تُقاس بأفضل تطابق). القبول هنا مزدوج:

    1) RMSD ≤ 2.0 Å  (أفضل بوز عبر كل البوزات — معيار pose prediction)
    2) ‖ΔΔG‖ ≤ 2.5 kcal/mol مقابل مرجع self-dock الموثق في receptors.json

المراجع البلورية (data/redocking/*.sdf) مُستخرجة من RCSB عبر
scripts/fetch_reference_ligands.py وتلتزم في المستودع — فالاختبار يعمل
بلا شبكة، ولا مرجع مُولَّد ولا RMSD ضد نفسه.

وحدات الدرجة الصادقة: RMSD وحدة هندسة (Å) — لا يُقارن أبداً بدرجات
الطاقة (kcal/mol) ولا بدرجات ML (pIC50)؛ عقد المسارات الثلاثة قائم.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from rdkit import Chem
from rdkit.Chem import rdMolAlign

from pharma_sdl.errors import ValidationError

REPO = Path(__file__).resolve().parent.parent.parent
REFERENCE_DIR = REPO / "data" / "redocking"
RECEPTORS_JSON = REPO / "data" / "receptors" / "receptors.json"

RMSD_ACCEPTANCE_ANGSTROM = 2.0
DDG_ACCEPTANCE_KCAL = 2.5


def has_redocking_stack() -> bool:
    """هل البيئة قادرة على ربط فعلي؟ (vina + meeko — وحدة core.docking تفحصهما)"""
    try:
        import core.docking as core_docking

        return bool(core_docking.HAS_VINA and core_docking.HAS_MEEKO)
    except ImportError:
        return False


def targets_with_references() -> list[dict]:
    """الأهداف التي لها مرجع بلوري ملتزم — نقطة الحقيقة لقائمة الاختبار."""
    if not RECEPTORS_JSON.exists():
        return []
    raw = json.loads(RECEPTORS_JSON.read_text(encoding="utf-8"))
    return [t for t in raw if reference_path(t["id"]).exists()]


def reference_path(target_id: str) -> Path:
    return REFERENCE_DIR / f"{target_id}_ligand.sdf"


def load_reference_ligand(target_id: str) -> Chem.Mol:
    """الليغاند البلوري المرجعي (إحداثيات RCSB الأصلية + روابط من SMILES المرجع)."""
    path = reference_path(target_id)
    if not path.exists():
        raise ValidationError(
            f"لا مرجع بلوري للهدف {target_id} — شغّل: "
            "python scripts/fetch_reference_ligands.py",
            f"No crystal reference for target {target_id} — run: "
            "python scripts/fetch_reference_ligands.py",
        )
    mol = Chem.SDMolSupplier(str(path), removeHs=False)[0]
    if mol is None:
        raise ValidationError(
            f"المرجع البلوري للهدف {target_id} تالف", f"Crystal reference for {target_id} is corrupt"
        )
    return mol


def pose_rmsd(probe: Chem.Mol, reference: Chem.Mol) -> float:
    """RMSD تناظري (Å) بين وضع مُتنبأ وبلورة — أفضل تطابق للذرات المتماثلة.

    الهيدروجينات تُستبعد (عرف المجال) — المقارنة على الهيكل الثقيل حصراً.
    """
    probe_heavy = Chem.RemoveAllHs(Chem.Mol(probe))
    ref_heavy = Chem.RemoveAllHs(Chem.Mol(reference))
    if probe_heavy.GetNumAtoms() != ref_heavy.GetNumAtoms():
        raise ValidationError(
            f"عدد الذرات الثقيلة مختلف: {probe_heavy.GetNumAtoms()} مقابل "
            f"{ref_heavy.GetNumAtoms()} — لا RMSD معنى له بين جزيئين مختلفين",
            f"Heavy atom count differs: {probe_heavy.GetNumAtoms()} vs "
            f"{ref_heavy.GetNumAtoms()} — RMSD is meaningless across molecules",
        )
    return float(rdMolAlign.GetBestRMS(probe_heavy, ref_heavy))


@dataclass
class RedockingResult:
    """نتيجة إعادة ربط هدف واحد — كل رقم صادق ومصدره معلن."""

    target_id: str
    ligand_name: str
    n_poses: int
    exhaustiveness: int
    best_kcal: float | None
    rmsd_best: float | None  # أدنى RMSD عبر كل البوزات (Å)
    rmsd_top3: float | None  # أدنى RMSD ضمن أعلى 3 بوزات (Å)
    self_dock_reference_kcal: float | None
    ddg_error: float | None  # |best − مرجع self-dock| (kcal/mol)
    accepted: bool
    failures: list[str]


def redock_reference(
    target_id: str, *, exhaustiveness: int = 8, n_poses: int = 9
) -> RedockingResult:
    """إعادة ربط كاملة لليغاند المشتبك مقابل مستقبله — النتيجة تحكم القبول."""
    import core.docking as core_docking

    receptor = next((r for r in core_docking.load_receptors() if r.id == target_id), None)
    if receptor is None:
        raise ValidationError(
            f"لا مستقبل جاهز للهدف {target_id}",
            f"No prepared receptor for target {target_id}",
        )
    reference = load_reference_ligand(target_id)
    result = core_docking.dock_ligand(
        receptor.demo_smiles, receptor, n_poses=n_poses, exhaustiveness=exhaustiveness
    )

    failures: list[str] = []
    rmsds: list[float] = []
    for i, pose_pdbqt in enumerate(result.poses_pdbqt, 1):
        pose_mol = _pose_to_mol(pose_pdbqt)
        if pose_mol is None:
            failures.append(f"pose {i}: تعذر التحويل من PDBQT إلى RDKit")
            continue
        try:
            rmsds.append(pose_rmsd(pose_mol, reference))
        except ValidationError as exc:
            failures.append(f"pose {i}: {exc.message_en}")

    rmsd_best = min(rmsds) if rmsds else None
    rmsd_top3 = min(rmsds[:3]) if rmsds else None
    best_kcal = result.best
    ddg = (
        abs(best_kcal - receptor.self_dock_best_kcal)
        if best_kcal is not None
        else None
    )

    if rmsd_best is None:
        failures.append("لا RMSD صالح — القبول مستحيل بصدق")
    accepted = (
        rmsd_best is not None
        and rmsd_best <= RMSD_ACCEPTANCE_ANGSTROM
        and ddg is not None
        and ddg <= DDG_ACCEPTANCE_KCAL
    )
    if rmsd_best is not None and rmsd_best > RMSD_ACCEPTANCE_ANGSTROM:
        failures.append(f"RMSD {rmsd_best:.2f} Å يتجاوز حد القبول 2.0 Å")
    if ddg is not None and ddg > DDG_ACCEPTANCE_KCAL:
        failures.append(f"|ΔΔG| {ddg:.2f} kcal يتجاوز حد القبول 2.5")

    return RedockingResult(
        target_id=target_id,
        ligand_name=receptor.demo_name_en or receptor.id,
        n_poses=len(result.poses_pdbqt),
        exhaustiveness=exhaustiveness,
        best_kcal=best_kcal,
        rmsd_best=rmsd_best,
        rmsd_top3=rmsd_top3,
        self_dock_reference_kcal=receptor.self_dock_best_kcal,
        ddg_error=ddg,
        accepted=accepted,
        failures=failures,
    )


def _pose_to_mol(pose_pdbqt: str) -> Chem.Mol | None:
    """بوز PDBQT واحد → جزيء RDKit بروابط صحيحة عبر Meeko."""
    try:
        from meeko import PDBQTMolecule, RDKitMolCreate

        pmol = PDBQTMolecule(pose_pdbqt, skip_typing=True)
        mols = RDKitMolCreate.from_pdbqt_mol(pmol)
        if not mols or mols[0] is None:
            return None
        return mols[0]
    except Exception:  # noqa: BLE001 — meeko يرمي أنواعاً كثيرة؛ الفشل يُوثَّق في failures لا يُخفى
        return None


__all__ = [
    "DDG_ACCEPTANCE_KCAL",
    "RMSD_ACCEPTANCE_ANGSTROM",
    "RedockingResult",
    "has_redocking_stack",
    "load_reference_ligand",
    "pose_rmsd",
    "redock_reference",
    "reference_path",
    "targets_with_references",
]
