"""طابور المهام الدائم — SQLite خلف نفس واجهة ADR-0005 حرفياً.

ADR-0007 (ترقية ADR-0005): تقييم ما قبل P2 كشف أن الطابور in-memory يفقد
المهام والنتائج عند إعادة تشغيل الخدمة — تعارضاً جزئياً مع وعد «المنصة
الدائمة» بعد أن صار السجل التجريبي دائماً. الحل هنا بنفس نمط
`experiments/registry.py`: SQLite (stdlib خالص، خيط-آمن، WAL) بلا خدمات
خارجية، والواجهة (المعرّف + الحالة + النتيجة) **لم تتغير** — فالمستدعون
لا يعرفون الفرق، والترقية إلى Celery/Redis تبقى محلية في هذا الملف.

الذاكرة الصادقة عند الإقلاع:
    - المهام المكتملة (done/failed) تُستعاد كما كانت — نتائجها معها.
    - المهام التي كانت running/pending لحظة السقوط تُعلَّم `failed` بسبب
      موثق `interrupted by service restart` — لا انقطاع صامت.
"""

from __future__ import annotations

import importlib
import json
import sqlite3
import threading
import time
import uuid
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from pharma_sdl.config import get_settings
from pharma_sdl.models import JobInfo, utcnow_iso


class SQLiteJobStore:
    """خزّن مهام دائم فوق SQLite — نفس عقد JobStore القديم حرفياً."""

    def __init__(self, db_path: str | Path, max_workers: int = 2, ttl_seconds: int = 3600) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._lock = threading.Lock()
        self._ttl = ttl_seconds
        with self._connect() as conn:
            conn.executescript(_SCHEMA)
        self._recover_interrupted()

    # ── التخزين ──────────────────────────────────────────────

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.row_factory = sqlite3.Row
        return conn

    def _persist_locked(self, job: JobInfo, result_encoded: tuple[str, str] | None) -> None:
        """كتابة صف المهمة — يجب حجز القفل خارجياً عند الاستدعاء من خيوط."""
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO jobs (id, kind, status, created_at, started_at, finished_at, "
                "error, detail, result_kind, result_payload) "
                "VALUES (?,?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT(id) DO UPDATE SET status=excluded.status, "
                "started_at=excluded.started_at, finished_at=excluded.finished_at, "
                "error=excluded.error, detail=excluded.detail, "
                "result_kind=excluded.result_kind, result_payload=excluded.result_payload",
                (
                    job.id,
                    job.kind,
                    job.status,
                    job.created_at,
                    job.started_at,
                    job.finished_at,
                    job.error,
                    json.dumps(job.detail, ensure_ascii=False),
                    result_encoded[0] if result_encoded else None,
                    result_encoded[1] if result_encoded else None,
                ),
            )

    def _encode_result(self, value: Any) -> tuple[str, str] | None:
        """تشفير نتيجة قابل للاسترجاع الصادق — أو None بلا ادعاء."""
        if isinstance(value, BaseModel):
            cls = type(value)
            return (
                f"pydantic:{cls.__module__}:{cls.__qualname__}",
                value.model_dump_json(),
            )
        try:
            return ("json:", json.dumps(value, ensure_ascii=False))
        except (TypeError, ValueError):
            return None

    def _decode_result(self, kind: str | None, payload: str | None) -> Any:
        if kind is None or payload is None:
            return None
        if kind == "json:":
            return json.loads(payload)
        if kind.startswith("pydantic:"):
            _, module, qualname = kind.split(":", 2)
            try:
                mod = importlib.import_module(module)
                target: Any = mod
                for part in qualname.split("."):
                    target = getattr(target, part)
                return target.model_validate_json(payload)
            except (ImportError, AttributeError, ValueError):
                return None
        return None

    @staticmethod
    def _row_to_job(row: sqlite3.Row) -> JobInfo:
        return JobInfo(
            id=row["id"],
            kind=row["kind"],
            status=row["status"],  # type: ignore[arg-type]
            created_at=row["created_at"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
            error=row["error"],
            detail=json.loads(row["detail"] or "{}"),
        )

    def _recover_interrupted(self) -> None:
        """توثيق المقاطعة لا إخفاؤها — running/pending لحظة السقوط تصبح failed."""
        now = utcnow_iso()
        with self._connect() as conn:
            conn.execute(
                "UPDATE jobs SET status='failed', error=?, finished_at=? "
                "WHERE status IN ('pending','running')",
                ("interrupted by service restart — أُعيد التشغيل أثناء تنفيذ المهمة", now),
            )

    # ── واجهة القراءة (نفس العقد) ────────────────────────────

    def get(self, job_id: str) -> JobInfo | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        job = self._row_to_job(row) if row else None
        if job is not None:
            self._cleanup()
        return job

    def result_of(self, job_id: str) -> Any:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT result_kind, result_payload FROM jobs WHERE id = ?", (job_id,)
            ).fetchone()
        if row is None:
            return None
        return self._decode_result(row["result_kind"], row["result_payload"])

    def list(self, kind: str | None = None) -> list[JobInfo]:
        with self._connect() as conn:
            if kind is None:
                rows = conn.execute("SELECT * FROM jobs ORDER BY created_at DESC").fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM jobs WHERE kind = ? ORDER BY created_at DESC", (kind,)
                ).fetchall()
        self._cleanup()
        return [self._row_to_job(r) for r in rows]

    # ── واجهة التنفيذ (نفس العقد) ────────────────────────────

    def submit(self, kind: str, fn: Callable[..., Any], *args: Any) -> JobInfo:
        job = JobInfo(id=uuid.uuid4().hex[:12], kind=kind, status="pending")
        self._persist_locked(job, None)

        def _runner() -> None:
            job.status = "running"
            job.started_at = utcnow_iso()
            self._persist_locked(job, None)
            try:
                value = fn(*args)
                encoded = self._encode_result(value)
                job.status = "done"
                job.finished_at = utcnow_iso()
                self._persist_locked(job, encoded)
            except Exception as exc:  # noqa: BLE001 — الخطأ يُوثَّق ولا يُبتلع
                job.status = "failed"
                job.error = f"{type(exc).__name__}: {exc}"
                job.finished_at = utcnow_iso()
                self._persist_locked(job, None)

        self._executor.submit(_runner)
        return job.model_copy(deep=True)

    # ── التنظيف ──────────────────────────────────────────────

    def _cleanup(self) -> None:
        """حذف المهام المنتهية الأقدم من TTL — دائم الكتابة، نظيف القراءة."""
        now = time.time()
        with self._lock:
            with self._connect() as conn:
                rows = conn.execute(
                    "SELECT id, finished_at FROM jobs WHERE status IN ('done','failed') "
                    "AND finished_at IS NOT NULL"
                ).fetchall()
            stale: list[str] = []
            for row in rows:
                try:
                    finished = datetime.fromisoformat(row["finished_at"]).timestamp()
                    if now - finished > self._ttl:
                        stale.append(row["id"])
                except ValueError:  # pragma: no cover
                    continue
            if stale:
                with self._connect() as conn:
                    conn.executemany(
                        "DELETE FROM jobs WHERE id = ?", ((sid,) for sid in stale)
                    )


_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT,
    error TEXT,
    detail TEXT NOT NULL DEFAULT '{}',
    result_kind TEXT,
    result_payload TEXT
);
CREATE INDEX IF NOT EXISTS idx_jobs_created ON jobs(created_at);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
"""


# ‑‑ توافق خلفي: الاسم القديم يشير للمخزن الدائم — الواجهة واحدة ‑‑
JobStore = SQLiteJobStore

_store: JobStore | None = None
_store_lock = threading.Lock()


def get_job_store() -> JobStore:
    """نسخة وحيدة من الخزّن الدائم بإعدادات المنصة."""
    global _store
    if _store is None:
        with _store_lock:
            if _store is None:
                settings = get_settings()
                _store = SQLiteJobStore(
                    db_path=settings.jobs_db,
                    max_workers=2,
                    ttl_seconds=settings.job_ttl_seconds,
                )
    return _store


def reset_job_store() -> None:
    """لاختبارات فقط — إغلاق النسخة الوحيدة لتُبنى من جديد بإعدادات جديدة."""
    global _store
    with _store_lock:
        _store = None
