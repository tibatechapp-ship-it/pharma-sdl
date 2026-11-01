"""اختبارات الطابور الدائم (ADR-0007) — تقييم #2: لا مهام تضيع بعد إعادة التشغيل."""

from __future__ import annotations

import time
from pathlib import Path

from pharma_sdl.jobs.runner import SQLiteJobStore
from pharma_sdl.models import ScreeningResult


def _make_result(run_id: str) -> ScreeningResult:
    return ScreeningResult(
        run_id=run_id,
        target_id="7VH8_A",
        target_label_ar="اختبار",
        target_label_en="test",
        engine_requested="simulation",
        engine_used="simulation",
    )


def _wait_done(store: SQLiteJobStore, job_id: str, timeout_s: float = 10.0):
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        job = store.get(job_id)
        if job and job.status in {"done", "failed"}:
            return job
        time.sleep(0.05)
    raise AssertionError("المهمة لم تكتمل خلال المهلة")


def test_result_persists_across_store_instances(tmp_path: Path):
    db = tmp_path / "jobs.sqlite3"
    first = SQLiteJobStore(db)
    job = first.submit("screening", lambda: _make_result("persist-1"))
    done = _wait_done(first, job.id)
    assert done.status == "done"

    # نسخة جديدة على نفس القاعدة — إعادة تشغيل خدمة افتراضية
    second = SQLiteJobStore(db)
    assert second.get(job.id).status == "done"
    restored = second.result_of(job.id)
    assert isinstance(restored, ScreeningResult)
    assert restored.run_id == "persist-1"


def test_interrupted_running_job_is_documented_not_hidden(tmp_path: Path):
    db = tmp_path / "jobs.sqlite3"
    SQLiteJobStore(db)
    import sqlite3

    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO jobs (id,kind,status,created_at,started_at,finished_at,error,detail) "
        "VALUES ('ghost-1','screening','running','2026-01-01','2026-01-01',NULL,NULL,'{}')"
    )
    conn.commit()
    conn.close()

    reopened = SQLiteJobStore(db)
    ghost = reopened.get("ghost-1")
    assert ghost.status == "failed"
    assert "restart" in (ghost.error or "")


def test_list_returns_copies_not_live_references(tmp_path: Path):
    store = SQLiteJobStore(tmp_path / "jobs.sqlite3")
    job = store.submit("screening", lambda: _make_result("copy-1"))
    _wait_done(store, job.id)
    listings = store.list(kind="screening")
    assert listings
    listings[0].status = "hacked"
    assert store.get(job.id).status == "done"


def test_json_results_roundtrip_and_unknown_ids(tmp_path: Path):
    store = SQLiteJobStore(tmp_path / "jobs.sqlite3")
    job = store.submit("analysis", lambda: {"n_hits": 5, "note": "قيمة عربية"})
    _wait_done(store, job.id)
    assert store.result_of(job.id) == {"n_hits": 5, "note": "قيمة عربية"}
    assert store.get("no-such-id") is None
    assert store.result_of("no-such-id") is None


def test_failed_job_keeps_error_documented(tmp_path: Path):
    store = SQLiteJobStore(tmp_path / "jobs.sqlite3")

    def boom() -> ScreeningResult:
        raise RuntimeError("انفجار مقصود للاختبار")

    job = store.submit("screening", boom)
    done = _wait_done(store, job.id)
    assert done.status == "failed"
    assert "RuntimeError" in (done.error or "")
    # بعد إعادة التشغيل يبقى الفشل موثقاً
    reopened = SQLiteJobStore(tmp_path / "jobs.sqlite3")
    assert reopened.get(job.id).status == "failed"
