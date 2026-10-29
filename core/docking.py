"""Docking جزيئي تعليمي — AutoDock Vina + Meeko.

السلسلة الكاملة داخل التبويب:
  SMILES → RDKit (Hs + conformer) → Meeko PDBQT → Vina (صندوق جاهز) → بوزات + طاقات
  → عرض 3Dmol.js تفاعلي داخل Streamlit.

المستقبلات مُجهَّزة مسبقاً (data/receptors/*.pdbqt) عبر scripts/prepare_receptors.py
وصندوق الربط مشتق من الليغاند المشتبك لكل هدف. الدرجات «تعليمية»: دالة تسجيل Vina
تُبالغ/تُقلّل مقارنة بالتجربة — لذلك نضعها بجانب جسر Cheng-Prusoff من pIC50.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar

from rdkit import Chem
from rdkit.Chem import AllChem

RECEPTORS_DIR = Path(__file__).resolve().parent.parent / "data" / "receptors"

# ── توفّر المحركات (تبقى الاختبارات الأساسية تعمل بلا Vina) ──
try:
    from vina import Vina  # type: ignore

    HAS_VINA = True
except ImportError:  # pragma: no cover - بيئة CI لها vina
    HAS_VINA = False

try:
    from meeko import MoleculePreparation, PDBQTWriterLegacy  # type: ignore

    HAS_MEEKO = True
except ImportError:  # pragma: no cover
    HAS_MEEKO = False


# ─────────────────────────────────────────────────────────────
# المستقبلات
# ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ReceptorInfo:
    """ميتاداتا مستقبل جاهز للـDocking (من receptors.json)."""

    NOTE_EN: ClassVar[dict[str, str]] = {
        "7VH8": (
            "Same target as the Predict & Capstone models — the co-crystallized "
            "ligand (PF-00835231) is the parent compound of nirmatrelvir."
        ),
        "7CMD": (
            "A second viral enzyme — a naphthyl-benzamide inhibitor bound in "
            "the active site."
        ),
    }
    id: str
    pdb_id: str
    ligand_resname: str
    name_ar: str
    name_en: str
    note_ar: str
    center: tuple[float, float, float]
    box_size: tuple[float, float, float]
    demo_smiles: str
    self_dock_best_kcal: float
    receptor_file: str
    demo_name_ar: str = ""
    demo_name_en: str = ""

    @property
    def label_ar(self) -> str:
        return f"{self.name_ar} ({self.pdb_id})"

    @property
    def label_en(self) -> str:
        return f"{self.name_en} ({self.pdb_id})"

    @property
    def note_en(self) -> str:
        return self.NOTE_EN.get(self.pdb_id, self.note_ar)

    @property
    def receptor_file_path(self) -> Path:
        return RECEPTORS_DIR / self.receptor_file

    def demo_label(self, lang: str = "ar") -> str:
        """اسم الليغاند التجريبي حسب اللغة."""
        return self.demo_name_ar if lang == "ar" else (self.demo_name_en or self.demo_name_ar)


def load_receptors() -> list[ReceptorInfo]:
    """قراءة المستقبلات المُجهَّزة من data/receptors/receptors.json."""
    meta_path = RECEPTORS_DIR / "receptors.json"
    if not meta_path.exists():  # pragma: no cover - الملف ملتزم بالمستودع
        return []
    raw = json.loads(meta_path.read_text(encoding="utf-8"))
    return [
        ReceptorInfo(
            id=r["id"],
            pdb_id=r["pdb_id"],
            ligand_resname=r["ligand_resname"],
            name_ar=r["name_ar"],
            name_en=r["name_en"],
            note_ar=r["note_ar"],
            center=tuple(r["center"]),  # type: ignore[arg-type]
            box_size=tuple(r["box_size"]),  # type: ignore[arg-type]
            demo_smiles=r["demo_smiles"],
            self_dock_best_kcal=float(r["self_dock_best_kcal"]),
            receptor_file=r["receptor_file"],
            demo_name_ar=r.get("demo_name_ar", ""),
            demo_name_en=r.get("demo_name_en", ""),
        )
        for r in raw
    ]


# ─────────────────────────────────────────────────────────────
# جسر Cheng-Prusoff — من pIC50 إلى ΔG
# ─────────────────────────────────────────────────────────────

RT_KCAL = 0.59248  # kcal/mol عند 298.15 K (R = 1.9872e-3 kcal/(mol·K))


def pic50_to_dg_kcal(pic50: float) -> float:
    """جسر Cheng-Prusoff: ΔG° = RT·ln(Kd) مع pKd ≈ pIC50.

    ΔG ≈ −(RT·ln10)·pIC50 = −1.3644·pIC50 kcal/mol.
    تقريب تعليمي (IC50≈Kd فقط عند [L]≪Ki وتوازن قياسي).
    """
    return -(RT_KCAL * math.log(10.0)) * float(pic50)


# ─────────────────────────────────────────────────────────────
# تجهيز الليغاند
# ─────────────────────────────────────────────────────────────

def prepare_ligand(smiles: str) -> tuple[str, Chem.Mol]:
    """SMILES → (نص PDBQT, جزيء RDKit ثلاثي الأبعاد).

    Raises:
        ValueError: SMILES غير صالح أو فشل توليد البنية/PDBQT.
    """
    if not HAS_MEEKO:  # pragma: no cover
        raise RuntimeError("Meeko غير متاح في هذه البيئة")

    mol = Chem.MolFromSmiles(smiles.strip())
    if mol is None:
        raise ValueError("SMILES غير صالح — راجع الصيغة")
    mol = Chem.AddHs(mol)
    params = AllChem.ETKDGv3()
    params.randomSeed = 42
    if AllChem.EmbedMolecule(mol, params) != 0:
        params.useRandomCoords = True
        if AllChem.EmbedMolecule(mol, params) != 0:
            raise ValueError("فشل توليد البنية ثلاثية الأبعاد لهذا الجزيء")
    try:
        AllChem.MMFFOptimizeMolecule(mol, maxIters=200)
    except Exception as exc:  # noqa: BLE001 - تحسين اختياري لا يعطّل السير
        print(f"MMFF optimization skipped: {exc}")

    setups = MoleculePreparation()(mol)
    pdbqt, ok, err = PDBQTWriterLegacy.write_string(setups[0])
    if not ok or not pdbqt:
        raise ValueError(f"فشل تجهيز PDBQT: {err}")
    return pdbqt, mol


# ─────────────────────────────────────────────────────────────
# تحويل بوز PDBQT → PDB (للعرض في 3Dmol.js)
# ─────────────────────────────────────────────────────────────

_AD_TYPE_TO_ELEMENT = {
    "A": "C", "C": "C", "N": "N", "NA": "N", "NS": "N",
    "O": "O", "OA": "O", "OS": "O",
    "S": "S", "SA": "S", "P": "P",
    "F": "F", "Cl": "Cl", "CL": "Cl", "Br": "Br", "BR": "Br", "I": "I",
    "HD": "H", "H": "H",
}


def _element_from_ad_type(ad_type: str) -> str:
    return _AD_TYPE_TO_ELEMENT.get(ad_type, _AD_TYPE_TO_ELEMENT.get(ad_type.capitalize(), "C"))


def pose_pdbqt_to_pdb(pose_pdbqt: str) -> str:
    """بوز PDBQT واحد → نص PDB نظيف (بدون أعمدة الشحنات، مع عنصر صحيح)."""
    out: list[str] = []
    for line in pose_pdbqt.splitlines():
        if not line.startswith(("ATOM", "HETATM")):
            continue
        rec = line[:66]
        ad_type = line[77:79].strip() if len(line) >= 78 else ""
        elem = _element_from_ad_type(ad_type)
        # الأعمدة 77-78 لعنصر PDB القياسي (فهرس صفري 76)
        out.append(f"{rec:<76}{elem:>2}")
    if not out:
        raise ValueError("البوز لا يحوي ذرات — PDBQT تالف؟")
    return "\n".join(out) + "\nEND\n"


def split_poses(poses_pdbqt: str) -> list[str]:
    """تقسيم مخرجات v.poses() إلى بوزات فردية (كتل MODEL … ENDMDL)."""
    blocks: list[list[str]] = []
    current: list[str] | None = None
    for line in poses_pdbqt.splitlines():
        if line.startswith("MODEL"):
            current = [line]
        elif line.startswith(("ENDMDL", "END MODEL")):
            if current is not None:
                current.append(line)
                blocks.append(current)
            current = None
        elif current is not None:
            current.append(line)
    return ["\n".join(b) for b in blocks]


# ─────────────────────────────────────────────────────────────
# الـDocking الفعلي
# ─────────────────────────────────────────────────────────────

@dataclass
class DockingResult:
    """نتيجة ربط لجزيء واحد مقابل مستقبل واحد."""

    smiles: str
    receptor_id: str
    scores: list[float] = field(default_factory=list)          # total (kcal/mol)
    energies: list[list[float]] = field(default_factory=list)  # صفوف Vina الخمسة
    poses_pdbqt: list[str] = field(default_factory=list)       # كتل MODEL
    exhaustiveness: int = 8
    engine: str = "vina"

    @property
    def best(self) -> float | None:
        return self.scores[0] if self.scores else None

    def best_pose_pdb(self) -> str:
        """أفضل بوز محوَّلاً إلى PDB للعرض."""
        if not self.poses_pdbqt:
            raise ValueError("لا توجد بوزات")
        return pose_pdbqt_to_pdb(self.poses_pdbqt[0])


def dock_ligand(
    smiles: str,
    receptor: ReceptorInfo,
    n_poses: int = 5,
    exhaustiveness: int = 8,
) -> DockingResult:
    """ربط كامل: تجهيز الليغاند ثم Vina داخل صندوق المستقبل الجاهز."""
    if not (HAS_VINA and HAS_MEEKO):  # pragma: no cover
        raise RuntimeError("vina/meeko غير متاحين — استخدم جسر Cheng-Prusoff في هذه الحالة")

    lig_pdbqt, _mol = prepare_ligand(smiles)
    v = Vina(sf_name="vina")
    v.set_receptor(str(RECEPTORS_DIR / receptor.receptor_file))
    v.compute_vina_maps(center=list(receptor.center), box_size=list(receptor.box_size))
    v.set_ligand_from_string(lig_pdbqt)
    v.dock(exhaustiveness=int(exhaustiveness), n_poses=int(n_poses))

    rows = v.energies(n_poses=int(n_poses)).tolist()
    poses = split_poses(v.poses(n_poses=int(n_poses)))
    return DockingResult(
        smiles=smiles,
        receptor_id=receptor.id,
        scores=[r[0] for r in rows],
        energies=rows,
        poses_pdbqt=poses,
        exhaustiveness=int(exhaustiveness),
    )


# ─────────────────────────────────────────────────────────────
# عرض 3Dmol.js — يُحقن عبر st.html (بلا تبعيات خارجية)
# ─────────────────────────────────────────────────────────────

def build_3d_html(
    receptor_pdbqt_path: Path,
    best_pose_pdb: str,
    width: int = 760,
    height: int = 460,
    div_id: str = "pharma-dock-3d",
) -> str:
    """HTML لعارض 3Dmol.js: المستقبل كارتون + الليغاند عصيّ + سطح الجيب خفيف.

    يعمل بلا شبكة داخلية (CDN 3Dmol.js يُحمَّل في المتصفح عند العرض فقط)،
    والاختبار يتحقق من التركيب النصي فقط.
    """
    rec_txt = Path(receptor_pdbqt_path).read_text(encoding="utf-8")

    def js_str(s: str) -> str:
        return json.dumps(s)

    return f"""
<div id="{div_id}" style="width:100%;max-width:{width}px;height:{height}px;position:relative;border-radius:12px;overflow:hidden;"></div>
<script src="https://cdn.jsdelivr.net/npm/3dmol@2.5.2/build/3Dmol-min.js"></script>
<script>
(function() {{
  function boot() {{
    var box = document.getElementById({js_str(div_id)});
    if (!box || !window.$3Dmol) {{ setTimeout(boot, 300); return; }}
    var view = $3Dmol.createViewer(box, {{backgroundColor: "#0e1524"}});
    view.addModel({js_str(rec_txt)}, "pdbqt", {{keepH: false}});
    view.setStyle({{}}, {{
      cartoon: {{color: "#3d5a98", opacity: 0.85}},
      stick: {{hidden: true}}
    }});
    view.addModel({js_str(best_pose_pdb)}, "pdb", {{keepH: true}});
    view.setStyle({{model: 1}}, {{
      stick: {{radius: 0.28, colorscheme: "cyanCarbon"}},
      sphere: {{scale: 0.22, colorscheme: "cyanCarbon"}}
    }});
    view.zoomTo({{model: 1}});
    view.zoom(4.2);
    view.render();
  }}
  boot();
}})();
</script>
"""


# ─────────────────────────────────────────────────────────────
# نص الوضع التعليمي (عربي/إنجليزي)
# ─────────────────────────────────────────────────────────────

LESSON: dict[str, str] = {
    "ar": """**ماذا يحدث هنا؟** يبحث الحاسوب عن أفضل «وضعية» يلتصق بها دواؤك في جيب
البروتييز، ثم يقدّر قوة الارتباط بطاقة (kcal/mol) — الأكثر سالبية = أقوى ارتباط.

1. **تجهيز الليغاند (Meeko)**: نولّد بنية 3D من SMILES ونضيف الهيدروجينات وشحنات
   Gasteiger — Vina يفهم صيغة PDBQT فقط.
2. **الشبكة (Maps)**: Vina يبسط البروتين إلى شبكة طاقة حول صندوق الربط — لذلك
   المستقبلات هنا مُجهَّزة مسبقاً والصندوق مشتق من الليغاند المشتبك في بلورة PDB.
3. **البحث (Monte Carlo + Local Opt)**: عشرات الأوضاع العشوائية تُثنّى وتُثبَّت،
   و«exhaustiveness» = كم نبحث قبل الاستسلام (أعلى = أدق وأبطأ).
4. **الدرجة**: total = inter (بروتين↔دواء) + intra (دواء مع نفسه) + قيود الالتفاف.

**حدود تعليمية**: درجة Vina ليست IC50 حقيقية — لذلك نقارنها بجسر Cheng-Prusoff
(ΔG ≈ −1.364 × pIC50) من نموذج ML في تبويب Predict. اتفاق تقريبي = ممتاز،
اختلاف كبير = رسالة تُعلَّم ولا تُخفى.""",
    "en": """**What happens here?** The computer searches for the best "pose" of your
ligand inside the protease pocket, then estimates binding strength as an energy
(kcal/mol) — more negative = stronger binding.

1. **Ligand prep (Meeko)**: we generate a 3D conformer from SMILES, add hydrogens
   and Gasteiger charges — Vina only understands PDBQT.
2. **Maps**: Vina precomputes an energy grid around the binding box; boxes here
   derive from the co-crystallized ligand of each PDB structure.
3. **Search (Monte Carlo + local opt)**: many random poses are folded and refined;
   "exhaustiveness" = how hard we search (higher = better & slower).
4. **Score**: total = inter (protein-ligand) + intra (ligand strain) + torsions.

**Teaching caveat**: a Vina score is not a real IC50 — we therefore compare it to
the Cheng-Prusoff bridge (ΔG ≈ −1.364 × pIC50) from the ML model in Predict.
Rough agreement is great; disagreement is a lesson, not a bug.""",
}


def estimate_summary_row(score_kcal: float | None, pic50: float | None) -> dict[str, Any]:
    """صف مقارنة موحّد: درجة Vina مقابل جسر pIC50 (للاستخدام في التطبيق والاختبارات)."""
    return {
        "vina_kcal": None if score_kcal is None else round(float(score_kcal), 2),
        "dg_from_pic50": None if pic50 is None else round(pic50_to_dg_kcal(pic50), 2),
        "gap": None
        if (score_kcal is None or pic50 is None)
        else round(float(score_kcal) - pic50_to_dg_kcal(pic50), 2),
    }
