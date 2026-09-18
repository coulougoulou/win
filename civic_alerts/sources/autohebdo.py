"""AutoHebdo (autoTrader.ca) - concessionnaires et particuliers, tout le Canada."""

from __future__ import annotations

import logging
import re

from .. import http_client
from ..config import Criteria
from ..models import Listing
from ._html import listings_from_anchors

log = logging.getLogger(__name__)

SOURCE = "autohebdo"
BASE_URL = "https://www.autohebdo.net"
SEARCH_URL = BASE_URL + "/autos/honda/civic/"
# Les fiches d'annonce vivent sous /a/<marque>/<modele>/<ville>/<prov>/<id>.

_HREF_RE = re.compile(r"/a/honda/civic/", re.IGNORECASE)
_ID_RE = re.compile(r"/(\d{6,})(?:$|[/?#])")

PAGE_SIZE = 100


def _search_params(criteria: Criteria) -> dict[str, str]:
    return {
        "rcp": str(PAGE_SIZE),
        "rcs": "0",
        "srt": "35",  # les plus recentes d'abord
        "prx": str(criteria.radius_km),
        "loc": criteria.city,
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
    response = http_client.get(session, SEARCH_URL, params=_search_params(criteria))
    if response is None:
        log.error("AutoHebdo : recherche inaccessible.")
        return []
    listings = _parse(response.text)
    log.info("AutoHebdo : %s annonces via la page de resultats.", len(listings))
    return listings


def _parse(html: str) -> list[Listing]:
    return listings_from_anchors(
        html,
        source=SOURCE,
        base_url=BASE_URL,
        href_pattern=_HREF_RE,
        id_pattern=_ID_RE,
    )
