"""مسار القياسات — النتائج الفيزيائية المقبولة تدخل ذاكرة المنصة (P9).

هذه هي نقطة عودة الحلقة: ما قاست الأجهزة عبر البوابة يُبلَع هنا فيصبح
ذاكرة دائمة — ملف JSONL لكل قياس بسطره، وسجل تجريبي دائم
(`kind="lab_batch"`) بحقله الإثبات الكامل (batch_id، محول، بصمات).

قواعد الصدق في هذا المسار:
    - **القياس الفيزيائي حصراً**: أي نتيجة `simulated=True` تُرفض
      استثناءً صريحاً — مسار القياسات لا تختلط فيه المحاكاة بالفيزياء.
    - **البلع عديم التكرار**: الدفعة نفسها لا تُبلَع مرتين — إعادة
      التسوية بعد مقاطعة تعيد «تخطّى» لا تضاعف.
    - **الترقية ليست من هنا**: القياسات نقاط بيانات UNVALIDATED —
      ترقيتها بشرية موثقة عبر بوابة الاعتماد (قاعدة المنصة الثابتة).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pharma_sdl.errors import ValidationError
from pharma_sdl.experiments.registry import (
    ExperimentRecord,
    ExperimentRegistry,
    code_version,
)
from pharma_sdl.lab.batch import BatchPoll
from pharma_sdl.models import utcnow_iso


class MeasurementIngestor:
    """بلّاع القياسات — JSONL + سجل تجريبي دائم، عديم التكرار بالدفعة."""

    def __init__(self, path: str | Path, registry: ExperimentRegistry | None = None) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.registry = registry

    # ── البلع ──

    def ingest(self, poll: BatchPoll) -> dict:
        """بلع دفعة مكتملة — يعيد ملخصاً صادقاً (مُبلَع / مُتخطّى)."""
        if poll.status != "completed" or not poll.results:
            raise ValidationError(
                f"الدفعة «{poll.batch_id}» ليست مكتملة — لا يُبلَع إلا القياس الواصل.",
                f"Batch “{poll.batch_id}” is not completed — only arrived measurements are ingested.",
            )
        if any(r.simulated for r in poll.results):
            raise ValidationError(
                "نتيجة محاكاة في مسار القياسات الفيزيائية — مرفوضة: المحاكاة لا تدخل القياسات.",
                "Simulated result in the physical-measurement lane — refused: simulation never enters measurements.",
            )
        already = self.ingested_batches()
        if poll.batch_id in already:
            return {
                "batch_id": poll.batch_id,
                "ingested": 0,
                "skipped": len(poll.results),
                "already_ingested": True,
            }
        rows = [
            {
                "batch_id": poll.batch_id,
                "adapter": poll.adapter,
                "smiles": r.smiles,
                "assay": r.assay,
                "ic50_um": r.ic50_um,
                "pic50": r.pic50,
                "notes_ar": r.notes_ar,
                "notes_en": r.notes_en,
                "ingested_at_utc": utcnow_iso(),
                "source": "lims-gateway",
            }
            for r in poll.results
        ]
        with self.path.open("a", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        if self.registry is not None:
            self.registry.upsert(self._record(poll, rows))
        return {
            "batch_id": poll.batch_id,
            "ingested": len(rows),
            "skipped": 0,
            "already_ingested": False,
        }

    # ── القراءة ──

    def measurements(self) -> list[dict]:
        """كل القياسات كما بلُعت — سطر تالف يعني عبثاً خارجياً فيُرفض."""
        if not self.path.exists():
            return []
        out: list[dict] = []
        with self.path.open("r", encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    out.append(json.loads(line))
        return out

    def ingested_batches(self) -> set[str]:
        """معرفات الدفعات المبلوعة — أساس عديم التكرار."""
        return {m["batch_id"] for m in self.measurements()}

    def by_smiles(self) -> dict[str, dict]:
        """آخر قياس لكل جزيء — المرجع عند دمج القياس مع التنبؤ."""
        out: dict[str, dict] = {}
        for m in self.measurements():
            out[m["smiles"]] = m
        return out

    # ── السجل الدائم ──

    def _record(self, poll: BatchPoll, rows: list[dict]) -> ExperimentRecord:
        smiles_list = [r["smiles"] for r in rows]
        fingerprint = hashlib.sha256(
            "\n".join(sorted(f"{m['smiles']}::{m['ic50_um']}" for m in rows)).encode()
        ).hexdigest()[:16]
        return ExperimentRecord(
            kind="lab_batch",
            status="completed",
            hypothesis_ar=(
                "أفضل مرشحي الحلقة تُقاس فيزيائياً عبر بوابة LIMS — "
                "الحلقة تُغلق حيث تلتقي التنبؤ بالقياس."
            ),
            hypothesis_en=(
                "Top loop candidates measured physically via the LIMS "
                "gateway — the loop closes where prediction meets measurement."
            ),
            question=(
                f"ما IC50 المقاس للمرشحين المقدمين في الدفعة «{poll.batch_id}»؟"
            ),
            engine_used=poll.adapter,
            method="lims_batch_confirmation",
            data_version=fingerprint,
            code_version=code_version(),
            parameters={
                "batch_id": poll.batch_id,
                "adapter": poll.adapter,
                "n_results": len(rows),
                "lane": "physical_confirmation",
                "n_molecules": len(set(smiles_list)),
            },
            top_hits=[
                {
                    "smiles": r["smiles"],
                    "ic50_um": r["ic50_um"],
                    "pic50": r["pic50"],
                }
                for r in rows
            ],
            lesson=(
                "قياسات فيزيائية مُقبولة ودخلت ذاكرة المنصة — نقاط بيانات "
                "UNVALIDATED حتى ترقية بشرية موثقة؛ إعادة التدريب عليها "
                "خطوة معلنة تالية لا تلقائية."
            ),
        )


__all__ = ["MeasurementIngestor"]
