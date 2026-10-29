"""اختبارات PGx — الاحتياطي المدمج + المطابقة + الجلب الحي (مزيف الشبكة).

كل الاختبارات بلا شبكة؛ نداء CPIC الحي الحقيقي موسوم integration.
"""
import pytest

from core.pgx import (
    FALLBACK_RECS,
    GENES,
    REC_COLUMNS,
    fallback_df,
    fetch_cpic,
    recommendations_df,
)


def test_five_genes_defined():
    assert set(GENES) == {"CYP2D6", "TPMT", "UGT1A1", "CYP2C19", "CYP3A5"}


def test_required_genes_have_diplotype_map():
    """CYP2D6/TPMT/UGT1A1 مطلوبة في خارطة السبرنت — لكل نمط ظاهري صالح."""
    for gid in ("CYP2D6", "TPMT", "UGT1A1"):
        dips = GENES[gid].diplotypes
        assert dips and all("Metabolizer" in v for v in dips.values())


def test_fallback_covers_all_diplotypes():
    """كل جين/نمط في GENES له صف توصية مدمج — لا نمط بلا توصية."""
    for gid, gene in GENES.items():
        for dip in gene.diplotypes:
            rows = fallback_df(gid, dip)
            assert not rows.empty, f"لا توصية مدمجة لـ {gid} {dip}"


def test_fallback_rec_columns():
    df = fallback_df()
    assert list(df.columns) == REC_COLUMNS
    assert len(df) == len(FALLBACK_RECS)
    assert set(df["classification"]).issubset(
        {"strong", "moderate", "optional", "informative"}
    )


def test_codeine_um_and_pm_both_avoid():
    """الدرس الأشهر: PM (لا تسكين) وUM (تسمم) كلاهما «تجنّب» لكن لأسباب متعاكسة."""
    um = fallback_df("CYP2D6", "*1/*1xN")
    um_codeine = um[um["drug"] == "codeine"].iloc[0]
    pm = fallback_df("CYP2D6", "*4/*4")
    pm_codeine = pm[pm["drug"] == "codeine"].iloc[0]
    assert um_codeine["classification"] == "strong"
    assert pm_codeine["classification"] == "strong"
    assert "تسمم" in um_codeine["recommendation_ar"]
    assert "لا تسكين" in pm_codeine["recommendation_ar"]


def test_tpmt_poor_starts_at_ten_percent():
    pm = fallback_df("TPMT", "*4/*4")
    rec = pm[pm["drug"] == "azathioprine"].iloc[0]["recommendation_ar"]
    assert "10%" in rec


def test_recommendations_df_arabic_columns():
    df = recommendations_df("TPMT", "*1/*4", lang="ar")
    assert list(df.columns) == ["الدواء", "النمط", "التوصية", "القوة", "المصدر"]
    assert "50%" in df["التوصية"].iloc[0]
    assert df["القوة"].iloc[0] == "قوي"


def test_recommendations_df_english():
    df = recommendations_df("CYP3A5", "*1/*1", lang="en")
    assert "1.5-2x" in df["التوصية"].iloc[0]


def test_fetch_cpic_mocked_success(monkeypatch):
    """شكل API المتوقع (phenotypes كقاموس) يُفسَّر لصفوف موحّدة."""
    from core import pgx

    class FakeResp:
        def raise_for_status(self):
            return None

        def json(self):
            return [
                {
                    "drugname": "codeine",
                    "phenotypes": {
                        "CYP2D6": {"gene": "CYP2D6", "phenotype": "Poor Metabolizer"}
                    },
                    "classification": "strong",
                    "recommendation": "Avoid codeine.",
                    "implication": "-",
                }
            ]

    monkeypatch.setattr(pgx.requests, "get", lambda *a, **k: FakeResp())
    rows = fetch_cpic("CYP2D6")
    assert len(rows) == 1
    assert rows[0]["drug"] == "codeine"
    assert rows[0]["phenotype_en"] == "Poor Metabolizer"
    assert rows[0]["classification"] == "strong"


def test_fetch_cpic_network_failure_returns_empty(monkeypatch):
    """أي فشل شبكة → [] (لا استثناءات تسقط التبويب)."""
    from core import pgx

    def boom(*a, **k):
        raise TimeoutError("offline")

    monkeypatch.setattr(pgx.requests, "get", boom)
    assert fetch_cpic("TPMT") == []


def test_live_rows_matching_by_phenotype(monkeypatch):
    """الصف الحي يُقبَل فقط حين يطابق فئة النمط — وإلا الاحتياطي."""
    from core import pgx

    class FakeResp:
        def raise_for_status(self):
            return None

        def json(self):
            return [
                {
                    "drugname": "codeine",
                    "phenotypes": {"CYP2D6": {"phenotype": "Poor Metabolizer"}},
                    "classification": "strong",
                    "recommendation": "Avoid codeine; use an alternative.",
                    "implication": "-",
                },
                {
                    "drugname": "atomoxetine",
                    "phenotypes": {"CYP2D6": {"phenotype": "Normal Metabolizer"}},
                    "classification": "moderate",
                    "recommendation": "Standard dosing.",
                    "implication": "-",
                },
            ]

    monkeypatch.setattr(pgx.requests, "get", lambda *a, **k: FakeResp())
    live = fetch_cpic("CYP2D6")
    df = recommendations_df("CYP2D6", "*4/*4", lang="en", live_rows=live)
    # صف NM (atomoxetine) يُرشَّح خارجاً — يبقى صف PM الحي فقط
    assert len(df) == 1
    assert df["الدواء"].iloc[0] == "codeine"
    assert "CPIC حي" in df["المصدر"].iloc[0]


def test_live_rows_wrong_phenotype_falls_back():
    """صفوف حية لا تطابق النمط → الاحتياطي المدمج (لا جدول فارغ)."""
    live = [
        {
            "gene": "TPMT",
            "diplotype": "",
            "phenotype_en": "Poor Metabolizer",
            "drug": "azathioprine",
            "drug_ar": "",
            "recommendation_ar": "",
            "recommendation_en": "Avoid; start ~10% if needed.",
            "classification": "strong",
            "guideline": "CPIC حي",
        }
    ]
    df = recommendations_df("TPMT", "*1/*1", lang="ar", live_rows=live)
    assert df["المصدر"].iloc[0].startswith("CPIC 2018") or df["المصدر"].iloc[0].startswith("CPIC")


@pytest.mark.integration
def test_fetch_cpic_live_smoke():
    """نداء حي حقيقي — يُشغَّل فقط مع -m integration (يتطلب شبكة)."""
    rows = fetch_cpic("CYP2D6")
    assert isinstance(rows, list)
    if rows:  # الشبكة متاحة: الشكل موحّد
        assert {"gene", "drug", "phenotype_en", "recommendation_en"} <= set(rows[0])
