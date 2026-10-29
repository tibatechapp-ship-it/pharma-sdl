"""اختبارات i18n — تكافؤ المفاتيح عربي/إنجليزي وسقوط الترجمة الآمن."""
from core.i18n import STRINGS, available_langs, t


def test_language_parity():
    """كل مفتاح عربي له مقابل إنجليزي والعكس — لا مفاتيح يتيمة."""
    assert set(STRINGS) == {"ar", "en"}
    assert set(STRINGS["ar"]) == set(STRINGS["en"])


def test_no_empty_strings():
    for lang, strings in STRINGS.items():
        for key, value in strings.items():
            assert isinstance(value, str) and value.strip(), f"{lang}/{key} فارغ"


def test_available_langs():
    assert available_langs() == ["ar", "en"]


def test_t_returns_translation():
    assert t("ar", "tab_docking") == "🧲 الربط الجزيئي"
    assert t("en", "tab_docking") == "🧲 Docking"
    assert t("ar", "tab_pgx") == "💊 الجينوم الدوائي"
    assert t("en", "tab_pgx") == "💊 PGx"


def test_t_fallback_unknown_key():
    """مفتاح غير موجود → يعاد المفتاح نفسه (لا استثناء)."""
    assert t("ar", "no_such_key") == "no_such_key"
    assert t("xx", "dock_btn") == t("ar", "dock_btn")
