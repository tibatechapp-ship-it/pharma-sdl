"""تبعيات FastAPI المشتركة — الإعدادات وخزّن المهام نسختان وحيدتان."""

from __future__ import annotations

from functools import lru_cache

from pharma_sdl.config import Settings, get_settings
from pharma_sdl.jobs.runner import JobStore, get_job_store


@lru_cache(maxsize=1)
def app_settings() -> Settings:
    return get_settings()


def job_store() -> JobStore:
    return get_job_store()
