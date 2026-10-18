"""Country defaults, so setup needs only the country: currency, time zone, week start, date and time format,
units and paper size. Week starts and date patterns follow Unicode CLDR locale data. Everything is a setting the
household can change afterwards.

Countries with several time zones are marked; setup then says which zone it picked so the person can correct it.
"""

from __future__ import annotations

from .util import ToolError, fold

# code: (name, currency, timezone, week_start, date_format, time_format, units, paper, several_time_zones)
_C = {
    "US": ("United States", "USD", "America/New_York", "sunday", "MM/DD/YYYY", "12h", "us", "letter", True),
    "CA": ("Canada", "CAD", "America/Toronto", "sunday", "YYYY-MM-DD", "12h", "metric", "letter", True),
    "MX": ("Mexico", "MXN", "America/Mexico_City", "sunday", "DD/MM/YYYY", "12h", "metric", "letter", True),
    "BR": ("Brazil", "BRL", "America/Sao_Paulo", "sunday", "DD/MM/YYYY", "24h", "metric", "a4", True),
    "AR": ("Argentina", "ARS", "America/Argentina/Buenos_Aires", "monday", "DD/MM/YYYY", "24h", "metric", "a4", False),
    "CL": ("Chile", "CLP", "America/Santiago", "monday", "DD-MM-YYYY", "24h", "metric", "letter", True),
    "CO": ("Colombia", "COP", "America/Bogota", "sunday", "DD/MM/YYYY", "12h", "metric", "letter", False),
    "PE": ("Peru", "PEN", "America/Lima", "sunday", "DD/MM/YYYY", "12h", "metric", "a4", False),
    "GB": ("United Kingdom", "GBP", "Europe/London", "monday", "DD/MM/YYYY", "24h", "metric", "a4", False),
    "IE": ("Ireland", "EUR", "Europe/Dublin", "monday", "DD/MM/YYYY", "24h", "metric", "a4", False),
    "FR": ("France", "EUR", "Europe/Paris", "monday", "DD/MM/YYYY", "24h", "metric", "a4", False),
    "DE": ("Germany", "EUR", "Europe/Berlin", "monday", "DD.MM.YYYY", "24h", "metric", "a4", False),
    "AT": ("Austria", "EUR", "Europe/Vienna", "monday", "DD.MM.YYYY", "24h", "metric", "a4", False),
    "CH": ("Switzerland", "CHF", "Europe/Zurich", "monday", "DD.MM.YYYY", "24h", "metric", "a4", False),
    "BE": ("Belgium", "EUR", "Europe/Brussels", "monday", "DD/MM/YYYY", "24h", "metric", "a4", False),
    "NL": ("Netherlands", "EUR", "Europe/Amsterdam", "monday", "DD-MM-YYYY", "24h", "metric", "a4", False),
    "LU": ("Luxembourg", "EUR", "Europe/Luxembourg", "monday", "DD.MM.YYYY", "24h", "metric", "a4", False),
    "ES": ("Spain", "EUR", "Europe/Madrid", "monday", "DD/MM/YYYY", "24h", "metric", "a4", True),
    "PT": ("Portugal", "EUR", "Europe/Lisbon", "sunday", "DD/MM/YYYY", "24h", "metric", "a4", True),
    "IT": ("Italy", "EUR", "Europe/Rome", "monday", "DD/MM/YYYY", "24h", "metric", "a4", False),
    "GR": ("Greece", "EUR", "Europe/Athens", "monday", "DD/MM/YYYY", "24h", "metric", "a4", False),
    "PL": ("Poland", "PLN", "Europe/Warsaw", "monday", "DD.MM.YYYY", "24h", "metric", "a4", False),
    "CZ": ("Czechia", "CZK", "Europe/Prague", "monday", "DD.MM.YYYY", "24h", "metric", "a4", False),
    "SK": ("Slovakia", "EUR", "Europe/Bratislava", "monday", "DD.MM.YYYY", "24h", "metric", "a4", False),
    "HU": ("Hungary", "HUF", "Europe/Budapest", "monday", "YYYY.MM.DD", "24h", "metric", "a4", False),
    "RO": ("Romania", "RON", "Europe/Bucharest", "monday", "DD.MM.YYYY", "24h", "metric", "a4", False),
    "BG": ("Bulgaria", "EUR", "Europe/Sofia", "monday", "DD.MM.YYYY", "24h", "metric", "a4", False),
    "HR": ("Croatia", "EUR", "Europe/Zagreb", "monday", "DD.MM.YYYY", "24h", "metric", "a4", False),
    "SI": ("Slovenia", "EUR", "Europe/Ljubljana", "monday", "DD.MM.YYYY", "24h", "metric", "a4", False),
    "DK": ("Denmark", "DKK", "Europe/Copenhagen", "monday", "DD.MM.YYYY", "24h", "metric", "a4", False),
    "SE": ("Sweden", "SEK", "Europe/Stockholm", "monday", "YYYY-MM-DD", "24h", "metric", "a4", False),
    "NO": ("Norway", "NOK", "Europe/Oslo", "monday", "DD.MM.YYYY", "24h", "metric", "a4", False),
    "FI": ("Finland", "EUR", "Europe/Helsinki", "monday", "DD.MM.YYYY", "24h", "metric", "a4", False),
    "IS": ("Iceland", "ISK", "Atlantic/Reykjavik", "monday", "DD.MM.YYYY", "24h", "metric", "a4", False),
    "EE": ("Estonia", "EUR", "Europe/Tallinn", "monday", "DD.MM.YYYY", "24h", "metric", "a4", False),
    "LV": ("Latvia", "EUR", "Europe/Riga", "monday", "DD.MM.YYYY", "24h", "metric", "a4", False),
    "LT": ("Lithuania", "EUR", "Europe/Vilnius", "monday", "YYYY-MM-DD", "24h", "metric", "a4", False),
    "UA": ("Ukraine", "UAH", "Europe/Kyiv", "monday", "DD.MM.YYYY", "24h", "metric", "a4", False),
    "TR": ("Türkiye", "TRY", "Europe/Istanbul", "monday", "DD.MM.YYYY", "24h", "metric", "a4", False),
    "IL": ("Israel", "ILS", "Asia/Jerusalem", "sunday", "DD.MM.YYYY", "24h", "metric", "a4", False),
    "AE": ("United Arab Emirates", "AED", "Asia/Dubai", "monday", "DD/MM/YYYY", "12h", "metric", "a4", False),
    "SA": ("Saudi Arabia", "SAR", "Asia/Riyadh", "sunday", "DD/MM/YYYY", "12h", "metric", "a4", False),
    "QA": ("Qatar", "QAR", "Asia/Qatar", "saturday", "DD/MM/YYYY", "12h", "metric", "a4", False),
    "EG": ("Egypt", "EGP", "Africa/Cairo", "saturday", "DD/MM/YYYY", "12h", "metric", "a4", False),
    "MA": ("Morocco", "MAD", "Africa/Casablanca", "monday", "DD/MM/YYYY", "24h", "metric", "a4", False),
    "NG": ("Nigeria", "NGN", "Africa/Lagos", "monday", "DD/MM/YYYY", "12h", "metric", "a4", False),
    "GH": ("Ghana", "GHS", "Africa/Accra", "monday", "DD/MM/YYYY", "12h", "metric", "a4", False),
    "KE": ("Kenya", "KES", "Africa/Nairobi", "sunday", "DD/MM/YYYY", "12h", "metric", "a4", False),
    "ZA": ("South Africa", "ZAR", "Africa/Johannesburg", "sunday", "YYYY/MM/DD", "24h", "metric", "a4", False),
    "IN": ("India", "INR", "Asia/Kolkata", "sunday", "DD/MM/YYYY", "12h", "metric", "a4", False),
    "PK": ("Pakistan", "PKR", "Asia/Karachi", "sunday", "DD/MM/YYYY", "12h", "metric", "a4", False),
    "BD": ("Bangladesh", "BDT", "Asia/Dhaka", "sunday", "DD/MM/YYYY", "12h", "metric", "a4", False),
    "LK": ("Sri Lanka", "LKR", "Asia/Colombo", "monday", "YYYY-MM-DD", "12h", "metric", "a4", False),
    "NP": ("Nepal", "NPR", "Asia/Kathmandu", "sunday", "YYYY-MM-DD", "12h", "metric", "a4", False),
    "CN": ("China", "CNY", "Asia/Shanghai", "monday", "YYYY/MM/DD", "24h", "metric", "a4", False),
    "HK": ("Hong Kong", "HKD", "Asia/Hong_Kong", "sunday", "DD/MM/YYYY", "12h", "metric", "a4", False),
    "TW": ("Taiwan", "TWD", "Asia/Taipei", "sunday", "YYYY/MM/DD", "12h", "metric", "a4", False),
    "JP": ("Japan", "JPY", "Asia/Tokyo", "sunday", "YYYY/MM/DD", "24h", "metric", "a4", False),
    "KR": ("South Korea", "KRW", "Asia/Seoul", "sunday", "YYYY.MM.DD", "12h", "metric", "a4", False),
    "SG": ("Singapore", "SGD", "Asia/Singapore", "sunday", "DD/MM/YYYY", "12h", "metric", "a4", False),
    "MY": ("Malaysia", "MYR", "Asia/Kuala_Lumpur", "monday", "DD/MM/YYYY", "12h", "metric", "a4", False),
    "ID": ("Indonesia", "IDR", "Asia/Jakarta", "sunday", "DD/MM/YYYY", "24h", "metric", "a4", True),
    "PH": ("Philippines", "PHP", "Asia/Manila", "sunday", "MM/DD/YYYY", "12h", "metric", "letter", False),
    "TH": ("Thailand", "THB", "Asia/Bangkok", "sunday", "DD/MM/YYYY", "24h", "metric", "a4", False),
    "VN": ("Vietnam", "VND", "Asia/Ho_Chi_Minh", "monday", "DD/MM/YYYY", "24h", "metric", "a4", False),
    "AU": ("Australia", "AUD", "Australia/Sydney", "monday", "DD/MM/YYYY", "12h", "metric", "a4", True),
    "NZ": ("New Zealand", "NZD", "Pacific/Auckland", "monday", "DD/MM/YYYY", "12h", "metric", "a4", False),
}

# Used for a country that isn't in the table: international formats, and the currency must be given.
FALLBACK = ("", "", "UTC", "monday", "YYYY-MM-DD", "24h", "metric", "a4", False)

_NAMES = {
    "usa": "US",
    "united states of america": "US",
    "america": "US",
    "uk": "GB",
    "britain": "GB",
    "great britain": "GB",
    "england": "GB",
    "scotland": "GB",
    "wales": "GB",
    "northern ireland": "GB",
    "uae": "AE",
    "emirates": "AE",
    "holland": "NL",
    "the netherlands": "NL",
    "czech republic": "CZ",
    "turkey": "TR",
    "korea": "KR",
    "republic of korea": "KR",
}

WEEK_STARTS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
DATE_FORMATS = ("YYYY-MM-DD", "DD/MM/YYYY", "MM/DD/YYYY", "DD.MM.YYYY", "DD-MM-YYYY", "YYYY/MM/DD", "YYYY.MM.DD")
TIME_FORMATS = ("24h", "12h")
UNITS = ("metric", "us")
PAPERS = ("a4", "letter")


def country_code(text: str) -> str:
    """ISO code from a code or a country name ("CA", "canada", "UK" -> "GB")."""
    key = fold(text)
    if not key:
        raise ToolError("Which country?", hint="Give a country name or its two-letter code, e.g. CA or Canada.")
    if key.upper() in _C:
        return key.upper()
    if key in _NAMES:
        return _NAMES[key]
    for code, row in _C.items():
        if fold(row[0]) == key:
            return code
    if len(key) == 2 and key.isalpha():
        return key.upper()  # a real country we have no defaults for: international formats
    raise ToolError(
        f"I don't know the country {text!r}.",
        hint="Use its two-letter ISO code (e.g. NZ, DE, ZA).",
        code="bad_country",
    )


def defaults(code: str) -> dict:
    """The settings a household in this country starts with."""
    row = _C.get(code, FALLBACK)
    return {
        "country": code,
        "country_name": row[0] or code,
        "currency": row[1],
        "timezone": row[2],
        "week_start": row[3],
        "date_format": row[4],
        "time_format": row[5],
        "units": row[6],
        "paper": row[7],
        "several_time_zones": row[8],
        "known": code in _C,
    }


def all_codes() -> list:
    return sorted(_C)
