"""Application des criteres a une annonce normalisee."""

from __future__ import annotations

import logging

from . import geo
from .config import Criteria
from .models import Listing

log = logging.getLogger(__name__)

# Pieges classiques : une annonce de pieces ou une Civic Type R hors budget qui
# remonte parce que le titre contient "Sport".
_EXCLUDE_KEYWORDS = ("pieces", "pièces", "parts only", "for parts", "scrap", "location", "leasing", "a louer", "à louer")


def matches(listing: Listing, criteria: Criteria) -> tuple[bool, str]:
    """Retourne (garde, raison_du_rejet)."""
    title = (listing.title or "").lower()

    if criteria.model.lower() not in title:
        return False, "modele absent du titre"

    if any(word in title for word in _EXCLUDE_KEYWORDS):
        return False, "annonce de pieces / location"

    if criteria.trim_keywords and not any(k in title for k in criteria.trim_keywords):
        return False, "finition Sport absente du titre"

    if listing.year is not None and listing.year < criteria.year_min:
        return False, f"annee {listing.year} < {criteria.year_min}"
    if listing.year is None and not criteria.keep_when_unknown:
        return False, "annee inconnue"

    if listing.price is not None and listing.price > criteria.price_max:
        return False, f"prix {listing.price} > {criteria.price_max}"
    if listing.price is None and not criteria.keep_when_unknown:
        return False, "prix inconnu"

    if listing.odometer_km is not None and listing.odometer_km > criteria.odometer_max:
        return False, f"kilometrage {listing.odometer_km} > {criteria.odometer_max}"
    if listing.odometer_km is None and not criteria.keep_when_unknown:
        return False, "kilometrage inconnu"

    # La transmission manuelle est le seul rejet ferme : "inconnu" passe, parce
    # que beaucoup d'annonces de particuliers ne la precisent tout simplement pas.
    if listing.transmission == "manual":
        return False, "transmission manuelle"

    # Le rayon annonce par les sites n'est pas fiable (une execution reelle a
    # remonte Lethbridge malgre radius=1000), alors on verifie nous-memes.
    coords = (
        (listing.latitude, listing.longitude)
        if listing.latitude is not None and listing.longitude is not None
        else None
    )
    in_range, detail = geo.within_radius(
        criteria.radius_km, listing.url, listing.location, coords=coords
    )
    if not in_range:
        return False, detail

    return True, ""


def dedupe_across_sources(listings: list[Listing]) -> list[Listing]:
    """Fusionne la meme voiture vue sur deux sites.

    Un concessionnaire publie souvent la meme annonce sur Kijiji et AutoHebdo.
    La signature annee + prix + kilometrage identifie le doublon de facon sure ;
    une annonce a laquelle il manque un de ces trois champs n'est jamais
    fusionnee, faute de certitude.
    """
    kept: list[Listing] = []
    seen: set[tuple[int, int, int]] = set()
    for listing in listings:
        if listing.year is None or listing.price is None or listing.odometer_km is None:
            kept.append(listing)
            continue
        signature = (listing.year, listing.price, listing.odometer_km)
        if signature in seen:
            log.debug("doublon inter-sources ignore [%s] %s", listing.source, listing.title)
            continue
        seen.add(signature)
        kept.append(listing)
    return kept


def apply(listings: list[Listing], criteria: Criteria) -> list[Listing]:
    kept: list[Listing] = []
    for listing in listings:
        ok, reason = matches(listing, criteria)
        if ok:
            kept.append(listing)
        else:
            log.debug("rejete [%s] %s -> %s", listing.source, listing.title, reason)
    return kept
