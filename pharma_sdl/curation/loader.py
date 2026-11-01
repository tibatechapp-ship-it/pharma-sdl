"""تحميل المدخلات — CSV أو قوائم مضمنة → LigandInput موحّد."""

from __future__ import annotations

import csv
from collections.abc import Iterable
from pathlib import Path

from pharma_sdl.errors import ValidationError
from pharma_sdl.models import LigandInput


def load_ligands_csv(
    path: str | Path,
    smiles_col: str = "smiles",
    name_col: str | None = "name",
    id_col: str | None = "id",
) -> list[LigandInput]:
    """قراءة مكتبة ليغاندات من CSV (أي أعمدة إضافية تُتجاهل بأمان)."""
    file_path = Path(path)
    if not file_path.exists():
        raise ValidationError(f"ملف الليغاندات غير موجود: {file_path}", f"Ligand file not found: {file_path}")
    with file_path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or smiles_col not in reader.fieldnames:
            raise ValidationError(
                f"العمود {smiles_col!r} غير موجود في {file_path.name} — الأعمدة: {reader.fieldnames}",
                f"Column {smiles_col!r} missing in {file_path.name} — columns: {reader.fieldnames}",
            )
        rows: list[LigandInput] = []
        for i, row in enumerate(reader, start=2):
            smiles = (row.get(smiles_col) or "").strip()
            if not smiles:
                continue
            name = (row.get(name_col) or "").strip() if name_col else ""
            identifier = (row.get(id_col) or f"row-{i}").strip() if id_col else f"row-{i}"
            rows.append(
                LigandInput(
                    name=name or None,
                    smiles=smiles,
                    source=f"csv:{file_path.name}#{identifier}",
                )
            )
    return rows


def load_ligands_inline(rows: Iterable[dict[str, object]]) -> list[LigandInput]:
    """قائمة قواميس مضمنة (من الـAPI مثلاً) → LigandInput مع تحقق Pydantic."""
    out: list[LigandInput] = []
    for i, row in enumerate(rows, start=1):
        if not isinstance(row, dict) or not str(row.get("smiles", "")).strip():
            raise ValidationError(
                f"الصف {i} بلا SMILES صالح", f"Row {i} has no valid SMILES"
            )
        out.append(LigandInput.model_validate(row))
    return out
