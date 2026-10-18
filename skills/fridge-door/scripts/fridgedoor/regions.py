"""Country defaults, so setup needs only the country: currency, time zone, week start, date and time format,
units and paper size. Week starts and date patterns follow Unicode CLDR locale data. Everything is a setting the
household can change afterwards.

Countries with several time zones are marked, with their main zones (ZONES): setup asks which one.
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


# The main time zones of each country marked as having several: setup asks which one (needs_timezone).
ZONES = {
    "AU": [("Australia/Sydney", "New South Wales and the ACT"), ("Australia/Melbourne", "Victoria"),
           ("Australia/Brisbane", "Queensland"), ("Australia/Adelaide", "South Australia"),
           ("Australia/Darwin", "Northern Territory"), ("Australia/Perth", "Western Australia"),
           ("Australia/Hobart", "Tasmania")],
    "BR": [("America/Sao_Paulo", "Brasília time: most of the south, southeast and northeast"),
           ("America/Manaus", "Amazonas"), ("America/Cuiaba", "Mato Grosso"), ("America/Rio_Branco", "Acre"),
           ("America/Noronha", "Fernando de Noronha")],
    "CA": [("America/Vancouver", "British Columbia"), ("America/Edmonton", "Alberta"),
           ("America/Regina", "Saskatchewan"), ("America/Winnipeg", "Manitoba"),
           ("America/Toronto", "Ontario and Quebec"), ("America/Halifax", "Nova Scotia, New Brunswick and PEI"),
           ("America/St_Johns", "Newfoundland"), ("America/Whitehorse", "Yukon")],
    "CL": [("America/Santiago", "the mainland"), ("America/Punta_Arenas", "Magallanes"),
           ("Pacific/Easter", "Easter Island")],
    "ES": [("Europe/Madrid", "the mainland and the Balearic Islands"), ("Atlantic/Canary", "the Canary Islands")],
    "ID": [("Asia/Jakarta", "western: Java and Sumatra"), ("Asia/Makassar", "central: Bali and Sulawesi"),
           ("Asia/Jayapura", "eastern: Papua and Maluku")],
    "MX": [("America/Mexico_City", "central"), ("America/Cancun", "Quintana Roo"),
           ("America/Mazatlan", "Sinaloa, Nayarit and Baja California Sur"), ("America/Hermosillo", "Sonora"),
           ("America/Tijuana", "Baja California"), ("America/Chihuahua", "Chihuahua")],
    "PT": [("Europe/Lisbon", "the mainland and Madeira"), ("Atlantic/Azores", "the Azores")],
    "US": [("America/New_York", "Eastern"), ("America/Chicago", "Central"), ("America/Denver", "Mountain"),
           ("America/Phoenix", "Arizona"), ("America/Los_Angeles", "Pacific"), ("America/Anchorage", "Alaska"),
           ("Pacific/Honolulu", "Hawaii")],
}  # fmt: skip


# Every country's name (ISO 3166-1), so setup takes any country by name; those without defaults above get
# international formats and setup asks for the currency.
_ISO = (
    "AD Andorra|AE United Arab Emirates|AF Afghanistan|AG Antigua and Barbuda|AI Anguilla|AL Albania|AM Armenia|"
    "AO Angola|AQ Antarctica|AR Argentina|AS American Samoa|AT Austria|AU Australia|AW Aruba|AX Aland Islands|"
    "AZ Azerbaijan|BA Bosnia and Herzegovina|BB Barbados|BD Bangladesh|BE Belgium|BF Burkina Faso|BG Bulgaria|"
    "BH Bahrain|BI Burundi|BJ Benin|BL Saint Barthelemy|BM Bermuda|BN Brunei|BO Bolivia|BQ Caribbean Netherlands|"
    "BR Brazil|BS Bahamas|BT Bhutan|BV Bouvet Island|BW Botswana|BY Belarus|BZ Belize|CA Canada|"
    "CC Cocos Islands|CD Democratic Republic of the Congo|CF Central African Republic|CG Republic of the Congo|"
    "CH Switzerland|CI Cote d'Ivoire|CK Cook Islands|CL Chile|CM Cameroon|CN China|CO Colombia|CR Costa Rica|"
    "CU Cuba|CV Cape Verde|CW Curacao|CX Christmas Island|CY Cyprus|CZ Czechia|DE Germany|DJ Djibouti|DK Denmark|"
    "DM Dominica|DO Dominican Republic|DZ Algeria|EC Ecuador|EE Estonia|EG Egypt|EH Western Sahara|ER Eritrea|"
    "ES Spain|ET Ethiopia|FI Finland|FJ Fiji|FK Falkland Islands|FM Micronesia|FO Faroe Islands|FR France|"
    "GA Gabon|GB United Kingdom|GD Grenada|GE Georgia|GF French Guiana|GG Guernsey|GH Ghana|GI Gibraltar|"
    "GL Greenland|GM Gambia|GN Guinea|GP Guadeloupe|GQ Equatorial Guinea|GR Greece|"
    "GS South Georgia and the South Sandwich Islands|GT Guatemala|GU Guam|GW Guinea-Bissau|GY Guyana|"
    "HK Hong Kong|HM Heard Island and McDonald Islands|HN Honduras|HR Croatia|HT Haiti|HU Hungary|ID Indonesia|"
    "IE Ireland|IL Israel|IM Isle of Man|IN India|IO British Indian Ocean Territory|IQ Iraq|IR Iran|IS Iceland|"
    "IT Italy|JE Jersey|JM Jamaica|JO Jordan|JP Japan|KE Kenya|KG Kyrgyzstan|KH Cambodia|KI Kiribati|KM Comoros|"
    "KN Saint Kitts and Nevis|KP North Korea|KR South Korea|KW Kuwait|KY Cayman Islands|KZ Kazakhstan|LA Laos|"
    "LB Lebanon|LC Saint Lucia|LI Liechtenstein|LK Sri Lanka|LR Liberia|LS Lesotho|LT Lithuania|LU Luxembourg|"
    "LV Latvia|LY Libya|MA Morocco|MC Monaco|MD Moldova|ME Montenegro|MF Saint Martin|MG Madagascar|"
    "MH Marshall Islands|MK North Macedonia|ML Mali|MM Myanmar|MN Mongolia|MO Macao|MP Northern Mariana Islands|"
    "MQ Martinique|MR Mauritania|MS Montserrat|MT Malta|MU Mauritius|MV Maldives|MW Malawi|MX Mexico|MY Malaysia|"
    "MZ Mozambique|NA Namibia|NC New Caledonia|NE Niger|NF Norfolk Island|NG Nigeria|NI Nicaragua|NL Netherlands|"
    "NO Norway|NP Nepal|NR Nauru|NU Niue|NZ New Zealand|OM Oman|PA Panama|PE Peru|PF French Polynesia|"
    "PG Papua New Guinea|PH Philippines|PK Pakistan|PL Poland|PM Saint Pierre and Miquelon|PN Pitcairn Islands|"
    "PR Puerto Rico|PS Palestine|PT Portugal|PW Palau|PY Paraguay|QA Qatar|RE Reunion|RO Romania|RS Serbia|"
    "RU Russia|RW Rwanda|SA Saudi Arabia|SB Solomon Islands|SC Seychelles|SD Sudan|SE Sweden|SG Singapore|"
    "SH Saint Helena|SI Slovenia|SJ Svalbard and Jan Mayen|SK Slovakia|SL Sierra Leone|SM San Marino|SN Senegal|"
    "SO Somalia|SR Suriname|SS South Sudan|ST Sao Tome and Principe|SV El Salvador|SX Sint Maarten|SY Syria|"
    "SZ Eswatini|TC Turks and Caicos Islands|TD Chad|TF French Southern Territories|TG Togo|TH Thailand|"
    "TJ Tajikistan|TK Tokelau|TL Timor-Leste|TM Turkmenistan|TN Tunisia|TO Tonga|TR Turkiye|"
    "TT Trinidad and Tobago|TV Tuvalu|TW Taiwan|TZ Tanzania|UA Ukraine|UG Uganda|"
    "UM United States Minor Outlying Islands|US United States|UY Uruguay|UZ Uzbekistan|VA Vatican City|"
    "VC Saint Vincent and the Grenadines|VE Venezuela|VG British Virgin Islands|VI US Virgin Islands|VN Vietnam|"
    "VU Vanuatu|WF Wallis and Futuna|WS Samoa|YE Yemen|YT Mayotte|ZA South Africa|ZM Zambia|ZW Zimbabwe|"
    # Other names people use
    "CI Ivory Coast|CV Cabo Verde|SZ Swaziland|TR Turkey|MM Burma|TL East Timor|VN Viet Nam|VA Holy See|"
    "VA Vatican|MK Macedonia|CD DR Congo|CD DRC|IE Republic of Ireland|RU Russian Federation|BN Brunei Darussalam|"
    "LA Lao|KR Republic of Korea|KP Democratic People's Republic of Korea|IR Islamic Republic of Iran|"
    "SY Syrian Arab Republic|MD Republic of Moldova|BO Plurinational State of Bolivia|VE Bolivarian Republic of "
    "Venezuela|TZ United Republic of Tanzania|PS State of Palestine|FM Federated States of Micronesia"
)
_ISO_NAMES = {fold(name): code for code, name in (item.split(" ", 1) for item in _ISO.split("|"))}


def country_code(text: str) -> str:
    """ISO code from a code or a country name ("CA", "canada", "UK" -> "GB")."""
    key = fold(text).replace("\u2019", "'")
    if not key:
        raise ToolError("Which country?", hint="Give a country name or its two-letter code, e.g. CA or Canada.")
    if key.upper() in _C:
        return key.upper()
    if key in _NAMES:
        return _NAMES[key]
    for code, row in _C.items():
        if fold(row[0]) == key:
            return code
    if key in _ISO_NAMES:
        return _ISO_NAMES[key]
    if key.startswith("the ") and key[4:] in _ISO_NAMES:
        return _ISO_NAMES[key[4:]]
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
