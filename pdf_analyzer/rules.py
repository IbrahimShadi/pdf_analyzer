
from typing import Dict, Any
import yaml

def load_rules(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    # Ensure all classes exist
    for cls in ["invoice", "flight_ticket", "passport", "other"]:
        data.setdefault(cls, {"keywords": [], "phrases": [], "regexes": [], "temperature": 1.0})
        data[cls].setdefault("keywords", [])
        data[cls].setdefault("phrases", [])
        data[cls].setdefault("regexes", [])
        data[cls].setdefault("temperature", 1.0)
    return data
