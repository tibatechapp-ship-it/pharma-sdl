"""تبعيات FastAPI المشتركة — الإعدادات وخزّن المهام نسختان وحيدتان."""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

from pharma_sdl.config import Settings, get_settings
from pharma_sdl.experiments.registry import ExperimentRegistry
from pharma_sdl.jobs.runner import JobStore, get_job_store

if TYPE_CHECKING:  # pragma: no cover — توثيق النمط فقط
    from pharma_sdl.experiments.pg_store import PostgresExperimentStore


@lru_cache(maxsize=1)
def app_settings() -> Settings:
    return get_settings()


def job_store() -> JobStore:
    """الطابور الموحد — sqlite أو postgres وفق الإعدادات (P3)، العقد نفسه."""
    return get_job_store()


_registry: ExperimentRegistry | PostgresExperimentStore | None = None


def experiment_registry() -> ExperimentRegistry | PostgresExperimentStore:
    """نسخة وحيدة من السجل التجريبي — الخلفية من المصنع الموحد (P3).

    إعادة ضبط `deps._registry = None` في الاختبارات تُعيد البناء على خلفية
    الاختبار (نفس العقد الراسخ منذ P1 — لا تغيير في سلوك المعزولة).
    """
    global _registry
    if _registry is None:
        from pharma_sdl.experiments import get_experiment_registry

        _registry = get_experiment_registry()
    return _registry


__all__ = ["app_settings", "experiment_registry", "job_store"]
