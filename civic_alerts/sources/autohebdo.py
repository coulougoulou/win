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
# Le site repond 308 et reecrit ?prx=1000&loc=... en .../cit_saint-hubert, ce
# qui reduit la recherche a la ville. On interroge donc explicitement les
# regions couvertes par un rayon de 1000 km ; le filtre de distance fait le
# tri fin ensuite.
REGIONS = ("reg_qc", "on", "nb", "ns")
# Les fiches d'annonce vivent sous /annonces/<slug>-<uuid>, constate en
# inspectant le HTML reel du site.

_HREF_RE = re.compile(r"/annonces/[^/]*civic", re.IGNORECASE)
_ID_RE = re.compile(r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})", re.IGNORECASE)

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


def _region_url(region: str, criteria: Criteria) -> str:
    return (
        f"{SEARCH_URL}{region}/ot_occasion/tr_automatique/pr_{criteria.price_max}"
    )


def fetch(session, criteria: Criteria) -> list[Listing]:
    params = {
        "modelyearfrom": str(criteria.year_min),
        "kmto": str(criteria.odometer_max),
        "rcp": str(PAGE_SIZE),
        "srt": "35",
    }
    found: dict[str, Listing] = {}
    for region in REGIONS:
        response = http_client.get(session, _region_url(region, criteria), params=params, attempts=2)
        if response is None:
            log.warning("AutoHebdo : region %s inaccessible.", region)
            continue
        for listing in _parse(response.text):
            found.setdefault(listing.listing_id, listing)
        log.info("AutoHebdo : %s annonces cumulees apres %s.", len(found), region)

    if not found:
        log.error("AutoHebdo : aucune annonce extraite.")
    return list(found.values())


def _title_from_href(href: str, anchor_text: str, context: str) -> str:
    """Le lien porte un libelle generique ("Ouvrir les details de l'annonce").

    Le vrai descriptif est dans le slug de l'URL, avant le marqueur `cat_`.
    """
    slug = href.split("/annonces/")[-1].split("?")[0]
    slug = re.split(r"-cat_", slug)[0]
    title = slug.replace("-", " ").strip()
    if len(title) >= 8:
        # L'annee n'est pas dans le slug : on la recupere du bloc de la carte.
        year = re.search(r"\b(20[0-4]\d)\b", context)
        return f"{year.group(1)} {title}" if year else title
    return anchor_text


def _parse(html: str) -> list[Listing]:
    return listings_from_anchors(
        html,
        source=SOURCE,
        base_url=BASE_URL,
        href_pattern=_HREF_RE,
        id_pattern=_ID_RE,
        title_builder=_title_from_href,
    )
