"""عميل JapanFold — أول API موحّد غير متزامن للنماذج الحيوية المفتوحة.

نتيجة خطوة التحقق (2026-10-29 — من الدليل الرسمي skill.md و openapi.json):

- القاعدة: https://api.japanfold.aiand.com (متغير بيئة JAPANFOLD_BASE_URL)
- المفتاح: **مطلوب** في كل مسار — Authorization: Bearer $JAPANFOLD_API_KEY
  (المفتاح من japanfold.aiand.com/account/token؛ حساب جديد برصيد 100$،
  والفوترة لكل ساعة معالج — لا نطبع المفتاح ولا نضمّنه في الكود أبداً)
- الإرسال: POST /v1/predictions  JSON: {"model": "boltz2", "name": ..., "sequence": ...}
  أو "input": <FASTA/YAML> أو "targets": [...] (شاشة دفعة واحدة)
- الانتظار: GET /v1/jobs/{id}?wait=60 — نداء محتجَز (RFC 7240) بلا sleep
- النتائج: GET /v1/jobs/{id}/results → rows تحمل confidence_score / complex_plddt /
  iptm وحقول affinity — والأرشيف /v1/jobs/{id}/archive
- الأخطاء: RFC 9457 problem+json (401 sign_in_required / 402 out_of_credit)
- النماذج: boltz2 (MSA + ليغاندات + **affinity**)، esmfold2/-fast، openfold3،
  openbind، rf3، opendde/-abag، af2ig — وكلها **بروتينية**: تصميم/طي بروتين
  وروابط ببتيدية/جسم مضاد، وليست توليد جزيئات صغيرة SMILES.

لذلك دوره الصحيح في pharma-sdl: **Boltz-2 كتحقق خارجي مستقل لطاقة ربط Vina**
(ترافق بروتين+ليغاند مع رأس affinity) — لا «توسيع مكتبة جزيئات»؛ تلك
تُنفَّذ محلياً (BRICS) وحياً (تشابه PubChem) في core/expander.py.
"""
from __future__ import annotations

import os

import requests

JAPANFOLD_BASE = os.environ.get(
    "JAPANFOLD_BASE_URL", "https://api.japanfold.aiand.com"
).rstrip("/")

SUBMIT_TIMEOUT = 30.0
POLL_TIMEOUT = 30.0
RESULTS_TIMEOUT = 30.0

# أسباب فشل قابلة للبرمجة (تُترجم في الواجهة، ولا تُرمى استثناءً)
REASON_OK = ""
REASON_NO_KEY = "no_api_key"
REASON_NETWORK = "network_error"
REASON_BAD_SHAPE = "bad_response_shape"
REASON_UNAUTHORIZED = "401_sign_in_required"
REASON_NO_CREDIT = "402_out_of_credit"
REASON_JOB_FAILED = "job_failed"
REASON_DEADLINE = "deadline_exceeded"
REASON_NO_AFFINITY = "no_affinity_fields"
REASON_BAD_REQUEST = "400_bad_request"

# حالة وظيفة محتجَزة افتراضياً لكل استعلام (RFC 7240 على /v1/jobs/{id})
POLL_WAIT_S = 15


def get_api_key() -> str | None:
    """المفتاح من البيئة فقط — لا يُخزَّن ولا يُطبع أبداً (بروتوكول التوكن)."""
    key = os.environ.get("JAPANFOLD_API_KEY", "").strip()
    return key or None


def _headers(api_key: str | None) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


def _problem_detail(resp: requests.Response) -> str:
    """استخراج detail من RFC 9457 problem+json إن وُجد."""
    try:
        return str(resp.json().get("detail", ""))[:200]
    except (ValueError, AttributeError):
        return ""


# ─────────────────────────────────────────────────────────────
# البناء — Boltz YAML لترافق بروتين + ليغاند مع رأس affinity
# ─────────────────────────────────────────────────────────────

def build_boltz_yaml(sequence: str, ligand_smiles: str) -> str:
    """Boltz YAML قياسي: سلسلة بروتين واحدة + ليغاند SMILES + خاصية affinity."""
    seq = sequence.strip().upper()
    # تنظيف FASTA إن لُصقت برأسها
    if seq.startswith(">"):
        lines = seq.splitlines()
        seq = "".join(line.strip() for line in lines[1:] if not line.startswith(">"))
    return (
        "sequences:\n"
        "  - protein:\n"
        "      id: A\n"
        f"      sequence: {seq}\n"
        "  - ligand:\n"
        "      id: LIG\n"
        f"      ligand: {ligand_smiles.strip()}\n"
        "properties:\n"
        "  - affinity:\n"
        "      binder: LIG\n"
    )


# ─────────────────────────────────────────────────────────────
# الدورة: إرسال → انتظار → نتائج (كل فشل → (None|[], سبب) بلا استثناء)
# ─────────────────────────────────────────────────────────────

def submit_prediction(
    payload: dict,
    api_key: str | None = None,
    base_url: str | None = None,
    timeout: float = SUBMIT_TIMEOUT,
) -> tuple[str | None, str]:
    """إرسال وظيفة إلى /v1/predictions — يُرجع (job_id, سبب)."""
    key = api_key if api_key is not None else get_api_key()
    if key is None:
        return None, REASON_NO_KEY
    base = (base_url or JAPANFOLD_BASE).rstrip("/")
    try:
        resp = requests.post(
            f"{base}/v1/predictions", json=payload, headers=_headers(key),
            timeout=timeout,
        )
        if resp.status_code == 401:
            return None, REASON_UNAUTHORIZED
        if resp.status_code == 402:
            return None, REASON_NO_CREDIT
        if resp.status_code == 400:
            return None, f"{REASON_BAD_REQUEST}: {_problem_detail(resp)}"
        resp.raise_for_status()
        job_id = resp.json().get("id")
        if not job_id:
            return None, REASON_BAD_SHAPE
        return str(job_id), REASON_OK
    except requests.RequestException:
        return None, REASON_NETWORK
    except ValueError:
        return None, REASON_BAD_SHAPE


def poll_job(
    job_id: str,
    api_key: str | None = None,
    base_url: str | None = None,
    deadline_s: float = 180.0,
    wait_s: int = POLL_WAIT_S,
) -> tuple[dict | None, str]:
    """استعلام محتجَز حتى حالة نهائية أو انقضاء المهلة — يُرجع (job, سبب).

    النداء GET ?wait=N يحتجَز على الخادم حتى انتهاء الوظيفة أو N ثانية
    (RFC 7240) — لا نضيف sleep بين الاستعلامات، نعيد فقط حتى المهلة.
    """
    key = api_key if api_key is not None else get_api_key()
    if key is None:
        return None, REASON_NO_KEY
    base = (base_url or JAPANFOLD_BASE).rstrip("/")
    import time

    deadline = time.monotonic() + deadline_s
    try:
        while time.monotonic() < deadline:
            remaining = max(1, int(deadline - time.monotonic()))
            resp = requests.get(
                f"{base}/v1/jobs/{job_id}",
                params={"wait": min(wait_s, remaining)},
                headers=_headers(key),
                timeout=POLL_TIMEOUT + min(wait_s, remaining),
            )
            if resp.status_code == 401:
                return None, REASON_UNAUTHORIZED
            if resp.status_code == 402:
                return None, REASON_NO_CREDIT
            resp.raise_for_status()
            job = resp.json()
            status = job.get("status")
            if status in ("succeeded", "failed", "canceled"):
                if status != "succeeded":
                    detail = str(job.get("error") or job.get("detail") or "")[:200]
                    return None, f"{REASON_JOB_FAILED}: {detail}" if detail else REASON_JOB_FAILED
                return job, REASON_OK
            # queued / running → استعلام محتجَز جديد
        return None, REASON_DEADLINE
    except requests.RequestException:
        return None, REASON_NETWORK
    except ValueError:
        return None, REASON_BAD_SHAPE


def get_results(
    job_id: str,
    api_key: str | None = None,
    base_url: str | None = None,
    timeout: float = RESULTS_TIMEOUT,
) -> tuple[dict | None, str]:
    """جلب /v1/jobs/{id}/results — يُرجع (results_dict, سبب)."""
    key = api_key if api_key is not None else get_api_key()
    if key is None:
        return None, REASON_NO_KEY
    base = (base_url or JAPANFOLD_BASE).rstrip("/")
    try:
        resp = requests.get(
            f"{base}/v1/jobs/{job_id}/results", headers=_headers(key), timeout=timeout
        )
        if resp.status_code == 401:
            return None, REASON_UNAUTHORIZED
        if resp.status_code == 402:
            return None, REASON_NO_CREDIT
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, dict):
            return None, REASON_BAD_SHAPE
        return data, REASON_OK
    except requests.RequestException:
        return None, REASON_NETWORK
    except ValueError:
        return None, REASON_BAD_SHAPE


def extract_affinity_fields(results: dict) -> dict[str, float]:
    """كل حقل رقمي يبدأ بـ affinity في صفوف النتائج — تحقق مرن لا يفترض أسماء.

    صفوف التنبؤ تحمل confidence_score/complex_plddt/iptm وحقول affinity
    (الدليل لا يسمّيها صراحة) — نلتقط ما يبدأ بـ affinity فقط ونجعل القيمة float.
    """
    out: dict[str, float] = {}
    rows = results.get("rows")
    if not isinstance(rows, list):
        return out
    for row in rows:
        if not isinstance(row, dict):
            continue
        for k, v in row.items():
            if isinstance(k, str) and k.lower().startswith("affinity"):
                if isinstance(v, bool):
                    continue
                if isinstance(v, (int, float)):
                    out[k] = float(v)
                elif isinstance(v, str):
                    try:
                        out[k] = float(v.strip())
                    except ValueError:
                        continue
        if out:
            break  # الصف الأول المكتمل يكفي — أفضل بوز
    return out


def boltz2_affinity(
    protein_sequence: str,
    ligand_smiles: str,
    api_key: str | None = None,
    base_url: str | None = None,
    deadline_s: float = 240.0,
) -> tuple[dict[str, float] | None, str, str | None]:
    """دورة كاملة: Boltz-2 ترافق بروتين + ليغاند ويُرجع حقول الارتباط.

    يُرجع (affinity_fields | None, سبب, job_id | None).
    نمط المنصة: أي فشل → (None, سبب قصير, ربما job_id) — بلا استثناءات.
    """
    yaml_input = build_boltz_yaml(protein_sequence, ligand_smiles)
    payload = {"model": "boltz2", "name": "pharma-sdl-affinity", "input": yaml_input}
    job_id, reason = submit_prediction(payload, api_key=api_key, base_url=base_url)
    if job_id is None:
        return None, reason, None
    job, reason = poll_job(
        job_id, api_key=api_key, base_url=base_url, deadline_s=deadline_s
    )
    if job is None:
        return None, reason, job_id
    results, reason = get_results(job_id, api_key=api_key, base_url=base_url)
    if results is None:
        return None, reason, job_id
    fields = extract_affinity_fields(results)
    if not fields:
        return None, REASON_NO_AFFINITY, job_id
    return fields, REASON_OK, job_id
