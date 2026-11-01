"""اختبارات بوابة الاعتماد العلمي — أربع حالات، لا ترقية تلقائية أبداً.

القاعدة الحاكمة (تدقيق P1): نجاح البرنامج أو ارتفاع الدرجة لا يرفعان
حالة أي نتيجة — الترقية قرار بشري صريح موثق، خطوة واحدة، بمرفقات إلزامية.
"""

from __future__ import annotations

import pytest

from pharma_sdl.errors import ValidationError
from pharma_sdl.validation.gate import (
    ValidationCard,
    ValidationState,
    card_summary,
    default_card,
    promote,
    revoke,
)


def _card() -> ValidationCard:
    return default_card(
        subject="screening_run:test001",
        engine="simulation",
        method="simulation",
        limits="درجات تطوير — ليست فيزياء.",
    )


# ── الحالات الأربع والبداية ─────────────────────────────────


def test_four_states_ordered():
    assert [s.value for s in ValidationState] == [
        "UNVALIDATED",
        "COMPUTATIONALLY_VALIDATED",
        "EXPERIMENTALLY_SUPPORTED",
        "INDEPENDENTLY_REPRODUCED",
    ]
    assert ValidationState.UNVALIDATED.rank == 0
    assert ValidationState.INDEPENDENTLY_REPRODUCED.rank == 3


def test_every_result_starts_unvalidated():
    card = _card()
    assert card.state is ValidationState.UNVALIDATED
    assert card.history == []


# ── قواعد الترقية الصارمة ──────────────────────────────────


def test_promotion_without_reason_rejected():
    with pytest.raises(ValidationError):
        promote(_card(), ValidationState.COMPUTATIONALLY_VALIDATED, "  ", "reviewer")


def test_skip_step_promotion_rejected():
    """لا قفزات: من UNVALIDATED إلى EXPERIMENTALLY_SUPPORTED مباشرة = مرفوض."""
    with pytest.raises(ValidationError, match="خطوة واحدة|single"):
        promote(
            _card(),
            ValidationState.EXPERIMENTALLY_SUPPORTED,
            reason="فحص تجريبي جيد",
            actor="reviewer",
            assay_ref="CHEMBL4523582",
        )


def test_experimental_state_requires_assay_ref():
    card = promote(
        _card(),
        ValidationState.COMPUTATIONALLY_VALIDATED,
        reason="فحوص العرض البرمجية اكتملت",
        actor="ci",
        checks=["curation gates", "deterministic engine"],
    )
    with pytest.raises(ValidationError, match="assay|فحص"):
        promote(
            card,
            ValidationState.EXPERIMENTALLY_SUPPORTED,
            reason="نعتقد أنه فعال",
            actor="reviewer",
        )
    promoted = promote(
        card,
        ValidationState.EXPERIMENTALLY_SUPPORTED,
        reason="فحص FRET تأكيدي مؤكد",
        actor="reviewer",
        assay_ref="FRET-2026-0117",
    )
    assert promoted.state is ValidationState.EXPERIMENTALLY_SUPPORTED


def test_top_state_requires_protocol_and_independent_lab():
    card = promote(
        _card(),
        ValidationState.COMPUTATIONALLY_VALIDATED,
        reason="فحوص محددة",
        actor="ci",
    )
    card = promote(
        card,
        ValidationState.EXPERIMENTALLY_SUPPORTED,
        reason="قياس موثق",
        actor="lab",
        assay_ref="ASSAY-1",
    )
    with pytest.raises(ValidationError, match="بروتوكول|protocol"):
        promote(
            card,
            ValidationState.INDEPENDENTLY_REPRODUCED,
            reason="مختبر آخر أكد",
            actor="external",
            protocol=None,
            independent_lab=None,
        )
    top = promote(
        card,
        ValidationState.INDEPENDENTLY_REPRODUCED,
        reason="إعادة إنتاج كاملة وفق البروتوكول",
        actor="external",
        protocol="PR-2026-004",
        independent_lab="University Lab X",
    )
    assert top.state is ValidationState.INDEPENDENTLY_REPRODUCED
    assert len(top.history) == 3  # كل انتقال موثق بالتسلسل


def test_no_auto_promotion_even_on_success():
    """جولة ناجحة تبقى UNVALIDATED — لا شيء في المنصة يرفعها تلقائياً."""
    card = _card()
    # لو كان هناك "نجاح" (checks ممتلئة) — الحالة لا تتغير بذاتها
    updated = card.model_copy(update={"checks": ["everything passed"]})
    assert updated.state is ValidationState.UNVALIDATED


# ── التخفيض الصريح ─────────────────────────────────────────


def test_revoke_is_explicit_and_documented():
    card = promote(
        _card(),
        ValidationState.COMPUTATIONALLY_VALIDATED,
        reason="فحوص أولية",
        actor="ci",
    )
    revoked = revoke(card, reason="اكتُشف خطأ في التوحيد الكيميائي", actor="reviewer")
    assert revoked.state is ValidationState.UNVALIDATED
    assert revoked.history[-1]["from"] == "COMPUTATIONALLY_VALIDATED"
    assert "خطأ" in revoked.history[-1]["reason"]
    with pytest.raises(ValidationError):
        revoke(revoked, reason="", actor="reviewer")


# ── العرض ──────────────────────────────────────────────────


def test_card_summary_bilingual():
    summary_ar = card_summary(_card(), "ar")
    assert "نتيجة أولية" in summary_ar
    assert "Preliminary" in card_summary(_card(), "en")
