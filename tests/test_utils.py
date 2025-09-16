
from pdf_analyzer.utils import softmax, sanitize_filename, dedupe_path
import os, tempfile

def test_softmax_sums_to_one():
    probs = softmax({"a":1.0, "b":2.0, "c":3.0}, temperature=1.0)
    assert abs(sum(probs.values()) - 1.0) < 1e-9

def test_sanitize_filename():
    s = 'Inv:001/"Acme"?*.pdf'
    out = sanitize_filename(s)
    assert ":" not in out and '"' not in out and "?" not in out and "*" not in out and "/" not in out

def test_dedupe_path(tmp_path):
    p = tmp_path/"file.pdf"
    p.write_text("x")
    out1 = dedupe_path(str(p))
    assert out1.endswith("-1.pdf")
