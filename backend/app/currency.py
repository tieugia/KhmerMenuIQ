"""
Fixed, approximate currency conversion so a diner can state their budget in a currency other
than USD. All internal combo math still happens in USD (the menus themselves are priced in
Riel and/or USD only) — these rates only convert a diner-stated budget in and back out.

Rates are NOT live market rates. They're rough reference values (see README/ASSUMPTIONS) and
will drift from the real exchange rate over time; treat any non-USD/KHR figure as approximate.
"""

# Units of each currency equal to 1 USD.
RATES_PER_USD = {
    "USD": 1.0,
    "KHR": 4100.0,   # Cambodian Riel
    "VND": 25400.0,  # Vietnamese Dong
    "PHP": 58.7,     # Philippine Peso
    "SGD": 1.34,     # Singapore Dollar
}

SYMBOLS = {
    "USD": "$",
    "KHR": "៛",
    "VND": "₫",
    "PHP": "₱",
    "SGD": "S$",
}

SUPPORTED_CURRENCIES = list(RATES_PER_USD.keys())


def normalize_currency(code) -> str:
    code = str(code or "USD").upper().strip()
    return code if code in RATES_PER_USD else "USD"


def to_usd(amount: float, currency) -> float:
    currency = normalize_currency(currency)
    return amount / RATES_PER_USD[currency]


def from_usd(usd_amount: float, currency) -> float:
    currency = normalize_currency(currency)
    return usd_amount * RATES_PER_USD[currency]
