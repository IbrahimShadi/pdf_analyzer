import os, json, click, csv, sys
from typing import Dict, Any, List
from .rules import load_rules
from .loader import load_pdf_text
from .classifier import probabilities
from .extractors import extract_invoice_fields, extract_flight_ticket_fields, extract_passport_fields
from .renamer import build_invoice_filename, build_flight_ticket_filename, build_passport_filename, maybe_rename

def analyze_file(path: str, rules_path: str, ocr: bool, lang: str, min_conf: float, do_rename: bool, dest: str, temperature: float) -> Dict[str, Any]:
    rules = load_rules(rules_path)
    text, err = load_pdf_text(path, ocr=ocr, lang=lang)
    probs, top_class, conf = probabilities(text, rules, temperature=temperature)
    effective_top = top_class
    effective_conf = conf
    path_out = None
    extracted: Dict[str, Any] = {}

    if top_class == "invoice":
        extracted = extract_invoice_fields(text)
        if conf >= min_conf:
            new_name = build_invoice_filename(
                extracted.get("invoice_number"),
                extracted.get("customer_name"),
                extracted.get("total_value"),
                extracted.get("invoice_date"),
                ext=os.path.splitext(path)[1] or ".pdf"
            )
            try:
                path_out = maybe_rename(path, dest, new_name, do_rename)
            except Exception as e:
                err = (err + " | " if err else "") + f"rename_error: {e}"
        else:
            effective_top = "other"
            effective_conf = conf

    elif top_class == "flight_ticket":
        extracted = extract_flight_ticket_fields(text)
        if conf >= min_conf:
            new_name = build_flight_ticket_filename(
                extracted.get("pnr"),
                extracted.get("passenger_name"),
                extracted.get("flight_number"),
                extracted.get("departure_date"),
                extracted.get("carrier"),
                ext=os.path.splitext(path)[1] or ".pdf"
            )
            try:
                path_out = maybe_rename(path, dest, new_name, do_rename)
            except Exception as e:
                err = (err + " | " if err else "") + f"rename_error: {e}"
        else:
            effective_top = "other"
            effective_conf = conf

    elif top_class == "passport":
        extracted = extract_passport_fields(text)
        if conf >= min_conf:
            new_name = build_passport_filename(
                extracted.get("surname"),
                extracted.get("given_names"),
                extracted.get("nationality"),
                extracted.get("date_of_expiry"),
                ext=os.path.splitext(path)[1] or ".pdf"
            )
            try:
                path_out = maybe_rename(path, dest, new_name, do_rename)
            except Exception as e:
                err = (err + " | " if err else "") + f"rename_error: {e}"
        else:
            effective_top = "other"
            effective_conf = conf

    elif conf < min_conf:
        effective_top = "other"
        effective_conf = conf

    result = {
        "path_in": path,
        "path_out": path_out,
        "top_class": effective_top,
        "confidence": round(float(effective_conf), 4),
        "probabilities": {k: round(float(v), 4) for k, v in probs.items()},
        "extracted": extracted if extracted else None,
        "errors": err
    }
    return result

@click.group()
def main():
    """PDF analyzer & auto-renamer"""

@main.command("analyze")
@click.argument("path", type=click.Path(exists=True))
@click.option("--ocr", is_flag=True, help="Enable OCR for scanned PDFs")
@click.option("--lang", default="eng", help="Tesseract language(s), e.g., 'eng+deu'")
@click.option("--rules", "rules_path", default="rules.yaml", type=click.Path(exists=True), help="Path to rules config")
@click.option("--recursive", is_flag=True, help="Recurse into directories")
@click.option("--rename", "do_rename", is_flag=True, help="Rename files on success (all supported classes)")
@click.option("--dest", default=None, type=click.Path(), help="Destination directory for renamed files")
@click.option("--min-confidence", "min_conf", default=0.6, show_default=True, type=float, help="Threshold for top class")
@click.option("--temperature", default=1.0, show_default=True, type=float, help="Softmax temperature")
@click.option("--report", default=None, type=click.Path(), help="Optional CSV report path")
def analyze_cmd(path, ocr, lang, rules_path, recursive, do_rename, dest, min_conf, temperature, report):
    """Analyze a PDF file or directory and optionally rename by class."""
    files: List[str] = []
    if os.path.isdir(path):
        for root, _, names in os.walk(path):
            for n in names:
                if n.lower().endswith(".pdf"):
                    files.append(os.path.join(root, n))
            if not recursive:
                break
    else:
        files = [path]

    results = []
    for f in files:
        res = analyze_file(f, rules_path, ocr, lang, min_conf, do_rename, dest, temperature)
        click.echo(json.dumps(res, ensure_ascii=False))
        results.append(res)

    if report and results:
        os.makedirs(os.path.dirname(report) or ".", exist_ok=True)
        with open(report, "w", newline="", encoding="utf-8") as csvfile:
            fieldnames = ["path_in","path_out","top_class","confidence","invoice_number","customer_name","invoice_date","total_value","currency","pnr","passenger_name","flight_number","departure_date","carrier","surname","given_names","nationality","date_of_expiry","errors"]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for r in results:
                ex = r.get("extracted") or {}
                writer.writerow({
                    "path_in": r["path_in"],
                    "path_out": r["path_out"],
                    "top_class": r["top_class"],
                    "confidence": r["confidence"],
                    "invoice_number": ex.get("invoice_number"),
                    "customer_name": ex.get("customer_name"),
                    "invoice_date": ex.get("invoice_date"),
                    "total_value": ex.get("total_value"),
                    "currency": ex.get("currency"),
                    "pnr": ex.get("pnr"),
                    "passenger_name": ex.get("passenger_name"),
                    "flight_number": ex.get("flight_number"),
                    "departure_date": ex.get("departure_date"),
                    "carrier": ex.get("carrier"),
                    "surname": ex.get("surname"),
                    "given_names": ex.get("given_names"),
                    "nationality": ex.get("nationality"),
                    "date_of_expiry": ex.get("date_of_expiry"),
                    "errors": r["errors"]
                })

if __name__ == "__main__":
    main()
