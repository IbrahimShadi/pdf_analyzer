from typing import Dict, Any, Optional, TypedDict, List, Tuple
import regex as re
from dateutil import parser as dateparser

# =========================
# Constants & small helpers
# =========================

MONTH_TOKENS = {"JAN","FEB","MAR","APR","MAY","JUN","JUL","AUG","SEP","SEPT","OCT","NOV","DEC"}

# One unified set for both filtering and glued-suffix removal
TITLE_TOKENS = {"MR","MRS","MS","MISS","MSTR","DR","PROF","REV","JR","SR","II","III","IV","MME","MLLE","SIR","LADY","INF","CHD"}

# words that must NOT appear inside a passenger name candidate (filters out "Person Kg", airline words, etc.)
NAME_STOPWORDS = {
    "AIR","AIRWAYS","AIRLINE","AERO","BURAQ","BERNIQ","MEDSKY","LIBYAN","WINGS","CARRIER",
    "BOARDING","GATE","ARRIVAL","DEPARTURE","DEPARTING","ARRIVING","FLIGHT","ORIGIN",
    "DESTINATION","AIRPORT","TERMINAL","VARS","PERSON","KG","CO2","EMISSIONS","CHECKMYTRIP","APP",
    "ELECTRONIC","TICKET","RECEIPT","REFERENCE","RECORD","LOCATOR","CONTACT","NAME","PASSENGER"
}

# Airline code allow-list (extend as you see more)
KNOWN_AIRLINE_CODES = {
    "NB","BM","UZ","YL",           # local samples (Berniq, MedSky, Buraq, Libyan Wings)
    "AF","TK","BJ","TU","KL","AZ","LH","BA","EK","QR","MS","PC","A3","W6","FR","U2","VY","TP","IB","SN","OS","LX","LO"
}

# Map 2/3-letter codes to carrier names (extend as needed)
AIRLINE_CODE_MAP = {
    "NB": "Berniq Airways", "BM": "MedSky Airways", "UZ": "Buraq Air", "YL": "Libyan Wings",
    "AF": "Air France", "TK": "Turkish Airlines", "BJ": "Nouvelair", "TU": "Tunisair"
}

def _normalize_time(hh: str, mm: str, ampm: Optional[str]) -> str:
    h = int(hh)
    if ampm:
        a = ampm.upper()
        if a == "PM" and h != 12: h += 12
        if a == "AM" and h == 12: h = 0
    return f"{h:02d}:{int(mm):02d}"

def try_parse_date(s: str) -> Optional[str]:
    try:
        dt = dateparser.parse(s, dayfirst=True, yearfirst=False, fuzzy=True)
        if dt:
            return dt.strftime("%Y-%m-%d")
    except Exception:
        return None
    return None

MONTH_MAP = {
    'JAN':'Jan','FEB':'Feb','MAR':'Mar','APR':'Apr','MAY':'May','JUN':'Jun',
    'JUL':'Jul','AUG':'Aug','SEP':'Sep','SEPT':'Sep','OCT':'Oct','NOV':'Nov','DEC':'Dec'
}

def parse_ddmmm(token: str) -> Optional[str]:
    # 02JUN / 2JUN / 02 JUN
    m = re.match(r"(?i)^\s*(\d{1,2})\s*([A-Z]{3,4})\s*$", token.strip())
    if not m:
        return None
    d, mon = m.group(1), m.group(2).upper()
    mon_std = MONTH_MAP.get(mon)
    if not mon_std:
        return None
    try:
        dt = dateparser.parse(f"{d} {mon_std}", dayfirst=True, fuzzy=True)
        if dt:
            return dt.strftime("%Y-%m-%d")
    except Exception:
        return None
    return None

def _title_case_name(part: str) -> str:
    def fix_token(tok: str) -> str:
        if not tok:
            return tok
        t = tok.lower()
        if t.startswith("o'"):
            return "O'" + t[2:].title()
        if t.startswith("d'"):
            return "D'" + t[2:].title()
        if t.startswith("mc") and len(t) > 2:
            return "Mc" + t[2:].title()
        return t.title()
    return " ".join(fix_token(t) for t in re.split(r"[ -]", part) if t)

def _normalize_name(first: str, last: str) -> str:
    return f"{_title_case_name(first)} {_title_case_name(last)}".strip()

def _unglue_title_suffix(s: str) -> str:
    # remove a title glued at the *end* of the first-name token (uses unified TITLE_TOKENS)
    pat = r"(?:%s)\.?$" % "|".join(sorted(TITLE_TOKENS, key=len, reverse=True))
    return re.sub(pat, "", s, flags=re.I)

def _looks_like_name(s: str) -> bool:
    # shape + stopword filter
    s = s.strip(" ,")
    if len(s) < 4 or len(s) > 80:
        return False
    if re.search(r"[^A-Za-z '\-]", s):  # only letters, spaces, apostrophes, hyphens
        return False
    parts = [p for p in re.split(r"\s+", s) if p]
    if not (2 <= len(parts) <= 4):
        return False
    if any(len(re.sub(r"[^A-Za-z]", "", p)) < 2 for p in parts):
        return False
    U = s.upper()
    if any(w in U for w in NAME_STOPWORDS):
        return False
    if any(m in U for m in MONTH_TOKENS):
        return False
    return True

# =================
# Invoice extractor
# =================

class InvoiceFields(TypedDict, total=False):
    invoice_number: Optional[str]
    customer_name: Optional[str]
    invoice_date: Optional[str]
    total_value: Optional[float]
    currency: Optional[str]

def extract_invoice_fields(text: str) -> InvoiceFields:
    out: InvoiceFields = {
        "invoice_number": None, "customer_name": None,
        "invoice_date": None, "total_value": None, "currency": None
    }

    # Invoice number
    m = re.search(r"(?i)(invoice\s*(no\.|no|number)?\s*[:#]?\s*)([A-Z0-9-]{3,})", text)
    if m:
        out["invoice_number"] = m.group(3)

    # Customer name (Bill To)
    m = re.search(r"(?is)(bill to|billed to|customer)\s*[:\n\r]+\s*([\p{L} \-\.,&]{2,80})", text)
    if m:
        out["customer_name"] = re.sub(r"\s+", " ", m.group(2)).strip(" \n\r\t:").strip()

    # Date
    m = re.search(r"(?i)(invoice date|date of issue|issue date|date)\s*[:#-]?\s*("
                  r"[0-9]{1,2}[./-][0-9]{1,2}[./-][0-9]{2,4}"
                  r"|[A-Za-z]{3,9}\s+\d{1,2},?\s+\d{2,4}"
                  r"|\d{1,2}\s+[A-Za-z]{3,9}\s+\d{2,4})", text)
    if m:
        d = try_parse_date(m.group(2))
        if d:
            out["invoice_date"] = d

    # Amount (supports Euro/commas)
        # Amount (supports Euro/commas)
    m = re.search(r"(?is)(total amount|amount due|grand total|total)\s*[:#-]?\s*([\p{Sc}$€£¥]?\s*)?"
                  r"([0-9]{1,3}(?:[.,][0-9]{3})*(?:[.,][0-9]{2})?)\s*(LYD|USD|EUR|GBP|SAR|AED)?", text)
    if m:
        val = m.group(3)
        cur = (m.group(4) or "").upper()
        sym = (m.group(2) or "").strip()

        vv = val.strip().replace(" ", "")

        if "," in vv and "." in vv:
            # Decide which is decimal separator by the last symbol
            if vv.rfind(",") > vv.rfind("."):
                # 2.345,67  ->  2345.67
                vv = vv.replace(".", "")
                vv = vv.replace(",", ".")
            else:
                # 2,345.67  ->  2345.67
                vv = vv.replace(",", "")
        elif "," in vv:
            # 2345,67 or 2,345  ->  2345.67 or 2345
            vv = vv.replace(".", "")
            vv = vv.replace(",", ".")
        elif vv.count(".") > 1:
            # 1.234.567.89 -> 1234567.89
            parts = vv.split(".")
            vv = "".join(parts[:-1]) + "." + parts[-1]

        try:
            out["total_value"] = float(vv)
        except Exception:
            out["total_value"] = None

        if not cur:
            out["currency"] = {"$": "USD", "€": "EUR", "£": "GBP", "¥": "JPY"}.get(sym) or None
        else:
            out["currency"] = cur


    # Fallback customer name from Name/Passenger if not found
    if not out["customer_name"]:
        m = re.search(r"(?i)\b(Passenger Name|Name)\b\s*[:#]?\s*([A-Z][A-Za-z '\-]{3,80})", text)
        if m:
            out["customer_name"] = re.sub(r"\s+", " ", m.group(2)).strip()

    return out

# ============================
# Flight ticket field extract
# ============================

class TicketFields(TypedDict, total=False):
    pnr: Optional[str]
    ticket_number: Optional[str]
    flight_number: Optional[str]
    passenger_name: Optional[str]
    departure_date: Optional[str]
    departure_time: Optional[str]
    arrival_time: Optional[str]
    origin: Optional[str]
    destination: Optional[str]
    booking_class: Optional[str]
    status: Optional[str]
    carrier: Optional[str]

def _extract_pnr(text: str) -> Optional[str]:
    # Label on same line OR next line (allow newline after the colon)
    pat = r"(?im)^\s*(?:Booking\s+Ref(?:erence|rence)|Record\s+Locator|PNR|Reservation\s+Code|Booking\s+Code)\s*(?:\(\s*PNR\s*\))?\s*[:#]?\s*(?:\r?\n)?\s*([A-Z][A-Z0-9]{4,6})\b"
    m = re.search(pat, text)
    if m:
        return m.group(1).upper()
    # small fallback near booking/locator terms
    m = re.search(r"(?is)\b(booking|locator|référence|record\s+locator|pnr)\b.{0,80}?([A-Z][A-Z0-9]{4,6})\b", text)
    if m:
        tok = m.group(2).upper()
        if tok not in {"ISSUE", "DATE", "TUN", "CDG", "IST", "EDI"}:
            return tok
    return None

def _extract_ticket_number(text: str) -> Optional[str]:
    # 13-digit IATA number (may have hyphen/space after first 3 digits)
    m = re.search(r"(?i)\b(?:ETKT|E-?TKT|TICKET(?:\s*NUMBER)?|ELECTRONIC\s+TICKET)\b[^0-9]{0,12}(\d{3}[- ]?\d{10})\b", text)
    if m:
        return re.sub(r"[- ]", "", m.group(1))
    # Fallback: any 13-digit split 3+10
    m = re.search(r"\b(\d{3})[- ]?(\d{10})\b", text)
    if m:
        return m.group(1) + m.group(2)
    return None

def _candidate_names(text: str) -> List[Tuple[str, int, int]]:
    """
    Return a list of (name, offset, priority). Higher priority wins.
    """
    cands: List[Tuple[str, int, int]] = []

    # 0) STRICT IATA "glued" form: SURNAME/GIVEN(TITLE) — highest priority
    # all caps, optional ' or -, no spaces; title may be stuck at the end of second token
    for m in re.finditer(r"(?<![A-Z])([A-Z][A-Z'\-]{1,39})/([A-Z][A-Z'\-]{1,39})(?![A-Z])", text):
        # avoid Agent/Contact context
        pre = text[max(0, m.start()-30):m.start()].upper()
        if "AGENT" in pre or "CONTACT" in pre:
            continue
        last = m.group(1).strip(" -'/")
        first_raw = m.group(2).strip(" -'/")
        first_raw = _unglue_title_suffix(first_raw)   # remove MR/MRS/MSTR… if glued
        # keep glued given names as ONE token (no splitting)
        first = _title_case_name(first_raw)
        cands.append((_normalize_name(first, last), m.start(), 5))

    # 1) PASSENGERS table line (very strong)
    for m in re.finditer(r"(?is)\bPASSENGERS?\b.*?\n\s*([A-Z][A-Z'\-]{1,39}/[A-Z][A-Z'\-]{1,39})", text):
        m2 = re.match(r"([A-Z][A-Z'\-]{1,39})/([A-Z][A-Z'\-]{1,39})", m.group(1))
        if m2:
            last = m2.group(1).strip(" -'/")
            first_raw = _unglue_title_suffix(m2.group(2).strip(" -'/"))
            first = _title_case_name(first_raw)  # keep glued
            cands.append((_normalize_name(first, last), m.start(1), 4))

    # 2) Passenger-specific labels (same line) — high priority
    for m in re.finditer(r"(?i)\b(Passenger(?:\s*Name)?|Traveller|Traveler|Name of Passenger)\b\s*[:#]?\s*([A-Z ,'\-]{4,80})", text):
        blob = m.group(2).strip(" ,")
        off = m.start(2)
        m2 = re.search(r"^\s*([A-Z'\- ]{2,40}),\s*([A-Z'\- ]{2,40})", blob)  # DOE, JOHN
        if m2:
            cands.append((_normalize_name(m2.group(2), m2.group(1)), off, 3))
        else:
            parts = [p for p in blob.split() if p.upper() not in TITLE_TOKENS]
            if len(parts) >= 2:
                cands.append((_normalize_name(parts[0], " ".join(parts[1:])), off, 3))

    # 3) Passenger-specific labels (next line) — high priority
    for m in re.finditer(r"(?is)\b(Passenger(?:\s*Name)?|Traveller|Traveler|Name of Passenger)\b\s*[:#]?\s*\r?\n\s*([A-Z ,'\-]{4,80})", text):
        blob = m.group(2).strip(" ,")
        off = m.start(2)
        parts = [p for p in blob.split() if p.upper() not in TITLE_TOKENS]
        if len(parts) >= 2:
            cands.append((_normalize_name(parts[0], " ".join(parts[1:])), off, 3))

    # 4) IATA LAST/FIRST (with spaces allowed) — medium priority
    for m in re.finditer(r"(?i)\b([A-Z][A-Z'\- ]{1,40})/([A-Z][A-Z'\- ]{1,40})\b", text):
        last = m.group(1).strip(" -'/")
        first_raw = _unglue_title_suffix(m.group(2).strip(" -'/"))
        first = _title_case_name(first_raw)
        cands.append((_normalize_name(first, last), m.start(), 2))

    # 5) Agent/Contact names — low priority (kept but unlikely to win)
    for m in re.finditer(r"(?i)\b(Contact\s+Name|Agent\s+Name)\b\s*[:#]?\s*([A-Z][A-Za-z'\- ]{3,80})", text):
        blob = m.group(2).strip()
        off = m.start(2)
        parts = [p for p in blob.split() if p.upper() not in TITLE_TOKENS]
        if len(parts) >= 2:
            cands.append((" ".join(_title_case_name(p) for p in parts), off, 1))

    return cands

def _pick_best_name(cands: List[Tuple[str, int, int]]) -> Optional[str]:
    cands = [(n, off, prio) for (n, off, prio) in cands if _looks_like_name(n)]
    if not cands:
        return None

    def score(item: Tuple[str, int, int]) -> float:
        n, off, prio = item
        t = len(n.split())
        base = (2.0 if t == 2 else 1.6 if t == 3 else 1.0) + 0.7 * prio  # priority matters more
        return base - 0.01 * len(n) - 0.000001 * off

    cands.sort(key=score, reverse=True)
    return cands[0][0]

def _extract_flight_number(text: str) -> Optional[str]:
    # 1) Explicit label variants
    m = re.search(r"(?i)\bFlight[-\s]*(?:Number|No\.?|N°)\b[^A-Za-z0-9]{0,10}([A-Z]{2,3}\s*\d{2,4})", text)
    if m:
        return m.group(1).replace(" ", "").upper()

    # 2) In 'Flight Date' tables (CODE ####)
    m = re.search(r"(?is)\bFlight\s+Date\b.*?\b([A-Z]{2,3})\s*(\d{2,4})\b", text)
    if m:
        code = m.group(1).upper()
        if code in KNOWN_AIRLINE_CODES:
            return (code + m.group(2)).upper()

    # 3) Generic airline code + digits (avoid aircraft types and months)
    for m in re.finditer(r"(?i)\b([A-Z]{2,3})\s*[- ]?\s*(\d{2,4})\b", text):
        code = m.group(1).upper()
        num = m.group(2)
        if code in {"A", "B"}:  # prevents A321/B737 equipment codes
            continue
        if code in MONTH_TOKENS:
            continue
        if KNOWN_AIRLINE_CODES and code not in KNOWN_AIRLINE_CODES:
            continue
        return (code + num).upper()

    return None

def _extract_route(text: str) -> tuple[Optional[str], Optional[str]]:
    # 1) Labeled pairs (allow next line, allow city names before codes)
    labeled = [
        r"(?im)^\s*(?:FROM|ORIGIN|DEPARTURE)\s*:?\s*(?:\r?\n)?\s*(?:[A-Za-z() ,]*?)\b([A-Z]{3})\b.*?"
        r"^\s*(?:TO|DESTINATION|ARRIVAL)\s*:?\s*(?:\r?\n)?\s*(?:[A-Za-z() ,]*?)\b([A-Z]{3})\b",
    ]
    for pat in labeled:
        m = re.search(pat, text)
        if m:
            return m.group(1).upper(), m.group(2).upper()

    # 2) With parentheses around IATA codes
    m = re.search(r"(?is)\(([A-Z]{3})\)\s*[-–—/>\u2192]\s*\(([A-Z]{3})\)", text)
    if m:
        return m.group(1).upper(), m.group(2).upper()

    # 3) Bare IATA codes with common separators: -, –, —, →, /, >
    m = re.search(r"(?is)\b([A-Z]{3})\b\s*[-–—/>\u2192]\s*\b([A-Z]{3})\b", text)
    if m:
        return m.group(1).upper(), m.group(2).upper()

    # 4) “from … to …” phrasing, code inside or without parentheses
    m = re.search(r"(?is)\bfrom\b.*?\(?\b([A-Z]{3})\b\)?[^A-Za-z]{0,60}\bto\b.*?\(?\b([A-Z]{3})\b\)?", text)
    if m:
        return m.group(1).upper(), m.group(2).upper()

    return None, None


def _extract_times(text: str) -> tuple[Optional[str], Optional[str]]:
    TIME = r"([01]?\d|2\d)(?::|\.|[hH])?([0-5]\d)\s*(?:([AaPp][Mm]))?"

    def find_time(labels: list[str]) -> Optional[str]:
        for lab in labels:
            # label then time
            m = re.search(fr"(?im)\b{lab}\b[^0-9A-Za-z]{{0,12}}{TIME}", text)
            if not m:
                # time then label
                m = re.search(fr"(?im){TIME}[^0-9A-Za-z]{{0,12}}\b{lab}\b", text)
            if m:
                return _normalize_time(m.group(1), m.group(2), m.group(3))
        return None

    dep = find_time(["DEPARTURE", "DEP", "STD", "ETD"])
    arr = find_time(["ARRIVAL", "ARR", "STA", "ETA"])

    # Fallback: a line that looks like a flight/route line and has two times
    if not (dep and arr):
        for line in text.splitlines():
            U = line.upper()
            if any(k in U for k in ["DEPART", "ARRIV", "FLIGHT", "ROUTE", "TUN", "BEN", "CDG", "IST", "TIP", "EDI"]):
                m = re.findall(TIME, line)
                if len(m) >= 2:
                    dep = dep or _normalize_time(m[0][0], m[0][1], m[0][2])
                    arr = arr or _normalize_time(m[1][0], m[1][1], m[1][2])
                    break

    return dep, arr

def _extract_booking_class(text: str) -> Optional[str]:
    m = re.search(r"(?im)^\s*CLASS\s*:\s*(?:\r?\n)?\s*([A-Z]{1,2})\b", text)
    if m:
        return m.group(1).upper()
    m = re.search(r"(?i)\bCLASS\b[^A-Za-z0-9]{0,5}([A-Z]{1,2})\b", text)
    return m.group(1).upper() if m else None

def _extract_status(text: str) -> Optional[str]:
    m = re.search(r"(?im)^\s*STATUS\s*:\s*(?:\r?\n)?\s*([A-Z]{2})\b", text)
    if m:
        return m.group(1).upper()
    m = re.search(r"\bStatus\b[^A-Za-z0-9]{0,5}([A-Z]{2})\b", text)
    return m.group(1).upper() if m else None

def _extract_departure_date(text: str) -> Optional[str]:
    # Prefer explicit blocks
    m = re.search(r"(?is)\bDEPARTING:\s*.*?\bDate\s+\w{3}\s+([0-9]{1,2}\s+[A-Za-z]{3}\s+[0-9]{2,4})", text)
    if m:
        d = try_parse_date(m.group(1))
        if d:
            return d

    # 'Flight Date' table
    m = re.search(r"(?is)\bFlight\s+Date\b.*?\b(\d{2}\s+[A-Za-z]{3}\s+\d{2,4})\b", text)
    if m:
        d = try_parse_date(m.group(1))
        if d:
            return d

    # DDMMM tokens (avoid Issue/Emission contexts)
    for m in re.finditer(r"\b(\d{1,2}\s*[A-Z]{3,4})\b", text):
        maybe = parse_ddmmm(m.group(1))
        if maybe:
            span = m.start()
            ctx = text[max(0, span-60): span+60].upper()
            if any(k in ctx for k in ["ISSUE","ISSUED","ISSUANCE","EMISSION","ÉMISSION","EMISIÓN","EMISSAO"]):
                continue
            return maybe

    # General date near airline codes
    for m in re.finditer(r"(?i)\b([A-Z]{2,3})\s*[- ]?\s*(\d{2,4})\b", text):
        code = m.group(1).upper()
        if code in KNOWN_AIRLINE_CODES:
            win = text[max(0, m.start()-80): min(len(text), m.end()+120)]
            dm = re.search(r"(\d{1,2}\s+[A-Za-z]{3}\s+\d{2,4}|\d{1,2}[./-]\d{1,2}[./-]\d{2,4})", win)
            if dm:
                d = try_parse_date(dm.group(1))
                if d:
                    return d

    return None

def extract_flight_ticket_fields(text: str) -> Dict[str, Optional[str]]:
    out: Dict[str, Optional[str]] = {
        "pnr": None, "ticket_number": None, "flight_number": None, "passenger_name": None,
        "departure_date": None, "departure_time": None, "arrival_time": None,
        "origin": None, "destination": None, "booking_class": None, "status": None, "carrier": None
    }

    out["pnr"] = _extract_pnr(text)
    out["ticket_number"] = _extract_ticket_number(text)

    fn = _extract_flight_number(text)
    if fn:
        out["flight_number"] = fn
        code = fn[:2] if len(fn) >= 2 else None
        if code and code in AIRLINE_CODE_MAP:
            out["carrier"] = AIRLINE_CODE_MAP[code]

    name = _pick_best_name(_candidate_names(text))
    if name:
        out["passenger_name"] = name

    out["departure_date"] = _extract_departure_date(text)

    o, d = _extract_route(text)
    out["origin"], out["destination"] = o, d

    dep, arr = _extract_times(text)
    out["departure_time"], out["arrival_time"] = dep, arr

    out["booking_class"] = _extract_booking_class(text)
    out["status"] = _extract_status(text)

    return out

# =================
# Passport (basic)
# =================

class PassportFields(TypedDict, total=False):
    surname: Optional[str]
    given_names: Optional[str]
    nationality: Optional[str]
    date_of_expiry: Optional[str]

def extract_passport_fields(text: str) -> Dict[str, Optional[str]]:
    out: Dict[str, Optional[str]] = {
        "surname": None, "given_names": None, "nationality": None, "date_of_expiry": None
    }
    m = re.search(r"(?i)\bSurname\b\s*[:#]?\s*([A-Z][A-Za-z \-]{2,60})", text)
    if m:
        out["surname"] = re.sub(r"\s+", " ", m.group(1)).strip()

    m = re.search(r"(?i)\b(Given Names|Given name|Forenames)\b\s*[:#]?\s*([A-Z][A-Za-z \-]{2,80})", text)
    if m:
        out["given_names"] = re.sub(r"\s+", " ", m.group(2)).strip()

    m = re.search(r"(?i)\bNationality\b\s*[:#]?\s*([A-Z]{3}|[A-Za-z ]{3,30})", text)
    if m:
        out["nationality"] = re.sub(r"\s+", " ", m.group(1)).strip()

    m = re.search(r"(?i)\b(Date of Expiry|Expiry Date|Date of expiration)\b\s*[:#]?\s*("
                  r"[0-9]{1,2}[./-][0-9]{1,2}[./-][0-9]{2,4}"
                  r"|[A-Za-z]{3,9}\s+\d{1,2},?\s+\d{2,4}"
                  r"|\d{1,2}\s+[A-Za-z]{3,9}\s+\d{2,4})", text)
    if m:
        d = try_parse_date(m.group(2))
        if d:
            out["date_of_expiry"] = d

    return out
