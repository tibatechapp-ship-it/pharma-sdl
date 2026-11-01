"""طابور المهام الحي فوق PostgreSQL — نفس عقد SQLiteJobStore حرفياً.

النصف الثاني من وعد ADR-0007 المؤجَّل: نفس واجهة ADR-0005/0007
(`submit/get/result_of/list` + استرجاع المقاطع عند الإقلاع) خلف PostgreSQL —
بلا أي تغيير في العقود. يُختار عبر `PHARMA_SDL_STORE=postgres` مع
`PHARMA_SDL_PG_DSN`، وينصب مخططه ذاتياً مطابقاً لـdeploy/postgres/schema.sql.

نتائج المهام تُخزَّن JSONB بنفس ترميز النسخة SQLite
(`pydantic:module:Class` أو JSON صريح) — فانتقال الخلفيتين لا يغيّر ما يراه المستدعي.
"""

from __future__ import annotations

import importlib
import json
import time
import uuid
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from pharma_sdl.errors import PlatformError
from pharma_sdl.models import JobInfo, utcnow_iso

# مطابق حرفياً لجدول jobs في deploy/postgres/schema.sql.
_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id             TEXT PRIMARY KEY,
    kind           TEXT NOT NULL,
    status         TEXT NOT NULL,
    created_at     TEXT NOT NULL,
    started_at     TEXT,
    finished_at    TEXT,
    error          TEXT,
    detail         JSONB NOT NULL DEFAULT '{}',
    result_kind    TEXT,
    result_payload JSONB
);
CREATE INDEX IF NOT EXISTS idx_jobs_created ON jobs(created_at);
CREATE INDEX IF NOT EXISTS idx_jobs_status  ON jobs(status);
"""

_RESTART_ERROR = "interrupted by service restart — أُعيد التشغيل أثناء تنفيذ المهمة"


class PostgresJobStore:
    """خزّن مهام حي فوق PostgreSQL — نفس عقد الطابور الدائم بلا انحراف."""

    def __init__(self, dsn: str, max_workers: int = 2, ttl_seconds: int = 3600) -> None:
        if not dsn or not dsn.strip():
            raise PlatformError(
                "خلفية postgres تطلب PHARMA_SDL_PG_DSN صريحاً — لا اتصال افتراضي ولا تخمين",
                "postgres backend requires an explicit PHARMA_SDL_PG_DSN — "
                "no default connection and no guessing",
            )
        self.dsn = dsn.strip()
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._ttl = ttl_seconds
        try:
            import psycopg
        except ImportError as exc:  # pragma: no cover — بيئة بلا extras «pg»
            raise PlatformError(
                "خلفية postgres مطلوبة لكن psycopg غير مركَّب — ثبّتها بالأمر: "
                "pip install 'pharma-sdl[pg]'",
                "postgres backend requested but psycopg is not installed — "
                "install with: pip install 'pharma-sdl[pg]'",
            ) from exc
        self.psycopg = psycopg
        with self._connect() as conn:
            conn.execute(_SCHEMA)
        self._recover_interrupted()

    def _connect(self):
        from psycopg.rows import dict_row

        try:
            return self.psycopg.connect(
                self.dsn, autocommit=True, row_factory=dict_row, connect_timeout=10
            )
        except self.psycopg.OperationalError as exc:
            from pharma_sdl.errors import StoreUnavailableError

            raise StoreUnavailableError(
                f"طابور المهام غير قابل للوصول: فشل الاتصال بخادم PostgreSQL — {exc}",
                f"Job store unreachable: PostgreSQL connection failed — {exc}",
            ) from exc

    # ── التخزين ──────────────────────────────────────────────

    def _persist(self, job: JobInfo, result_encoded: tuple[str, str] | None) -> None:
        from psycopg.types.json import Json

        with self._connect() as conn:
            conn.execute(
                "INSERT INTO jobs (id, kind, status, created_at, started_at, finished_at, "
                "error, detail, result_kind, result_payload) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                "ON CONFLICT (id) DO UPDATE SET status = EXCLUDED.status, "
                "started_at = EXCLUDED.started_at, finished_at = EXCLUDED.finished_at, "
                "error = EXCLUDED.error, detail = EXCLUDED.detail, "
                "result_kind = EXCLUDED.result_kind, result_payload = EXCLUDED.result_payload",
                (
                    job.id,
                    job.kind,
                    job.status,
                    job.created_at,
                    job.started_at,
                    job.finished_at,
                    job.error,
                    Json(job.detail),
                    result_encoded[0] if result_encoded else None,
                    result_encoded[1] if result_encoded else None,
                ),
            )

    def _encode_result(self, value: Any) -> tuple[str, str] | None:
        """تشفير نتيجة قابل للاسترجاع الصادق — نفس ترميز النسخة SQLite."""
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

    def _decode_result(self, kind: str | None, payload: Any) -> Any:
        if kind is None or payload is None:
            return None
        raw = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)
        if kind == "json:":
            return json.loads(raw)
        if kind.startswith("pydantic:"):
            _, module, qualname = kind.split(":", 2)
            try:
                mod = importlib.import_module(module)
                target: Any = mod
                for part in qualname.split("."):
                    target = getattr(target, part)
                return target.model_validate_json(raw)
            except (ImportError, AttributeError, ValueError):
                return None
        return None

    @staticmethod
    def _row_to_job(row: dict) -> JobInfo:
        detail = row.get("detail") or {}
        if isinstance(detail, str):
            detail = json.loads(detail or "{}")
        return JobInfo(
            id=row["id"],
            kind=row["kind"],
            status=row["status"],  # type: ignore[arg-type]
            created_at=row["created_at"],
            started_at=row.get("started_at"),
            finished_at=row.get("finished_at"),
            error=row.get("error"),
            detail=detail,
        )

    def _recover_interrupted(self) -> None:
        """توثيق المقاطعة لا إخفاؤها — running/pending لحظة السقوط تصبح failed."""
        with self._connect() as conn:
            conn.execute(
                "UPDATE jobs SET status = 'failed', error = %s, finished_at = %s "
                "WHERE status IN ('pending','running')",
                (_RESTART_ERROR, utcnow_iso()),
            )

    # ── واجهة القراءة (نفس العقد) ────────────────────────────

    def get(self, job_id: str) -> JobInfo | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE id = %s", (job_id,)).fetchone()
        job = self._row_to_job(row) if row else None
        if job is not None:
            self._cleanup()
        return job

    def result_of(self, job_id: str) -> Any:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT result_kind, result_payload FROM jobs WHERE id = %s", (job_id,)
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
                    "SELECT * FROM jobs WHERE kind = %s ORDER BY created_at DESC", (kind,)
                ).fetchall()
        self._cleanup()
        return [self._row_to_job(r) for r in rows]

    def stats(self) -> dict[str, int]:
        """توزيع المهام على الحالات — عدّاد تشغيلي صادق للمقاييس."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT status, COUNT(*) AS n FROM jobs GROUP BY status"
            ).fetchall()
        return {r["status"]: int(r["n"]) for r in rows}

    # ── واجهة التنفيذ (نفس العقد) ────────────────────────────

    def submit(self, kind: str, fn: Callable[..., Any], *args: Any) -> JobInfo:
        job = JobInfo(id=uuid.uuid4().hex[:12], kind=kind, status="pending")
        self._persist(job, None)

        def _runner() -> None:
            job.status = "running"
            job.started_at = utcnow_iso()
            self._persist(job, None)
            try:
                value = fn(*args)
                encoded = self._encode_result(value)
                job.status = "done"
                job.finished_at = utcnow_iso()
                self._persist(job, encoded)
            except Exception as exc:  # noqa: BLE001 — الخطأ يُوثَّق ولا يُبتلع
                job.status = "failed"
                job.error = f"{type(exc).__name__}: {exc}"
                job.finished_at = utcnow_iso()
                self._persist(job, None)

        self._executor.submit(_runner)
        return job.model_copy(deep=True)

    # ── التنظيف ──────────────────────────────────────────────

    def _cleanup(self) -> None:
        """حذف المهام المنتهية الأقدم من TTL — دائم الكتابة، نظيف القراءة."""
        now = time.time()
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
                conn.execute(
                    "DELETE FROM jobs WHERE id = ANY(%s)", (stale,)
                )


__all__ = ["PostgresJobStore"]
