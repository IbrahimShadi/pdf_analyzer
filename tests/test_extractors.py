
from pdf_analyzer.extractors import extract_invoice_fields

def test_extract_invoice_fields_basic():
    text = """Invoice Number: INV-789
Bill To:
Mega Corp GmbH
Some Street 1
12345 City
Invoice Date: 12/08/2025
Grand Total: € 2.345,67
"""
    ex = extract_invoice_fields(text)
    assert ex["invoice_number"] == "INV-789"
    assert ex["customer_name"].startswith("Mega Corp")
    assert ex["invoice_date"] == "2025-08-12"
    assert abs(ex["total_value"] - 2345.67) < 0.01
