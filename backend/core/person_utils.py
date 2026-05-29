import re

from .constants import PERSON_SKIP_PREFIXES


def is_valid_person_name(name: str) -> bool:
    if not name or len(name.split()) < 2:
        return False
    normalized = name.lower().strip()
    if any(normalized.startswith(p) for p in PERSON_SKIP_PREFIXES):
        return False
    if re.search(r"\d", name) and not re.match(r"^[\w\s.,]+$", name):
        return False
    return True
