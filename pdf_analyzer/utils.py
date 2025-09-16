
import os
import re
import math
import unicodedata
from typing import Dict, List

ILLEGAL_FILENAME_CHARS = r'<>:"/\\|?*'
_ILLEGAL_RE = re.compile(r'[<>:"/\\|?*\x00-\x1F]')

def normalize_text(s: str) -> str:
    """Lowercase, strip accents, collapse whitespace."""
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = "".join([c for c in s if not unicodedata.combining(c)])
    s = s.lower()
    s = re.sub(r'\s+', ' ', s).strip()
    return s

def softmax(scores: Dict[str, float], temperature: float = 1.0) -> Dict[str, float]:
    """Convert class scores to probabilities."""
    if not scores:
        return {}
    # Stability
    vals = list(scores.values())
    if len(set(vals)) == 1 and next(iter(set(vals))) == 0:
        # all zeros -> uniform
        n = len(scores)
        return {k: 1.0/n for k in scores}
    mx = max(scores.values())
    exps = {k: math.exp((v - mx)/max(1e-6, temperature)) for k, v in scores.items()}
    total = sum(exps.values()) or 1.0
    return {k: exps[k]/total for k in scores}

def sanitize_filename(s: str, max_len: int = 180) -> str:
    s = s or ""
    s = re.sub(_ILLEGAL_RE, "_", s)
    s = re.sub(r"\s+", " ", s).strip()
    # prevent dot-only names
    s = s.strip(". ")
    # limit
    return s[:max_len] if len(s) > max_len else s

def dedupe_path(path: str) -> str:
    """If path exists, append -1, -2, ... before extension."""
    if not os.path.exists(path):
        return path
    root, ext = os.path.splitext(path)
    i = 1
    while True:
        candidate = f"{root}-{i}{ext}"
        if not os.path.exists(candidate):
            return candidate
        i += 1
