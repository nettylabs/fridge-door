"""Exact money maths: Decimal only, each currency's own decimal places, and splits that add up exactly.

Use these instead of floats or round(). A rounding mistake on money is worse than an error message.
Delete this file if the plugin never handles money.
"""

from __future__ import annotations

import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from .util import ToolError

# ISO 4217 currencies whose smallest unit isn't 2 decimal places. Every other currency uses 2.
ZERO_DECIMAL = {
    "BIF", "CLP", "DJF", "GNF", "ISK", "JPY", "KMF", "KRW", "PYG", "RWF", "UGX", "VND", "VUV", "XAF", "XOF", "XPF",
}  # fmt: skip
THREE_DECIMAL = {"BHD", "IQD", "JOD", "KWD", "LYD", "OMR", "TND"}
_PLAIN_RE = re.compile(r"^-?(\d+(\.\d+)?|\.\d+)$")


def places(currency: str) -> int:
    """Decimal places of the currency's smallest unit: JPY 0, KWD 3, most others 2."""
    code = (currency or "").upper()
    return 0 if code in ZERO_DECIMAL else 3 if code in THREE_DECIMAL else 2


def unit(currency: str) -> Decimal:
    return Decimal(1).scaleb(-places(currency))


def to_decimal(value, field: str = "amount") -> Decimal:
    """Parse a number strictly: 1234.5, "1234.50", "$1234.50" or "1234.50 EUR".

    Commas are refused. "1,500" is fifteen hundred in some countries and one and a half in others, and a
    wrong guess on money is worse than a clear error the agent can fix.
    """
    if isinstance(value, bool) or value is None:
        raise ToolError(
            f"{field} is missing or not a number.", hint="Pass a plain number such as 1234.50.", code="bad_number"
        )
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, float):
        return Decimal(repr(value))
    text = str(value).strip().replace(" ", "").replace(" ", "")
    text = re.sub(r"^[^\d\-.]+", "", text)  # a currency symbol or code in front
    text = re.sub(r"[^\d.]+$", "", text)  # or after
    if not _PLAIN_RE.match(text):
        raise ToolError(
            f"{field} {value!r} is not a plain number.",
            hint="Use digits with a dot for decimals and no thousands separators, e.g. 1500 or 1.50.",
            code="bad_number",
        )
    try:
        return Decimal(text)
    except InvalidOperation as exc:  # pragma: no cover - the pattern already guards this
        raise ToolError(f"{field} {value!r} is not a number.", code="bad_number") from exc


def quantize(value, currency: str) -> Decimal:
    """Round to the currency's smallest unit, half up (the way people round money by hand)."""
    return to_decimal(value).quantize(unit(currency), rounding=ROUND_HALF_UP)


def allocate(total, weights, currency: str) -> list:
    """Split total by weights so the parts add up to exactly total, in the currency's smallest unit.

    Largest-remainder method: everyone gets their share rounded down, then the units left over go to the
    largest remainders (ties to the earlier entry). Rounding each share on its own loses or invents cents:
    100.00 split three ways must be 33.34 + 33.33 + 33.33, never 33.33 x 3.
    """
    weights = [to_decimal(w, "weight") for w in weights]
    if not weights or any(w < 0 for w in weights) or sum(weights) == 0:
        raise ToolError("Weights must be zero or more, and not all zero.", code="bad_weights")
    step = unit(currency)
    total = quantize(total, currency)
    sign = -1 if total < 0 else 1
    units = int(abs(total) / step)
    weight_sum = sum(weights)
    exact = [Decimal(units) * w / weight_sum for w in weights]
    shares = [int(e) for e in exact]
    leftover = units - sum(shares)
    for i in sorted(range(len(weights)), key=lambda i: (-(exact[i] - shares[i]), i))[:leftover]:
        shares[i] += 1
    return [sign * Decimal(n) * step for n in shares]


def cash_round(value, step) -> Decimal:
    """Round a cash amount to the smallest coin in use: for example 0.05 in Canada and Australia, 0.10 in New
    Zealand. Card and bank payments stay exact. Keep the step as a business setting: for the euro it depends
    on the country, so never assume it from the currency alone."""
    step = to_decimal(step, "cash rounding step")
    if step <= 0:
        raise ToolError("The cash rounding step must be more than zero.", code="bad_step")
    return (to_decimal(value) / step).quantize(Decimal(1), rounding=ROUND_HALF_UP) * step


# --------------------------------------------------------------------------- display (from Job to Paid)

# (symbol, position, decimal separator, thousands separator). Settings can override the code display.
CURRENCY_DEFAULTS = {
    "USD": ("$", "before", ".", ","),
    "CAD": ("$", "before", ".", ","),
    "AUD": ("$", "before", ".", ","),
    "NZD": ("$", "before", ".", ","),
    "MXN": ("$", "before", ".", ","),
    "GBP": ("£", "before", ".", ","),
    "EUR": (" €", "after", ",", "."),
    "CHF": ("CHF ", "before", ".", "'"),
    "JPY": ("¥", "before", ".", ","),
    "CNY": ("¥", "before", ".", ","),
    "INR": ("₹", "before", ".", ","),
    "ZAR": ("R ", "before", ".", " "),
    "BRL": ("R$ ", "before", ",", "."),
    "SEK": (" kr", "after", ",", " "),
    "NOK": (" kr", "after", ",", " "),
    "DKK": (" kr.", "after", ",", "."),
    "ISK": (" kr", "after", ",", "."),
    "PLN": (" zł", "after", ",", " "),
    "CZK": (" Kč", "after", ",", " "),
    "HUF": (" Ft", "after", ",", " "),
    "SGD": ("S$", "before", ".", ","),
    "HKD": ("HK$", "before", ".", ","),
    "TWD": ("NT$", "before", ".", ","),
    "AED": ("AED ", "before", ".", ","),
    "SAR": ("SAR ", "before", ".", ","),
    "PHP": ("₱", "before", ".", ","),
    "NGN": ("₦", "before", ".", ","),
    "KES": ("KSh ", "before", ".", ","),
    "ILS": ("₪", "before", ".", ","),
    "KRW": ("₩", "before", ".", ","),
    "TRY": ("₺", "before", ",", "."),
    "THB": ("฿", "before", ".", ","),
    "IDR": ("Rp ", "before", ",", "."),
    "MYR": ("RM ", "before", ".", ","),
    "VND": (" ₫", "after", ",", "."),
    "KWD": ("KWD ", "before", ".", ","),
}


def currency_display(settings: dict) -> dict:
    code = (settings.get("currency") or "USD").upper()
    symbol, position, dec_sep, thou_sep = CURRENCY_DEFAULTS.get(code, (code + " ", "before", ".", ","))
    return {
        "code": code,
        "symbol": symbol,
        "position": position,
        "decimal": dec_sep,
        "thousands": thou_sep,
        "places": places(code),
        "show_code": _show_code(code, symbol, settings.get("currency_display") or "auto"),
        "always": (settings.get("currency_display") or "auto") == "always",
    }


def _show_code(code: str, symbol: str, setting: str) -> bool:
    """Show the ISO code next to totals? "auto" does when another currency shares the symbol ($, kr, ¥)."""
    if symbol.strip().upper() == code or setting == "never":
        return False
    if setting == "always":
        return True
    mine = symbol.strip()
    return any(other != code and entry[0].strip() == mine for other, entry in CURRENCY_DEFAULTS.items())


def _group(digits: str, sep: str) -> str:
    if not sep or len(digits) <= 3:
        return digits
    head = len(digits) % 3 or 3
    return sep.join([digits[:head]] + [digits[i : i + 3] for i in range(head, len(digits), 3)])


def format_number(value, disp: dict) -> str:
    rounded = to_decimal(value).quantize(unit(disp["code"]), rounding=ROUND_HALF_UP)
    negative = rounded < 0
    whole, _, frac = format(abs(rounded), "f").partition(".")
    out = _group(whole, disp["thousands"])
    if disp["places"]:
        out += disp["decimal"] + frac
    return ("-" if negative else "") + out


def fmt(value, disp: dict, code: bool = False) -> str:
    """ "$1,234.50", "1.234,50 €", "¥1,235". The code is added ("$1,234.50 CAD") on every amount when the household
    chose currency_display=always, and with code=True (a printout's headline total) when the symbol is shared."""
    number = format_number(value, disp)
    negative = number.startswith("-")
    number = number.lstrip("-")
    number = disp["symbol"] + number if disp["position"] == "before" else number + disp["symbol"]
    if (code or disp.get("always")) and disp["show_code"]:
        number += f" {disp['code']}"
    return ("-" if negative else "") + number
