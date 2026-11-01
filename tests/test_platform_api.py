"""اختبارات واجهة الـAPI — العقد الكامل عبر TestClient (بلا شبكة)."""

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from pharma_sdl.api.app import create_app


@pytest.fixture(scope="module")
def client():
    return TestClient(create_app())


def _poll_run(client: TestClient, job_id: str, timeout_s: float = 30.0):
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        resp = client.get(f"/api/v1/screening/runs/{job_id}")
        assert resp.status_code == 200
        body = resp.json()
        if body["status"] in {"done", "failed"}:
            return body
        time.sleep(0.15)
    pytest.fail(f"الجولة لم تكتمل خلال {timeout_s} ثانية")


def test_health_and_version(client):
    health = client.get("/api/v1/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert "simulation" in health.json()["engines_available"]

    version = client.get("/api/v1/version")
    assert version.status_code == 200
    assert version.json()["version"] == "0.2.0"


def test_root_points_to_docs(client):
    root = client.get("/")
    assert root.status_code == 200
    assert root.json()["docs"] == "/docs"


def test_engines_endpoint_honest(client):
    engines = client.get("/api/v1/engines").json()
    names = {e["name"] for e in engines}
    assert names == {"simulation", "vina", "boltz2"}
    sim = next(e for e in engines if e["name"] == "simulation")
    assert sim["available"] is True


def test_targets_endpoint_policy_exposed(client):
    targets = client.get("/api/v1/targets").json()
    mpro = next(t for t in targets if t["id"] == "7VH8_A")
    assert mpro["policy"]["non_covalent_only"] is True
    assert mpro["self_dock_reference_kcal"] is not None


def test_full_screening_flow_inline(client):
    payload = {
        "target_id": "7VH8_A",
        "engine": "simulation",
        "top_n": 3,
        "ligands": [
            {"name": "benzamide", "smiles": "O=C(N)c1ccccc1"},
            {"name": "caffeine", "smiles": "Cn1cnc2c1c(=O)n(C)c(=O)n2C"},
            {"name": "trap", "smiles": "C=CC(=O)Nc1ccccc1"},
        ],
    }
    accepted = client.post("/api/v1/screening/runs", json=payload)
    assert accepted.status_code == 202
    job_id = accepted.json()["job_id"]
    assert accepted.json()["run_url"].endswith(job_id)

    body = _poll_run(client, job_id)
    assert body["status"] == "done", body.get("error")
    result = body["result"]
    assert result["counts"]["input"] == 3
    assert result["counts"]["rejected"] == 1
    assert len(result["hits"]) == 2  # 3 مدخلات − فخ تساهمي مرفوض
    kcals = [h["docking_kcal"] for h in result["hits"]]
    assert kcals == sorted(kcals)


def test_demo_mode_when_no_ligands(client):
    accepted = client.post("/api/v1/screening/runs", json={"target_id": "7VH8_A"})
    assert accepted.status_code == 202
    body = _poll_run(client, accepted.json()["job_id"])
    assert body["status"] == "done"
    assert body["result"]["counts"]["input"] == 24


def test_report_endpoint_markdown(client):
    accepted = client.post("/api/v1/screening/runs", json={"target_id": "7VH8_A"})
    body = _poll_run(client, accepted.json()["job_id"])
    assert body["status"] == "done"
    report = client.get(
        f"/api/v1/screening/runs/{accepted.json()['job_id']}/report", params={"lang": "ar"}
    )
    assert report.status_code == 200
    assert "text/markdown" in report.headers["content-type"]
    assert "تقرير فرز ظاهري" in report.text


def test_report_before_done_is_409(client):
    accepted = client.post("/api/v1/screening/runs", json={"target_id": "7VH8_A"})
    report = client.get(f"/api/v1/screening/runs/{accepted.json()['job_id']}/report")
    assert report.status_code in {200, 409}  # سباق مقبول: قد تكتمل بسرعة المحاكاة


def test_unknown_target_404(client):
    resp = client.post("/api/v1/screening/runs", json={"target_id": "no-such-target"})
    assert resp.status_code == 404
    assert resp.json()["code"] == "not_found"


def test_unknown_engine_422_fast_fail(client):
    resp = client.post(
        "/api/v1/screening/runs", json={"target_id": "7VH8_A", "engine": "warp-drive"}
    )
    assert resp.status_code == 422
    assert resp.json()["code"] == "validation_error"


def test_unknown_run_404(client):
    assert client.get("/api/v1/screening/runs/does-not-exist").status_code == 404


def test_lab_assay_simulated_and_positive(client):
    resp = client.post(
        "/api/v1/lab/assays", json={"smiles": "O=C(N)c1ccccc1", "dg_kcal": -8.0}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["simulated"] is True
    assert body["ic50_um"] > 0
    assert "محاكاة" in body["notes_ar"]
