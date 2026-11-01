"""اختبار واجهة سطر الأوامر — المنصة بلا متصفح."""

from __future__ import annotations

import json

from pharma_sdl.cli import main


def test_cli_engines(capsys):
    assert main(["engines"]) == 0
    out = capsys.readouterr().out
    assert "simulation" in out and "vina" in out and "boltz2" in out


def test_cli_targets(capsys):
    assert main(["targets"]) == 0
    out = capsys.readouterr().out
    assert "7VH8_A" in out and "غير تساهمي" in out


def test_cli_screen_writes_reports(tmp_path):
    out = tmp_path / "report.json"
    rc = main(
        [
            "screen",
            "--target", "7VH8_A",
            "--ligands", "data/demo_ligands.csv",
            "--engine", "simulation",
            "--top", "3",
            "--out", str(out),
        ]
    )
    assert rc == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["counts"]["input"] == 24
    assert len(data["hits"]) == 3
    assert out.with_suffix(".md").exists()
    md = out.with_suffix(".md").read_text(encoding="utf-8")
    assert "تقرير فرز ظاهري" in md


def test_cli_assay(capsys):
    rc = main(["assay", "--smiles", "O=C(N)c1ccccc1", "--dg", "-8.2"])
    assert rc == 0
    body = json.loads(capsys.readouterr().out)
    assert body["simulated"] is True
    assert body["ic50_um"] > 0
