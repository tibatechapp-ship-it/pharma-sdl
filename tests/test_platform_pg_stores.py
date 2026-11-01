"""اختبارات المخازن الحية فوق PostgreSQL حقيقي (P3 — ADR-0008).

لا mocks: خادم PostgreSQL مضمّن فعلي (pgserver) يشغّل نفس عقود
ExperimentRegistry/SQLiteJobStore حرفياً — ثم مقارنة تكافؤ مباشرة مع
النسخة SQLite على نفس التسلسل. تُخطَّى بصدق إن غاب pgserver.
"""

from __future__ import annotations

import time

import pytest

from pharma_sdl.experiments.registry import ExperimentRecord

pgserver = pytest.importorskip("pgserver", reason="pgserver غير متاح — اختبارات PG تُخطَّى")


@pytest.fixture(scope="module")
def pg_dsn(tmp_path_factory):
    """عنقود PostgreSQL حقيقي لكل الوحدة — يُنشأ مرة ويُنظَّف في النهاية."""
    data = tmp_path_factory.mktemp("pgdata")
    server = pgserver.get_server(str(data))
    try:
        yield server.get_uri()
    finally:
        server.cleanup()


@pytest.fixture()
def clean_db(pg_dsn):
    """قاعدة نظيفة لكل اختبار — إسقاط الجداول بعد الاختبار (لا بقايا)."""
    import psycopg

    yield pg_dsn
    with psycopg.connect(pg_dsn, autocommit=True) as conn:
        conn.execute("DROP TABLE IF EXISTS jobs")
        conn.execute("DROP TABLE IF EXISTS experiments")


def _seed_record(target: str = "7VH8_A") -> ExperimentRecord:
    return ExperimentRecord(
        hypothesis_ar=f"فرضية اختبار على {target}",
        hypothesis_en="test hypothesis",
        question="ما ترتيب المكتبة؟",
        target_id=target,
        engine_used="simulation",
    )


def _run_experiment_contract(store) -> dict:
    """تسلسل قياسي موحد على أي خلفية — يعيد ما يلزم للمقارنة."""
    from pharma_sdl.validation.gate import ValidationState, default_card

    rec = _seed_record()
    store.begin(rec)
    store.complete(
        rec.experiment_id,
        counts={"input": 4, "screened": 4},
        top_hits=[
            {"rank": 1, "name": "أ", "smiles": "CCO", "kcal": -3.4},
            {"rank": 2, "name": "ب", "smiles": "CCC", "kcal": -2.8},
        ],
        warnings=["تنبيه اختبار"],
        elapsed_seconds=0.42,
        engine_used="simulation",
        method="simulation",
        lesson="درس موثق",
    )
    # فشل موثق كجزء من الذاكرة
    fail_rec = _seed_record("7CMD_A")
    store.begin(fail_rec)
    store.fail(fail_rec.experiment_id, "ValueError: ليغاند تالف")

    # بطاقة اعتماد محفوظة مع التجربة
    card = default_card(
        subject=f"experiment:{rec.experiment_id}",
        result_id=rec.experiment_id,
        engine="simulation",
        method="simulation",
        data_version="sha256:test",
        code_version="test-commit",
    )
    store.attach_validation(
        rec.experiment_id,
        card.model_copy(update={"state": ValidationState.COMPUTATIONALLY_VALIDATED}),
        reason="اختبار عقد",
    )
    done = store.get(rec.experiment_id)
    failed = store.get(fail_rec.experiment_id)
    return {
        "done": done,
        "failed": failed,
        "card_state": store.validation_card_of(rec.experiment_id).state,
        "stats": store.stats(),
        "vstats": store.validation_stats(),
        "count": store.count(),
        "latest": [r.experiment_id for r in store.latest(limit=5)],
        "latest_completed": [
            r.experiment_id for r in store.latest(limit=5, status="completed")
        ],
    }


def test_experiment_contract_matches_sqlite_parity(pg_dsn, clean_db, tmp_path):
    from pharma_sdl.experiments.pg_store import PostgresExperimentStore
    from pharma_sdl.experiments.registry import ExperimentRegistry

    pg = _run_experiment_contract(PostgresExperimentStore(pg_dsn))
    lite = _run_experiment_contract(ExperimentRegistry(tmp_path / "exp.sqlite3"))

    assert pg["done"].status == lite["done"].status == "completed"
    assert pg["done"].counts == lite["done"].counts
    assert pg["done"].top_hits == lite["done"].top_hits
    assert pg["done"].warnings == lite["done"].warnings
    assert pg["done"].lesson == lite["done"].lesson
    assert pg["failed"].status == "failed"
    assert "ليغاند تالف" in pg["failed"].error
    assert str(pg["card_state"]) == str(lite["card_state"]) == "ValidationState.COMPUTATIONALLY_VALIDATED"
    assert pg["stats"] == lite["stats"] == {"completed": 1, "failed": 1}
    assert pg["vstats"] == lite["vstats"] == {
        "UNVALIDATED": 1,
        "COMPUTATIONALLY_VALIDATED": 1,
    }
    assert pg["count"] == lite["count"] == 2
    # البنية متكافئة (المعرّفات UUID مستقلة لكل خلفية فلا تُقارن نصياً)
    assert len(pg["latest"]) == len(lite["latest"]) == 2
    assert len(pg["latest_completed"]) == len(lite["latest_completed"]) == 1


def test_lineage_and_restart_durability_on_postgres(pg_dsn, clean_db):
    from pharma_sdl.experiments.pg_store import PostgresExperimentStore

    first = PostgresExperimentStore(pg_dsn)
    r1 = _seed_record()
    first.begin(r1)
    first.complete(r1.experiment_id, counts={"input": 2}, top_hits=[])
    r2 = _seed_record()
    r2.parent_experiment_id = r1.experiment_id
    first.begin(r2)
    first.complete(r2.experiment_id, counts={"input": 2}, top_hits=[])

    chain = first.lineage(r2.experiment_id)
    assert [r.experiment_id for r in chain] == [r1.experiment_id, r2.experiment_id]

    # إعادة تشغيل افتراضية: نسخة جديدة على نفس الـDSN ترى كل شيء
    second = PostgresExperimentStore(pg_dsn)
    assert second.get(r1.experiment_id).status == "completed"
    assert [r.experiment_id for r in second.lineage(r2.experiment_id)] == [
        r1.experiment_id,
        r2.experiment_id,
    ]


def test_pg_job_store_contract_and_recovery(pg_dsn, clean_db):
    from pharma_sdl.jobs.pg_store import PostgresJobStore

    store = PostgresJobStore(pg_dsn)
    job = store.submit("screening", lambda: {"n": 3, "note": "قيمة عربية"})
    deadline = time.time() + 15
    while time.time() < deadline:
        if store.get(job.id).status in {"done", "failed"}:
            break
        time.sleep(0.05)
    assert store.get(job.id).status == "done"
    assert store.result_of(job.id) == {"n": 3, "note": "قيمة عربية"}
    assert store.stats() == {"done": 1}

    # نسخة جديدة = إعادة تشغيل: النتيجة تُستعاد
    restarted = PostgresJobStore(pg_dsn)
    assert restarted.get(job.id).status == "done"
    assert restarted.result_of(job.id) == {"n": 3, "note": "قيمة عربية"}

    # المقاطعة تُوثَّق لا تُخفى: running شبح يصبح failed بسبب معلن
    import psycopg

    with psycopg.connect(pg_dsn, autocommit=True) as conn:
        conn.execute(
            "INSERT INTO jobs (id, kind, status, created_at, detail) "
            "VALUES ('ghost-pg', 'screening', 'running', '2026-01-01', '{}')"
        )
    reopened = PostgresJobStore(pg_dsn)
    ghost = reopened.get("ghost-pg")
    assert ghost.status == "failed"
    assert "restart" in (ghost.error or "")


def test_pydantic_result_roundtrip_on_postgres(pg_dsn, clean_db):
    from pharma_sdl.jobs.pg_store import PostgresJobStore
    from pharma_sdl.models import ScreeningResult

    store = PostgresJobStore(pg_dsn)
    expected = ScreeningResult(
        run_id="pg-pyd-1",
        target_id="7VH8_A",
        target_label_ar="اختبار",
        target_label_en="test",
        engine_requested="simulation",
        engine_used="simulation",
    )
    job = store.submit("screening", lambda: expected)
    deadline = time.time() + 15
    while time.time() < deadline:
        if store.get(job.id).status in {"done", "failed"}:
            break
        time.sleep(0.05)
    restored = store.result_of(job.id)
    assert isinstance(restored, ScreeningResult)
    assert restored.run_id == "pg-pyd-1"


def test_factory_selects_postgres_backend(pg_dsn, clean_db, monkeypatch):
    from pharma_sdl.config import reset_settings
    from pharma_sdl.experiments import get_experiment_registry
    from pharma_sdl.experiments.pg_store import PostgresExperimentStore
    from pharma_sdl.jobs import reset_job_store
    from pharma_sdl.jobs.pg_store import PostgresJobStore
    from pharma_sdl.jobs.runner import get_job_store

    monkeypatch.setenv("PHARMA_SDL_STORE", "postgres")
    monkeypatch.setenv("PHARMA_SDL_PG_DSN", pg_dsn)
    reset_settings()
    reset_job_store()
    try:
        registry = get_experiment_registry()
        assert isinstance(registry, PostgresExperimentStore)
        assert isinstance(get_job_store(), PostgresJobStore)
    finally:
        reset_job_store()
        reset_settings()


def test_factory_rejects_postgres_without_dsn(monkeypatch):
    """لا DSN = خطأ صريح مُعلَّل — لا تخمين ولا سقوط غامض."""
    from pharma_sdl.config import reset_settings
    from pharma_sdl.errors import PlatformError
    from pharma_sdl.experiments import get_experiment_registry

    monkeypatch.setenv("PHARMA_SDL_STORE", "postgres")
    monkeypatch.delenv("PHARMA_SDL_PG_DSN", raising=False)
    reset_settings()
    try:
        with pytest.raises(PlatformError) as excinfo:
            get_experiment_registry()
        assert "PHARMA_SDL_PG_DSN" in excinfo.value.message_en
    finally:
        reset_settings()


def test_sqlite_backend_is_default(monkeypatch):
    from pharma_sdl.config import reset_settings
    from pharma_sdl.experiments import get_experiment_registry
    from pharma_sdl.experiments.registry import ExperimentRegistry

    monkeypatch.setenv("PHARMA_SDL_STORE", "sqlite")
    monkeypatch.setenv("PHARMA_SDL_EXPERIMENTS_DB", "/tmp/p3-factory-default/exp.sqlite3")
    reset_settings()
    try:
        assert isinstance(get_experiment_registry(), ExperimentRegistry)
    finally:
        reset_settings()


def test_jsonl_migration_sqlite_to_postgres(pg_dsn, clean_db, tmp_path):
    """الترقية الفعلية الموعودة في ADR-0007: حلقة كاملة من SQLite إلى PostgreSQL
    عبر JSONL — المعرّفات وسلسلة الأسلاف وحالات الاعتماد تنجو حرفياً."""
    from pharma_sdl.experiments.pg_store import PostgresExperimentStore
    from pharma_sdl.experiments.portability import export_jsonl, import_jsonl
    from pharma_sdl.experiments.registry import ExperimentRegistry
    from pharma_sdl.loop.closed_loop import run_closed_loop

    # 1) حلقة كاملة على SQLite
    lite_db = tmp_path / "migration.sqlite3"
    rounds = run_closed_loop(db_path=lite_db, top_n=2)
    assert len(rounds) == 3

    # 2) تصدير JSONL ثم استيراده في PostgreSQL الحي
    jsonl = tmp_path / "migration.jsonl"
    exported = export_jsonl(ExperimentRegistry(lite_db), jsonl)
    assert exported == 3
    pg = PostgresExperimentStore(pg_dsn)
    imported = import_jsonl(pg, jsonl)
    assert imported == 3

    # 3) سلسلة الأسلاف وحالات الاعتماد كما كُتبت في SQLite حرفياً
    last = rounds[-1]
    chain = pg.lineage(last.experiment_id)
    assert [r.experiment_id for r in chain] == [r.experiment_id for r in rounds]
    assert all(r.validation_state == "UNVALIDATED" for r in chain)
    assert pg.get(last.experiment_id).top_hits == last.top_hits
    assert pg.stats() == {"completed": 3}


def test_cli_migration_commands_accept_postgres_dsn(pg_dsn, clean_db, tmp_path, capsys):
    """الأوامر الموثقة في README تعمل حرفياً: export من SQLite ثم import بـDSN."""
    from pharma_sdl.cli import main as cli_main
    from pharma_sdl.loop.closed_loop import run_closed_loop

    lite_db = tmp_path / "cli-migration.sqlite3"
    rounds = run_closed_loop(db_path=lite_db, top_n=2)
    jsonl = tmp_path / "cli-migration.jsonl"

    exported = cli_main(["export-experiments", "--db", str(lite_db), "--out", str(jsonl)])
    assert exported == 0
    imported = cli_main(["import-experiments", "--db", pg_dsn, "--in", str(jsonl)])
    assert imported == 0

    from pharma_sdl.experiments.pg_store import PostgresExperimentStore

    pg = PostgresExperimentStore(pg_dsn)
    assert pg.count() == 3
    assert [r.experiment_id for r in pg.lineage(rounds[-1].experiment_id)] == [
        r.experiment_id for r in rounds
    ]
