"""الحلقة الفيزيائية — من أفضل مرشحي الحلقة إلى قياس مخبري إلى الذاكرة (P9).

هذه الوحدة تُغلق الدائرة التي وصفتها خطة التدقيق: المنصة تقترح،
المختبر يقيس، والذاكرة تستقبل القياس. ثلاث دوال بسيطة:

    submit_confirmation_batch  → أرسل أفضل المرشحين إلى المختبر النشط
    reconcile_batches          → استطلع ما لم يصل حالته النهائية وابلعه
    run_physical_confirmation  → الدائرة كاملة في نداء واحد (تقديم ←
                                 استطلاع ← بلع؛ ومع المحاكاة تكتمل
                                 فوراً، ومع LIMS تعود التذكرة ويُستكمل
                                 لاحقاً بالتسوية)

الصدق: البلع حصراً للنتائج الفيزيائية (`MeasurementIngestor` يرفض
المحاكاة)، والمقاطعة تُوثَّق في صندوق الصادر ولا تُخفى.
"""

from __future__ import annotations

from pharma_sdl.errors import ValidationError
from pharma_sdl.lab.batch import BatchPoll, BatchTicket
from pharma_sdl.lab.interface import AssayRequest
from pharma_sdl.lab.lims import HttpLimsLab
from pharma_sdl.lab.outbox import BatchOutbox
from pharma_sdl.lab.simulation import SimulatedFretLab

#: شكل مرشح قادم من سجلات الحلقة أو الفرز — smiles إلزامي والاسم اختياري.


def submit_confirmation_batch(
    top_hits: list[dict],
    lab: SimulatedFretLab | HttpLimsLab | None = None,
    idempotency_key: str | None = None,
) -> BatchTicket:
    """تقديم دفعة تأكيدية لأفضل المرشحين إلى المختبر النشط."""
    if not top_hits:
        raise ValidationError(
            "لا مرشحين للتأكيد الفيزيائي — مرر top_hits من جولة الحلقة.",
            "No candidates to confirm physically — pass top_hits from a loop round.",
        )
    if lab is None:
        from pharma_sdl.lab import make_lab_client

        lab = make_lab_client()
    requests = [
        AssayRequest(
            smiles=str(hit["smiles"]),
            dg_kcal=hit.get("kcal"),
            compound_name=hit.get("name"),
        )
        for hit in top_hits
        if str(hit.get("smiles") or "").strip()
    ]
    return lab.submit_batch(requests, idempotency_key=idempotency_key)


def reconcile_batches(
    lab: SimulatedFretLab | HttpLimsLab | None = None,
    ingestor: object | None = None,
    outbox: BatchOutbox | None = None,
) -> list[dict]:
    """تسوية ما بعد المقاطعة: استطلع الدفعات المعلّقة وابلع ما وصل."""
    if outbox is None:
        return []  # لا صندوق صادر ⇒ لا شيء معلّق معلوماً — لا تخمين
    if lab is None:
        from pharma_sdl.lab import make_lab_client

        lab = make_lab_client()
    summary: list[dict] = []
    for entry in outbox.pending():
        batch_id = str(entry.get("batch_id"))
        try:
            poll = lab.poll_batch(batch_id)
        except Exception as exc:  # noqa: BLE001 — التسوية توثّق كل فشل وتتخطاه لا تُخفيه
            summary.append({"batch_id": batch_id, "status": "unreachable", "error": str(exc)})
            continue
        row: dict = {"batch_id": batch_id, "status": poll.status}
        if poll.status == "completed" and ingestor is not None:
            if any(r.simulated for r in poll.results or []):
                row["ingested"] = 0
                row["note"] = "نتائج محاكاة — مسار القياسات الفيزيائية لا يبلعها"
            else:
                row.update(ingestor.ingest(poll))  # type: ignore[attr-defined]
        summary.append(row)
    return summary


def run_physical_confirmation(
    top_hits: list[dict],
    lab: SimulatedFretLab | HttpLimsLab | None = None,
    ingestor: object | None = None,
    idempotency_key: str | None = None,
) -> dict:
    """الدائرة كاملة: تقديم ← استطلاع ← بلع — أو تذكرة تنتظر التسوية.

    صندوق الصادر يُوصَل عبر `lab` نفسه (`HttpLimsLab(outbox=…)`) —
    فالتقديم يُسطَّر حيث يحدث، والتسوية لاحقاً عبر `reconcile_batches`.
    """
    if lab is None:
        from pharma_sdl.lab import make_lab_client

        lab = make_lab_client()
    ticket = submit_confirmation_batch(top_hits, lab=lab, idempotency_key=idempotency_key)
    out: dict = {"batch_id": ticket.batch_id, "adapter": ticket.adapter}
    if ticket.status != "completed":
        out["state"] = "submitted"
        out["note_ar"] = "الدفعة عند المختبر — استطلاع بالتسوية (reconcile_batches) لا بالتكرار."
        out["note_en"] = "Batch is at the lab — poll via reconciliation, not by resubmitting."
        return out
    # مكتمل فوراً (المحاكاة) — استطلاع وبلع في نفس النداء
    poll = lab.poll_batch(ticket.batch_id)
    return _finish(poll, ingestor, out)


def _finish(poll: BatchPoll, ingestor: object | None, out: dict) -> dict:
    out["status"] = poll.status
    if poll.status == "failed":
        out["error_ar"] = poll.error_ar
        out["error_en"] = poll.error_en
        return out
    results = poll.results or ()
    out["results"] = [
        {
            "smiles": r.smiles,
            "ic50_um": r.ic50_um,
            "pic50": r.pic50,
            "simulated": r.simulated,
        }
        for r in results
    ]
    simulated = any(r.simulated for r in results)
    out["simulated"] = simulated
    if ingestor is not None:
        if simulated:
            out["ingested"] = {"ingested": 0, "skipped": len(results), "note": "محاكاة لا تُبلَع"}
        else:
            out["ingested"] = ingestor.ingest(poll)  # type: ignore[attr-defined]
    return out


__all__ = [
    "reconcile_batches",
    "run_physical_confirmation",
    "submit_confirmation_batch",
]
