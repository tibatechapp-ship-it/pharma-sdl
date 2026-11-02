"""اختبارات جسر الفيزياء (P8, ADR-0013) — عقد الدفعات وعميل LIMS بلا شبكة.

كل اختبار هنا يعمل على نقل مفبرك أو محاكاة حتمية — CI لا يلمس جهازاً
حقيقياً، والعقد نفسه هو ما يُختبر: ما يُقبَل وما يُرفض ولماذا.
"""

from __future__ import annotations

import json
import math

import pytest
from fastapi.testclient import TestClient

from pharma_sdl.api.app import create_app
from pharma_sdl.config import Settings
from pharma_sdl.errors import (
    LabError,
    LimsContractError,
    NotFoundError,
    ValidationError,
)
from pharma_sdl.lab import (
    BatchOutbox,
    HttpLimsLab,
    LabBatchClient,
    LimsSettings,
    SimulatedFretLab,
    make_lab_client,
)
from pharma_sdl.lab.interface import AssayRequest

# ── أدوات الفحص ──


class FakeTransport:
    """نقل مفبرك — يسجّل كل نداء ويعيد سيناريو مجدولاً بلا عالم خارجي."""

    def __init__(self, responses: list) -> None:
        self._responses = list(responses)
        self.calls: list[dict] = []

    def __call__(self, method: str, url: str, headers: dict, body: bytes | None):
        self.calls.append(
            {
                "method": method,
                "url": url,
                "headers": headers,
                "body": json.loads(body.decode("utf-8")) if body else None,
            }
        )
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        status, payload = item
        if isinstance(payload, bytes):
            return status, payload
        return status, json.dumps(payload).encode("utf-8")


def _lims(transport: FakeTransport, **kw) -> HttpLimsLab:
    settings = LimsSettings(
        base_url="http://gateway.test/api",
        token="secret-token",
        poll_interval_s=0.0,
        max_polls=3,
        **kw,
    )
    return HttpLimsLab(settings, transport=transport)


def _row(smiles: str = "CCO", ic50: float = 2.5, **extra) -> dict:
    row: dict = {"smiles": smiles, "ic50_um": ic50}
    ic50_ok = (
        isinstance(ic50, (int, float))
        and not isinstance(ic50, bool)
        and math.isfinite(ic50)
        and ic50 > 0
    )
    if "pic50_raw" in extra:
        row["pic50"] = extra.pop("pic50_raw")
    elif "pic50" not in extra and ic50_ok:
        row["pic50"] = round(-math.log10(ic50 * 1e-6), 3)
    row.update(extra)
    return row


R1 = AssayRequest(smiles="CCO", dg_kcal=-8.0)
R2 = AssayRequest(smiles="CC(=O)OC", dg_kcal=-6.5)

# ── المحاكاة تنفذ عقد الدفعات ──


def test_adapters_satisfy_batch_protocol():
    """المحولان ينفذان العقد نفسه — هذا هو الجسر كله في سطر."""
    assert isinstance(SimulatedFretLab(), LabBatchClient)
    assert isinstance(
        HttpLimsLab(LimsSettings(base_url="http://x")), LabBatchClient
    )


def test_simulated_batch_completes_immediately():
    lab = SimulatedFretLab()
    ticket = lab.submit_batch([R1, R2])
    assert ticket.status == "completed" and ticket.n_assays == 2
    poll = lab.poll_batch(ticket.batch_id)
    assert poll.status == "completed" and poll.results is not None
    assert len(poll.results) == 2
    assert all(r.simulated for r in poll.results)
    assert all(r.ic50_um is not None for r in poll.results)


def test_simulated_idempotent_resubmit():
    lab = SimulatedFretLab()
    t1 = lab.submit_batch([R1], idempotency_key="k-42")
    t2 = lab.submit_batch([R1], idempotency_key="k-42")
    assert t1.batch_id == t2.batch_id


def test_simulated_unknown_batch_raises_bilingually():
    lab = SimulatedFretLab()
    with pytest.raises(NotFoundError) as exc:
        lab.poll_batch("sim-nope")
    assert "غير معروفة" in str(exc.value)


# ── المصنع: نقطة التبديل الوحيدة ──


def test_factory_defaults_to_simulation():
    assert make_lab_client(Settings()).name == "simulated-fret"


def test_factory_switches_to_lims_when_configured():
    client = make_lab_client(Settings(lims_url="http://gw", lims_outbox=None))
    assert isinstance(client, HttpLimsLab)


def test_factory_wires_outbox_when_path_set(tmp_path):
    outbox_path = tmp_path / "ob.jsonl"
    client = make_lab_client(Settings(lims_url="http://gw", lims_outbox=outbox_path))
    assert client._outbox is not None and client._outbox.path == outbox_path


# ── عقد التقديم ──


def test_submit_sends_contract_request():
    tr = FakeTransport([(201, {"batch_id": "B-1", "status": "pending"})])
    ticket = _lims(tr).submit_batch([R1, R2])
    assert ticket.batch_id == "B-1" and ticket.status == "pending"
    call = tr.calls[0]
    assert call["method"] == "POST" and call["url"].endswith("/batches")
    assert call["headers"]["Authorization"] == "Bearer secret-token"
    assert call["headers"]["Idempotency-Key"]
    assert call["body"]["idempotency_key"] == call["headers"]["Idempotency-Key"]
    assert [a["smiles"] for a in call["body"]["assays"]] == ["CCO", "CC(=O)OC"]


def test_submit_custom_idempotency_key_is_stable():
    tr = FakeTransport([(201, {"batch_id": "B-9", "status": "pending"})])
    _lims(tr).submit_batch([R1], idempotency_key="run-7")
    assert tr.calls[0]["headers"]["Idempotency-Key"] == "run-7"


def test_submit_rejects_non_201():
    tr = FakeTransport([(500, {"error": "boom"})])
    with pytest.raises(LimsContractError) as exc:
        _lims(tr).submit_batch([R1])
    assert "500" in str(exc.value)


def test_submit_rejects_missing_batch_id():
    tr = FakeTransport([(201, {"status": "pending"})])
    with pytest.raises(LimsContractError):
        _lims(tr).submit_batch([R1])


def test_submit_rejects_unknown_status():
    tr = FakeTransport([(201, {"batch_id": "B", "status": "quantum"})])
    with pytest.raises(LimsContractError):
        _lims(tr).submit_batch([R1])


def test_submit_empty_batch_is_validation_error():
    with pytest.raises(ValidationError):
        _lims(FakeTransport([])).submit_batch([])


def test_network_failure_raises_lab_error_without_token():
    tr = FakeTransport([ConnectionRefusedError("no route")])
    with pytest.raises(LabError) as exc:
        _lims(tr).submit_batch([R1])
    assert "secret-token" not in str(exc.value)


def test_non_json_response_is_contract_violation():
    tr = FakeTransport([(200, b"<html>gateway error</html>")])
    with pytest.raises(LimsContractError):
        _lims(tr).poll_batch("B-1")


# ── عقد الاستطلاع ──


def _completed_lab(rows: list[dict], n: int = 2):
    tr = FakeTransport(
        [
            (201, {"batch_id": "B-1", "status": "pending"}),
            (200, {"batch_id": "B-1", "status": "running"}),
            (200, {"batch_id": "B-1", "status": "completed", "results": rows}),
        ]
    )
    lab = _lims(tr)
    ticket = lab.submit_batch([R1, R2] if n == 2 else [R1])
    poll = lab.poll_batch(ticket.batch_id)
    assert poll.status == "running" and poll.results is None
    return lab.poll_batch(ticket.batch_id)


def test_poll_completed_happy_path():
    poll = _completed_lab([_row("CCO"), _row("CC(=O)OC")])
    assert poll.status == "completed" and poll.results is not None
    assert all(not r.simulated for r in poll.results)
    assert poll.results[0].ic50_um == 2.5
    assert "UNVALIDATED" in poll.results[0].notes_en
    assert "ترقية بشرية" in poll.results[0].notes_ar


def test_poll_rejects_molecule_not_requested():
    with pytest.raises(LimsContractError) as exc:
        _completed_lab([_row("CCO"), _row("CNC")])  # CNC سليم لكنه لم يُطلَب
    assert "لم يُطلَب" in str(exc.value)


def test_poll_rejects_count_mismatch():
    with pytest.raises(LimsContractError) as exc:
        _completed_lab([_row("CCO")])  # دفعتان مقدَّمتان ونتيجة واحدة
    assert "عدد النتائج" in str(exc.value)


def test_poll_rejects_unparseable_smiles():
    with pytest.raises(LimsContractError):
        _completed_lab([_row("NOT_A_SMILES"), _row("CC(=O)OC")])


@pytest.mark.parametrize("bad", [0, -3.0, "high", None])
def test_poll_rejects_invalid_ic50(bad):
    with pytest.raises(LimsContractError):
        _completed_lab([_row("CCO", ic50=bad), _row("CC(=O)OC")])


def test_poll_rejects_inconsistent_pic50():
    with pytest.raises(LimsContractError) as exc:
        _completed_lab([_row("CCO", pic50_raw=1.0), _row("CC(=O)OC")])
    assert "pic50" in str(exc.value)


def test_poll_accepts_missing_pic50():
    rows = [_row("CCO"), {"smiles": "CC(=O)OC", "ic50_um": 4.0}]
    poll = _completed_lab(rows)
    assert poll.results is not None and poll.results[1].pic50 is None


def test_poll_rejects_simulated_true_from_real_gateway():
    with pytest.raises(LimsContractError) as exc:
        _completed_lab([_row("CCO", simulated=True), _row("CC(=O)OC")])
    assert "simulated" in str(exc.value)


def test_poll_qc_flags_survive_into_notes():
    poll = _completed_lab([_row("CCO", qc_flags=["borderline-curve"]), _row("CC(=O)OC")])
    assert poll.results is not None
    assert poll.results[0].notes_en.startswith("QC: borderline-curve")


def test_poll_failed_status_surfaces_error():
    tr = FakeTransport(
        [
            (201, {"batch_id": "B-2", "status": "pending"}),
            (200, {"batch_id": "B-2", "status": "failed", "error_en": "plate 3 crashed"}),
        ]
    )
    lab = _lims(tr)
    ticket = lab.submit_batch([R1])
    poll = lab.poll_batch(ticket.batch_id)
    assert poll.status == "failed" and poll.error_en == "plate 3 crashed"
    assert poll.results is None


def test_poll_unknown_status_rejected():
    tr = FakeTransport(
        [
            (201, {"batch_id": "B-3", "status": "pending"}),
            (200, {"batch_id": "B-3", "status": "teleported"}),
        ]
    )
    lab = _lims(tr)
    ticket = lab.submit_batch([R1])
    with pytest.raises(LimsContractError):
        lab.poll_batch(ticket.batch_id)


# ── راحة run_assay التزامنية فوق الدفعات ──


def test_run_assay_over_lims_happy_path():
    tr = FakeTransport(
        [
            (201, {"batch_id": "B-4", "status": "completed"}),
            (200, {"batch_id": "B-4", "status": "completed", "results": [_row("CCO")]}),
        ]
    )
    result = _lims(tr).run_assay(R1)
    assert result.simulated is False and result.ic50_um == 2.5


def test_run_assay_timeout_raises_instead_of_inventing():
    tr = FakeTransport(
        [
            (201, {"batch_id": "B-5", "status": "pending"}),
            (200, {"batch_id": "B-5", "status": "running"}),
            (200, {"batch_id": "B-5", "status": "running"}),
            (200, {"batch_id": "B-5", "status": "running"}),
        ]
    )
    with pytest.raises(LabError) as exc:
        _lims(tr).run_assay(R1)  # max_polls=3 من _lims
    assert "مهلة" in str(exc.value)


def test_run_assay_failed_batch_raises():
    tr = FakeTransport(
        [
            (201, {"batch_id": "B-6", "status": "failed"}),
            (200, {"batch_id": "B-6", "status": "failed", "error_ar": "انكسار لوحة"}),
        ]
    )
    with pytest.raises(LabError):
        _lims(tr).run_assay(R1)


# ── صندوق الصادر ──


def test_outbox_records_submit_and_polls(tmp_path):
    ob = BatchOutbox(tmp_path / "outbox.jsonl")
    tr = FakeTransport(
        [
            (201, {"batch_id": "B-7", "status": "pending"}),
            (200, {"batch_id": "B-7", "status": "running"}),
            (200, {"batch_id": "B-7", "status": "completed", "results": [_row("CCO"), _row("CC(=O)OC")]}),
        ]
    )
    lab = HttpLimsLab(
        LimsSettings(base_url="http://gw", poll_interval_s=0.0), transport=tr, outbox=ob
    )
    ticket = lab.submit_batch([R1, R2], idempotency_key="run-77")
    lab.poll_batch(ticket.batch_id)
    lab.poll_batch(ticket.batch_id)
    kinds = [e["kind"] for e in ob.events()]
    assert kinds == ["submit", "poll", "poll"]
    assert ob.events()[0]["idempotency_key"] == "run-77"
    assert ob.pending() == []  # الحالة النهائية بلغت — لا شيء معلّق


def test_outbox_pending_after_interruption(tmp_path):
    ob = BatchOutbox(tmp_path / "outbox.jsonl")
    tr = FakeTransport(
        [
            (201, {"batch_id": "B-8", "status": "pending"}),
            (200, {"batch_id": "B-8", "status": "pending"}),
        ]
    )
    lab = HttpLimsLab(
        LimsSettings(base_url="http://gw", poll_interval_s=0.0), transport=tr, outbox=ob
    )
    ticket = lab.submit_batch([R1], idempotency_key="run-88")
    lab.poll_batch(ticket.batch_id)
    pending = ob.pending()
    assert len(pending) == 1
    assert pending[0]["batch_id"] == ticket.batch_id
    assert pending[0]["idempotency_key"] == "run-88"


# ── الـAPI فوق الخلفية النشطة ──


@pytest.fixture(scope="module")
def client():
    return TestClient(create_app())


def test_api_backend_reports_simulation_honestly(client):
    resp = client.get("/api/v1/lab/backend")
    assert resp.status_code == 200
    body = resp.json()
    assert body["adapter"] == "simulated-fret"
    assert body["simulated"] is True and body["lims_configured"] is False
    assert "محاكاة" in body["note_ar"]


def test_api_batch_flow_with_simulated_backend(client):
    resp = client.post(
        "/api/v1/lab/batches",
        json={
            "assays": [
                {"smiles": "CCO", "dg_kcal": -8.0},
                {"smiles": "CC(=O)OC", "dg_kcal": -6.5},
            ],
            "idempotency_key": "api-k1",
        },
    )
    assert resp.status_code == 202
    body = resp.json()
    assert body["n_assays"] == 2 and body["simulated"] is True
    assert body["status"] == "completed"

    poll = client.get(f"/api/v1/lab/batches/{body['batch_id']}")
    assert poll.status_code == 200
    pbody = poll.json()
    assert pbody["status"] == "completed"
    assert len(pbody["results"]) == 2
    assert all(r["simulated"] for r in pbody["results"])
    assert all(r["ic50_um"] is not None for r in pbody["results"])


def test_api_unknown_batch_is_404(client):
    assert client.get("/api/v1/lab/batches/sim-does-not-exist").status_code == 404


def test_api_assay_endpoint_backward_compatible(client):
    resp = client.post("/api/v1/lab/assays", json={"smiles": "CCO", "dg_kcal": -8.0})
    assert resp.status_code == 200
    assert resp.json()["simulated"] is True


def test_api_rejects_empty_batch(client):
    resp = client.post("/api/v1/lab/batches", json={"assays": []})
    assert resp.status_code == 422
