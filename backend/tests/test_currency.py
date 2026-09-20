import pytest

from app.currency import RATES_PER_USD, from_usd, normalize_currency, to_usd


@pytest.mark.parametrize("currency,rate", RATES_PER_USD.items())
def test_fixed_currency_rates_round_trip_one_usd(currency, rate):
    assert from_usd(1, currency) == rate
    assert to_usd(rate, currency) == 1


@pytest.mark.parametrize("raw,expected", [(" vnd ", "VND"), (None, "USD"), ("EUR", "USD")])
def test_normalize_currency_accepts_only_supported_codes(raw, expected):
    assert normalize_currency(raw) == expected
