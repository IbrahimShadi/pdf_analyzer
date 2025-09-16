
from pdf_analyzer.renamer import build_invoice_filename

def test_build_invoice_filename_sanitizes():
    name = build_invoice_filename("INV:1", 'Client/"A"', 1000.0, "2025-08-01")
    assert ":" not in name and '"' not in name and "/" not in name
    assert name.endswith(".pdf")
