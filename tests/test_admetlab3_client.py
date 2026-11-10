"""اختبارات عميل ADMETlab 3.0 — كلها بلا شبكة (نمط test_ersilia.py).

النداء الحي موسوم integration ولا يعمل في CI (خادم خارجي متقلب موثّق).
"""
import pytest

from core.clients import admetlab3_client as c
from core.clients.admet_ai_client import ML_TASKS
from core.clients.admetlab3_client import (
    CROSSWALK_TO_ADMET_AI,
    ENDPOINTS,
    EXPECTED_COLUMNS,
    REASON_BAD_SHAPE,
    REASON_EMPTY,
    REASON_NETWORK,
    REASON_RATE,
    REASON_SERVICE,
    REASON_UNAVAILABLE,
    AdmetLab3Batch,
    base_url,
    predict_admet_batch,
    washmol,
)

# ── الكتالوج الموثّق ─────────────────────────────────────────


def test_expected_columns_matches_official_csv():
    """الأعمدة الـ121 حرفياً من results.csv الرسمي — بلا أعمدة عرض الصور."""
    assert len(EXPECTED_COLUMNS) == 121
    for key in ("MW", "TPSA", "hERG", "Ames", "caco2", "NR-ER", "SR-p53"):
        assert key in EXPECTED_COLUMNS
    assert not any("highlightAtom" in k or k in ("smiles", "molstr") for k in EXPECTED_COLUMNS)


def test_endpoints_catalog_is_subset_of_documented_columns():
    """لا مفتاح مُخترع: كل بطاقة عرض موجودة في الأعمدة الموثّقة حصراً."""
    assert len(ENDPOINTS) >= 70
    for key, ep in ENDPOINTS.items():
        assert key in EXPECTED_COLUMNS, key
        assert ep.name_ar and ep.name_en
        assert ep.kind in {"physchem", "rule", "adme", "tox"}


def test_crosswalk_pairs_valid_on_both_sides():
    """كل زوج تقاطع صحيح الطرفين: مفتاح موثّق + مهمة ADMET-AI معروفة."""
    assert len(CROSSWALK_TO_ADMET_AI) == 34
    for key, task_id in CROSSWALK_TO_ADMET_AI.items():
        assert key in EXPECTED_COLUMNS
        assert task_id in ML_TASKS


def test_lesson_bilingual_and_formatted():
    for lang in ("ar", "en"):
        text = c.ADMETLAB3_LESSON[lang].format(n=34)
        assert "ADMETlab 3.0" in text
        assert "34" in text


# ── أدوات مساعدة ─────────────────────────────────────────────


class _FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


def _ok_payload(chunk):
    """استجابة ناجحة بالعقد الموثّق — قيم رقمية + غير صالح نصي."""
    rows = []
    for i, smi in enumerate(chunk):
        if smi == "BAD":
            rows.append({"smiles": smi, "MW": "Invalid Molecule", "TPSA": "Invalid Molecule"})
        else:
            rows.append({"smiles": smi, "MW": 318.1 + i, "TPSA": 80.05, "nHA": 5})
    return {
        "status": "success",
        "code": 200,
        "data": {
            "taskid": "tmpabc123",
            "number of all molecules": len(chunk),
            "number of valid molecules": sum(1 for r in rows if "Invalid" not in str(r.get("MW"))),
            "data": rows,
            "explanation": {"MW": "Molecular weight"},
        },
    }


# ── المسار السليم ────────────────────────────────────────────


def test_success_single_and_invalid_filtered():
    calls = []

    def fake_post(url, json=None, timeout=None):
        calls.append(url)
        return _FakeResponse(200, _ok_payload(json["SMILES"]))

    batch = predict_admet_batch(["CCO", "BAD"], _post=fake_post)
    assert isinstance(batch, AdmetLab3Batch)
    assert batch.ok and batch.reason is None
    assert batch.n_all == 2
    assert batch.n_valid == 1  # غير الصالح رُشِّح بصصدق
    assert [r.smiles for r in batch.results] == ["CCO"]
    assert batch.results[0].get("MW") == 318.1
    assert batch.results[0].get("TPSA") == 80.05
    assert batch.taskid == "tmpabc123"
    assert calls == [base_url() + "/api/admet"]


def test_get_returns_none_for_missing_key():
    def fake_post(url, json=None, timeout=None):
        return _FakeResponse(200, _ok_payload(json["SMILES"]))

    batch = predict_admet_batch(["CCO"], _post=fake_post)
    assert batch.results[0].get("nonexistent_key") is None


def test_batch_chunking_with_interval(monkeypatch):
    """أكثر من MAX_BATCH جزيء → دفعات متعددة بتباعد زمني (بوليصة ≤5 req/s)."""
    monkeypatch.setattr(c, "_MIN_INTERVAL_S", 0.0)  # لا ننتظر في الاختبار
    seen = []

    def fake_post(url, json=None, timeout=None):
        chunk = json["SMILES"]
        seen.append(len(chunk))
        return _FakeResponse(200, _ok_payload(chunk))

    n = c.MAX_BATCH + 5
    batch = predict_admet_batch([f"C{'C' * i}O" for i in range(n)], _post=fake_post)
    assert seen == [c.MAX_BATCH, 5]
    assert batch.ok and len(batch.results) == n


def test_empty_input_short_circuits_without_network():
    calls = []

    def fake_post(url, **kwargs):
        calls.append(url)
        raise AssertionError("لا نداء شبكة لإدخال فارغ")

    batch = predict_admet_batch(["", "   "], _post=fake_post)
    assert not calls
    assert batch.ok is False and batch.reason == REASON_EMPTY
    assert batch.results == []


# ── مسارات الفشل — العقد: لا استثناءات أبداً ─────────────────


def test_404_maps_to_endpoint_unavailable():
    """التدهور الموثّق حياً 2026-11-09: نقطة الحساب 404 — السبب قابل للبرمجة."""
    batch = predict_admet_batch(["CCO"], _post=lambda *a, **k: _FakeResponse(404, {}))
    assert batch.ok is False
    assert batch.reason == REASON_UNAVAILABLE
    assert batch.results == []
    assert REASON_UNAVAILABLE in c.REASON_MESSAGES_AR


def test_429_maps_to_rate_limited():
    batch = predict_admet_batch(["CCO"], _post=lambda *a, **k: _FakeResponse(429, {}))
    assert batch.reason == REASON_RATE and not batch.ok


def test_5xx_maps_to_service_error():
    batch = predict_admet_batch(["CCO"], _post=lambda *a, **k: _FakeResponse(502, {}))
    assert batch.reason == REASON_SERVICE and not batch.ok


def test_network_exception_never_raises():
    def boom(url, json=None, timeout=None):
        raise ConnectionError("offline")

    batch = predict_admet_batch(["CCO"], _post=boom)
    assert batch.ok is False and batch.reason == REASON_NETWORK
    assert batch.results == []


def test_unexpected_shape_maps_to_bad_response():
    batch = predict_admet_batch(
        ["CCO"], _post=lambda *a, **k: _FakeResponse(200, {"unexpected": True})
    )
    assert batch.reason == REASON_BAD_SHAPE and not batch.ok


# ── washmol — النقطة المتحقق منها حياً ───────────────────────


def test_washmol_success_canonicalizes():
    def fake_post(url, json=None, timeout=None):
        assert url == base_url() + "/api/washmol"
        return _FakeResponse(200, {"status": "success", "code": 200, "data": ["CC(=O)Oc1ccccc1C(=O)O"]})

    assert washmol("CC(=O)OC1=CC=CC=C1C(=O)O", _post=fake_post) == "CC(=O)Oc1ccccc1C(=O)O"


def test_washmol_failure_returns_none_never_raises():
    assert washmol("", _post=lambda *a, **k: None) is None
    batch_bad = washmol("CCO", _post=lambda *a, **k: _FakeResponse(503, {}))
    assert batch_bad is None

    def boom(url, json=None, timeout=None):
        raise TimeoutError("slow service")

    assert washmol("CCO", _post=boom) is None


# ── الإعدادات ────────────────────────────────────────────────


def test_base_url_env_override(monkeypatch):
    monkeypatch.setenv("PHARMA_SDL_ADMETLAB3_BASE", "http://mirror.local///")
    assert base_url() == "http://mirror.local"
    monkeypatch.delenv("PHARMA_SDL_ADMETLAB3_BASE")
    assert base_url() == "https://admetlab3.scbdd.com"


def test_reason_messages_cover_all_codes():
    """كل سبب فشل قابل للبرمجة له رسالة عربية صادقة للواجهة."""
    for reason in (REASON_EMPTY, REASON_NETWORK, REASON_RATE, REASON_UNAVAILABLE,
                   REASON_SERVICE, REASON_BAD_SHAPE):
        assert reason in c.REASON_MESSAGES_AR
        assert len(c.REASON_MESSAGES_AR[reason]) > 10


def test_reason_message_bilingual_and_safe():
    """المساعد ثنائي اللغة، والسبب المجهول يُعاد كما هو (لا اختراع نص)."""
    assert "404" in c.reason_message(REASON_UNAVAILABLE, "ar")
    assert "404" in c.reason_message(REASON_UNAVAILABLE, "en")
    assert c.reason_message(None, "ar") == ""
    assert c.reason_message("mystery_code", "ar") == "mystery_code"


# ── النداء الحي — integration فقط (خادم خارجي متقلب) ─────────


@pytest.mark.integration
def test_live_washmol_verification():
    """إعادة تشغيل خطوة التحقق الحية — لا تعمل في CI."""
    assert washmol("CC(=O)OC1=CC=CC=C1C(=O)O") == "CC(=O)Oc1ccccc1C(=O)O"
