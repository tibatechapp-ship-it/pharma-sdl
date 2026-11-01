"""نماذج الأهداف — هدف = بنية مستقبل + صندوق ربط + سياسة فرز صريحة.

السياسة هي العقد الحاكم: ما يُسمح بفرزه مقابل هذا الهدف وما يُرفض،
ومصدر الحقيقة فيها الخطة الاستراتيجية v1.1 (وليس تفضيلاً برمجياً).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TargetPolicy:
    """سياسة الفرز المسموح لمستهدف معيّن."""

    non_covalent_only: bool = True
    reason_ar: str = "السياسة الافتراضية: محركات المنصة (Vina/Boltz-2) لا تمثّل الترابط التساهمي."
    reason_en: str = (
        "Default policy: platform engines (Vina/Boltz-2) do not model covalent bonding."
    )
    # سقوف اختيارية تُطبَّق عند التنقية (أعلام توثيقية لا رفض صارم).
    max_mol_weight: float | None = None


@dataclass(frozen=True)
class Target:
    """مستهدف دوائي جاهز للفرز (مشتق من receptors.json المُتحقق منه)."""

    id: str
    pdb_id: str
    name_ar: str
    name_en: str
    receptor_file: str
    center: tuple[float, float, float]
    box_size: tuple[float, float, float]
    policy: TargetPolicy
    note_ar: str = ""
    note_en: str = ""
    self_dock_reference_kcal: float | None = None
    co_crystal_smiles: str = ""
    co_crystal_name: str = ""

    @property
    def label_ar(self) -> str:
        return f"{self.name_ar} ({self.pdb_id})"

    @property
    def label_en(self) -> str:
        return f"{self.name_en} ({self.pdb_id})"

    def to_dict(self) -> dict[str, object]:
        """تمثيل JSON صادق — يُستخدم في الـAPI والـCLI والتقارير."""
        return {
            "id": self.id,
            "pdb_id": self.pdb_id,
            "name_ar": self.name_ar,
            "name_en": self.name_en,
            "receptor_file": self.receptor_file,
            "center": list(self.center),
            "box_size": list(self.box_size),
            "policy": {
                "non_covalent_only": self.policy.non_covalent_only,
                "reason_ar": self.policy.reason_ar,
                "reason_en": self.policy.reason_en,
            },
            "self_dock_reference_kcal": self.self_dock_reference_kcal,
            "co_crystal_name": self.co_crystal_name,
        }
