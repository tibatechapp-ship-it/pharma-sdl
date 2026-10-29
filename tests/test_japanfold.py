"""اختبارات عميل JapanFold — كلها بلا شبكة (عقد مُتحقَّق من skill.md/openapi).

النداء الحي موسوم integration ولا يعمل في CI (يتطلب مفتاحاً ورصيداً).
"""
import pytest

from core.clients import japanfold as jf
from core.clients.japanfold import (
    REASON_BAD_SHAPE,
    REASON_DEADLINE,
    REASON_JOB_FAILED,
    REASON_NETWORK,
    REASON_NO_AFFINITY,
    REASON_NO_CREDIT,
    REASON_NO_KEY,
    REASON_OK,
    REASON_UNAUTHORIZED,
    boltz2_affinity,
    build_boltz_yaml,
    extract_affinity_fields,
    get_api_key,
    poll_job,
    submit_prediction,
)


class _FakeResp:
    def __init__(self, payload=None, status=200):
        self._payload = payload
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise jf.requests.HTTPError(str(self.status_code))

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


# ── المفتاح ─────────────────────────────────────────────────


def test_get_api_key_from_env(monkeypatch):
    monkeypatch.setenv("JAPANFOLD_API_KEY", "  jf_test_123  ")
    assert get_api_key() == "jf_test_123"  # يُنظَّف من الفراغات
    monkeypatch.delenv("JAPANFOLD_API_KEY")
    assert get_api_key() is None


# ── بناء Boltz YAML ─────────────────────────────────────────


def test_build_boltz_yaml_shape():
    yaml = build_boltz_yaml("MKTAYIAK", "CC(=O)Oc1ccccc1C(=O)O")
    assert "protein:" in yaml and "id: A" in yaml
    assert "sequence: MKTAYIAK" in yaml
    assert "ligand:" in yaml and "id: LIG" in yaml
    assert "ligand: CC(=O)Oc1ccccc1C(=O)O" in yaml
    assert "affinity:" in yaml and "binder: LIG" in yaml


def test_build_boltz_yaml_strips_fasta_header():
    yaml = build_boltz_yaml(">sp|P01308|INS\nGIVEQCCTSICSLYQLENYCN\n", "CCO")
    assert "sequence: GIVEQCCTSICSLYQLENYCN" in yaml
    assert ">" not in yaml


# ── submit ──────────────────────────────────────────────────


def test_submit_without_key_fails_fast(monkeypatch):
    """بلا مفتاح: لا نداء شبكة إطلاقاً — فشل فوري بسبب واضح."""
    monkeypatch.delenv("JAPANFOLD_API_KEY", raising=False)

    def fail(*a, **k):
        raise AssertionError("must not touch network without key")

    monkeypatch.setattr(jf.requests, "post", fail)
    job_id, reason = submit_prediction({"model": "boltz2"})
    assert job_id is None and reason == REASON_NO_KEY


def test_submit_success_returns_job_id(monkeypatch):
    seen: dict = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        seen.update(url=url, json=json, headers=headers)
        return _FakeResp({"id": "job_abc"})

    monkeypatch.setenv("JAPANFOLD_API_KEY", "k1")
    monkeypatch.setattr(jf.requests, "post", fake_post)
    job_id, reason = submit_prediction({"model": "boltz2"}, base_url="http://x")
    assert job_id == "job_abc" and reason == REASON_OK
    assert seen["url"] == "http://x/v1/predictions"
    assert seen["json"] == {"model": "boltz2"}
    assert seen["headers"]["Authorization"] == "Bearer k1"


def test_submit_401_and_402_reasons(monkeypatch):
    monkeypatch.setenv("JAPANFOLD_API_KEY", "k1")
    monkeypatch.setattr(
        jf.requests, "post", lambda *a, **k: _FakeResp({"detail": "bad"}, status=401)
    )
    assert submit_prediction({})[1] == REASON_UNAUTHORIZED
    monkeypatch.setattr(
        jf.requests, "post", lambda *a, **k: _FakeResp({"detail": "spent"}, status=402)
    )
    assert submit_prediction({})[1] == REASON_NO_CREDIT


def test_submit_network_and_shape_failures(monkeypatch):
    monkeypatch.setenv("JAPANFOLD_API_KEY", "k1")

    def boom(*a, **k):
        raise jf.requests.ConnectionError("offline")

    monkeypatch.setattr(jf.requests, "post", boom)
    assert submit_prediction({}) == (None, REASON_NETWORK)

    monkeypatch.setattr(jf.requests, "post", lambda *a, **k: _FakeResp({}))
    assert submit_prediction({}) == (None, REASON_BAD_SHAPE)


# ── poll ────────────────────────────────────────────────────


def test_poll_immediate_terminal(monkeypatch):
    monkeypatch.setenv("JAPANFOLD_API_KEY", "k1")
    job = {"status": "succeeded"}
    monkeypatch.setattr(
        jf.requests, "get", lambda *a, **k: _FakeResp(job)
    )
    got, reason = poll_job("j1", deadline_s=5, base_url="http://x")
    assert got == job and reason == REASON_OK


def test_poll_loops_until_succeeded(monkeypatch):
    monkeypatch.setenv("JAPANFOLD_API_KEY", "k1")
    states = iter(
        [_FakeResp({"status": "queued"}), _FakeResp({"status": "running"}),
         _FakeResp({"status": "succeeded"})]
    )
    monkeypatch.setattr(jf.requests, "get", lambda *a, **k: next(states))
    got, reason = poll_job("j1", deadline_s=30)
    assert got["status"] == "succeeded" and reason == REASON_OK


def test_poll_failed_job_carries_reason(monkeypatch):
    monkeypatch.setenv("JAPANFOLD_API_KEY", "k1")
    monkeypatch.setattr(
        jf.requests, "get", lambda *a, **k: _FakeResp({"status": "failed", "error": "oom"})
    )
    got, reason = poll_job("j1", deadline_s=5)
    assert got is None and REASON_JOB_FAILED in reason and "oom" in reason


def test_poll_deadline(monkeypatch):
    monkeypatch.setenv("JAPANFOLD_API_KEY", "k1")
    monkeypatch.setattr(
        jf.requests, "get", lambda *a, **k: _FakeResp({"status": "running"})
    )
    got, reason = poll_job("j1", deadline_s=0)
    assert got is None and reason == REASON_DEADLINE


def test_poll_network_failure(monkeypatch):
    monkeypatch.setenv("JAPANFOLD_API_KEY", "k1")

    def boom(*a, **k):
        raise jf.requests.Timeout("offline")

    monkeypatch.setattr(jf.requests, "get", boom)
    assert poll_job("j1", deadline_s=5) == (None, REASON_NETWORK)


# ── استخراج الارتباط ────────────────────────────────────────


def test_extract_affinity_fields_from_first_row():
    results = {
        "rows": [
            {"iptm": 0.8, "affinity": -6.2, "affinity_probability_binder": 0.9},
            {"affinity": -1.0},
        ]
    }
    fields = extract_affinity_fields(results)
    assert fields == {"affinity": -6.2, "affinity_probability_binder": 0.9}


def test_extract_affinity_fields_non_numeric_ignored():
    results = {"rows": [{"affinity": "strong", "affinity_probability": 0.5}]}
    assert extract_affinity_fields(results) == {"affinity_probability": 0.5}


def test_extract_affinity_fields_empty_shapes():
    assert extract_affinity_fields({}) == {}
    assert extract_affinity_fields({"rows": "junk"}) == {}
    assert extract_affinity_fields({"rows": [{"iptm": 0.9}]}) == {}


# ── الدورة الكاملة ──────────────────────────────────────────


def test_boltz2_affinity_full_cycle_mocked(monkeypatch):
    monkeypatch.setenv("JAPANFOLD_API_KEY", "k1")
    posts: list[dict] = []

    def fake_post(url, json=None, headers=None, timeout=None):
        posts.append(json or {})
        return _FakeResp({"id": "j42"})

    gets: list[str] = []

    def fake_get(url, params=None, headers=None, timeout=None):
        gets.append(url)
        if "/results" in url:
            return _FakeResp({"rows": [{"affinity": -7.1, "iptm": 0.6}]})
        return _FakeResp({"status": "succeeded"})

    monkeypatch.setattr(jf.requests, "post", fake_post)
    monkeypatch.setattr(jf.requests, "get", fake_get)
    fields, reason, job_id = boltz2_affinity(
        "MKTAYIAK", "CCO", base_url="http://x", deadline_s=30
    )
    assert fields == {"affinity": -7.1} and reason == REASON_OK and job_id == "j42"
    yaml_sent = posts[0]["input"]
    assert "ligand: CCO" in yaml_sent and "affinity:" in yaml_sent
    assert gets[0].startswith("http://x/v1/jobs/j42")


def test_boltz2_affinity_no_key_short_circuits(monkeypatch):
    monkeypatch.delenv("JAPANFOLD_API_KEY", raising=False)

    def fail(*a, **k):
        raise AssertionError("no network without key")

    monkeypatch.setattr(jf.requests, "post", fail)
    fields, reason, job_id = boltz2_affinity("MKT", "CCO")
    assert fields is None and reason == REASON_NO_KEY and job_id is None


def test_boltz2_affinity_no_affinity_in_results(monkeypatch):
    monkeypatch.setenv("JAPANFOLD_API_KEY", "k1")
    monkeypatch.setattr(
        jf.requests, "post", lambda *a, **k: _FakeResp({"id": "j7"})
    )

    def fake_get(url, *a, **k):
        if "/results" in url:
            return _FakeResp({"rows": [{"iptm": 0.5}]})
        return _FakeResp({"status": "succeeded"})

    monkeypatch.setattr(jf.requests, "get", fake_get)
    fields, reason, job_id = boltz2_affinity("MKT", "CCO", deadline_s=10)
    assert fields is None and reason == REASON_NO_AFFINITY and job_id == "j7"


# ── نداء حي (لا يعمل في CI — يتطلب مفتاحاً ورصيداً) ──────────


@pytest.mark.integration
def test_boltz2_affinity_live_smoke():
    """يتطلب JAPANFOLD_API_KEY ورصيداً — ينجح بصمت عندما لا يكون المفتاح موجوداً."""
    if get_api_key() is None:
        pytest.skip("JAPANFOLD_API_KEY not set")
    fields, reason, _job_id = boltz2_affinity(
        "GIVEQCCTSICSLYQLENYCN", "CC(=O)Oc1ccccc1C(=O)O", deadline_s=300.0
    )
    if reason == jf.REASON_OK:
        assert fields and all(isinstance(v, float) for v in fields.values())
