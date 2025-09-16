import os
from .utils import sanitize_filename, dedupe_path

def build_invoice_filename(invoice_number, customer_name, total_value, invoice_date, ext=".pdf"):
    parts = [
        "Inv",
        str(invoice_number or "NA"),
        str(customer_name or "NA"),
        f"{total_value:.2f}" if isinstance(total_value, (int, float)) else "NA",
        str(invoice_date or "NA")
    ]
    base = "_".join(sanitize_filename(p) for p in parts if p is not None)
    return sanitize_filename(base) + ext

def build_flight_ticket_filename(pnr, passenger_name, flight_number, departure_date, carrier, ext=".pdf"):
    parts = ["Ticket"]
    if carrier:
        parts.append(str(carrier))
    parts += [
        str(pnr or "NA"),
        str(passenger_name or "NA"),
        str(flight_number or "NA"),
        str(departure_date or "NA"),
    ]
    base = "_".join(sanitize_filename(p) for p in parts if p is not None)
    return sanitize_filename(base) + ext

def build_passport_filename(surname, given_names, nationality, date_of_expiry, ext=".pdf"):
    parts = [
        "Passport",
        str(surname or "NA"),
        str(given_names or "NA"),
        str(nationality or "NA"),
        str(date_of_expiry or "NA")
    ]
    base = "_".join(sanitize_filename(p) for p in parts if p is not None)
    return sanitize_filename(base) + ext

def maybe_rename(path_in: str, dest_dir: str, new_name: str, do_rename: bool = True):
    if not do_rename:
        return None
    dest_dir = dest_dir or os.path.dirname(path_in)
    os.makedirs(dest_dir, exist_ok=True)
    out_path = os.path.join(dest_dir, new_name)
    out_path = dedupe_path(out_path)
    os.rename(path_in, out_path)
    return out_path
