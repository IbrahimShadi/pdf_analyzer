from typing import Dict, Any, Optional, TypedDict, List
import regex as re
from dateutil import parser as dateparser

CURRENCY_SYMBOLS = {
    "$": "USD", "€": "EUR", "£": "GBP", "¥": "JPY", "د.ل": "LYD", "د.إ": "AED", "﷼": "SAR"
}
MONTH_TOKENS = {"JAN","FEB","MAR","APR","MAY","JUN","JUL","AUG","SEP","SEPT","OCT","NOV","DEC"}
TITLE_TOKENS = {"MR","MRS","MS","MISS","MSTR","DR","PROF","REV","SIR","LADY","MME","MLLE","INF","CHD"}
FARE_STOPWORDS = {"NOSHOW","NO-SHOW","NO SHOW","REFUND","NONREF","NON-REF","NON REF","CHANGE","PENALTY","FEE","TAX","BAGGAGE","LYD","USD","EUR","SAR","AED","RULE","FARE","CONDITION","STATUS","HK","OK","VOID"}
AIRLINE_CODE_MAP = {"YL": "Libyan Wings"}

class InvoiceFields(TypedDict, total=False):
    invoice_number: Optional[str]
    customer_name: Optional[str]
    invoice_date: Optional[str]
    total_value: Optional[float]
    currency: Optional[str]

class TicketFields(TypedDict, total=False):
    pnr: Optional[str]
    flight_number: Optional[str]
    passenger_name: Optional[str]
    departure_date: Optional[str]
    carrier: Optional[str]

class PassportFields(TypedDict, total=False):
    surname: Optional[str]
    given_names: Optional[str]
    nationality: Optional[str]
    date_of_expiry: Optional[str]

def try_parse_date(s: str) -> Optional[str]:
    try:
        dt = dateparser.parse(s, dayfirst=True, yearfirst=False, fuzzy=True)
        if dt:
            return dt.strftime("%Y-%m-%d")
    except Exception:
        return None
    return None

def _parse_money(val: str) -> Optional[float]:
    """Parse money strings with both US and EU formats."""
    if not val:
        return None
    val = val.strip().replace(" ", "")
    # If both separators exist, decide decimal by the last occurrence
    if "," in val and "." in val:
        if val.rfind(",") > val.rfind("."):
            # EU style: '.' thousands, ',' decimal
            val = val.replace(".", "").replace(",", ".")
        else:
            # US style: ',' thousands, '.' decimal
            val = val.replace(",", "")
    else:
        if "," in val:
            # Assume comma is decimal
            val = val.replace(".", "").replace(",", ".")
        else:
            # Only '.' present or plain digits: remove thousands just in case
            parts = val.split(".")
            if len(parts) > 2:
                val = "".join(parts[:-1]) + "." + parts[-1]
    try:
        return float(val)
    except Exception:
        return None

def extract_invoice_fields(text: str) -> InvoiceFields:
    out: InvoiceFields = {
        "invoice_number": None,
        "customer_name": None,
        "invoice_date": None,
        "total_value": None,
        "currency": None
    }
    # Invoice number
    m = re.search(r'(?i)(invoice\s*(no\.|no|number)?\s*[:#]?\s*)([A-Z0-9-]{3,})', text)
    if m:
        out["invoice_number"] = m.group(3)

    # Customer name (look after "Bill To" or "Billed To" or "Customer")
    m = re.search(r'(?is)(bill to|billed to|customer)\s*[:\n\r]+\s*([\p{L} \-\.,&]{2,80})', text)
    if m:
        out["customer_name"] = re.sub(r'\s+', ' ', m.group(2)).strip(" \n\r\t:").strip()

    # Date (look for invoice date or date)
    m = re.search(r'(?i)(invoice date|date)\s*[:#-]?\s*([0-9]{1,2}[./-][0-9]{1,2}[./-][0-9]{2,4}|[A-Za-z]{3,9}\s+\d{1,2},?\s+\d{2,4}|\d{1,2}\s+[A-Za-z]{3,9}\s+\d{2,4})', text)
    if m:
        norm = try_parse_date(m.group(2))
        if norm:
            out["invoice_date"] = norm

    # Total (look for total / amount due)
    m = re.search(r'(?is)(total|amount due|grand total)\s*[:#-]?\s*([\p{Sc}$€£¥]?)\s*([0-9]{1,3}(?:[.,][0-9]{3})*(?:[.,][0-9]{2})?)', text)
    if m:
        sym = m.group(2)
        val = m.group(3)
        out["total_value"] = _parse_money(val)
        if sym in CURRENCY_SYMBOLS:
            out["currency"] = CURRENCY_SYMBOLS[sym]

    return out

def _title_case_name(part: str) -> str:
    def fix_token(tok: str) -> str:
        if not tok:
            return tok
        tok = tok.lower()
        if tok.startswith("o'"):  # O'Connor
            return "O'" + tok[2:].title()
        if tok.startswith("d'"):  # D'Arcy
            return "D'" + tok[2:].title()
        if tok.startswith("mc") and len(tok) > 2:  # McDonald
            return "Mc" + tok[2:].title()
        return tok.title()
    return " ".join(fix_token(t) for t in re.split(r"[ -]", part) if t)

def _looks_like_name(s: str) -> bool:
    s = s.strip().strip(",")
    if len(s) < 4 or len(s) > 80:
        return False
    # Must have at least two alphabetic tokens
    tokens = [t for t in re.split(r"\s+", s) if t]
    if sum(1 for t in tokens if re.search(r"[A-Za-z]", t)) < 2:
        return False
    # Reject if it contains obvious fare-rule/currency words
    upper = s.upper()
    for w in FARE_STOPWORDS:
        if w in upper:
            return False
    # Reject if it contains month tokens (often near dates)
    for m in MONTH_TOKENS:
        if m in upper:
            return False
    return True

def _normalize_name(first: str, last: str) -> str:
    return f"{_title_case_name(first)} {_title_case_name(last)}".strip()

def _parse_passenger_name_anywhere(text: str) -> Optional[str]:
    # 1) "PASSENGER INFORMATION" -> title + firstname lastname
    m = re.search(r'(?is)\bPASSENGER INFORMATION\b.*?\b(MR|MRS|MS|MISS|MSTR|DR|PROF)\b\s+([A-Z][A-Z\'\- ]{2,40})', text)
    if m:
        cand = " ".join(re.split(r"\s+", m.group(2).strip()))
        if _looks_like_name(cand):
            parts = cand.split(" ")
            if len(parts) >= 2:
                return _normalize_name(parts[0], " ".join(parts[1:]))

    # 2) IATA LAST/FIRST [TITLE] anywhere
    for m in re.finditer(r'(?i)\b([A-Z][A-Z\'\- ]{1,40})/([A-Z][A-Z\'\- ]{1,40})(?:\s+([A-Z]{2,5}))?\b', text):
        last = m.group(1).strip(" -'/")
        first = m.group(2).strip(" -'/")
        title = (m.group(3) or "").upper().strip()
        if title and title in TITLE_TOKENS:
            pass
        cand = _normalize_name(first, last)
        if _looks_like_name(cand):
            return cand

    # 3) "Passenger Name: ..." variants (DOE, JOHN) or (JOHN DOE)
    for m in re.finditer(r'(?i)\b(Passenger(?: Name)?|Name of Passenger|Passenger)\b\s*[:#]?\s*([A-Z ,\'\-]{4,80})', text):
        cand = m.group(2).strip(" ,")
        m2 = re.search(r'^\s*([A-Z\'\- ]{2,40}),\s*([A-Z\'\- ]{2,40})', cand)
        if m2:
            last, first = m2.group(1), m2.group(2)
            cand2 = _normalize_name(first, last)
            if _looks_like_name(cand2):
                return cand2
        parts = [p for p in cand.split(" ") if p and p.upper() not in TITLE_TOKENS]
        if len(parts) >= 2:
            cand2 = _normalize_name(parts[0], " ".join(parts[1:]))
            if _looks_like_name(cand2):
                return cand2

    # 4) Generic lines with Mr/Mrs + FIRST LAST
    for m in re.finditer(r'(?i)\b(MR|MRS|MS|MISS|MSTR|DR|PROF)\b\s+([A-Z][A-Z\'\- ]{2,60})', text):
        cand = " ".join(re.split(r"\s+", m.group(2).strip()))
        if _looks_like_name(cand):
            parts = cand.split(" ")
            if len(parts) >= 2:
                return _normalize_name(parts[0], " ".join(parts[1:]))

    return None

def _extract_flight_number(text: str) -> Optional[str]:
    # Prefer explicit "Flight-Number" label
    m = re.search(r'(?i)\bFlight-Number\b[^A-Za-z0-9]{0,10}([A-Z]{1,3}\s*\d{2,4})', text)
    if m:
        return m.group(1).replace(" ", "").upper()
    # Next, patterns like "YL 0801 (HK)"
    m = re.search(r'(?i)\b([A-Z]{1,3})\s*(\d{2,4})\s*\(', text)
    if m and m.group(1).upper() not in MONTH_TOKENS:
        return (m.group(1) + m.group(2)).upper()
    # Fallback: standalone code+number but avoid months (e.g., AUG2025)
    m = re.search(r'(?i)\b([A-Z]{1,3})\s*-?\s*(\d{2,4})\b', text)
    if m and m.group(1).upper() not in MONTH_TOKENS:
        return (m.group(1) + m.group(2)).upper()
    return None

def extract_flight_ticket_fields(text: str) -> TicketFields:
    out: TicketFields = {"pnr": None, "flight_number": None, "passenger_name": None, "departure_date": None, "carrier": None}

    # PNR / Booking reference
    m = re.search(r'(?i)\b(PNR|Booking Reference|Booking Ref|Record Locator)\b\s*[:#]?\s*([A-Z0-9]{5,7})', text)
    if m:
        out["pnr"] = m.group(2)

    # Flight number
    fn = _extract_flight_number(text)
    if fn:
        out["flight_number"] = fn
        # Carrier from airline code
        code = re.match(r'([A-Z]{1,3})', fn).group(1) if fn else None
        if code and code in AIRLINE_CODE_MAP:
            out["carrier"] = AIRLINE_CODE_MAP[code]

    # Passenger name anywhere with multiple strategies
    name = _parse_passenger_name_anywhere(text)
    if name:
        out["passenger_name"] = name

    # Departure date: capture the whole "Date ..." line and parse fuzzy
    m = re.search(r'(?im)^\s*Date\b[^\n\r]{0,60}', text)
    if m:
        line = m.group(0)
        line = re.sub(r'(?i)\bDate\b', '', line)
        d = try_parse_date(line)
        if d:
            out["departure_date"] = d

    return out

def extract_passport_fields(text: str) -> Dict[str, Optional[str]]:
    out = {"surname": None, "given_names": None, "nationality": None, "date_of_expiry": None}
    m = re.search(r'(?i)\bSurname\b\s*[:#]?\s*([A-Z][A-Za-z \-]{2,60})', text)
    if m:
        out["surname"] = re.sub(r'\s+', ' ', m.group(1)).strip()
    m = re.search(r'(?i)\b(Given Names|Given name|Forenames)\b\s*[:#]?\s*([A-Z][A-Za-z \-]{2,80})', text)
    if m:
        out["given_names"] = re.sub(r'\s+', ' ', m.group(2)).strip()
    m = re.search(r'(?i)\bNationality\b\s*[:#]?\s*([A-Z]{3}|[A-Za-z ]{3,30})', text)
    if m:
        out["nationality"] = re.sub(r'\s+', ' ', m.group(1)).strip()
    m = re.search(r'(?i)\b(Date of Expiry|Expiry Date|Date of expiration)\b\s*[:#]?\s*([0-9]{1,2}[./-][0-9]{1,2}[./-][0-9]{2,4}|[A-Za-z]{3,9}\s+\d{1,2},?\s+\d{2,4}|\d{1,2}\s+[A-Za-z]{3,9}\s+\d{2,4})', text)
    if m:
        d = try_parse_date(m.group(2))
        if d:
            out["date_of_expiry"] = d
    return out
