"""نقل التجارب — تصدير/استيراد JSONL وطريق الترقية إلى PostgreSQL.

تدقيق ما قبل P2: السجل التجريبي SQLite كافٍ لمستخدم علمي واحد، لكن
«الترقية دون إعادة بناء» تتطلب أن تخرج التجارب من SQLite وتدخل أي مخزن
آخر بلا فقد. صيغة النقل JSONL — سطر لكل تجربة كاملة (ExperimentRecord)
بترتيب مستقر، والاستيراد يحفظ المعرّفات وسلسلة parent_experiment_id كما هي.

الترقية إلى PostgreSQL (deploy/postgres/schema.sql):
    1) pharma-sdl export-experiments --db data/experiments.sqlite3 --out exp.jsonl
    2) psql -f deploy/postgres/schema.sql
    3) pharma-sdl import-experiments --db postgres://... --in exp.jsonl
       (أو أداة النسخ التي تفضلها — الصيغة سطر JSON لكل تجربة حرفياً)
"""

from __future__ import annotations

from pathlib import Path

from pharma_sdl.errors import ValidationError
from pharma_sdl.experiments.registry import ExperimentRecord, ExperimentRegistry


def export_jsonl(registry: ExperimentRegistry, out_path: str | Path) -> int:
    """تصدير كل التجارب إلى JSONL — سطر JSON لكل تجربة كاملة. يعيد العدد."""
    rows = registry.latest(limit=registry.count())
    lines = [r.model_dump_json() for r in rows]
    Path(out_path).write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return len(lines)


def import_jsonl(
    registry: ExperimentRegistry, jsonl_path: str | Path, *, overwrite: bool = False
) -> int:
    """استيراد تجارب من JSONL — المعرّفات وسلاسل الأسلاف محفوظة حرفياً.

    overwrite=False (الافتراضي): التكرار الموجود مسبقاً يُتخطى — الاستيراد
    آمن لإعادة المحاولة. overwrite=True: الاستيراد يكتب فوق الموجود.
    """
    path = Path(jsonl_path)
    if not path.exists():
        raise ValidationError(
            f"ملف الاستيراد غير موجود: {path}", f"Import file not found: {path}"
        )
    imported = 0
    # الترتيب الاعتمادي قبل الكتابة: مخازن FK (PostgreSQL — ADR-0008) ترفض
    # طفلاً بلا أبيض. والتصدير أحدث-أولاً، وساعة المنصة بدقة ثانية
    # (timespec="seconds") فالجولات السريعة تتشارك created_at نفسه —
    # لذا الترتيب يتطلب سلسلة الأسلاف نفسها (أعلاوي) لا مقارنة زمنية:
    # الأساس زمني صاعد، ثم تُصدر كل تجربة بعد أبيها (داخل الملف أو في المخزن).
    records: list[ExperimentRecord] = []
    for i, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        raw = raw.strip()
        if not raw:
            continue
        try:
            records.append(ExperimentRecord.model_validate_json(raw))
        except ValueError as exc:
            raise ValidationError(
                f"السطر {i} ليس تجربة صالحة: {exc}",
                f"Line {i} is not a valid experiment record: {exc}",
            ) from exc
    records.sort(key=lambda r: r.created_at)
    in_file = {r.experiment_id for r in records}
    emitted: set[str] = set()
    ordered: list[ExperimentRecord] = []
    remaining = records
    while remaining:
        progressed = False
        for record in list(remaining):
            parent = record.parent_experiment_id
            if parent is None or parent in emitted or parent not in in_file:
                ordered.append(record)
                emitted.add(record.experiment_id)
                remaining.remove(record)
                progressed = True
        if not progressed:  # pragma: no cover — دورة أسلاف: تُرفض فوق FK بصدق
            ordered.extend(remaining)
            break
    for record in ordered:
        if not overwrite and registry.get(record.experiment_id) is not None:
            continue
        registry.upsert(record)
        imported += 1
    return imported


__all__ = ["export_jsonl", "import_jsonl"]
