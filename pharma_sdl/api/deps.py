"""تبعيات FastAPI المشتركة — الإعدادات وخزّن المهام نسختان وحيدتان."""

from __future__ import annotations

from functools import lru_cache

from pharma_sdl.config import Settings, get_settings
from pharma_sdl.experiments.registry import ExperimentRegistry
from pharma_sdl.jobs.runner import JobStore, get_job_store


@lru_cache(maxsize=1)
def app_settings() -> Settings:
    return get_settings()


def job_store() -> JobStore:
    return get_job_store()


_registry: ExperimentRegistry | None = None


def experiment_registry() -> ExperimentRegistry:
    """نسخة وحيدة من السجل التجريبي الدائم على مسار الإعدادات."""
    global _registry
    if _registry is None:
        _registry = ExperimentRegistry(app_settings().experiments_db)
    return _registry
