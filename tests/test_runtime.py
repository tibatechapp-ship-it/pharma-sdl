"""اختبارات كشف بيئة stlite (Hardening P2-2)."""
from __future__ import annotations

import sys
from types import ModuleType

from core.runtime import is_stlite


def test_full_python_runtime_is_not_stlite():
    """البيئة الكاملة (CPython) ليست stlite."""
    assert is_stlite() is False


def test_emscripten_platform_detected(monkeypatch):
    """sys.platform == emscripten → stlite (المسار الأساسي في Pyodide)."""
    monkeypatch.setattr(sys, "platform", "emscripten")
    assert is_stlite() is True


def test_pyodide_module_detected(monkeypatch):
    """وجود وحدة pyodide في sys.modules → stlite."""
    monkeypatch.setitem(sys.modules, "pyodide", ModuleType("pyodide"))
    assert is_stlite() is True
