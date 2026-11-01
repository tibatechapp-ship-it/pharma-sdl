"""اختبارات خط الفرز end-to-end — الهيكل الهزّ من المدخلات إلى التقرير."""

from __future__ import annotations

import json

from pharma_sdl.curation.loader import load_ligands_csv
from pharma_sdl.models import LigandInput
from pharma_sdl.reporting.report import build_json, build_markdown
from pharma_sdl.screening.runner import run_screening

DEMO_CSV = "data/demo_ligands.csv"


def _demo_ligands():
    return load_ligands_csv(DEMO_CSV)


def test_end_to_end_demo_screening():
    result = run_screening("7VH8_A", _demo_ligands(), engine_name="simulation", top_n=5)
    assert result.counts["input"] == 24, "مجموعة العرض كاملة 24 جزيء"
    assert result.engine_used == "simulation"
    assert result.counts["returned"] == 5
    assert [h.rank for h in result.hits] == [1, 2, 3, 4, 5]
    kcals = [h.docking_kcal for h in result.hits]
    assert kcals == sorted(kcals), "الترتيب تصاعدي (الأقوى أولاً)"
    assert any("المحاكاة" in w for w in result.warnings), "علامة الصدق موجودة"


def test_covalent_anchors_rejected_in_demo_run():
    result = run_screening("7VH8_A", _demo_ligands(), engine_name="simulation")
    rejected_names = {r.name for r in result.rejected}
    assert "Nirmatrelvir" in rejected_names, "نيتريل → رفض بسياسة غير التساهمي"
    assert "N-phenylacrylamide (trap)" in rejected_names
    gate_reasons = [r for r in result.rejected if r.stage == "covalent_gate"]
    assert len(gate_reasons) >= 5, "نيتريل + 4 فخاخ تساهمية على الأقل"
    hit_names = {h.name for h in result.hits}
    assert hit_names.isdisjoint(rejected_names), "لا مرشح مرفوض في قائمة النجاة"


def test_rejections_carry_bilingual_reasons():
    result = run_screening("7VH8_A", _demo_ligands(), engine_name="simulation")
    for r in result.rejected:
        assert r.reason_ar and r.reason_en


def test_report_markdown_and_json_roundtrip():
    result = run_screening("7VH8_A", _demo_ligands(), engine_name="simulation", top_n=3)
    md = build_markdown(result, lang="ar")
    assert result.run_id in md
    assert "تقرير فرز ظاهري" in md
    assert result.hits[0].name in md if result.hits[0].name else True
    parsed = json.loads(build_json(result))
    assert parsed["run_id"] == result.run_id
    assert parsed["counts"]["input"] == 24


def test_screening_with_inline_ligands_small():
    ligands = [
        LigandInput(name="a", smiles="O=C(N)c1ccccc1"),
        LigandInput(name="b", smiles="Cn1cnc2c1c(=O)n(C)c(=O)n2C"),
        LigandInput(name="trap", smiles="C=CC(=O)Nc1ccccc1"),
    ]
    result = run_screening("7CMD_A", ligands, engine_name="simulation", top_n=2)
    assert result.target_id == "7CMD_A"
    assert result.counts["input"] == 3
    assert result.counts["returned"] == 2
    assert result.counts["rejected"] == 1
