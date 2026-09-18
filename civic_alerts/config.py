"""Criteres de recherche et parametres runtime.

Les valeurs peuvent etre surchargees par variables d'environnement, ce qui
permet d'ajuster le job GitHub Actions sans toucher au code.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    return int(raw) if raw else default


@dataclass
class Criteria:
    make: str = "Honda"
    model: str = "Civic"
    # Le mot-cle de finition. Kijiji/AutoHebdo ne filtrent pas la finition de
    # facon fiable : on le fait nous-memes sur le titre.
    trim_keywords: tuple[str, ...] = ("sport",)
    year_min: int = field(default_factory=lambda: _int_env("YEAR_MIN", 2017))
    price_max: int = field(default_factory=lambda: _int_env("PRICE_MAX", 15000))
    odometer_max: int = field(default_factory=lambda: _int_env("ODOMETER_MAX", 170000))
    transmission: str = "automatic"
    # Code postal de reference (St-Hubert, QC) et rayon en km.
    postal_code: str = field(default_factory=lambda: os.environ.get("POSTAL_CODE", "J3Y8Y9"))
    city: str = "Saint-Hubert, QC"
    radius_km: int = field(default_factory=lambda: _int_env("RADIUS_KM", 1000))
    # Filet de securite : une annonce sans kilometrage ou sans transmission
    # lisible est gardee plutot que jetee, pour ne pas rater une aubaine.
    keep_when_unknown: bool = True


CRITERIA = Criteria()

# Chemin du fichier d'etat (annonces deja notifiees), relatif a la racine du repo.
STATE_PATH = os.environ.get("STATE_PATH", "data/seen.json")

# Nombre de jours avant qu'une annonce disparue soit oubliee de l'etat.
STATE_TTL_DAYS = _int_env("STATE_TTL_DAYS", 90)

# Nombre max d'annonces listees dans un seul message de notification.
MAX_LISTINGS_PER_MESSAGE = _int_env("MAX_LISTINGS_PER_MESSAGE", 20)
