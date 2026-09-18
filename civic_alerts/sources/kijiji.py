"""Kijiji Autos - annonces de particuliers et de petits marchands."""

from __future__ import annotations

import json
import logging
import re

from .. import http_client
from .._compat import deep_find_dicts
from ..config import Criteria
from ..models import Listing
from ..parsing import parse_odometer, parse_price, parse_transmission, parse_year
from ._html import listings_from_anchors

log = logging.getLogger(__name__)

SOURCE = "kijiji"
BASE_URL = "https://www.kijiji.ca"
# c174 = Autos et camions, l0 = Canada au complet (le rayon fait le tri).
SEARCH_URL = BASE_URL + "/b-autos-camions/canada/honda-civic-sport/k0c174l0"

_HREF_RE = re.compile(r"/v-autos-camions/|/v-cars-trucks/")
_ID_RE = re.compile(r"/(\d{9,})(?:$|[/?#])")
_NEXT_DATA_RE = re.compile(
    r'<script[^>]+id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.DOTALL
)


def _search_params(criteria: Criteria) -> dict[str, str]:
    return {
        "address": criteria.postal_code,
        "radius": str(criteria.radius_km),
        "price": f"__{criteria.price_max}",
        "sort": "dateDesc",
    }


def fetch(session, criteria: Criteria) -> list[Listing]:
    response = http_client.get(session, SEARCH_URL, params=_search_params(criteria))
    if response is None:
        log.error("Kijiji : recherche inaccessible.")
        return []

    listings = _from_next_data(response.text)
    if listings:
        log.info("Kijiji : %s annonces via __NEXT_DATA__.", len(listings))
        return listings

    listings = listings_from_anchors(
        response.text,
        source=SOURCE,
        base_url=BASE_URL,
        href_pattern=_HREF_RE,
        id_pattern=_ID_RE,
    )
    log.info("Kijiji : %s annonces via le HTML.", len(listings))
    return listings


def _from_next_data(html: str) -> list[Listing]:
    """Kijiji sert ses resultats dans un blob Next.js, bien plus fiable que le DOM."""
    match = _NEXT_DATA_RE.search(html)
    if not match:
        return []
    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError:
        log.warning("Kijiji : __NEXT_DATA__ illisible.")
        return []

    listings: dict[str, Listing] = {}
    sampled = False
    for node in deep_find_dicts(data, required_any=("title", "adTitle")):
        listing_id = _first_str(node, ("id", "adId", "listingId"))
        title = _first_str(node, ("title", "adTitle"))
        url = _first_str(node, ("url", "seoUrl", "adUrl", "href"))
        if not (listing_id and title and url):
            continue
        listing_id = re.sub(r"\D", "", listing_id)
        if len(listing_id) < 9 or listing_id in listings:
            continue

        blob = json.dumps(node, ensure_ascii=False)
        if not sampled:
            # Sert a ajuster l'extraction quand Kijiji change la forme du payload.
            log.debug("Kijiji : exemple de noeud brut -> %s", blob[:1500])
            sampled = True
        listings[listing_id] = Listing(
            source=SOURCE,
            listing_id=listing_id,
            title=title,
            url=url if url.startswith("http") else BASE_URL + url,
            price=_price_from_node(node) or parse_price(blob),
            year=parse_year(title) or parse_year(blob),
            odometer_km=parse_odometer(blob),
            transmission=parse_transmission(blob),
            location=_first_str(node, ("location", "locationName", "city")),
        )
    return list(listings.values())


def _first_str(node: dict, keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = node.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, (int, float)):
            return str(value)
    return None


def _price_from_node(node: dict) -> int | None:
    price = node.get("price")
    if isinstance(price, dict):
        # Kijiji exprime souvent le montant en cents.
        amount = price.get("amount") or price.get("value")
        if isinstance(amount, (int, float)):
            amount = int(amount)
            return amount // 100 if amount > 200_000 else amount
    if isinstance(price, (int, float)):
        amount = int(price)
        return amount // 100 if amount > 200_000 else amount
    return None
