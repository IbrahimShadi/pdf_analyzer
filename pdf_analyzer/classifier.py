
from typing import Dict, Any, Tuple
from .utils import normalize_text, softmax
import regex as re
try:
    from rapidfuzz import fuzz
    HAVE_FUZZ=True
except Exception:
    HAVE_FUZZ=False

def score_text(text: str, rules: Dict[str, Any]) -> Dict[str, float]:
    """
    Compute raw scores per class using rules: keywords, phrases, regexes.
    Uses basic counts and optional fuzzy boosts.
    """
    norm = normalize_text(text)
    scores = {cls: 0.0 for cls in rules.keys()}
    for cls, cfg in rules.items():
        score = 0.0
        for kw in cfg.get("keywords", []):
            count = norm.count(kw.lower())
            score += 1.0 * count
            if HAVE_FUZZ and count == 0:
                # fuzzy boost
                sim = fuzz.partial_ratio(kw.lower(), norm[:10000]) / 100.0
                if sim > 0.9:
                    score += 0.5
        for phr in cfg.get("phrases", []):
            count = norm.count(phr.lower())
            score += 1.5 * count
        for rx in cfg.get("regexes", []):
            pat = rx.get("pattern")
            w = float(rx.get("weight", 1.0))
            try:
                matches = re.findall(pat, text, flags=re.IGNORECASE)
                score += w * len(matches)
            except Exception:
                pass
        scores[cls] = score
    return scores

def probabilities(text: str, rules: Dict[str, Any], temperature: float = 1.0) -> Tuple[Dict[str, float], str, float]:
    """
    Return (probs, top_class, top_prob) as floats 0..1
    """
    scores = score_text(text, rules)
    # temperature per-class (use average)
    temps = []
    for cls, cfg in rules.items():
        temps.append(float(cfg.get("temperature", 1.0)))
    avg_temp = sum(temps)/len(temps) if temps else temperature
    probs = softmax(scores, temperature=avg_temp)
    top_class = max(probs, key=probs.get)
    return probs, top_class, probs[top_class]
