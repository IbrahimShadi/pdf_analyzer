
# PDF Analyzer & Auto-Renamer (with per-class probabilities) STILL ON "PROGRESS"

A small CLI tool to analyze PDFs, classify document type with calibrated probabilities, extract invoice metadata, and (optionally) auto-rename invoice files.

## Features

- Input: Single PDF or directory (with `--recursive`)
- Text PDFs via `pdfminer.six`, scanned PDFs via OCR (`--ocr`) using `pdf2image` + `pytesseract`
- UTF‑8 & multi-language friendly (pass `--lang`, e.g., `eng+deu`)
- Classification into: `invoice`, `flight_ticket`, `passport`, `other`
- Configurable rules: keywords/phrases/regexes + weights in `rules.yaml`
- Probabilities via softmax (with `--temperature`)
- Thresholding with `--min-confidence` (default 0.6)
- Invoice metadata extraction (number, customer, date, total + currency)
- Auto-renaming invoices: `Inv_{invoice_number}_{customer_name}_{total_value}_{invoice_date}.pdf`
- CSV report with `--report`
- Modular code + unit tests

## Install

> Requires Python 3.9+.

System deps for OCR:
- Tesseract OCR (binary `tesseract` in PATH) with language packs (e.g., `eng`, `deu`)
- Poppler (for `pdf2image` to render PDF pages), e.g., `apt install poppler-utils`

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Local dev install (editable):
```bash
pip install -e .
```

## Usage

Analyze a single file (with OCR, rename if invoice, min confidence 0.7):
```bash
python -m pdf_analyzer analyze ./docs/sample.pdf --ocr --rename --min-confidence 0.7
```

Analyze a directory recursively and export CSV:
```bash
python -m pdf_analyzer analyze ./docs --recursive --rename --report results.csv
```

Custom rules:
```bash
python -m pdf_analyzer analyze ./docs --rules ./rules.yaml
```

Change softmax temperature (lower -> sharper):
```bash
python -m pdf_analyzer analyze ./docs --temperature 0.7
```

## Output format

For each file, the tool prints a compact JSON like:
```json
{
  "path_in": "./docs/inv1.pdf",
  "path_out": "./docs/Inv_INV-123_ACME_GmbH_123.45_2025-07-01.pdf",
  "top_class": "invoice",
  "confidence": 0.92,
  "probabilities": {"invoice":0.92,"flight_ticket":0.04,"passport":0.03,"other":0.01},
  "extracted": {"invoice_number":"INV-123","customer_name":"ACME GmbH","invoice_date":"2025-07-01","total_value":123.45,"currency":"EUR"},
  "errors": null
}
```

## Project structure

```
pdf_analyzer/
  pdf_analyzer/
    __init__.py
    __main__.py
    cli.py
    loader.py
    utils.py
    rules.py
    classifier.py
    extractors.py
    renamer.py
  tests/
    test_*.py
    fixtures/
      *.txt (sample text fixtures)
rules.yaml
requirements.txt
```

## Tests

Run with:
```bash
pytest -q
```

The tests focus on:
- Scoring & softmax normalization
- Classification on positive/negative samples
- Invoice field extraction
- Filename sanitization & collision handling

## Limitations

- OCR quality depends on Tesseract and Poppler being installed.
- Rules-based classifier is simple; for higher accuracy, add labeled samples and calibrate probabilities (e.g., Platt/Isotonic).
- Currency detection is symbol-based; extend mapping in `extractors.py`.

## Extending

Add new classes (e.g., `receipt`, `hotel_booking`) by editing `rules.yaml`:
```yaml
receipt:
  keywords: ["receipt", "store", "cashier", "tax"]
  phrases: []
  regexes: []
  temperature: 1.0
```


