"""البوابة المرجعية لـLIMS — الجهة الأخرى من عقد ADR-0013 (P9).

هذا التطبيق يقف بين المنصة والفيزياء: يستقبل أوامر العمل من المنصة
بنفس عقد `HttpLimsLab` حرفياً، ويحتفظ بها حتى ترفع جهة المختبر (سواقة
جهاز SiLA 2 أو إنسان عند الأجهزة الحقيقية) النتائج — **هنا تُوصَل
الأجهزة**: ما خلف نقطة الرفع هو الميدان، والبوابة أمين أرشيف لا مولّد.

صدقه البنيوي: **البوابة لا تختلق رقماً واحداً** — النتائج لا تدخل إلا
برفع صريح من جهة المختبر وتُخزَّن حرفياً كما وردت؛ التحقق الصارم من
العقد مسؤولية العميل (`HttpLimsLab`).

- التعرف مُكرَّم من الخادم نفسه: إعادة التقديم بالمفتاح نفسه تعيد أمر
  العمل الأصلي ولا تكرر الفحص الفيزيائي أبداً.
- دورة الحالة صريحة: `pending` عند التقديم → `running` بتشغيل مشغّل
  المختبر → `completed`/`failed` برفع النتائج أو الخطأ من الميدان.
- المصادقة Bearer (نفس عقد العميل): `PHARMA_SDL_GATEWAY_PLATFORM_KEY`
  لطرف المنصة و`PHARMA_SDL_GATEWAY_LAB_KEY` لطرف المختبر — مفتاحان
  مختلفان لدورين مختلفين؛ بلا مفتاح ⇒ وضع مفتوح للتطوير والاختبار.
- التخزين sqlite (stdlib خالص) — أوامر العمل تنجو من إعادة التشغيل.
"""

from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from pydantic import BaseModel, Field

from pharma_sdl import __version__

_STATUSES = ("pending", "running", "completed", "failed")
_TERMINAL = ("completed", "failed")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS batches (
    batch_id TEXT PRIMARY KEY,
    idempotency_key TEXT UNIQUE NOT NULL,
    payload TEXT NOT NULL,
    status TEXT NOT NULL,
    results TEXT,
    error_ar TEXT,
    error_en TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_gw_batches_status ON batches(status);
"""


def _utcnow() -> str:
    return datetime.now(UTC).isoformat()


class GatewayBatch(BaseModel):
    """أمر عمل واحد كما تراه الجهتان — النتائج بعد الرفع حصراً."""

    batch_id: str
    status: str
    n_assays: int
    results: list[dict] | None = None
    error_ar: str | None = None
    error_en: str | None = None


class GatewayBatchIn(BaseModel):
    """تقديم أمر عمل — عقد ADR-0013 من جهة المنصة."""

    idempotency_key: str = Field(min_length=1, max_length=128)
    assays: list[dict] = Field(min_length=1, max_length=500)


class GatewayResultsIn(BaseModel):
    """رفع من جهة المختبر — نتائج كما قيست أو خطأ كما وقع."""

    results: list[dict] | None = None
    error_ar: str | None = None
    error_en: str | None = None


class GatewayStore:
    """تخزين أوامر العمل — sqlite خالص، اتصال جديد لكل عملية (آمن خيوطياً)."""

    def __init__(self, db_path: str | Path) -> None:
        self.path = Path(db_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as con:
            con.executescript(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.path, check_same_thread=False)
        con.row_factory = sqlite3.Row
        return con

    def _to_batch(self, row: sqlite3.Row) -> GatewayBatch:
        payload = json.loads(row["payload"])
        return GatewayBatch(
            batch_id=row["batch_id"],
            status=row["status"],
            n_assays=len(payload.get("assays") or []),
            results=json.loads(row["results"]) if row["results"] else None,
            error_ar=row["error_ar"],
            error_en=row["error_en"],
        )

    def create(self, idempotency_key: str, payload: dict) -> tuple[GatewayBatch, bool]:
        """إنشاء أمر عمل — المفتاح نفسه يعيد الأمر الأصلي (created=False)."""
        with self._connect() as con:
            row = con.execute(
                "SELECT * FROM batches WHERE idempotency_key = ?", (idempotency_key,)
            ).fetchone()
            if row is not None:
                return self._to_batch(row), False
            batch_id = f"gw-{uuid.uuid4().hex[:12]}"
            now = _utcnow()
            con.execute(
                "INSERT INTO batches VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    batch_id,
                    idempotency_key,
                    json.dumps(payload, ensure_ascii=False),
                    "pending",
                    None,
                    None,
                    None,
                    now,
                    now,
                ),
            )
        return GatewayBatch(batch_id=batch_id, status="pending", n_assays=len(payload.get("assays") or [])), True

    def get(self, batch_id: str) -> GatewayBatch | None:
        with self._connect() as con:
            row = con.execute(
                "SELECT * FROM batches WHERE batch_id = ?", (batch_id,)
            ).fetchone()
            return self._to_batch(row) if row is not None else None

    def list(self, status: str | None = None) -> list[GatewayBatch]:
        with self._connect() as con:
            if status:
                rows = con.execute(
                    "SELECT * FROM batches WHERE status = ? ORDER BY created_at", (status,)
                ).fetchall()
            else:
                rows = con.execute("SELECT * FROM batches ORDER BY created_at").fetchall()
            return [self._to_batch(r) for r in rows]

    def _set_status(self, batch_id: str, status: str, *, results: str | None = None, error_ar: str | None = None, error_en: str | None = None) -> GatewayBatch:
        with self._connect() as con:
            con.execute(
                "UPDATE batches SET status = ?, results = ?, error_ar = ?, error_en = ?, updated_at = ?"
                " WHERE batch_id = ?",
                (status, results, error_ar, error_en, _utcnow(), batch_id),
            )
        return self.get(batch_id)  # type: ignore[return-value]

    def start(self, batch_id: str) -> GatewayBatch:
        """مشغّل المختبر يأخذ أمر العمل: pending/running → running."""
        batch = self.get(batch_id)
        if batch is None:
            raise KeyError(batch_id)
        if batch.status in _TERMINAL:
            raise ValueError(f"دفعة نهائية {batch.status} — لا عودة")
        return self._set_status(batch_id, "running")

    def upload_results(self, batch_id: str, results: list[dict]) -> GatewayBatch:
        """رفع نتائج من الميدان — تُخزَّن حرفياً كما وردت."""
        return self._set_status(batch_id, "completed", results=json.dumps(results, ensure_ascii=False))

    def upload_failure(self, batch_id: str, error_ar: str, error_en: str) -> GatewayBatch:
        return self._set_status(batch_id, "failed", error_ar=error_ar, error_en=error_en)


def create_gateway_app(
    platform_key: str | None = None,
    lab_key: str | None = None,
    store: GatewayStore | None = None,
) -> FastAPI:
    """مصنع البوابة — نسخة جديدة كاملة (صديقة للاختبارات والتشغيل المتعدد)."""
    platform_key = (
        platform_key
        if platform_key is not None
        else (os.getenv("PHARMA_SDL_GATEWAY_PLATFORM_KEY") or None)
    )
    lab_key = lab_key if lab_key is not None else (os.getenv("PHARMA_SDL_GATEWAY_LAB_KEY") or None)
    if store is None:
        from pharma_sdl.config import get_settings

        store = GatewayStore(get_settings().gateway_db)

    def _require(role: str):
        def dep(authorization: str | None = Header(default=None)) -> None:
            expected = platform_key if role == "platform" else lab_key
            if expected is None:  # وضع مفتوح — تطوير/اختبار فقط
                return
            if not authorization or not authorization.startswith("Bearer "):
                raise HTTPException(
                    status_code=401,
                    detail="مصادقة البوابة مطلوبة: Authorization: Bearer <key> / gateway auth required",
                )
            token = authorization.removeprefix("Bearer ").strip()
            if token == expected:
                return
            other = lab_key if role == "platform" else platform_key
            if other and token == other:
                raise HTTPException(
                    status_code=403,
                    detail="مفتاح دور آخر — هذا المسار لدور مختلف / key belongs to the other role",
                )
            raise HTTPException(status_code=401, detail="مفتاح بوابة غير صالح / invalid gateway key")

        return dep

    app = FastAPI(
        title="Pharma SDL — LIMS Reference Gateway",
        version=__version__,
        description="الجهة الأخرى من عقد ADR-0013 — أمين أوامر عمل لا مولّد بيانات",
    )

    def _validate_assays(assays: list[dict]) -> None:
        for i, assay in enumerate(assays):
            if not isinstance(assay, dict) or not str(assay.get("smiles") or "").strip():
                raise HTTPException(
                    status_code=422,
                    detail=f"فحص #{i} بلا smiles صالح — العقد يتطلبها / assay #{i} lacks valid smiles",
                )

    @app.get("/health")
    def health() -> dict:
        batches = store.list()
        return {
            "status": "ok",
            "role": "lims-gateway",
            "version": __version__,
            "auth_platform": platform_key is not None,
            "auth_lab": lab_key is not None,
            "counts": {s: sum(1 for b in batches if b.status == s) for s in _STATUSES},
        }

    @app.post("/batches", status_code=201, dependencies=[Depends(_require("platform"))])
    def submit_batch(body: GatewayBatchIn) -> GatewayBatch:
        _validate_assays(body.assays)
        batch, _created = store.create(body.idempotency_key, body.model_dump())
        # إعادة التقديم بالمفتاح نفسه تعيد الأمر الأصلي — التعرف مُكرَّم
        return batch

    @app.get("/batches", dependencies=[Depends(_require("platform"))])
    def list_batches(status: str | None = Query(default=None)) -> list[GatewayBatch]:
        if status is not None and status not in _STATUSES:
            raise HTTPException(status_code=422, detail="حالة غير معروفة / unknown status")
        return store.list(status)

    @app.get("/batches/{batch_id}", dependencies=[Depends(_require("platform"))])
    def get_batch(batch_id: str) -> GatewayBatch:
        batch = store.get(batch_id)
        if batch is None:
            raise HTTPException(
                status_code=404,
                detail=f"أمر عمل «{batch_id}» غير معروف / unknown work order {batch_id}",
            )
        return batch

    @app.post("/batches/{batch_id}/start", dependencies=[Depends(_require("lab"))])
    def start_batch(batch_id: str) -> GatewayBatch:
        try:
            return store.start(batch_id)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"أمر عمل غير معروف / unknown work order {batch_id}")
        except ValueError:
            raise HTTPException(
                status_code=409,
                detail="أمر عمل نهائي — لا عودة للحالة / terminal work order",
            )

    @app.post("/batches/{batch_id}/results", dependencies=[Depends(_require("lab"))])
    def upload_results(batch_id: str, body: GatewayResultsIn) -> GatewayBatch:
        batch = store.get(batch_id)
        if batch is None:
            raise HTTPException(status_code=404, detail=f"أمر عمل غير معروف / unknown work order {batch_id}")
        if batch.status in _TERMINAL:
            raise HTTPException(
                status_code=409,
                detail="أمر عمل نهائي — الرفع مرتين مرفوض / terminal work order",
            )
        if body.results is not None:
            if not body.results:
                raise HTTPException(
                    status_code=422, detail="رفع قائمة نتائج فارغة / empty results list"
                )
            _validate_assays(body.results)
            return store.upload_results(batch_id, body.results)
        if body.error_ar or body.error_en:
            return store.upload_failure(
                batch_id,
                body.error_ar or "فشل الفحص عند المختبر.",
                body.error_en or "Assay failed at the bench.",
            )
        raise HTTPException(
            status_code=422,
            detail="بلا نتائج وبلا خطأ — لا شيء يُخزَّن / neither results nor error",
        )

    return app


__all__ = ["GatewayBatch", "GatewayResultsIn", "GatewayStore", "create_gateway_app"]
