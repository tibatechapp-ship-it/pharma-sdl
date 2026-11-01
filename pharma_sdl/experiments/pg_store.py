"""مخزن التجارب الحي فوق PostgreSQL — نفس عقد ExperimentRegistry حرفياً.

إكمال وعد ADR-0007 المؤجَّل («طريق PostgreSQL»): حين يتعدد المستخدمون أو
تشتّت النشر، تُبدَّل خلفية السجل التجريبي من SQLite إلى PostgreSQL **بلا أي
تغيير في العقود أو المستدعين** — نفس الدوال، نفس الدلالات، نفس حقول الإثبات.

الصدق بنيوياً:
    - psycopg تبعية اختيارية (extras «pg») — غيابها خطأ صريح مُعلَّل لا انهيار صامت.
    - المخطط يُنصَّب ذاتياً (CREATE TABLE IF NOT EXISTS) مطابقاً حرفياً
      لـdeploy/postgres/schema.sql — لا ترحيل يدوي ولا مفاجآت عند الإقلاع.
    - payload = ExperimentRecord كاملاً في عمود JSONB — نفس السطر المُصدَّر
      JSONL حرفياً، فالتصدير/الاستيراد بين الخلفيتين بلا تحويل.
    - كل عملية تفتح اتصالاً قصير العمر (autocommit) — آمنة بين الخيوط بلا
      pool ولا خدمات إضافية، بنفس روح نمط SQLite.
"""

from __future__ import annotations

import uuid

from pharma_sdl.errors import PlatformError
from pharma_sdl.experiments.registry import ExperimentRecord
from pharma_sdl.models import utcnow_iso
from pharma_sdl.validation.gate import ValidationCard, ValidationState

# مطابق حرفياً لجدول experiments في deploy/postgres/schema.sql —
# أي تعديل هناك يُقابَل هنا (المخزن ينصب المخطط ذاتياً عند الإقلاع).
_SCHEMA = """
CREATE TABLE IF NOT EXISTS experiments (
    experiment_id         TEXT PRIMARY KEY,
    created_at            TEXT NOT NULL,
    updated_at            TEXT NOT NULL,
    status                TEXT NOT NULL,
    target_id             TEXT,
    engine_used           TEXT,
    parent_experiment_id  TEXT REFERENCES experiments(experiment_id),
    payload               JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_experiments_created ON experiments(created_at);
CREATE INDEX IF NOT EXISTS idx_experiments_target  ON experiments(target_id);
CREATE INDEX IF NOT EXISTS idx_experiments_status  ON experiments(status);
"""


def _load_psycopg():
    """استيراد psycopg برسالة تثبيت صادقة — التبعية اختيارية لا مخفية."""
    try:
        import psycopg

        return psycopg
    except ImportError as exc:  # pragma: no cover — بيئة بلا extras «pg»
        raise PlatformError(
            "خلفية postgres مطلوبة لكن psycopg غير مركَّب — ثبّتها بالأمر: "
            "pip install 'pharma-sdl[pg]'",
            "postgres backend requested but psycopg is not installed — "
            "install with: pip install 'pharma-sdl[pg]'",
        ) from exc


class PostgresExperimentStore:
    """سجل تجارب حي فوق PostgreSQL — عقد ExperimentRegistry نفسه بلا انحراف."""

    def __init__(self, dsn: str) -> None:
        if not dsn or not dsn.strip():
            raise PlatformError(
                "خلفية postgres تطلب PHARMA_SDL_PG_DSN صريحاً — لا اتصال افتراضي ولا تخمين",
                "postgres backend requires an explicit PHARMA_SDL_PG_DSN — "
                "no default connection and no guessing",
            )
        self.dsn = dsn.strip()
        self.psycopg = _load_psycopg()
        # فشل الاتصال عند الإقلاع خطأ صريح — لا منصة «تعمل» على ذاكرة وهمية.
        with self._connect() as conn:
            conn.execute(_SCHEMA)

    def _connect(self):
        psycopg = self.psycopg
        from psycopg.rows import dict_row

        try:
            return psycopg.connect(
                self.dsn, autocommit=True, row_factory=dict_row, connect_timeout=10
            )
        except psycopg.OperationalError as exc:
            from pharma_sdl.errors import StoreUnavailableError

            raise StoreUnavailableError(
                f"سجل التجارب غير قابل للوصول: فشل الاتصال بخادم PostgreSQL — {exc}",
                f"Experiment store unreachable: PostgreSQL connection failed — {exc}",
            ) from exc

    # ── الكتابة (نفس دلالات registry.py حرفياً) ─────────────

    def _upsert(self, record: ExperimentRecord) -> None:
        from psycopg.types.json import Json

        # كائن JSON حقيقي في عمود JSONB — لا نص مضاعف الترميز: استعلامات
        # payload->>'...' تعمل، ونفس بنية سطر JSONL المُصدَّر (model_dump).
        payload = record.model_dump(mode="json")
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO experiments "
                "(experiment_id, created_at, updated_at, status, target_id, engine_used, "
                " parent_experiment_id, payload) VALUES (%s,%s,%s,%s,%s,%s,%s,%s) "
                "ON CONFLICT (experiment_id) DO UPDATE SET updated_at = EXCLUDED.updated_at, "
                "status = EXCLUDED.status, payload = EXCLUDED.payload",
                (
                    record.experiment_id,
                    record.created_at,
                    record.updated_at,
                    record.status,
                    record.target_id,
                    record.engine_used,
                    record.parent_experiment_id,
                    Json(payload),
                ),
            )

    def begin(self, record: ExperimentRecord) -> ExperimentRecord:
        """تسجيل تجربة جديدة بحالة running — قبل أي حساب."""
        self._upsert(record)
        return record

    def upsert(self, record: ExperimentRecord) -> ExperimentRecord:
        """كتابة سجل كامل كما هو — للاستيراد والنقل (يحفظ المعرّفات والتواريخ)."""
        self._upsert(record)
        return record

    def complete(
        self,
        experiment_id: str,
        *,
        counts: dict | None = None,
        top_hits: list[dict] | None = None,
        warnings: list[str] | None = None,
        elapsed_seconds: float = 0.0,
        engine_used: str | None = None,
        method: str | None = None,
        lesson: str | None = None,
    ) -> ExperimentRecord:
        record = self._require(experiment_id)
        record.status = "completed"
        record.updated_at = utcnow_iso()
        record.counts = counts or record.counts
        record.top_hits = top_hits or record.top_hits
        record.warnings = warnings or record.warnings
        record.elapsed_seconds = elapsed_seconds
        record.engine_used = engine_used or record.engine_used
        record.method = method or record.method
        record.lesson = lesson or record.lesson
        record.error = None
        self._upsert(record)
        return record

    def fail(self, experiment_id: str, error: str) -> ExperimentRecord:
        """فشل موثق — الإخفاق جزء من الذاكرة العلمية لا حذف منها."""
        record = self._require(experiment_id)
        record.status = "failed"
        record.updated_at = utcnow_iso()
        record.error = error
        self._upsert(record)
        return record

    def attach_validation(
        self, experiment_id: str, card: ValidationCard, reason: str | None = None
    ) -> ExperimentRecord:
        """ربط بطاقة بوابة الاعتماد بالتجربة — الترقية بشرية عبر gate.promote حصراً."""
        record = self._require(experiment_id)
        record.validation_state = card.state.value
        record.validation_card = card.model_dump(mode="json")
        if reason:
            record.lesson = f"{record.lesson or ''} — {reason}".strip(" —")
        record.updated_at = utcnow_iso()
        self._upsert(record)
        return record

    def validation_card_of(self, experiment_id: str) -> ValidationCard:
        """قراءة البطاقة المحفوظة — أو بطاقة UNVALIDATED مشتقة بصدق بلا تاريخ مُختلق."""
        from pharma_sdl.validation.gate import default_card

        record = self._require(experiment_id)
        if record.validation_card:
            return ValidationCard.model_validate(record.validation_card)
        try:
            state = ValidationState(record.validation_state)
        except ValueError:
            state = ValidationState.UNVALIDATED
        card = default_card(
            subject=f"experiment:{record.experiment_id}",
            result_id=record.experiment_id,
            engine=record.engine_used,
            method=record.method,
            data_version=record.data_version,
            code_version=record.code_version,
        )
        return card.model_copy(update={"state": state})

    def save_validation_card(
        self, experiment_id: str, card: ValidationCard
    ) -> ExperimentRecord:
        """حفظ بطاقة بعد ترقية/تخفيض بشري — الحالة النصية تُزامَن تلقائياً."""
        record = self._require(experiment_id)
        record.validation_card = card.model_dump(mode="json")
        record.validation_state = card.state.value
        record.updated_at = utcnow_iso()
        self._upsert(record)
        return record

    # ── القراءة (نفس العقد) ──────────────────────────────────

    def get(self, experiment_id: str) -> ExperimentRecord | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload FROM experiments WHERE experiment_id = %s",
                (experiment_id,),
            ).fetchone()
        if row is None:
            return None
        return ExperimentRecord.model_validate(row["payload"])

    def latest(self, limit: int = 10, status: str | None = None) -> list[ExperimentRecord]:
        sql = "SELECT payload FROM experiments"
        params: list = []
        if status:
            sql += " WHERE status = %s"
            params.append(status)
        sql += " ORDER BY created_at DESC, updated_at DESC LIMIT %s"
        params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [ExperimentRecord.model_validate(r["payload"]) for r in rows]

    def lineage(self, experiment_id: str) -> list[ExperimentRecord]:
        """سلسلة الأسلاف من الجذر إلى هذه التجربة — ذاكرة الحلقة تُقرأ كما كُتبت."""
        chain: list[ExperimentRecord] = []
        current = self.get(experiment_id)
        while current is not None:
            chain.append(current)
            current = (
                self.get(current.parent_experiment_id)
                if current.parent_experiment_id
                else None
            )
        return list(reversed(chain))

    def stats(self) -> dict[str, int]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT status, COUNT(*) AS n FROM experiments GROUP BY status"
            ).fetchall()
        return {r["status"]: int(r["n"]) for r in rows}

    def validation_stats(self) -> dict[str, int]:
        """توزيع حالات الاعتماد من الـpayload مباشرة — عدّاد تشغيلي صادق."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT payload->>'validation_state' AS state, COUNT(*) AS n "
                "FROM experiments GROUP BY state"
            ).fetchall()
        return {r["state"] or "unknown": int(r["n"]) for r in rows}

    def count(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS n FROM experiments").fetchone()
        return int(row["n"])

    # ── داخلي ────────────────────────────────────────────────

    def _require(self, experiment_id: str) -> ExperimentRecord:
        record = self.get(experiment_id)
        if record is None:
            from pharma_sdl.errors import NotFoundError

            raise NotFoundError(
                f"لا توجد تجربة بالمعرّف {experiment_id}",
                f"No experiment with id {experiment_id}",
            )
        return record


def new_experiment_id() -> str:
    """معرّف تجربة قياسي — نفس صيغة السجل الافتراضية (12 hex)."""
    return uuid.uuid4().hex[:12]


__all__ = ["PostgresExperimentStore", "new_experiment_id"]
