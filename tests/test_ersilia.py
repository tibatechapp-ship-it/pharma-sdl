"""اختبارات عميل Ersilia — كلها بلا شبكة (نمط test_pgx.py).

النداء الحي لخادم محلي موسوم integration ولا يعمل في CI.
"""
import pytest

from core.clients import ersilia_client as ec
from core.clients.ersilia_client import (
    ADMET_LESSON,
    FALLBACK_REFERENCE,
    MODELS,
    AdmetRow,
    _extract_value,
    _iter_result_rows,
    _to_float,
    fallback_reference_df,
    predict_admet,
    predict_admet_batch,
    verdict,
)

# ── الكتالوج المُتحقَّق ──────────────────────────────────────


def test_verified_models_present():
    """النموذجان المُتحقَّق منهما في خارطة الطريق يجب أن يكونا في الكتالوج."""
    assert {"eos2ta5", "eos6oli"} <= set(MODELS)
    for model in MODELS.values():
        assert model.column_hint
        assert model.endpoint
        assert isinstance(model.low_good, bool)


def test_unknown_model_raises_value_error():
    """model_id مجهول = خطأ مبرمج (لا فشل شبكة) → استثناء صريح."""
    with pytest.raises(ValueError, match="unknown Ersilia model_id"):
        predict_admet("CCO", "eosXXXX")


def test_lesson_text_bilingual_and_formatted():
    for lang in ("ar", "en"):
        text = ADMET_LESSON[lang].format(
            hlow="0.1", hhigh="0.3", sgood="-2", sbad="-4"
        )
        assert "hERG" in text
        assert "SolTranNet" in text


# ── الأحكام التعليمية ────────────────────────────────────────


def test_herg_verdict_scale():
    assert verdict("eos2ta5", 0.05, "ar") == "خطر منخفض"
    assert verdict("eos2ta5", 0.2, "ar") == "منطقة رمادية — مراقبة"
    assert verdict("eos2ta5", 0.9, "ar") == "خطر مرتفع — فحوص QT"
    assert verdict("eos2ta5", 0.9, "en") == "High risk — QT follow-up"


def test_solubility_verdict_scale():
    assert verdict("eos6oli", -1.0, "ar") == "ذوبان جيد"
    assert verdict("eos6oli", -3.0, "ar") == "ذوبان متوسط"
    assert verdict("eos6oli", -6.0, "ar") == "ذوبان ضعيف — عقبة تطوير"
    assert verdict("eos6oli", -6.0, "en") == "Poor solubility — development risk"


# ── التفسير المرن ────────────────────────────────────────────


def test_to_float_variants():
    assert _to_float(0.5) == 0.5
    assert _to_float(" -3.2 ") == -3.2
    assert _to_float([1.23]) == 1.23
    assert _to_float({"score": 0.7}) == 0.7
    assert _to_float(True) is None  # bool ليس رقماً هنا
    assert _to_float("n/a") is None
    assert _to_float([1, 2]) is None  # قائمة متعددة ليست قيمة مفردة


def test_extract_value_prefers_known_column():
    model = MODELS["eos2ta5"]
    assert _extract_value({"input": "CCO", "score": 0.4}, model) == 0.4


def test_extract_value_falls_back_to_outcome_then_any():
    model = MODELS["eos2ta5"]
    assert _extract_value({"input": "CCO", "outcome": 0.8}, model) == 0.8
    assert _extract_value({"input": "CCO", "weird_col": 1.5}, model) == 1.5
    assert _extract_value({"input": "CCO", "score": "bad"}, model) is None


def test_iter_result_rows_shapes():
    assert _iter_result_rows([{"input": "CCO"}]) == [{"input": "CCO"}]
    assert _iter_result_rows({"outputs": [{"outcome": 1}]}) == [{"outcome": 1}]
    assert _iter_result_rows({"result": {"outcome": 1}}) == [{"outcome": 1}]
    assert _iter_result_rows({"input": "CCO", "score": 0.1}) == [
        {"input": "CCO", "score": 0.1}
    ]
    assert _iter_result_rows([]) == []
    assert _iter_result_rows("junk") == []


# ── predict_admet — mock بلا شبكة ───────────────────────────


class _FakeResp:
    def __init__(self, payload, ok=True):
        self._payload = payload
        self._ok = ok

    def raise_for_status(self):
        if not self._ok:
            raise ec.requests.HTTPError("500")

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


def test_predict_admet_mocked_standard_shape(monkeypatch):
    """الشكل الموثّق من standard_api.py: [{input, score}]."""
    monkeypatch.setattr(
        ec.requests,
        "post",
        lambda *a, **k: _FakeResp([{"input": "CCO", "score": 0.42}]),
    )
    row = predict_admet("CCO", "eos2ta5")
    assert isinstance(row, AdmetRow)
    assert row.value == 0.42
    assert row.smiles == "CCO"
    assert row.endpoint == "hERG_blockade_prob"
    assert row.verdict_en == "High risk — QT follow-up"


def test_predict_admet_mocked_value_column(monkeypatch):
    """eos6oli يُرجع عمود value — logS سالب يحمل حكم ذوبان جيد."""
    monkeypatch.setattr(
        ec.requests,
        "post",
        lambda *a, **k: _FakeResp([{"input": "CCO", "value": -1.3}]),
    )
    row = predict_admet("CCO", "eos6oli")
    assert row.value == -1.3
    assert row.verdict_ar == "ذوبان جيد"


def test_predict_admet_mocked_outputs_wrapper(monkeypatch):
    """شكل قديم ملفوف بـ outputs يُقبل أيضاً."""
    monkeypatch.setattr(
        ec.requests,
        "post",
        lambda *a, **k: _FakeResp({"outputs": [{"outcome": 0.9}]}),
    )
    row = predict_admet("CCO", "eos2ta5")
    assert row is not None and row.value == 0.9


def test_predict_admet_network_failure_returns_none(monkeypatch):
    """أي فشل شبكة → None (لا استثناءات تسقط التبويب)."""
    def boom(*a, **k):
        raise ec.requests.ConnectionError("offline")

    monkeypatch.setattr(ec.requests, "post", boom)
    assert predict_admet("CCO", "eos2ta5") is None


def test_predict_admet_bad_json_returns_none(monkeypatch):
    monkeypatch.setattr(
        ec.requests, "post", lambda *a, **k: _FakeResp(ValueError("not json"))
    )
    assert predict_admet("CCO", "eos2ta5") is None


def test_predict_admet_http_error_returns_none(monkeypatch):
    monkeypatch.setattr(
        ec.requests, "post", lambda *a, **k: _FakeResp([], ok=False)
    )
    assert predict_admet("CCO", "eos2ta5") is None


def test_predict_admet_non_numeric_value_returns_none(monkeypatch):
    monkeypatch.setattr(
        ec.requests,
        "post",
        lambda *a, **k: _FakeResp([{"input": "CCO", "score": "very high"}]),
    )
    assert predict_admet("CCO", "eos2ta5") is None


def test_predict_admet_respects_base_url_and_timeout(monkeypatch):
    seen: dict = {}

    def fake_post(url, json=None, timeout=None):
        seen["url"], seen["json"], seen["timeout"] = url, json, timeout
        return _FakeResp([{"input": "CCO", "score": 0.1}])

    monkeypatch.setattr(ec.requests, "post", fake_post)
    predict_admet("CCO", "eos2ta5", timeout=3.5, base_url="http://127.0.0.1:9999")
    assert seen["url"] == "http://127.0.0.1:9999/run"
    assert seen["json"] == [{"input": "CCO"}]
    assert seen["timeout"] == 3.5


def test_predict_admet_batch_partial_and_order(monkeypatch):
    """النجاح الجزئي: صفاً من ثلاثة يُرجعان، والترتيب محفوظ."""
    payload = [
        {"input": "CCO", "score": 0.1},
        {"input": "bad-row-without-value"},
        {"input": "c1ccccc1", "score": 0.5},
    ]
    monkeypatch.setattr(
        ec.requests, "post", lambda *a, **k: _FakeResp(payload)
    )
    rows = predict_admet_batch(
        ["CCO", "junk", "c1ccccc1", "  "], "eos2ta5"
    )
    assert [r.smiles for r in rows] == ["CCO", "c1ccccc1"]
    assert [r.value for r in rows] == [0.1, 0.5]


def test_predict_admet_batch_empty_input_skips_server(monkeypatch):
    def fail(*a, **k):
        raise AssertionError("must not call the server for empty input")

    monkeypatch.setattr(ec.requests, "post", fail)
    assert predict_admet_batch([], "eos2ta5") == []
    assert predict_admet_batch(["", "   "], "eos2ta5") == []


# ── المرجعية التعليمية المدمجة ───────────────────────────────


def test_fallback_reference_covers_both_models_bilingual():
    for model_id in MODELS:
        rows = FALLBACK_REFERENCE[model_id]
        assert len(rows) >= 3
        for r in rows:
            assert r.example_ar and r.example_en
            assert r.note_ar and r.note_en
        df_rows = fallback_reference_df(model_id, "ar")
        assert set(df_rows[0]) == {"مثال", "الفئة", "لماذا؟"}
        df_rows_en = fallback_reference_df(model_id, "en")
        assert set(df_rows_en[0]) == {"Example", "Category", "Why?"}


def test_herg_reference_tells_the_withdrawal_story():
    """الدرس الأشهر: تيرفينادين سُحب بسبب hERG — يجب أن يظهر في المرجعية."""
    rows = FALLBACK_REFERENCE["eos2ta5"]
    terf = next(r for r in rows if r.example_en == "Terfenadine")
    assert terf.category_ar.startswith("خطر مرتفع")
    assert "1997" in terf.note_ar  # سُحب من الأسواق 1997/1998


# ── نداء حي (لا يعمل في CI) ──────────────────────────────────


@pytest.mark.integration
def test_predict_admet_live_local_server_smoke():
    """يتطلب خادماً محلياً: ersilia serve eos2ta5 — ينجح بصمت إن غاب."""
    row = predict_admet("CC(=O)OC1=CC=CC=C1C(=O)O", "eos2ta5", timeout=5.0)
    if row is not None:
        assert 0.0 <= row.value <= 1.0
        assert row.endpoint == "hERG_blockade_prob"
