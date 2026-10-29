"""اختبارات التصنيف الدوائي (S10) — كاتالوج ATC محلي + عميل RxNorm حي موسوم.

المعيار العالمي: ATC لمنظمة الصحة العالمية. كل الاختبارات offline؛ نداء RxNorm
الحي موسوم integration (شبكة RxNav محجوبة من بيئة التطوير — موثّق في الوحدة).
"""
from __future__ import annotations

import pytest
import requests as requests_lib

from core.drug_classes import CATALOG, atc_live, card_by_id, classify
from core.i18n import STRINGS
from core.viz import render_png

ASPIRIN = "CC(=O)OC1=CC=CC=C1C(=O)O"
PARACETAMOL = "CC(=O)Nc1ccc(O)cc1"


# ── سلامة الكاتالوج ──────────────────────────────────────────


def test_catalog_unique_ids_and_atc():
    ids = [c.class_id for c in CATALOG]
    assert len(ids) == len(set(ids))
    for c in CATALOG:
        assert c.atc and c.name_ar and c.name_en
        assert c.mech_ar and c.mech_en
        assert c.members, f"{c.class_id} بلا أعضاء"


def test_catalog_resolvable_via_card_by_id():
    for c in CATALOG:
        assert card_by_id(c.class_id) is c


def test_card_is_frozen_dataclass():
    card = CATALOG[0]
    with pytest.raises(Exception):  # noqa: B017 — الفريزن يرمي FrozenInstanceError
        card.atc = "XX"  # type: ignore[misc]


# ── التصنيف المحلي — الأعضاء ────────────────────────────────


def test_member_match_english():
    hits = classify("ciprofloxacin")
    assert hits and hits[0].card.class_id == "fluoroquinolones"
    assert hits[0].basis == "member"


def test_member_match_arabic():
    hits = classify("أموكسيسيلين")
    assert hits and hits[0].card.class_id == "penicillins"


def test_case_and_whitespace_insensitive():
    assert classify("  AmoxiCillin  ")[0].card.class_id == "penicillins"
    assert classify("CIPROFLOXACIN")[0].card.class_id == "fluoroquinolones"


def test_smiles_match():
    hits = classify(ASPIRIN)
    assert hits and hits[0].card.class_id == "nsaids"
    assert hits[0].basis == "smiles"
    assert classify(PARACETAMOL)[0].card.class_id == "anilides"


# ── اللواحق/البادئات — مع فض الالتباس ───────────────────────


def test_suffix_rules():
    assert classify("somecillin")[0].card.class_id == "penicillins"
    assert classify("somefloxacin")[0].card.class_id == "fluoroquinolones"
    assert classify("somestatin")[0].card.class_id == "statins"
    assert classify("somedipine")[0].card.class_id == "dhp_ccbs"


def test_disambiguation_thromycin_before_mycin():
    """أزيثروميسين (-thromycin) ماكروليد لا أمينوغليكوزيد."""
    assert classify("roxithromycin")[0].card.class_id == "macrolides"


def test_disambiguation_prazole_before_conazole():
    """أوميبرازول (-prazole) مثبط مضخة لا مضاد فطريات."""
    assert classify("someprazole")[0].card.class_id == "ppis"
    assert classify("someconazole")[0].card.class_id == "azoles"


def test_prefix_rules():
    assert classify("cefuroxime")[0].card.class_id == "cephalosporins"
    assert classify("sulfadimidine")[0].card.class_id == "sulfonamides"


def test_benzodiazepines_two_suffixes():
    """اللوحاقتان -azepam و -azolam → نفس المجموعة N05BA."""
    assert classify("xazepam")[0].card.class_id == "benzodiazepines"
    assert classify("xazolam")[0].card.class_id == "benzodiazepines"


def test_unknown_and_empty_are_honest():
    assert classify("xyzdrug") == []
    assert classify("   ") == []
    assert classify("C1CCOCC1") == []  # بنية غير مفهرسة — صدق بلا تخمين


# ── العميل الحي RxNorm — mock كامل ──────────────────────────


class _FakeResp:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests_lib.HTTPError(str(self.status_code))


def _patch_get(monkeypatch, responses):
    calls = []

    def fake_get(url, params=None, timeout=None):
        calls.append((url, params))
        return responses.pop(0)

    monkeypatch.setattr("core.drug_classes.requests.get", fake_get)
    return calls


def test_atc_live_success(monkeypatch):
    responses = [
        _FakeResp({"idGroup": {"rxnormId": ["723"]}}),
        _FakeResp({"rxclassDrugInfoList": {"rxclassDrugInfo": [
            {"rxclassMinConceptItem": {"classId": "J01CA04", "className": "amoxicillin"}},
            {"rxclassMinConceptItem": {"classId": "J01CA", "className": "Aminopenicillins"}},
            {"rxclassMinConceptItem": {"classId": "J01CA", "className": "Aminopenicillins"}},
        ]}}),
    ]
    calls = _patch_get(monkeypatch, responses)
    out = atc_live("amoxicillin")
    assert out == [("J01CA04", "amoxicillin"), ("J01CA", "Aminopenicillins")]
    assert "rxcui.json" in calls[0][0] and "rxclass" in calls[1][0]
    assert calls[1][1]["relaSource"] == "ATC"


def test_atc_live_no_rxcui(monkeypatch):
    _patch_get(monkeypatch, [_FakeResp({"idGroup": {}})])
    assert atc_live("notadrug") is None


def test_atc_live_network_failure(monkeypatch):
    def boom(url, params=None, timeout=None):
        raise requests_lib.ConnectionError("blocked")

    monkeypatch.setattr("core.drug_classes.requests.get", boom)
    assert atc_live("amoxicillin") is None  # فشل الشبكة → None بلا استثناءات


def test_atc_live_http_error(monkeypatch):
    _patch_get(monkeypatch, [_FakeResp({}, status=503)])
    assert atc_live("amoxicillin") is None


def test_atc_live_empty_name():
    assert atc_live("   ") is None


@pytest.mark.integration
def test_atc_live_real_network():
    """نداء حي — RxNav محجوب من بيئة التطوير (مهلة)؛ التحقق عند شبكة مفتوحة."""
    out = atc_live("amoxicillin", timeout=15.0)
    if out is not None:  # إن استجابت الشبكة فالعقد يجب أن يصح
        assert any(code.startswith("J01") for code, _ in out)


# ── الرسم ثنائي الأبعاد (طرق عرض أفضل) ─────────────────────


def test_render_png_valid():
    png = render_png(ASPIRIN, size=240)
    assert png is not None
    assert png.startswith(b"\x89PNG")
    assert len(png) > 1000


def test_render_png_invalid_and_empty():
    assert render_png("NOT_SMILES") is None
    assert render_png("   ") is None


# ── i18n — مكافأة المفاتيح والقوالب ─────────────────────────


def test_cls_keys_parity():
    ar = {k for k in STRINGS["ar"] if k.startswith("cls_") or k == "tab_classes"}
    en = {k for k in STRINGS["en"] if k.startswith("cls_") or k == "tab_classes"}
    assert ar == en and len(ar) >= 20


def test_cls_format_templates():
    from core.i18n import t

    assert "{n}" in t("ar", "cls_caption") and "{n}" in t("en", "cls_caption")
    assert "{basis}" in t("ar", "cls_found") and "{basis}" in t("en", "cls_found")
    assert "{drug}" in t("ar", "cls_live_done") and "{drug}" in t("en", "cls_live_done")
    assert "{n}" in t("ar", "cls_browse") and "{n}" in t("en", "cls_browse")


def test_all_basis_labels_exist():
    for basis in ("member", "suffix", "prefix", "smiles"):
        assert STRINGS["ar"][f"cls_basis_{basis}"].strip()
        assert STRINGS["en"][f"cls_basis_{basis}"].strip()
