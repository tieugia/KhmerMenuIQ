import pytest

from app import guardrails as g


def test_validate_message_rejects_blank():
    with pytest.raises(ValueError):
        g.validate_message("   ")


def test_validate_message_rejects_empty_string():
    with pytest.raises(ValueError):
        g.validate_message("")


def test_validate_message_trims_and_returns():
    assert g.validate_message("  hello  ") == "hello"


@pytest.mark.parametrize(
    "raw,expected",
    [
        (10, 10.0),
        (-5, g.MIN_BUDGET_USD),
        (99999999, g.MAX_BUDGET_USD),
        (0, g.MIN_BUDGET_USD),
        (0.25, 0.25),
        ("10", 10.0),
        ("$10", 10.0),
        ("10,000", g.MAX_BUDGET_USD),
        (" 7.50 ", 7.5),
        ("not a number", None),
        (None, None),
    ],
)
def test_clamp_budget(raw, expected):
    assert g.clamp_budget(raw) == expected


@pytest.mark.parametrize(
    "raw,expected",
    [
        (1, 1),
        (0, 1),
        (-3, 1),
        (99999, g.MAX_QUANTITY_PER_ITEM),
        (5, 5),
        ("not a number", 1),
        (None, 1),
    ],
)
def test_clamp_quantity(raw, expected):
    assert g.clamp_quantity(raw) == expected


def test_cap_wants_truncates_to_max():
    wants = [{"role": "chicken", "quantity": 1}] * (g.MAX_WANTS_PER_REQUEST + 5)
    assert len(g.cap_wants(wants)) == g.MAX_WANTS_PER_REQUEST


def test_cap_wants_keeps_short_list_untouched():
    wants = [{"role": "chicken", "quantity": 1}]
    assert g.cap_wants(wants) == wants


def test_cap_notes_truncates_long_text():
    long_notes = "x" * (g.MAX_NOTES_LENGTH + 50)
    assert len(g.cap_notes(long_notes)) == g.MAX_NOTES_LENGTH


def test_cap_notes_handles_none():
    assert g.cap_notes(None) == ""


@pytest.mark.parametrize(
    "raw,expected",
    [
        (4, 4),
        (1, 1),
        (0, 1),
        (-2, 1),
        (999, g.MAX_PARTY_SIZE),
        (None, 1),
        ("not a number", 1),
    ],
)
def test_clamp_party_size(raw, expected):
    assert g.clamp_party_size(raw) == expected


def test_out_of_scope_reply_mentions_menu():
    assert "menu" in g.OUT_OF_SCOPE_REPLY.lower()


def test_prompt_injection_guard_is_nonempty():
    assert len(g.PROMPT_INJECTION_GUARD) > 20
