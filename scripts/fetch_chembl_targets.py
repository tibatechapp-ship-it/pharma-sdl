#!/usr/bin/env python3
"""جلب بيانات نشاط ChEMBL لهدفين جديدين (P6) — بنفس صرامة بيانات MPRO.

الأهداف (خطة 30 يوماً — بند توسيع الأهداف):
    - CHEMBL220 : أستيل كولين أستيراز البشري (AChE) — الفئة العصبية/الكولينية
    - CHEMBL203 : مستقبل عامل النمو الطلائي البشري (EGFR) — بروتين كيناز

قواعد التخريج (موثقة في ADR-0011):
    1) target_chembl_id مطابق حصراً
    2) standard_type = IC50 حصراً — نقطة نهاية واحدة متجانسة
    3) pchembl_value >= 5 (القياسات الضعيفة بلا معلومة ترتيبية)
    4) data_validity_comment فارغ — لا بيانات معلَّمة من ChEMBL
    5) canonical_smiles موجود وقابل للتحليل في RDKit
    6) إزالة التكرار: جزيء واحد بإعلى pchembl
    7) عينة موحدة عشوائية 900 صف (حجم MPRO نفسه) ببذرة ثابتة 0 — حتمية
       عبر الترتيب المعجمي لمعرفات الجزيئات قبل السحب.

الإخراج: data/ache_sample.csv و data/egfr_sample.csv — بنفس أعمدة
data/mpro_sample.csv تماماً (smiles, pchembl_value, mol_chembl_id).

الاستعمال:  python scripts/fetch_chembl_targets.py [--n 900]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd
from rdkit import Chem, RDLogger

RDLogger.DisableLog("rdApp.*")

BASE = "https://www.ebi.ac.uk/chembl/api/data"
REPO = Path(__file__).resolve().parent.parent

TARGETS: dict[str, dict] = {
    "CHEMBL220": {
        "out": "ache_sample.csv",
        "name_en": "Human acetylcholinesterase (AChE)",
    },
    "CHEMBL203": {
        "out": "egfr_sample.csv",
        "name_en": "Human epidermal growth factor receptor (EGFR)",
    },
}


CACHE = Path("/tmp/chembl_p6_cache")
"""كاش محلي للصفحات الخام — إعادة التشغيل لا تعيد الجلب بلا داع."""


def _get_json(url: str, tries: int = 3, timeout: int = 45) -> dict:
    """GET مع إعادة محاولة خطية — الشبكة هنا غير مضمونة."""
    last: Exception | None = None
    for i in range(tries):
        try:
            req = urllib.request.Request(
                url, headers={"Accept": "application/json", "User-Agent": "pharma-sdl-p6"}
            )
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:  # noqa: BLE001 — سجل ثم أعد
            last = e
            wait = 2.0 * (i + 1)
            print(f"    retry {i + 1}/{tries} after {wait:.0f}s: {e}", file=sys.stderr)
            time.sleep(wait)
    raise RuntimeError(f"ChEMBL fetch failed for {url}: {last}")


def fetch_activities(target_id: str, page_size: int = 100, max_pages: int = 50) -> list[dict]:
    """صفوف نشاط IC50 للهدف — حتى max_pages صفحة (تكفي عينة 900 فريدة).

    ملاحظة صدقية (ADR-0011): المجمع = أول max_pages×page_size صف نشاط
    بترتيب معرف النشاط الداخلي على خادم ChEMBL (ترتيب ثابت قابل للتكرار)،
    ثم عينة موحدة عشوائية ببذرة 0 — لا ادعاء بأن المجمع كامل السكان.
    صفحة فاشلة تُدمَج بتحذير (الخادم العام يفشل عند الإزاحات العميقة أحياناً).
    حجم الصفحة 100 حصراً عملياً: خادم EBI يفشل بـ500/عُطل على الصفحات
    الأكبر في أوقات الكظمة (قيس 2026-11-02).
    """
    # كاش تزايدي قابل للاستئناف — تُحفظ كل صفحة فور وصولها، فإعادة
    # التشغيل تكمل من نفس الإزاحة (الخادم متقلب والجلب قد ينقطع)
    cache_file = CACHE / f"{target_id}.json"
    if cache_file.exists():
        cached = json.loads(cache_file.read_text())
        if isinstance(cached, dict):  # تنسيق الاستئناف
            acts, offset0 = cached["rows"], cached["next_offset"]
        else:  # تنسيق قديم — قائمة خام مكتملة
            acts, offset0 = cached, len(cached)
        print(f"  {target_id}: resuming with {len(acts)} cached rows from offset {offset0}")
        if len(acts) >= max_pages * page_size:
            return acts
    else:
        acts, offset0 = [], 0
        CACHE.mkdir(parents=True, exist_ok=True)

    # بلا فلتر pchembl من الخادم: يُطبق محلياً في curate() — الفلتر الخادمي
    # يُفجّر خطأ 500 على الأهداف كبيرة القياسات (قيس 2026-11-02)
    filt = f"target_chembl_id={target_id}&standard_type=IC50&limit={page_size}"
    if offset0 == 0:
        first = _get_json(f"{BASE}/activity.json?{filt}")
        total = first["page_meta"]["total_count"]
        acts.extend(first["activities"])
        print(f"  {target_id}: total_count={total} (pool cap: {max_pages * page_size})")
    else:
        total = 10**9  # مجهول عند الاستئناف — السقف target_rows حصراً
        print(f"  {target_id}: total unknown on resume — cap {max_pages * page_size}")
    target_rows = max_pages * page_size
    offset = max(offset0, len(acts))
    skipped_windows = 0
    ceiling = min(total, target_rows * 2)
    while len(acts) < target_rows and offset < ceiling:
        try:
            page = _get_json(f"{BASE}/activity.json?{filt}&offset={offset}")
        except RuntimeError as e:
            skipped_windows += 1
            print(f"    WARN window at offset {offset} skipped: {e}", file=sys.stderr)
            if skipped_windows > 8:
                print("    WARN 8 skipped windows — stopping with current pool", file=sys.stderr)
                break
            offset += page_size  # تخطى النافذة العالقة — لا انحباس
            continue
        batch = page["activities"]
        if not batch:
            break
        acts.extend(batch)
        offset += len(batch)
        cache_file.write_text(json.dumps({"rows": acts, "next_offset": offset}))
        print(f"    fetched {len(acts)}")
        time.sleep(0.15)  # أدب مع الخادم العام
    if skipped_windows:
        print(f"    pool note: {skipped_windows} windows skipped (flaky server) — موثق في ADR-0011")
    cache_file.write_text(json.dumps({"rows": acts, "next_offset": offset}))
    return acts


def curate(acts: list[dict], n: int, seed: int = 0) -> pd.DataFrame:
    """قواعد التخريج — كل قاعدة موثقة في ADR-0011.

    الفلترة الجانبية هنا حصراً (لا اعتماد على فلاتر الخادم): خادم ChEMBL
    تجاهل فلتر pchembl_value>=5 بصمت أثناء القياس (total_count متطابق معه
    وبدونه) — فلتر pchembl يُطبق على الصفوف محلياً.
    """
    rows: dict[str, dict] = {}
    dropped = {"no_smiles": 0, "bad_smiles": 0, "flagged": 0, "low_pchembl": 0}
    for a in acts:
        if a.get("data_validity_comment"):
            dropped["flagged"] += 1
            continue
        smi = a.get("canonical_smiles")
        cid = a.get("molecule_chembl_id")
        pv = a.get("pchembl_value")
        if not smi or not cid or pv is None:
            dropped["no_smiles"] += 1
            continue
        pv = float(pv)
        if pv < 5.0:
            dropped["low_pchembl"] += 1
            continue
        mol = Chem.MolFromSmiles(smi)
        if mol is None or mol.GetNumAtoms() == 0:
            dropped["bad_smiles"] += 1
            continue
        pv = float(pv)
        prev = rows.get(cid)
        if prev is None or pv > prev["pchembl_value"]:
            rows[cid] = {
                "smiles": smi,
                "pchembl_value": pv,
                "mol_chembl_id": cid,
            }
    df = pd.DataFrame(rows.values()).sort_values("mol_chembl_id").reset_index(drop=True)
    print(f"  after curation: {len(df)} unique molecules (dropped: {dropped})")
    if len(df) < n:
        raise RuntimeError(f"only {len(df)} rows after curation — need {n}")
    return df.sample(n=n, random_state=seed).reset_index(drop=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=900, help="حجم العينة (افتراضي 900 = حجم MPRO)")
    args = ap.parse_args()

    for tid, spec in TARGETS.items():
        print(f"== {tid} — {spec['name_en']} ==")
        acts = fetch_activities(tid)
        df = curate(acts, n=args.n)
        out = REPO / "data" / spec["out"]
        df.to_csv(out, index=False)
        rng = (df.pchembl_value.min(), df.pchembl_value.max())
        print(f"  wrote {out.name}: {len(df)} rows, pchembl in [{rng[0]:.2f}, {rng[1]:.2f}]")
    print("done")


if __name__ == "__main__":
    main()
