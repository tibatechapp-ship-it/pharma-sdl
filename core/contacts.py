"""المحلل الداخلي للبوزات — «محرك تسجيل ثانٍ صنعناه بأنفسنا» (S7-a).

خلفية القرار: خارطة الدمج خططت لمحرك تحقام ثانٍ (DockThor/Matcha)، لكن خطوة
التحقق (2026-10-29) كشفت أن حزمة `dock-thor-client` على PyPI **ليست** محرك
DockThor الحقيقي (LNCC) — بل أداة مراقبة أخطاء لخدمة dock.codes (تصادم أسماء)،
وMatcha الحقيقية تحتاج PyTorch/GPU خارج نطاق المنصة. بدل خدمة تحتاج اشتراكاً
أو حساباً: **بنينا المحرك الثاني محلياً** — محلل تفاعلات هندسي بسيط يقرأ نفس
بوزات Vina ويُعيد تقييمها بأدوات مجردة:

- اتصالات ثقيلة (heavy contacts ≤ 4.5 Å) — كم ذرة لاتص بالجيب.
- مرشحات روابط هيدروجينية (مانح HD ↔ مستقبِل OA/NA/SA ≤ 3.5 Å) بالاتجاهين.
- أزواج كارهة للماء (C/A/هالوجين ↔ C/A ≤ 4.2 Å).
- تعارضات sterik (heavy-heavy < 2.7 Å) — عقوبة صريحة.

الدرجة الداخلية التعليمية:
  score = −1.10·(روابط H) − 0.12·(كارهة للماء) + 2.80·(تعارضات)
وهي ليست بديلاً عن دالة Vina — وجودها بجانبها هو الدرس: «نفس البوز،
محركان، فرق الدرجات = اختلاف دوال التسجيل» (قاعدة الخندق التعليمي).

تنسيق الإدخال: PDBQT (AutoDock types في العمودين 77-78) — نفس صيغة
مستقبلاتنا المُجهَّزة ومخرجات `v.poses()`؛ التحليل بلا شبكة وبلا Vina.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

# ── تصنيف أنواع AutoDock ──
AD_DONOR = {"HD", "HS", "H"}                 # هيدروجين قطبي (الذرة نفسها)
AD_ACCEPTOR = {"OA", "NA", "NS", "SA", "OS"}  # ذرات ثقيلة مستقبِلة
AD_HYDROPHOBIC = {"C", "A", "F", "CL", "BR", "I", "S", "SA", "P"}
AD_HYDROGEN = {"HD", "HS", "H", "D"}

# ── عتبات هندسية (Å) — قيم شائعة في أدبيات تحليل التفاعلات ──
HBOND_MAX = 3.5
CONTACT_MAX = 4.5
HYDROPHOBIC_MAX = 4.2
CLASH_MIN = 2.7

# ── أوزان الدرجة التعليمية (kcal/mol تقريبية) ──
HBOND_W = -1.10
HYDROPHOBIC_W = -0.12
CLASH_W = 2.80


@dataclass(frozen=True)
class PdbqtAtom:
    """ذرة واحدة من PDBQT — إحداثيات + تصنيفات نوع AutoDock."""

    x: float
    y: float
    z: float
    ad_type: str
    is_donor: bool
    is_acceptor: bool
    is_hydrophobic: bool
    is_heavy: bool

    @property
    def xyz(self) -> tuple[float, float, float]:
        return (self.x, self.y, self.z)


def _norm_ad_type(raw: str) -> str:
    """توحيد نوع AD (CL→CL، Br→BR…) — الطرف الأعلى (upper) كافٍ للتصنيف."""
    return raw.strip().upper()


def parse_pdbqt_atoms(pdbqt_text: str) -> list[PdbqtAtom]:
    """استخراج الذرات من نص PDBQT (مستقبل أو بوز) — يتجاهل REMARK/ROOT/BRANCH…"""
    out: list[PdbqtAtom] = []
    for line in pdbqt_text.splitlines():
        if not line.startswith(("ATOM", "HETATM")):
            continue
        raw_type = line[77:79].strip() if len(line) >= 78 else ""
        if not raw_type:
            continue
        try:
            x = float(line[30:38])
            y = float(line[38:46])
            z = float(line[46:54])
        except ValueError:
            continue  # سطر تالف — يُتجاهل بلا انهيار
        ad = _norm_ad_type(raw_type)
        out.append(
            PdbqtAtom(
                x=x, y=y, z=z, ad_type=ad,
                is_donor=ad in AD_DONOR,
                is_acceptor=ad in AD_ACCEPTOR,
                is_hydrophobic=ad in AD_HYDROPHOBIC,
                is_heavy=ad not in AD_HYDROGEN,
            )
        )
    return out


@dataclass(frozen=True)
class PoseContacts:
    """خلاصة تحليل بوز واحد مقابل المستقبل — أعداد + درجة تعليمية."""

    n_pose_heavy: int
    n_contacts: int
    n_hbonds: int
    n_hydrophobic: int
    n_clashes: int

    @property
    def score(self) -> float:
        """الدرجة الداخلية (kcal/mol تقريبية) — الأكثر سالبية = تفاعل أفضل."""
        return round(
            HBOND_W * self.n_hbonds
            + HYDROPHOBIC_W * self.n_hydrophobic
            + CLASH_W * self.n_clashes,
            2,
        )

    def to_row(self, pose_index: int | None = None, vina_kcal: float | None = None) -> dict:
        """صف جاهز لجدول الواجهة — يجمع الدرجتين (Vina والداخلية) جنباً إلى جنب."""
        row: dict = {}
        if pose_index is not None:
            row["#"] = pose_index
        if vina_kcal is not None:
            row["vina"] = round(float(vina_kcal), 2)
        row.update(
            {
                "contacts": self.n_contacts,
                "hbonds": self.n_hbonds,
                "hydrophobic": self.n_hydrophobic,
                "clashes": self.n_clashes,
                "inhouse": self.score,
            }
        )
        return row


def _coords(atoms: list[PdbqtAtom]) -> np.ndarray:
    return np.array([a.xyz for a in atoms], dtype=float) if atoms else np.empty((0, 3))


def _pair_count(pa: np.ndarray, pb: np.ndarray, max_d: float) -> int:
    """عدد الأزواج (a,b) التي المسافتها ≤ max_d — بثقة numpy بلا حلقات ثنائية."""
    if pa.shape[0] == 0 or pb.shape[0] == 0:
        return 0
    d = np.linalg.norm(pa[:, None, :] - pb[None, :, :], axis=2)
    return int((d <= max_d).sum())


def analyze_pose(receptor_atoms: list[PdbqtAtom], pose_pdbqt: str) -> PoseContacts:
    """تحليل بوز واحد (نص PDBQT) مقابل ذرات المستقبل المُجهَّزة.

    Raises:
        ValueError: البوز بلا ذرات ثقيلة (PDBQT تالف).
    """
    pose_atoms = parse_pdbqt_atoms(pose_pdbqt)
    pose_heavy = [a for a in pose_atoms if a.is_heavy]
    if not pose_heavy:
        raise ValueError("البوز لا يحوي ذرات ثقيلة — PDBQT تالف؟")

    rec_heavy = [a for a in receptor_atoms if a.is_heavy]
    pose_xyz, rec_xyz = _coords(pose_heavy), _coords(rec_heavy)

    # 1) اتصالات + 2) تعارضات (أزواج ثقيلة ↔ ثقيلة)
    d_heavy = np.linalg.norm(pose_xyz[:, None, :] - rec_xyz[None, :, :], axis=2) \
        if (pose_xyz.shape[0] and rec_xyz.shape[0]) else np.empty((0, 0))
    n_contacts = int((d_heavy <= CONTACT_MAX).sum()) if d_heavy.size else 0
    n_clashes = int((d_heavy < CLASH_MIN).sum()) if d_heavy.size else 0

    # 3) أزواج كارهة للماء — عتبة أضيق (كلا الطرفين C/A/هالوجين)
    pose_hyd = _coords([a for a in pose_heavy if a.is_hydrophobic])
    rec_hyd = _coords([a for a in rec_heavy if a.is_hydrophobic])
    n_hydrophobic = _pair_count(pose_hyd, rec_hyd, HYDROPHOBIC_MAX)

    # 4) مرشحات روابط هيدروجينية بالاتجاهين: مانح H ↔ مستقبِل ثقيل ≤ 3.5 Å
    pose_h = _coords([a for a in pose_atoms if a.is_donor])
    pose_acc = _coords([a for a in pose_heavy if a.is_acceptor])
    rec_h = _coords([a for a in receptor_atoms if a.is_donor])
    rec_acc = _coords([a for a in rec_heavy if a.is_acceptor])
    n_hbonds = _pair_count(pose_h, rec_acc, HBOND_MAX) + _pair_count(rec_h, pose_acc, HBOND_MAX)

    return PoseContacts(
        n_pose_heavy=len(pose_heavy),
        n_contacts=n_contacts,
        n_hbonds=n_hbonds,
        n_hydrophobic=n_hydrophobic,
        n_clashes=n_clashes,
    )


def score_poses(receptor_pdbqt_path: Path | str, poses_pdbqt: list[str]) -> list[PoseContacts]:
    """تحليل قائمة بوزات مقابل ملف مستقبل مُجهَّز — بترتيبها نفسها.

    Raises:
        FileNotFoundError: المستقبل غير موجود.
        ValueError: المستقبل أو أي بوز بلا ذرات.
    """
    text = Path(receptor_pdbqt_path).read_text(encoding="utf-8")
    atoms = parse_pdbqt_atoms(text)
    if not atoms:
        raise ValueError("المستقبل بلا ذرات — PDBQT تالف؟")
    return [analyze_pose(atoms, p) for p in poses_pdbqt]


# ─────────────────────────────────────────────────────────────
# نص الوضع التعليمي (عربي/إنجليزي)
# ─────────────────────────────────────────────────────────────

LESSON: dict[str, str] = {
    "ar": """**لماذا محرك ثانٍ؟** درجة Vina تأتي من دالة تسجيل معقدة (شبكة طاقات
+ معايرة إحصائية) — لا نرى مكوناتها بوضوح. المحلل الداخلي **صنعناه محلياً**
يقيس هندسة التفاعل مباشرة من إحداثيات البوز نفسها:

1. **اتصالات (≤ 4.5 Å)**: كم ذرة من دوائك تلامس الجيب — الالتصاق الواسع
   غالباً أفضل، لكن ليس دائماً.
2. **روابط هيدروجينية (H···مستقبِل ≤ 3.5 Å)**: أقوى أنواع التفاعل الاتجاهي —
   كل رابط ≈ −1.1 kcal/mol في درجتنا التعليمية.
3. **أزواج كارهة للماء (≤ 4.2 Å)**: التثبيت الهيدروفوبي هو ما يُبقي الدواء
   داخل الجيب رغم ماء الجسم.
4. **تعارضات (< 2.7 Å)**: ذرتان ثقيلتان تتداخلان — عقوبة +2.8 لكل تعارض،
   لأنها مستحيلة فيزيائياً.

**الدرس**: قد يعطي بوزان درجة Vina متقاربة لكن عدد روابط/تعارضات مختلف —
قارن الدرجتين، وتساءل: أي دالة تسجيل تصف الواقع أدق؟ كلاهما تقريب.""",
    "en": """**Why a second engine?** Vina's score comes from a complex scoring
function (energy grids + statistical calibration) whose components are not
directly visible. Our **in-house analyzer, built locally**, measures binding
geometry straight from the same pose coordinates:

1. **Contacts (≤ 4.5 Å)**: how many ligand atoms touch the pocket — broad
   contact is usually good, but not always.
2. **H-bond candidates (H···acceptor ≤ 3.5 Å)**: the strongest directional
   interaction — each ≈ −1.1 kcal/mol in our educational score.
3. **Hydrophobic pairs (≤ 4.2 Å)**: hydrophobic packing is what keeps a drug
   in the pocket despite body water.
4. **Clashes (< 2.7 Å)**: two heavy atoms overlapping — a +2.8 penalty each,
   since overlap is physically impossible.

**Lesson**: two poses with similar Vina scores can differ a lot in H-bonds or
clashes. Compare both scores and ask: which scoring function describes reality
better? Both are approximations — that is the point.""",
}
