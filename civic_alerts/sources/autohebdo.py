"""AutoHebdo (autoTrader.ca) - concessionnaires et particuliers, tout le Canada."""

from __future__ import annotations

import json
import logging
import re

from .. import http_client
from ..config import Criteria
from ..models import Listing
from ._html import listings_from_anchors

log = logging.getLogger(__name__)

SOURCE = "autohebdo"
BASE_URL = "https://www.autohebdo.net"
SEARCH_URL = BASE_URL + "/voitures-usages/honda/civic/"
# Endpoint interne utilise par la pagination du site : il renvoie le HTML des
# cartes d'annonces, sans le bruit de la page complete.
REFINEMENT_URL = BASE_URL + "/Refinement/Search"

_HREF_RE = re.compile(r"/a/honda/civic/", re.IGNORECASE)
_ID_RE = re.compile(r"/(\d{6,})(?:$|[/?#])")

PAGE_SIZE = 100


def _search_params(criteria: Criteria) -> dict[str, str]:
    return {
        "rcp": str(PAGE_SIZE),
        "rcs": "0",
        "srt": "9",  # les plus recentes d'abord
        "prx": str(criteria.radius_km),
        "loc": criteria.postal_code,
        "hprc": "True",
        "wcp": "True",
        "sts": "Used",
        "yRng": f"{criteria.year_min},",
        "pRng": f",{criteria.price_max}",
        "oRng": f",{criteria.odometer_max}",
        "trans": "Automatic",
        "inMarket": "advancedSearch",
    }


def fetch(session, criteria: Criteria) -> list[Listing]:
    params = _search_params(criteria)

    response = http_client.post(
        session,
        REFINEMENT_URL,
        json=_refinement_payload(criteria),
        headers={"Content-Type": "application/json", "Accept": "application/json", "Referer": SEARCH_URL},
        attempts=2,
    )
    html = _html_from_refinement(response)
    if html:
        listings = _parse(html)
        if listings:
            log.info("AutoHebdo : %s annonces via Refinement/Search.", len(listings))
            return listings

    response = http_client.get(session, SEARCH_URL, params=params)
    if response is None:
        log.error("AutoHebdo : recherche inaccessible.")
        return []
    listings = _parse(response.text)
    log.info("AutoHebdo : %s annonces via la page de resultats.", len(listings))
    return listings


def _refinement_payload(criteria: Criteria) -> dict:
    return {
        "Address": criteria.postal_code,
        "Proximity": criteria.radius_km,
        "Make": criteria.make,
        "Model": criteria.model,
        "PriceMax": criteria.price_max,
        "YearMin": criteria.year_min,
        "OdometerMax": criteria.odometer_max,
        "Transmission": "Automatic",
        "IsNew": False,
        "IsUsed": True,
        "Top": PAGE_SIZE,
        "Skip": 0,
        "micrositeType": 1,
    }


def _html_from_refinement(response) -> str | None:
    if response is None:
        return None
    try:
        payload = response.json()
    except ValueError:
        return None
    # La reponse imbrique une chaine JSON qui contient le HTML des cartes.
    raw = payload.get("SearchResultsDataJson") or payload.get("searchResultsDataJson")
    if isinstance(raw, str) and raw.strip():
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return None
    for key in ("AdsHtml", "adsHtml", "ResultsHtml"):
        html = payload.get(key)
        if isinstance(html, str) and html.strip():
            return html
    return None


def _parse(html: str) -> list[Listing]:
    return listings_from_anchors(
        html,
        source=SOURCE,
        base_url=BASE_URL,
        href_pattern=_HREF_RE,
        id_pattern=_ID_RE,
    )
