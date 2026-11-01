"""طابور المهام الداخلي — حالياً in-memory بخيوط (ADR-0005).

يكفي لحجم v0.2.0 (جولات فرز ثوانٍ–دقائق، مستخدم علمي واحد). الترقيم
إلى Celery/Redis عند تعدد المستخدمين أو طول المهام — الواجهة هنا
(المعرّف + الحالة + النتيجة) لن تتغير، فالترقية محلية في هذا الملف.
"""

from __future__ import annotations

import threading
import time
import uuid
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from pharma_sdl.config import get_settings
from pharma_sdl.models import JobInfo


class JobStore:
    """خزّن مهام خيط-الآمن مع عامل تنفيذ خلفي وTTL تنظيف."""

    def __init__(self, max_workers: int = 2, ttl_seconds: int = 3600) -> None:
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._jobs: dict[str, JobInfo] = {}
        self._results: dict[str, Any] = {}
        self._lock = threading.Lock()
        self._ttl = ttl_seconds

    # ── واجهة القراءة ──
    def get(self, job_id: str) -> JobInfo | None:
        with self._lock:
            self._cleanup_locked()
            job = self._jobs.get(job_id)
            return job.model_copy(deep=True) if job else None

    def result_of(self, job_id: str) -> Any:
        with self._lock:
            return self._results.get(job_id)

    def list(self, kind: str | None = None) -> list[JobInfo]:
        with self._lock:
            self._cleanup_locked()
            jobs = [j for j in self._jobs.values() if kind is None or j.kind == kind]
        return sorted(jobs, key=lambda j: j.created_at, reverse=True)

    # ── واجهة التنفيذ ──
    def submit(self, kind: str, fn: Callable[..., Any], *args: Any) -> JobInfo:
        job = JobInfo(id=uuid.uuid4().hex[:12], kind=kind, status="pending")
        with self._lock:
            self._jobs[job.id] = job

        def _runner() -> None:
            with self._lock:
                current = self._jobs.get(job.id)
                if current is not None:
                    current.status = "running"
                    current.started_at = _now_iso()
            try:
                value = fn(*args)
                with self._lock:
                    self._results[job.id] = value
                    stored = self._jobs.get(job.id)
                    if stored is not None:
                        stored.status = "done"
                        stored.finished_at = _now_iso()
            except Exception as exc:  # noqa: BLE001 — الخطأ يُوثَّق ولا يُبتلع
                with self._lock:
                    stored = self._jobs.get(job.id)
                    if stored is not None:
                        stored.status = "failed"
                        stored.error = f"{type(exc).__name__}: {exc}"
                        stored.finished_at = _now_iso()

        self._executor.submit(_runner)
        with self._lock:
            stored = self._jobs[job.id]
            return stored.model_copy(deep=True)

    # ── التنظيف ──
    def _cleanup_locked(self) -> None:
        """حذف المهام المنتهية الأقدم من TTL — يجب حجز القفل خارجياً."""
        now = time.time()
        stale: list[str] = []
        for job_id, job in self._jobs.items():
            if job.status in {"done", "failed"} and job.finished_at:
                try:
                    from datetime import datetime

                    finished = datetime.fromisoformat(job.finished_at).timestamp()
                    if now - finished > self._ttl:
                        stale.append(job_id)
                except ValueError:  # pragma: no cover
                    continue
        for job_id in stale:
            self._jobs.pop(job_id, None)
            self._results.pop(job_id, None)


def _now_iso() -> str:
    from pharma_sdl.models import utcnow_iso

    return utcnow_iso()


_store: JobStore | None = None


def get_job_store() -> JobStore:
    """نسخة وحيدة من الخزّن بإعدادات المنصة."""
    global _store
    if _store is None:
        settings = get_settings()
        _store = JobStore(max_workers=2, ttl_seconds=settings.job_ttl_seconds)
    return _store
