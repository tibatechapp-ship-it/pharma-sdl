"""اختبارات P12 — القياس الخارجي الرسمي على TDC admet_group.

تختبر السلوك المحلي فقط (لا شبكة، ولا تحميل TDC): سلامة النسخة المجمدة
من التقسيم الرسمي، وواجهات خط v0.12.0 المعتمد المستخدمة في القياس.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

FROZEN = REPO / "data" / "external" / "admet_group"

TASKS = {
    "lipophilicity_astrazeneca": {"train_val": 3360, "test": 840},
    "solubility_aqsoldb": {"train_val": 7985, "test": 1997},
}


class TestFrozenOfficialSplits:
    """النسخة المجمدة من تقسيم TDC الرسمي — شهادة التكرار دون شبكة."""

    def test_frozen_files_exist(self):
        for task in TASKS:
            assert (FROZEN / task / "train_val.csv").is_file(), task
            assert (FROZEN / task / "test.csv").is_file(), task

    def test_row_counts_match_official(self):
        import csv

        for task, sizes in TASKS.items():
            for split, n in sizes.items():
                with open(FROZEN / task / f"{split}.csv", newline="", encoding="utf-8") as f:
                    rows = list(csv.reader(f))
                assert len(rows) - 1 == n, f"{task}/{split}: {len(rows)-1} != {n}"

    def test_manifest_checksums_match(self):
        import hashlib

        manifest = json.loads((FROZEN / "MANIFEST.json").read_text(encoding="utf-8"))
        for rel, digest in manifest["files"].items():
            actual = hashlib.sha256((FROZEN / rel).read_bytes()).hexdigest()
            assert actual == digest, rel

    def test_columns_are_official_schema(self):
        import pandas as pd

        df = pd.read_csv(FROZEN / "lipophilicity_astrazeneca" / "test.csv")
        assert list(df.columns) == ["Drug_ID", "Drug", "Y"]
        assert df["Y"].notna().all()
        assert df["Drug"].str.len().min() > 0


class TestAdoptedPipelineHelpers:
    """واجهات القياس: تكوين v0.12.0 المعتمد يعمل على تقسيم خارجي."""

    def test_fit_and_predict_on_external_split(self):
        from scripts.evaluate_tdc_p12 import (
            fit_adopted_pipeline,
            predict_adopted_pipeline,
        )

        train = ["CCO", "c1ccccc1O", "CC(=O)Oc1ccccc1C(=O)O", "CCCCN",
                 "OCC1OC(O)C(O)C(O)C1O", "CCN", "c1ccc(F)cc1", "CCCCO"]
        y = [1.0, 2.0, 3.0, 1.5, 2.5, 0.5, 2.2, 1.8]
        model, n_fail = fit_adopted_pipeline(train, y)
        assert n_fail == 0
        preds, te_fail = predict_adopted_pipeline(model, ["CCO", "CCC"])
        assert len(preds) == 2 and te_fail == 0
        assert np.isfinite(preds).all()

    def test_invalid_smiles_are_dropped_not_crashing(self):
        from core.ml_potency import featurize

        X, idx = featurize(["CCO", "ليس-سمايلز", "CCC"], count_based=True)
        assert len(idx) == 2 and X.shape == (2, 2048)

    def test_protocol_constants_match_v0120(self):
        import scripts.evaluate_tdc_p12 as m

        assert m.COUNT_BASED is True          # بصمة التكرارات المعتمدة
        assert m.RF_TREES == 300               # نفس P0/P11
        assert m.RF_MAX_FEATURES == 0.3        # المعتمد في P11
        assert m.SEEDS == [1, 2, 3, 4, 5]      # البذور الرسمية للوحة TDC

    def test_leaderboard_reference_numbers_present(self):
        import scripts.evaluate_tdc_p12 as m

        for task, spec in m.TASKS.items():
            assert spec["metric"] == "MAE" and spec["split"] == "Scaffold"
            assert len(spec["leaderboard"]) >= 15, task
            assert spec["leaderboard_url"].startswith("https://tdcommons.ai/")


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
