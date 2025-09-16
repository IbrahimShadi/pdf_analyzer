
from pdf_analyzer.classifier import probabilities
from pdf_analyzer.rules import load_rules

def test_classifier_positive_invoice():
    rules = load_rules("rules.yaml")
    text = "Invoice No: INV-12345\nBill To: ACME GmbH\nAmount Due: € 1.234,56\n"
    probs, top, conf = probabilities(text, rules)
    assert top == "invoice"
    assert conf > 0.5

def test_classifier_negative_other():
    rules = load_rules("rules.yaml")
    text = "This is a random document with no special keywords."
    probs, top, conf = probabilities(text, rules)
    assert top in probs
