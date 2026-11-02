"""عميل LIMS حقيقي عبر REST — جسر الفيزياء (P8, ADR-0013).

عقد البوابة المرجعي (Gateway Contract) — أي خدمة تنفذه تصبح «المختبر»:

    POST {base}/batches        → 201 {"batch_id": str, "status": pending|running|completed|failed}
                                  body: {"idempotency_key": str, "assays": [{smiles, dg_kcal, compound_name?}]}
    GET  {base}/batches/{id}   → 200 {"batch_id", "status", "results"?, "error_ar"?, "error_en"?}
        النتائج: [{smiles, ic50_um, pic50?, assay?, qc_flags?, notes_ar?, notes_en?, simulated?}]
    المصادقة: Authorization: Bearer — التوكن من البيئة حصراً، لا يُسجَّل ولا يظهر في أي رسالة خطأ.
    التعرّج: ترويسة Idempotency-Key مع كل تقديم — إعادة الإرسال بعد مقاطعة آمنة.

انضباط العقد (درس عقود ChEMBL مطبَّق على الفيزياء): كل خروج يُرفض كاملاً
وتُجمَّع الخروق كلها في رفض واحد — SMILES غير قابل للتحليل أو غير مطابق
للطلب، ic50_um مفقود أو غير موجب، pic50 غير متسق، أو بوابة «حقيقية»
تعلِم simulated=true. النتائج تُرفض دفعاتٍ لا تُقبل جزئياً بلا سؤال.

النقل قابل للحقن — الاختبارات تعمل بلا شبكة، وCI لا يلمس جهازاً حقيقياً.
"""

from __future__ import annotations

import json
import math
import time
import urllib.error
import urllib.request
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

from rdkit import Chem

from pharma_sdl.errors import LabError, LimsContractError, ValidationError
from pharma_sdl.lab.batch import BATCH_STATUSES, BatchPoll, BatchTicket
from pharma_sdl.lab.interface import AssayRequest
from pharma_sdl.lab.outbox import BatchOutbox
from pharma_sdl.models import AssayResult

#: أقصى انحراف مقبول بين pic50 المعلن والمحسوب من ic50_um (تقريب بوابة سليم).
PIC50_TOLERANCE = 0.05

#: نوع النقل القابل للحقن — يفصل العقد عن الشبكة فيُختبر بلا عالم خارجي.
Transport = Callable[[str, str, dict[str, str], bytes | None], tuple[int, bytes]]


@dataclass(frozen=True)
class LimsSettings:
    """إعدادات البوابة — الرابط والتوكن والمهل. التوكن لا يُطبع أبداً."""

    base_url: str
    token: str | None = None
    timeout_s: float = 10.0
    poll_interval_s: float = 2.0
    max_polls: int = 60


def _default_transport(timeout_s: float) -> Transport:
    """نقل urllib قياسي — صفر اعتماديات جديدة؛ أخطاء HTTP تحمل معنى العقد."""

    def transport(
        method: str, url: str, headers: dict[str, str], body: bytes | None
    ) -> tuple[int, bytes]:
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout_s) as resp:
                return int(resp.status), resp.read()
        except urllib.error.HTTPError as exc:  # 4xx/5xx جزء من العقد لا استثناء شبكة
            return exc.code, exc.read()

    return transport


def _canonical(smiles: str) -> str | None:
    mol = Chem.MolFromSmiles(smiles)
    return Chem.MolToSmiles(mol) if mol is not None else None


def _join(violations: list[str]) -> str:
    return " | ".join(violations)


class HttpLimsLab:
    """المختبر الحقيقي عبر بوابة REST — نفس العقود فوق، كل التعقيد هنا.

    لا تراجع صامت: فشل الشبكة أو العقد أو المهلة خطأ صريح — العودة إلى
    المحاكاة بعد ضبط البوابة تلفيقٌ نتائج، وممنوعة بنيوياً في هذه الوحدة.
    """

    name = "lims-rest"

    def __init__(
        self,
        settings: LimsSettings,
        transport: Transport | None = None,
        outbox: BatchOutbox | None = None,
    ) -> None:
        self._s = settings
        self._base = settings.base_url.rstrip("/")
        self._transport = transport or _default_transport(settings.timeout_s)
        self._outbox = outbox
        # توقعاتنا لكل دفعة مقدَّمة — للتحقق المطابق في الاستطلاع؛ في
        # عملية أعيد تشغيلها تُقرأ البوابة وحدها (فحص الصفوف يبقى كاملاً).
        self._submitted: dict[str, list[AssayRequest]] = {}

    # ── النقل ──

    def _call(
        self, method: str, url: str, payload: dict | None, idempotency_key: str | None = None
    ) -> tuple[int, Any]:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self._s.token:
            headers["Authorization"] = f"Bearer {self._s.token}"
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        try:
            status, raw = self._transport(method, url, headers, body)
        except Exception as exc:  # شبكة/مهلة/اسم نطاق — فشل صريح بلا تفاصيل توكن
            raise LabError(
                f"بوابة المختبر (LIMS) غير قابلة للوصول: {type(exc).__name__}",
                f"Lab gateway (LIMS) unreachable: {type(exc).__name__}",
            ) from exc
        try:
            data = json.loads(raw.decode("utf-8")) if raw else None
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise LimsContractError(
                "استجابة البوابة ليست JSON سليماً — عقد مخرق.",
                "Gateway response is not valid JSON — contract violated.",
            ) from exc
        return status, data

    # ── العقد: تقديم ← تذكرة ← استطلاع ──

    def submit_batch(
        self, requests: list[AssayRequest], idempotency_key: str | None = None
    ) -> BatchTicket:
        """تقديم دفعة — مفتاح التعرّج يجعل إعادة الإرسال آمنة."""
        if not requests:
            raise ValidationError(
                "دفعة المختبر فارغة — قدّم فحصاً واحداً على الأقل.",
                "Lab batch is empty — submit at least one assay.",
            )
        key = idempotency_key or f"lims-{uuid.uuid4().hex}"
        payload = {
            "idempotency_key": key,
            "assays": [
                {
                    "smiles": r.smiles,
                    "dg_kcal": r.dg_kcal,
                    "compound_name": r.compound_name,
                }
                for r in requests
            ],
        }
        status, data = self._call("POST", f"{self._base}/batches", payload, idempotency_key=key)
        violations: list[str] = []
        if status != 201:
            violations.append(f"تقديم الدفعة أعاد {status} بدل 201 / submit returned {status}")
        if not isinstance(data, dict) or not str(data.get("batch_id") or "").strip():
            violations.append("الاستجابة بلا batch_id صالح / response lacks a valid batch_id")
        ticket_status = data.get("status", "pending") if isinstance(data, dict) else None
        if ticket_status not in BATCH_STATUSES:
            violations.append(f"حالة دفعة غير معروفة: {ticket_status!r} / unknown batch status")
        if violations:
            raise LimsContractError(
                f"خرق عقد تقديم الدفعة — {_join(violations)}",
                f"Batch-submit contract violated — {_join(violations)}",
            )
        batch_id = str(data["batch_id"])
        self._submitted[batch_id] = list(requests)
        if self._outbox is not None:
            self._outbox.record_submit(
                batch_id=batch_id, adapter=self.name, n_assays=len(requests), idempotency_key=key
            )
        return BatchTicket(
            batch_id=batch_id,
            adapter=self.name,
            n_assays=len(requests),
            status=str(ticket_status),
        )

    def poll_batch(self, batch_id: str) -> BatchPoll:
        """استطلاع حالة دفعة — أي خروج عن العقد يرفض الدفعة كاملة."""
        status_code, data = self._call(
            "GET", f"{self._base}/batches/{quote(batch_id, safe='')}", None
        )
        violations: list[str] = []
        if status_code != 200:
            violations.append(f"الاستطلاع أعاد {status_code} بدل 200 / poll returned {status_code}")
        if not isinstance(data, dict):
            violations.append(
                "استجابة الاستطلاع ليست كائن JSON / poll response is not a JSON object"
            )
            raise LimsContractError(
                f"خرق عقد الاستطلاع — {_join(violations)}",
                f"Poll contract violated — {_join(violations)}",
            )
        state = data.get("status")
        if state not in BATCH_STATUSES:
            raise LimsContractError(
                f"خرق عقد الاستطلاع — حالة غير معروفة: {state!r}",
                f"Poll contract violated — unknown status: {state!r}",
            )

        if self._outbox is not None:
            self._outbox.record_poll(batch_id=batch_id, status=str(state))

        if state == "failed":
            return BatchPoll(
                batch_id=batch_id,
                adapter=self.name,
                status="failed",
                error_ar=str(data.get("error_ar") or "فشلت الدفعة عند البوابة."),
                error_en=str(data.get("error_en") or "Batch failed at the gateway."),
            )
        if state in {"pending", "running"}:
            return BatchPoll(batch_id=batch_id, adapter=self.name, status=str(state))

        # completed — التحقق الصارم الكامل قبل قبول أي نتيجة
        results_raw = data.get("results")
        if not isinstance(results_raw, list):
            raise LimsContractError(
                "خرق عقد النتائج — حالة completed بلا قائمة نتائج.",
                "Results contract violated — completed without a results list.",
            )
        expected = self._submitted.get(batch_id)
        if expected is not None and len(results_raw) != len(expected):
            violations.append(
                f"عدد النتائج {len(results_raw)} ≠ المفحوص {len(expected)} / result count mismatch"
            )
        allowed: set[str] | None = None
        if expected is not None:
            allowed = {c for c in (_canonical(r.smiles) for r in expected) if c is not None}
        results: list[AssayResult] = []
        for i, row in enumerate(results_raw):
            _ok, row_results, row_violations = _validate_result_row(i, row, allowed, self.name)
            violations.extend(row_violations)
            results.extend(row_results)
        if violations:
            raise LimsContractError(
                f"خرق عقد نتائج المختبر — الدفعة مرفوضة كاملة: {_join(violations)}",
                f"Lab results contract violated — the batch is rejected in full: {_join(violations)}",
            )
        return BatchPoll(
            batch_id=batch_id,
            adapter=self.name,
            status="completed",
            results=tuple(results),
        )

    # ── راحة LabClient التزامني فوق الدفعات ──

    def run_assay(self, request: AssayRequest) -> AssayResult:
        """فحص واحد متزامن — تقديم فردي واستطلاع حتى حالة نهائية."""
        ticket = self.submit_batch([request])
        for _ in range(max(1, self._s.max_polls)):
            poll = self.poll_batch(ticket.batch_id)
            if poll.status == "completed" and poll.results:
                return poll.results[0]
            if poll.status == "failed":
                raise LabError(
                    poll.error_ar or "فشل الفحص عند البوابة.",
                    poll.error_en or "Assay failed at the gateway.",
                )
            time.sleep(self._s.poll_interval_s)
        raise LabError(
            "انتهت مهلة استطلاع المختبر بلا حالة نهائية — لا نتيجة تُختلق.",
            "Lab polling deadline passed without a terminal state — no result is invented.",
        )


def _validate_result_row(
    index: int, row: Any, allowed: set[str] | None, adapter_name: str
) -> tuple[bool, list[AssayResult], list[str]]:
    """فحص صف نتيجة واحد — يجمع كل خروقه ثم يقرر: قبول أو إدراج في الرفض."""
    violations: list[str] = []
    if not isinstance(row, dict):
        return False, [], [f"نتيجة #{index} ليست كائناً / result #{index} is not an object"]
    label = f"نتيجة #{index}"

    smiles = row.get("smiles")
    canonical = _canonical(smiles) if isinstance(smiles, str) else None
    if canonical is None:
        violations.append(f"{label}: SMILES غير قابل للتحليل / unparseable SMILES")
    elif allowed is not None and canonical not in allowed:
        violations.append(f"{label}: جزيء لم يُطلَب في هذه الدفعة / molecule not in this batch")

    ic50: float | None = row.get("ic50_um")
    if isinstance(ic50, bool) or not isinstance(ic50, (int, float)):
        violations.append(f"{label}: ic50_um مفقود أو ليس عدداً / ic50_um missing or not numeric")
        ic50 = None
    elif not math.isfinite(float(ic50)) or float(ic50) <= 0:
        violations.append(f"{label}: ic50_um ليس موجباً منتهياً / ic50_um not finite-positive")
        ic50 = None

    pic50: float | None = row.get("pic50")
    if pic50 is not None:
        if (
            isinstance(pic50, bool)
            or not isinstance(pic50, (int, float))
            or not math.isfinite(float(pic50))
        ):
            violations.append(f"{label}: pic50 ليس عدداً سليماً / pic50 not a sane number")
        elif ic50 is not None:
            expected_pic = -math.log10(float(ic50) * 1e-6)
            if abs(float(pic50) - expected_pic) > PIC50_TOLERANCE:
                violations.append(
                    f"{label}: pic50={float(pic50):.3f} لا يطابق ic50_um"
                    f" (المتوقع ≈ {expected_pic:.3f}) / pic50 inconsistent with ic50_um"
                )

    if row.get("simulated") is True:
        violations.append(
            f"{label}: بوابة «حقيقية» تعلّم simulated=true — خرق صدق"
            f" / real gateway must never mark simulated"
        )

    flags = row.get("qc_flags")
    if flags is not None and (
        not isinstance(flags, list) or not all(isinstance(f, str) for f in flags)
    ):
        violations.append(f"{label}: qc_flags ليست قائمة نصوص / qc_flags not a list of strings")
        flags = None

    if violations:
        return False, [], violations

    assert ic50 is not None and canonical is not None  # مضمون بمرور كل الفحوص أعلاه
    qc_text = ("QC: " + ", ".join(flags) + ". ") if flags else ""
    result = AssayResult(
        smiles=canonical,
        assay=str(row.get("assay") or adapter_name),
        simulated=False,
        ic50_um=round(float(ic50), 3),
        pic50=None if pic50 is None else round(float(pic50), 2),
        notes_ar=qc_text + "قياس من بوابة LIMS — UNVALIDATED حتى ترقية بشرية موثقة.",
        notes_en=qc_text
        + "Measurement via LIMS gateway — UNVALIDATED until documented human promotion.",
    )
    return True, [result], []


__all__ = [
    "PIC50_TOLERANCE",
    "HttpLimsLab",
    "LimsSettings",
    "Transport",
]
