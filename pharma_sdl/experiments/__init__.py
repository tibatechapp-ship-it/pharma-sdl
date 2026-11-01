"""سجل التجارب الدائم — الذاكرة التجريبية للمنصة (P3: خلفيتان بنفس العقد).

- `ExperimentRegistry` — SQLite (الافتراضي، stdlib خالص).
- `PostgresExperimentStore` — PostgreSQL حي (ADR-0008) بنفس العقد حرفياً.
- `get_experiment_registry()` — المصنع الموحد وفق `PHARMA_SDL_STORE`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pharma_sdl.experiments.registry import (
    ExperimentRecord,
    ExperimentRegistry,
    code_version,
    dataset_fingerprint,
    hits_to_rows,
    ligands_fingerprint,
)

if TYPE_CHECKING:  # pragma: no cover — توثيق النمط فقط
    from pharma_sdl.experiments.pg_store import PostgresExperimentStore

__all__ = [
    "ExperimentRecord",
    "ExperimentRegistry",
    "code_version",
    "dataset_fingerprint",
    "get_experiment_registry",
    "hits_to_rows",
    "ligands_fingerprint",
]


def get_experiment_registry() -> ExperimentRegistry | PostgresExperimentStore:
    """المصنع الموحد للسجل التجريبي — الخلفية من الإعدادات، والعقد نفسه حرفياً.

    - `PHARMA_SDL_STORE=sqlite` (الافتراضي): ExperimentRegistry على مسار الإعدادات.
    - `PHARMA_SDL_STORE=postgres`: PostgresExperimentStore على `PHARMA_SDL_PG_DSN`
      — غياب DSN أو psycopg خطأ صريح مُعلَّل، لا انهيار غامض ولا ترقية صامتة.
    """
    from pharma_sdl.config import get_settings

    settings = get_settings()
    if settings.store_backend == "postgres":
        from pharma_sdl.experiments.pg_store import PostgresExperimentStore

        return PostgresExperimentStore(settings.pg_dsn or "")
    return ExperimentRegistry(settings.experiments_db)
