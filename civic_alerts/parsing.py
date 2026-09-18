"""Extraction de l'annee, du prix, du kilometrage et de la transmission.

Les sources decrivent ces champs de facons tres variees ; on normalise ici pour
pouvoir appliquer les memes filtres partout.
"""

from __future__ import annotations

import re

_PRICE_RE = re.compile(r"(\d[\d\s.,]{2,})\s*\$|\$\s*(\d[\d\s.,]{2,})")
_ODOMETER_RE = re.compile(r"(\d[\d\s.,]*)\s*(?:km|kilom)", re.IGNORECASE)
_YEAR_RE = re.compile(r"\b(19[89]\d|20[0-4]\d)\b")

_AUTOMATIC_HINTS = ("automatique", "automatic", "auto.", "cvt", "a/t", "boite auto")
_MANUAL_HINTS = (
    "manuelle", "manual", "manuel", "m/t", "stick",
    "6 vitesses", "5 vitesses", "6 speed", "5 speed", "6-speed", "5-speed",
    "6spd", "6-spd", "5-spd", "boite manuelle",
)


def _to_int(raw: str) -> int | None:
    digits = re.sub(r"[^\d]", "", raw or "")
    return int(digits) if digits else None


def parse_price(text: str | None) -> int | None:
    if not text:
        return None
    match = _PRICE_RE.search(text)
    if not match:
        return _to_int(text) if text.strip().replace(" ", "").isdigit() else None
    value = _to_int(match.group(1) or match.group(2))
    # Un "prix" a 4 chiffres est plausible ; en dessous de 500 $ c'est du bruit
    # (numero de lot, mensualite, etc.).
    return value if value and value >= 500 else None


def parse_odometer(text: str | None) -> int | None:
    if not text:
        return None
    match = _ODOMETER_RE.search(text)
    if not match:
        return None
    value = _to_int(match.group(1))
    # Rejette les faux positifs du genre "1 km du metro".
    return value if value and 100 <= value <= 999_999 else None


def parse_year(text: str | None) -> int | None:
    if not text:
        return None
    match = _YEAR_RE.search(text)
    return int(match.group(1)) if match else None


def parse_transmission(text: str | None) -> str | None:
    if not text:
        return None
    lowered = text.lower()
    if any(hint in lowered for hint in _AUTOMATIC_HINTS):
        return "automatic"
    if any(hint in lowered for hint in _MANUAL_HINTS):
        return "manual"
    return None
