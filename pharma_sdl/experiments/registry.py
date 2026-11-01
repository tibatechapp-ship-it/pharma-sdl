"""سجل التجارب الدائم — الذاكرة التجريبية للمنصة.

التدقيق P1: نتائج الفرز لا تضيع بعد إعادة تشغيل الخدمة بعد الآن. كل تجربة
تُحفظ في SQLite (stdlib خالص — بلا خدمات خارجية) بحقول الإثبات الكاملة:

    experiment_id · hypothesis (سؤال علمي) · target · engine_used · method
    data_version (بصمة sha256 للمدخلات) · code_version (git commit)
    parameters · status · top_hits · warnings · elapsed_seconds
    validation_state · parent_experiment_id (سلسلة الحلقة) · lesson

«الفائدة» المعلنة: يعرف الباحث لماذا اختلف نتيجتان، ويعيد تجربة سابقة،
وتبدأ الجولة التالية من حيث انتهت الأولى — لا من الصفر.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
import threading
import uuid
from pathlib import Path

from pydantic import BaseModel, Field

from pharma_sdl.models import utcnow_iso
from pharma_sdl.validation.gate import ValidationCard, ValidationState

REPO_ROOT = Path(__file__).resolve().parent.parent

_SCHEMA = """
CREATE TABLE IF NOT EXISTS experiments (
    experiment_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    status TEXT NOT NULL,
    target_id TEXT,
    engine_used TEXT,
    parent_experiment_id TEXT,
    payload TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_experiments_created ON experiments(created_at);
CREATE INDEX IF NOT EXISTS idx_experiments_target ON experiments(target_id);
CREATE INDEX IF NOT EXISTS idx_experiments_status ON experiments(status);
"""


class ExperimentRecord(BaseModel):
    """سجل تجربة واحد كامل — الإعدادات والنتائج وأسباب القرار معاً."""

    experiment_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    created_at: str = Field(default_factory=utcnow_iso)
    updated_at: str = Field(default_factory=utcnow_iso)
    status: str = "running"  # running | completed | failed
    kind: str = "screening"
    hypothesis_ar: str
    hypothesis_en: str = ""
    question: str | None = None  # السؤال العلمي الذي تجيب عنه التجربة
    target_id: str | None = None
    engine_used: str | None = None
    method: str | None = None
    data_version: str | None = None  # بصمة المدخلات — يعرف الباحث لماذا اختلف اثنان
    code_version: str | None = None  # git commit — قابلية إعادة الإنتاج
    parameters: dict = Field(default_factory=dict)
    counts: dict[str, int] = Field(default_factory=dict)
    top_hits: list[dict] = Field(default_factory=list)  # rank/name/smiles/kcal
    warnings: list[str] = Field(default_factory=list)
    elapsed_seconds: float = 0.0
    validation_state: str = ValidationState.UNVALIDATED.value
    # بطاقة الاعتماد كاملة (dict من ValidationCard) — التاريخ والمنطق والمرفقات
    # تُحفظ مع التجربة، فـ«لماذا رُقّيت؟» يُجاب من السجل لا من ذاكرة ناقصة (P2).
    validation_card: dict | None = None
    parent_experiment_id: str | None = None  # الحلقة: من أي تجربة انطلقت
    lesson: str | None = None  # ماذا تعلمنا وما بقي غير مؤكد
    error: str | None = None


def code_version() -> str:
    """git commit القصير للمستودع — أو قيمة بيئة صريحة، أو 'unknown' بصدق."""
    env = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if env.returncode == 0 and env.stdout.strip():
        return env.stdout.strip()
    import os

    return os.getenv("PHARMA_SDL_CODE_VERSION", "unknown")


def dataset_fingerprint(path: str | Path) -> str:
    """بصمة sha256 مقتطعة لملف بيانات — أي اختلاف مدخلات يصير مرئياً."""
    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()[:16]


def ligands_fingerprint(smiles_list: list[str]) -> str:
    """بصمة مجموعة ليغاندات (الترتيب لا يهم) — إثبات هوية مدخلات الجولة."""
    canonical = sorted(s.strip() for s in smiles_list)
    return "sha256:" + hashlib.sha256("::".join(canonical).encode()).hexdigest()[:16]


class ExperimentRegistry:
    """سجل دائم فوق SQLite — خيط-آمن، WAL، بلا خدمات خارجية."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.row_factory = sqlite3.Row
        return conn

    # ── الكتابة ──────────────────────────────────────────────

    def _upsert(self, record: ExperimentRecord) -> None:
        payload = record.model_dump_json()
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO experiments "
                "(experiment_id, created_at, updated_at, status, target_id, engine_used, "
                " parent_experiment_id, payload) VALUES (?,?,?,?,?,?,?,?) "
                "ON CONFLICT(experiment_id) DO UPDATE SET updated_at=excluded.updated_at, "
                "status=excluded.status, payload=excluded.payload",
                (
                    record.experiment_id,
                    record.created_at,
                    record.updated_at,
                    record.status,
                    record.target_id,
                    record.engine_used,
                    record.parent_experiment_id,
                    payload,
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
        counts: dict[str, int] | None = None,
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
        """ربط حالة بوابة الاعتماد بالتجربة — الترقية تبقى بشرية عبر gate.promote.

        البطاقة كاملة (التاريخ والمرفقات والمنطق) تُحفظ مع التجربة — لا نص حالة مجرّد.
        """
        record = self._require(experiment_id)
        record.validation_state = card.state.value
        record.validation_card = card.model_dump(mode="json")
        if reason:
            record.lesson = f"{record.lesson or ''} — {reason}".strip(" —")
        record.updated_at = utcnow_iso()
        self._upsert(record)
        return record

    def validation_card_of(self, experiment_id: str) -> ValidationCard:
        """قراءة البطاقة المحفوظة — أو بطاقة UNVALIDATED افتراضية مشتقة من السجل.

        الاشتقاق صادق: لا يخترع تاريخاً ولا مرفقات — إن لم تُحفظ بطاقة فالسجل
        لا يدّعي أن ترقيات حصلت.
        """
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
        """حفظ بطاقة بعد ترقية/تخفيض بشري — الحالة النصية تُزامن تلقائياً."""
        record = self._require(experiment_id)
        record.validation_card = card.model_dump(mode="json")
        record.validation_state = card.state.value
        record.updated_at = utcnow_iso()
        self._upsert(record)
        return record

    # ── القراءة ──────────────────────────────────────────────

    def get(self, experiment_id: str) -> ExperimentRecord | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload FROM experiments WHERE experiment_id = ?",
                (experiment_id,),
            ).fetchone()
        return ExperimentRecord.model_validate_json(row["payload"]) if row else None

    def latest(self, limit: int = 10, status: str | None = None) -> list[ExperimentRecord]:
        sql = "SELECT payload FROM experiments"
        params: tuple = ()
        if status:
            sql += " WHERE status = ?"
            params = (status,)
        sql += " ORDER BY created_at DESC, updated_at DESC LIMIT ?"
        with self._connect() as conn:
            rows = conn.execute(sql, (*params, limit)).fetchall()
        return [ExperimentRecord.model_validate_json(r["payload"]) for r in rows]

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

    def stats(self) -> dict:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT status, COUNT(*) AS n FROM experiments GROUP BY status"
            ).fetchall()
        return {r["status"]: r["n"] for r in rows}

    def validation_stats(self) -> dict[str, int]:
        """توزيع حالات الاعتماد — عدّاد تشغيلي صادق (P3 /metrics).

        json_extract متاح في SQLite المدمجة حديثاً؛ وعند غيابه يُعدّ من
        الـpayload مباشرة — العدّاد صادق بأي حال، والترتيب ثابت.
        """
        try:
            with self._connect() as conn:
                rows = conn.execute(
                    "SELECT json_extract(payload, '$.validation_state') AS state, "
                    "COUNT(*) AS n FROM experiments GROUP BY state ORDER BY state"
                ).fetchall()
            return {r["state"] or "unknown": int(r["n"]) for r in rows}
        except sqlite3.OperationalError:  # pragma: no cover — SQLite قديمة بلا JSON1
            counts: dict[str, int] = {}
            with self._connect() as conn:
                rows = conn.execute("SELECT payload FROM experiments").fetchall()
            for row in rows:
                state = json.loads(row["payload"]).get("validation_state") or "unknown"
                counts[state] = counts.get(state, 0) + 1
            return dict(sorted(counts.items()))

    def count(self) -> int:
        """إجمالي التجارب في السجل — بلا تحميل payloads."""
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


def hits_to_rows(result) -> list[dict]:
    """تحويل قائمة ScoredHit إلى صفوف تخزين قياسية في السجل."""
    return [
        {
            "rank": h.rank,
            "name": h.name,
            "smiles": h.canonical_smiles,
            "inchikey": h.inchikey,
            "kcal": h.docking_kcal,
            "method": h.method,
        }
        for h in result.hits
    ]


def dumps(obj) -> str:
    """مساعد JSON موحد للسجلات المخزنة داخل الحقول."""
    return json.dumps(obj, ensure_ascii=False, sort_keys=True)


__all__ = [
    "ExperimentRecord",
    "ExperimentRegistry",
    "code_version",
    "dataset_fingerprint",
    "dumps",
    "hits_to_rows",
    "ligands_fingerprint",
]
