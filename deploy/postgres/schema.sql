-- Pharma SDL — مخطط PostgreSQL للترقية من SQLite (ADR-0007).
-- الهدف: نفس محتوى data/experiments.sqlite3 وdata/jobs.sqlite3 على
-- خادم حقيقي عند تعدد المستخدمين — بلا تغيير في العقود أو الواجهات.
-- الاستخدام:
--   psql -f deploy/postgres/schema.sql
--   ثم استيراد JSONL المُصدَّر من pharma-sdl export-experiments
--   (سطر لكل تجربة — يُدرج في experiments.payload مباشرة).

-- ── سجل التجارب ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS experiments (
    experiment_id         TEXT PRIMARY KEY,
    created_at            TEXT NOT NULL,
    updated_at            TEXT NOT NULL,
    status                TEXT NOT NULL,            -- running | completed | failed
    target_id             TEXT,
    engine_used           TEXT,
    parent_experiment_id  TEXT REFERENCES experiments(experiment_id),
    -- payload = ExperimentRecord كاملاً (JSON) — نفس السطر المُصدَّر JSONL حرفياً
    payload               JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_experiments_created ON experiments(created_at);
CREATE INDEX IF NOT EXISTS idx_experiments_target  ON experiments(target_id);
CREATE INDEX IF NOT EXISTS idx_experiments_status  ON experiments(status);

-- ── طابور المهام ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS jobs (
    id             TEXT PRIMARY KEY,
    kind           TEXT NOT NULL,
    status         TEXT NOT NULL,                   -- pending | running | done | failed
    created_at     TEXT NOT NULL,
    started_at     TEXT,
    finished_at    TEXT,
    error          TEXT,
    detail         JSONB NOT NULL DEFAULT '{}',
    result_kind    TEXT,                            -- pydantic:module:Class | json:
    result_payload JSONB
);
CREATE INDEX IF NOT EXISTS idx_jobs_created ON jobs(created_at);
CREATE INDEX IF NOT EXISTS idx_jobs_status  ON jobs(status);

-- ملاحظة Celery/Redis (ADR-0007): عند تعدد المستخدمين أو المهام الطويلة
-- يُستبدل SQLiteJobStore بـ Celery worker على Redis broker — الواجهة
-- (submit/get/result_of/list) كما هي، فالترقية محلية في jobs/runner.py.
