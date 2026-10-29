"""رسم بنيوي ثنائي الأبعاد — طرق عرض أفضل بدل نص SMILES المجرد.

سؤال المستخدم: «هل طريقنا صحيح أو هناك طرق عرض أفضل؟» — أحد الأجوبة:
المولّدات كانت تُعرض نصاً فقط؛ الآن كل مرشح يُرسم بنيوياً (RDKit Cairo)
وأسمى منهجياً: الصورة قبل السلسلة تبني الحدس الكيميائي لدى الطالب.

نمط المنصة: HAS_RDKIT حارس وجود، وفشل الرسم (Cairo غائب مثلاً) يعيد None
بلا استثناءات — الواجهة تتراجع للنص تلقائياً.
"""
from __future__ import annotations

import importlib.util

HAS_RDKIT = importlib.util.find_spec("rdkit") is not None
if HAS_RDKIT:
    from rdkit import Chem
    from rdkit.Chem.Draw import rdMolDraw2D

PNG_MAGIC = b"\x89PNG"


def render_png(smiles: str, size: int = 280) -> bytes | None:
    """PNG بايتات لبنية ثنائية الأبعاد — None عند أي فشل (بلا استثناءات)."""
    if not HAS_RDKIT:
        return None
    mol = Chem.MolFromSmiles((smiles or "").strip())
    if mol is None or mol.GetNumAtoms() == 0:
        return None
    try:
        drawer = rdMolDraw2D.MolDraw2DCairo(int(size), int(size))
        rdMolDraw2D.PrepareAndDrawMolecule(drawer, mol)
        drawer.FinishDrawing()
        png = drawer.GetDrawingText()
    except Exception:  # noqa: BLE001 — Cairo قد لا يتوفر في بعض البيئات
        return None
    return png if png.startswith(PNG_MAGIC) else None
