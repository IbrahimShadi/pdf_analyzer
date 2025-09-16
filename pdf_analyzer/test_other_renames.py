from pdf_analyzer.renamer import build_flight_ticket_filename, build_passport_filename

def test_build_flight_ticket_filename():
    name = build_flight_ticket_filename("ABC123", "John Doe", "LH123", "2025-08-12", "Lufthansa")
    assert name.startswith("Ticket_") and name.endswith(".pdf")
    assert "ABC123" in name and "LH123" in name

def test_build_passport_filename():
    name = build_passport_filename("MUSTERMANN", "MAX", "DEU", "2030-01-01")
    assert name.startswith("Passport_") and name.endswith(".pdf")
    assert "MUSTERMANN" in name and "2030-01-01" in name
