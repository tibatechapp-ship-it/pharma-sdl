"""سجل الأهداف — يسحب المستقبلات المُجهَّزة والمُتحقق منها من receptors.json.

إعادة استخدام مباشرة لأصل قائم (core.docking.load_receptors) بدل تكراره:
نفس الملف، نفس التحقق (self-dock)، وسياسات فرز موثقة فوقه.
"""

from __future__ import annotations

from core.docking import load_receptors
from pharma_sdl.errors import NotFoundError
from pharma_sdl.targets.models import Target, TargetPolicy

# ─────────────────────────────────────────────────────────────
# السياسات — مصدر الحقيقة: الخطة v1.1 (Mpro غير تساهمي حصراً).
# المرجع: docs/plan/PharmaSDL_Strategic_Plan_v1.1.pdf — القرار D2.
# ─────────────────────────────────────────────────────────────

_MPRO_POLICY = TargetPolicy(
    non_covalent_only=True,
    reason_ar=(
        "Mpro غير تساهمي حصراً (خطة v1.1): Vina وBoltz-2 لا يمثّلان الترابط "
        "التساهمي — أي رأس تساهمي (أكريلاميد/نيتريل/ألدهيد…) يُرفض مسبَّباً."
    ),
    reason_en=(
        "Mpro is non-covalent only (Plan v1.1): Vina and Boltz-2 do not model "
        "covalent bonding — any warhead (acrylamide/nitrile/aldehyde…) is rejected."
    ),
)

_PLPRO_POLICY = TargetPolicy(
    non_covalent_only=True,
    reason_ar=(
        "PLpro يُفرز غير تساهمي بنفس منطق Mpro حتى توفّر محرك يمثّل التساهمي."
    ),
    reason_en=(
        "PLpro screened non-covalent under the same policy until a covalent-aware "
        "engine is onboarded."
    ),
)

_POLICIES: dict[str, TargetPolicy] = {
    "7VH8_A": _MPRO_POLICY,
    "7CMD_A": _PLPRO_POLICY,
}

_DEFAULT_POLICY = TargetPolicy()


def list_targets() -> list[Target]:
    """كل الأهداف الجاهزة في السجل."""
    targets: list[Target] = []
    for rec in load_receptors():
        targets.append(
            Target(
                id=rec.id,
                pdb_id=rec.pdb_id,
                name_ar=rec.name_ar,
                name_en=rec.name_en,
                receptor_file=rec.receptor_file,
                center=rec.center,
                box_size=rec.box_size,
                policy=_POLICIES.get(rec.id, _DEFAULT_POLICY),
                note_ar=rec.note_ar,
                note_en=rec.note_en,
                self_dock_reference_kcal=rec.self_dock_best_kcal,
                co_crystal_smiles=rec.demo_smiles,
                co_crystal_name=rec.demo_name_en or rec.demo_name_ar,
            )
        )
    return targets


def get_target(target_id: str) -> Target:
    """هدف واحد بالمعرّف — خطأ واضح إن لم يوجد."""
    for target in list_targets():
        if target.id == target_id:
            return target
    known = ", ".join(t.id for t in list_targets()) or "لا يوجد"
    raise NotFoundError(
        f"هدف غير معروف: {target_id} — الأهداف المتاحة: {known}",
        f"Unknown target: {target_id} — available targets: {known}",
    )
