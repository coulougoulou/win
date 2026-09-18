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
        attrs = _attributes(node)
        latitude, longitude = _coordinates(node)
        description = node.get("description") if isinstance(node.get("description"), str) else ""
        listings[listing_id] = Listing(
            source=SOURCE,
            listing_id=listing_id,
            title=title,
            url=url if url.startswith("http") else BASE_URL + url,
            price=_price_from_node(node) or parse_price(blob),
            year=parse_year(title) or _year_from_attributes(attrs) or parse_year(blob),
            odometer_km=_odometer_from_attributes(attrs) or parse_odometer(f"{title} {description}"),
            transmission=(
                _transmission_from_attributes(attrs)
                or parse_transmission(title)
                or parse_transmission(description)
            ),
            location=_location_name(node),
            latitude=latitude,
            longitude=longitude,
        )
    return list(listings.values())


_ODOMETER_KEYS = ("mileage", "kilometrage", "kilometre", "odometer", "km")
_TRANSMISSION_KEYS = ("transmission", "boite", "gearbox")


def _attributes(node: dict) -> dict[str, str]:
    """Aplati la liste d'attributs Kijiji en {nom normalise: valeur}."""
    flat: dict[str, str] = {}
    raw = node.get("attributes")
    if isinstance(raw, dict):
        raw = [{"name": key, "value": value} for key, value in raw.items()]
    if not isinstance(raw, list):
        return flat
    for item in raw:
        if not isinstance(item, dict):
            continue
        name = item.get("name") or item.get("canonicalName") or item.get("key")
        value = item.get("value") or item.get("canonicalValue") or item.get("values")
        if isinstance(value, list):
            value = " ".join(str(part) for part in value)
        if isinstance(name, str) and value is not None:
            flat[name.strip().lower()] = str(value)
    return flat


def _odometer_from_attributes(attrs: dict[str, str]) -> int | None:
    for name, value in attrs.items():
        if any(key in name for key in _ODOMETER_KEYS):
            digits = re.sub(r"[^\d]", "", value)
            if digits and 100 <= int(digits) <= 999_999:
                return int(digits)
    return None


def _transmission_from_attributes(attrs: dict[str, str]) -> str | None:
    for name, value in attrs.items():
        if any(key in name for key in _TRANSMISSION_KEYS):
            found = parse_transmission(value)
            if found:
                return found
    return None


def _year_from_attributes(attrs: dict[str, str]) -> int | None:
    for name, value in attrs.items():
        if "year" in name or "annee" in name:
            year = parse_year(value)
            if year:
                return year
    return None


def _coordinates(node: dict) -> tuple[float | None, float | None]:
    location = node.get("location")
    coords = location.get("coordinates") if isinstance(location, dict) else None
    if isinstance(coords, dict):
        lat, lon = coords.get("latitude"), coords.get("longitude")
        if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
            return float(lat), float(lon)
    return None, None


def _location_name(node: dict) -> str | None:
    location = node.get("location")
    if isinstance(location, dict):
        for key in ("name", "address", "city"):
            value = location.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    if isinstance(location, str) and location.strip():
        return location.strip()
    return None


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
