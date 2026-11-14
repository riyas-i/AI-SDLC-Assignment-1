"""Card-number masking (T027; FR-065, FR-070, FR-071, AC-048)."""

from __future__ import annotations

import pytest

from expense import masking

MASKED = "************1111"


@pytest.mark.parametrize("card", [
    "4111 1111 1111 1111",
    "4111-1111-1111-1111",
    "4111111111111111",
])
def test_test_card_forms_are_masked(card):
    assert masking.mask_card_numbers(card) == MASKED


def test_masking_inside_text():
    text = "lunch 70 SAR on 2026-11-13, paid with card 4111 1111 1111 1111, receipt"
    assert masking.mask_card_numbers(text) == (
        f"lunch 70 SAR on 2026-11-13, paid with card {MASKED}, receipt")


def test_13_digit_run_is_masked():
    assert masking.mask_card_numbers("1234567890123") == "*********0123"


def test_19_digit_run_is_masked():
    assert masking.mask_card_numbers("1234567890123456789") == "*" * 15 + "6789"


@pytest.mark.parametrize("text", [
    "123456789012",  # 12 digits
    "1100",
    "2026-11-14",
    "taxi 85 SAR yesterday",
    "Oasis Inn, 2 nights, 1100 SAR",
])
def test_non_card_numbers_untouched(text):
    assert masking.mask_card_numbers(text) == text


def test_find_unmasked_card_numbers():
    text = "card 4111-1111-1111-1111 and 4111111111111111"
    assert len(masking.find_unmasked_card_numbers(text)) == 2
    assert masking.find_unmasked_card_numbers(masking.mask_card_numbers(text)) == []
    assert masking.find_unmasked_card_numbers("amount 1100 on 2026-11-14") == []


def test_card_pattern_constant():
    assert masking.CARD_PATTERN == r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)"


def test_mask_output_masks_every_string(sample_outputs):
    output = sample_outputs["AC-011"]
    output["description"] = "Dinner, card 4111 1111 1111 1111"
    output["merchant"] = "Cafe 4111111111111111"
    output["policy_reasons"] = ["ref 4111-1111-1111-1111", "Amount 151 SAR exceeds the meals "
                                "limit of 150 SAR"]
    masked = masking.mask_output(output)
    assert masked["description"] == f"Dinner, card {MASKED}"
    assert masked["merchant"] == f"Cafe {MASKED}"
    assert masked["policy_reasons"] == [f"ref {MASKED}",
                                        "Amount 151 SAR exceeds the meals limit of 150 SAR"]
    assert masked["amount"] == 151 and masked["has_receipt"] is True
    assert masked["clarification_question"] is None
    assert list(masked) == list(output)
