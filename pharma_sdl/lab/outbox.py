"""صندوق الصادر المختبري — ذاكرة الدفعات المقدَّمة للفيزياء (P8).

سطر JSON واحد لكل حدث (تقديم أو استطلاع) في ملف ملحق فقط. المقاطعة
تُوثَّق لا تُخفى: بعد انهيار العملية تُقرأ `pending()` لمعرفة الدفعات
التي لم تصل حالة نهائية، ومفتاح `idempotency_key` يجعل إعادة التقديم
آمنة — البوابة تُكرِّم المفتاح فلا يتكرر الفحص الفيزيائي ولا يُدفع مرتين.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from pharma_sdl.lab.batch import TERMINAL_BATCH_STATUSES


class BatchOutbox:
    """دفتر حدثي ملحق (JSONL) — يُكتب ولا يُعدَّل، والقراءة إعادة كاملة."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    # ── الكتابة ──

    def record(self, kind: str, **fields: object) -> None:
        """تسطير حدث واحد — سطر واحد، بلا إعادة كتابة ما سبقه أبداً."""
        event = {"ts_utc": datetime.now(UTC).isoformat(), "kind": kind, **fields}
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, ensure_ascii=False) + "\n")

    def record_submit(
        self, *, batch_id: str, adapter: str, n_assays: int, idempotency_key: str
    ) -> None:
        self.record(
            "submit",
            batch_id=batch_id,
            adapter=adapter,
            n_assays=n_assays,
            idempotency_key=idempotency_key,
            status="pending",
        )

    def record_poll(self, *, batch_id: str, status: str) -> None:
        self.record("poll", batch_id=batch_id, status=status)

    # ── القراءة ──

    def events(self) -> list[dict]:
        """إعادة الأحداث كما كُتبت — سطر تالف يعني عبثاً خارجياً فيُرفض."""
        if not self.path.exists():
            return []
        events: list[dict] = []
        with self.path.open("r", encoding="utf-8") as fh:
            for lineno, line in enumerate(fh, 1):
                if not line.strip():
                    continue
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError as exc:  # pragma: no cover — مسار عبث خارجي
                    raise ValueError(
                        f"سطر {lineno} في صندوق الصادر تالف — عبث خارجي محتمل: {exc}"
                    ) from exc
        return events

    def pending(self) -> list[dict]:
        """الدفعات غير النهائية — بيان التقديم (بمفتاح التعرّج) وآخر حالة.

        الدمج مقصود: مفتاح التعرّج يسكن في حدث التقديم، وآخر حالة في حدث
        الاستطلاع — التسوية بعد المقاطعة تحتاج الاثنين معاً لا واحداً.
        """
        submits: dict[str, dict] = {}
        latest: dict[str, dict] = {}
        for event in self.events():
            batch_id = event.get("batch_id")
            if batch_id is None:
                continue
            latest[batch_id] = event
            if event.get("kind") == "submit":
                submits[batch_id] = event
        out: list[dict] = []
        for batch_id, last in latest.items():
            if last.get("status") in TERMINAL_BATCH_STATUSES:
                continue
            merged = dict(submits.get(batch_id, last))
            merged["status"] = last.get("status")
            out.append(merged)
        return out


__all__ = ["BatchOutbox"]
