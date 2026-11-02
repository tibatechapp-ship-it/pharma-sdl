"""اختبارات الحلقة الفيزيائية (P9) — البوابة المرجعية ومسار القياسات.

الطرف-إلى-الطرف هنا حقيقي المعنى: عميل العقد (`HttpLimsLab`) يتحادث
البوابة المرجعية عبر دلالات HTTP كاملة، ثم تدخل القياسات المقبولة
ذاكرة المنصة (JSONL + سجل تجريبي دائم). لا جهاز في CI — والعقد هو
ما يُختبر من الجهتين.
"""

from __future__ import annotations

from urllib.parse import urlparse

import pytest
from fastapi.testclient import TestClient

from pharma_sdl.errors import ValidationError
from pharma_sdl.experiments.registry import ExperimentRegistry
from pharma_sdl.lab import (
    BatchOutbox,
    HttpLimsLab,
    LimsSettings,
    MeasurementIngestor,
    SimulatedFretLab,
    reconcile_batches,
    run_physical_confirmation,
    submit_confirmation_batch,
)
from pharma_sdl.lab.batch import BatchPoll
from pharma_sdl.lab.gateway_app import GatewayStore, create_gateway_app
from pharma_sdl.lab.interface import AssayRequest
from pharma_sdl.models import AssayResult

PLATFORM_KEY = "plat-key-1"
LAB_KEY = "lab-key-2"


def _auth(key: str) -> dict:
    return {"Authorization": f"Bearer {key}"}


@pytest.fixture()
def gw(tmp_path):
    """بوابة مرجعية بمفاتيح مفروكة — (عميل، مخزن)."""
    store = GatewayStore(tmp_path / "gw.sqlite3")
    app = create_gateway_app(platform_key=PLATFORM_KEY, lab_key=LAB_KEY, store=store)
    return TestClient(app), store


def _submit(client: TestClient, *, key: str = PLATFORM_KEY, idem: str = "k1", smiles: str = "CCO"):
    return client.post(
        "/batches",
        json={"idempotency_key": idem, "assays": [{"smiles": smiles, "dg_kcal": -8.0}]},
        headers=_auth(key),
    )


def _forward_transport(gw_client: TestClient):
    """نقل يحوّل نداءات HttpLimsLab إلى البوابة — دلالات HTTP كاملة."""

    def transport(method: str, url: str, headers: dict, body: bytes | None):
        parsed = urlparse(url)
        fwd_headers = {
            k: v
            for k, v in headers.items()
            if k.lower() not in {"content-type", "accept", "content-length", "host"}
        }
        resp = gw_client.request(method, parsed.path, content=body, headers=fwd_headers)
        return resp.status_code, resp.content

    return transport


# ── البوابة المرجعية ──


def test_gateway_health(gw):
    client, _ = gw
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["role"] == "lims-gateway"
    assert r.json()["auth_platform"] is True and r.json()["auth_lab"] is True


def test_gateway_submit_then_poll_pending(gw):
    client, _ = gw
    r = _submit(client)
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "pending" and body["n_assays"] == 1 and body["results"] is None
    g = client.get(f"/batches/{body['batch_id']}", headers=_auth(PLATFORM_KEY))
    assert g.status_code == 200 and g.json()["status"] == "pending"


def test_gateway_idempotent_replay_returns_same_work_order(gw):
    client, _ = gw
    r1 = _submit(client, idem="same-key")
    r2 = _submit(client, idem="same-key")
    assert r1.status_code == r2.status_code == 201
    assert r1.json()["batch_id"] == r2.json()["batch_id"]


def test_gateway_rejects_invalid_assays(gw):
    client, _ = gw
    assert (
        client.post(
            "/batches",
            json={"idempotency_key": "k", "assays": [{"smiles": "  "}]},
            headers=_auth(PLATFORM_KEY),
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/batches",
            json={"idempotency_key": "k2", "assays": []},
            headers=_auth(PLATFORM_KEY),
        ).status_code
        == 422
    )


def test_gateway_lifecycle_with_two_roles(gw):
    client, _ = gw
    bid = _submit(client, idem="life").json()["batch_id"]
    # المنصة لا تشغّل ولا ترفع — دور المختبر حصراً
    assert client.post(f"/batches/{bid}/start", headers=_auth(PLATFORM_KEY)).status_code == 403
    s = client.post(f"/batches/{bid}/start", headers=_auth(LAB_KEY))
    assert s.status_code == 200 and s.json()["status"] == "running"
    up = client.post(
        f"/batches/{bid}/results",
        json={"results": [{"smiles": "CCO", "ic50_um": 3.2}]},
        headers=_auth(PLATFORM_KEY),
    )
    assert up.status_code == 403
    up2 = client.post(
        f"/batches/{bid}/results",
        json={"results": [{"smiles": "CCO", "ic50_um": 3.2}]},
        headers=_auth(LAB_KEY),
    )
    assert up2.status_code == 200 and up2.json()["status"] == "completed"
    # الرفع مرتين مرفوض — أمر عمل نهائي
    assert (
        client.post(
            f"/batches/{bid}/results",
            json={"results": [{"smiles": "CCO", "ic50_um": 9.9}]},
            headers=_auth(LAB_KEY),
        ).status_code
        == 409
    )
    # النتائج كما رُفعت حرفياً — البوابة لا تعدّل شيئاً
    g = client.get(f"/batches/{bid}", headers=_auth(PLATFORM_KEY))
    assert g.json()["results"] == [{"smiles": "CCO", "ic50_um": 3.2}]


def test_gateway_failure_upload_marks_failed(gw):
    client, _ = gw
    bid = _submit(client, idem="fail1").json()["batch_id"]
    r = client.post(
        f"/batches/{bid}/results",
        json={"error_ar": "انكسار لوحة", "error_en": "plate crash"},
        headers=_auth(LAB_KEY),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "failed" and body["error_en"] == "plate crash"


def test_gateway_rejects_upload_with_neither_results_nor_error(gw):
    client, _ = gw
    bid = _submit(client, idem="none").json()["batch_id"]
    assert client.post(f"/batches/{bid}/results", json={}, headers=_auth(LAB_KEY)).status_code == 422


def test_gateway_auth_enforced_when_configured(gw):
    client, _ = gw
    assert (
        client.post(
            "/batches", json={"idempotency_key": "x", "assays": [{"smiles": "CCO"}]}
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/batches",
            json={"idempotency_key": "x", "assays": [{"smiles": "CCO"}]},
            headers=_auth("wrong-key"),
        ).status_code
        == 401
    )
    assert client.get("/batches/nope", headers=_auth(PLATFORM_KEY)).status_code == 404


def test_gateway_open_mode_when_unconfigured(tmp_path):
    app = create_gateway_app(store=GatewayStore(tmp_path / "g2.sqlite3"))
    client = TestClient(app)
    assert (
        client.post(
            "/batches", json={"idempotency_key": "k", "assays": [{"smiles": "CCO"}]}
        ).status_code
        == 201
    )
    assert client.get("/health").json()["auth_platform"] is False


def test_gateway_persists_across_restart(tmp_path):
    store = GatewayStore(tmp_path / "p.sqlite3")
    bid = TestClient(create_gateway_app(store=store)).post(
        "/batches", json={"idempotency_key": "k", "assays": [{"smiles": "CCO"}]}
    ).json()["batch_id"]
    # إعادة تشغيل على نفس الملف — أمر العمل لم يضيع
    g = TestClient(create_gateway_app(store=GatewayStore(tmp_path / "p.sqlite3"))).get(
        f"/batches/{bid}"
    )
    assert g.status_code == 200 and g.json()["status"] == "pending"


# ── مسار القياسات ──


def _poll_of(results: list[AssayResult], batch_id: str = "B-1", adapter: str = "lims-rest"):
    return BatchPoll(batch_id=batch_id, adapter=adapter, status="completed", results=tuple(results))


def test_ingest_refuses_simulated_results(tmp_path):
    ing = MeasurementIngestor(tmp_path / "m.jsonl")
    poll = _poll_of(
        [AssayResult(smiles="CCO", assay="simulated-fret", simulated=True, ic50_um=1.0)]
    )
    with pytest.raises(ValidationError):
        ing.ingest(poll)
    assert ing.measurements() == []


def test_ingest_refuses_incomplete_poll(tmp_path):
    ing = MeasurementIngestor(tmp_path / "m.jsonl")
    with pytest.raises(ValidationError):
        ing.ingest(BatchPoll(batch_id="B", adapter="a", status="running"))


def test_ingest_is_idempotent_per_batch(tmp_path):
    ing = MeasurementIngestor(tmp_path / "m.jsonl")
    poll = _poll_of([AssayResult(smiles="CCO", assay="lims-rest", simulated=False, ic50_um=2.5)])
    s1 = ing.ingest(poll)
    s2 = ing.ingest(poll)
    assert s1["ingested"] == 1
    assert s2 == {"batch_id": "B-1", "ingested": 0, "skipped": 1, "already_ingested": True}
    assert len(ing.measurements()) == 1


def test_by_smiles_keeps_latest_measurement(tmp_path):
    ing = MeasurementIngestor(tmp_path / "m.jsonl")
    ing.ingest(
        _poll_of([AssayResult(smiles="CCO", assay="a", simulated=False, ic50_um=2.5)], batch_id="B1")
    )
    ing.ingest(
        _poll_of([AssayResult(smiles="CCO", assay="a", simulated=False, ic50_um=4.0)], batch_id="B2")
    )
    assert ing.by_smiles()["CCO"]["ic50_um"] == 4.0


def test_ingest_writes_permanent_registry_record(tmp_path):
    reg = ExperimentRegistry(tmp_path / "e.sqlite3")
    ing = MeasurementIngestor(tmp_path / "m.jsonl", registry=reg)
    ing.ingest(
        _poll_of(
            [AssayResult(smiles="CCO", assay="lims-rest", simulated=False, ic50_um=2.5)],
            batch_id="B9",
        )
    )
    recs = reg.latest(5)
    assert len(recs) == 1
    rec = recs[0]
    assert rec.kind == "lab_batch" and rec.status == "completed"
    assert rec.parameters["lane"] == "physical_confirmation"
    assert rec.parameters["batch_id"] == "B9"
    assert rec.top_hits[0]["ic50_um"] == 2.5
    assert "UNVALIDATED" in (rec.lesson or "") or "ترقية بشرية" in (rec.lesson or "")


# ── الحلقة الفيزيائية ──


def test_confirmation_over_simulated_is_completed_but_never_ingested(tmp_path):
    ing = MeasurementIngestor(tmp_path / "m.jsonl")
    out = run_physical_confirmation(
        [{"smiles": "CCO", "name": "ethanol", "kcal": -8.0}], lab=SimulatedFretLab(), ingestor=ing
    )
    assert out["status"] == "completed" and out["simulated"] is True
    assert out["ingested"]["ingested"] == 0
    assert ing.measurements() == []  # المحاكاة لا تدخل القياسات أبداً


def test_submit_confirmation_requires_candidates():
    with pytest.raises(ValidationError):
        submit_confirmation_batch([], lab=SimulatedFretLab())


def test_reconcile_without_outbox_is_honestly_empty():
    assert reconcile_batches(lab=SimulatedFretLab()) == []


def test_end_to_end_platform_gateway_ingest(tmp_path, gw):
    """الدائرة كاملة: عميل العقد ↔ البوابة عبر HTTP، ثم بلع القياس للذاكرة."""
    client, _ = gw
    outbox = BatchOutbox(tmp_path / "ob.jsonl")
    lab = HttpLimsLab(
        LimsSettings(base_url="http://gateway.test", token=PLATFORM_KEY, poll_interval_s=0.0),
        transport=_forward_transport(client),
        outbox=outbox,
    )
    ticket = lab.submit_batch(
        [AssayRequest(smiles="CCO", dg_kcal=-8.0)], idempotency_key="e2e-1"
    )
    assert ticket.status == "pending"  # عند البوابة الآن
    bid = ticket.batch_id
    # جهة الميدان: تشغيل ثم رفع نتيجة فيزيائية
    assert client.post(f"/batches/{bid}/start", headers=_auth(LAB_KEY)).status_code == 200
    assert (
        client.post(
            f"/batches/{bid}/results",
            json={"results": [{"smiles": "CCO", "ic50_um": 2.5, "pic50": 5.602}]},
            headers=_auth(LAB_KEY),
        ).status_code
        == 200
    )
    # المنصة تستطلع عبر العقد — التحقق الصارم فوق HTTP حقيقي
    poll = lab.poll_batch(bid)
    assert poll.status == "completed"
    assert poll.results is not None and poll.results[0].simulated is False
    assert poll.results[0].ic50_um == 2.5
    # البلع إلى الذاكرة الدائمة
    reg = ExperimentRegistry(tmp_path / "e.sqlite3")
    ing = MeasurementIngestor(tmp_path / "m.jsonl", registry=reg)
    assert ing.ingest(poll)["ingested"] == 1
    assert reg.latest(5)[0].kind == "lab_batch"
    # التسوية بعدها: لا شيء معلّق
    assert reconcile_batches(lab, ing, outbox) == []


def test_reconcile_ingests_completed_and_reports_pending(tmp_path, gw):
    client, _ = gw
    outbox = BatchOutbox(tmp_path / "ob.jsonl")
    lab = HttpLimsLab(
        LimsSettings(base_url="http://gw", token=PLATFORM_KEY, poll_interval_s=0.0),
        transport=_forward_transport(client),
        outbox=outbox,
    )
    reg = ExperimentRegistry(tmp_path / "e.sqlite3")
    ing = MeasurementIngestor(tmp_path / "m.jsonl", registry=reg)
    t1 = lab.submit_batch([AssayRequest(smiles="CCO")], idempotency_key="r1")
    t2 = lab.submit_batch([AssayRequest(smiles="CC(=O)OC")], idempotency_key="r2")
    client.post(f"/batches/{t1.batch_id}/start", headers=_auth(LAB_KEY))
    client.post(
        f"/batches/{t1.batch_id}/results",
        json={"results": [{"smiles": "CCO", "ic50_um": 3.0}]},
        headers=_auth(LAB_KEY),
    )
    summary = reconcile_batches(lab, ing, outbox)
    by_id = {s["batch_id"]: s for s in summary}
    assert by_id[t1.batch_id]["status"] == "completed"
    assert by_id[t1.batch_id]["ingested"] == 1
    assert by_id[t2.batch_id]["status"] == "pending"  # لم يصل — يبقى معلّقاً بصدق
    assert len(reg.latest(5)) == 1


def test_run_physical_confirmation_submitted_state_over_lims(tmp_path, gw):
    client, _ = gw
    outbox = BatchOutbox(tmp_path / "ob.jsonl")
    lab = HttpLimsLab(
        LimsSettings(base_url="http://gw", token=PLATFORM_KEY, poll_interval_s=0.0),
        transport=_forward_transport(client),
        outbox=outbox,
    )
    out = run_physical_confirmation(
        [{"smiles": "CCO", "kcal": -8.0}], lab=lab, idempotency_key="run-x"
    )
    assert out["state"] == "submitted"
    assert "التسوية" in out["note_ar"] or "reconcile" in out["note_ar"]
    # والتقديم مُسطَّر في صندوق الصادر عبر lab نفسه
    assert len(outbox.pending()) == 1
