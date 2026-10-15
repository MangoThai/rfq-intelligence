import re

_NON_ALPHANUMERIC = re.compile(r"[^A-Z0-9]+")


def normalize_sku(value: str) -> str:
    normalized = value.strip().upper()
    return _NON_ALPHANUMERIC.sub("", normalized)
