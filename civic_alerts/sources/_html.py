"""Extraction generique de cartes d'annonces depuis du HTML.

Les deux sources changent leur balisage regulierement. Plutot que de dependre de
selecteurs CSS precis, on part des liens vers les fiches d'annonce et on lit le
texte du bloc parent pour en tirer prix / km / annee.
"""

from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from ..models import Listing
from ..parsing import parse_odometer, parse_price, parse_transmission, parse_year


def _block_text(anchor: Tag, href_pattern: re.Pattern[str], levels: int = 5) -> str:
    """Texte de la carte contenant l'annonce.

    On remonte tant que l'ancetre ne couvre qu'une seule annonce. Des qu'il en
    contient deux, on s'est hisse jusqu'a la liste : le texte melangerait alors
    le prix et la transmission de l'annonce voisine.
    """
    node: Tag = anchor
    for _ in range(levels):
        parent = node.parent
        if parent is None or not isinstance(parent, Tag):
            break
        if _count_listing_links(parent, href_pattern) > 1:
            break
        node = parent
    return node.get_text(" ", strip=True)


def _count_listing_links(node: Tag, href_pattern: re.Pattern[str]) -> int:
    return sum(
        1 for link in node.find_all("a", href=True) if href_pattern.search(link["href"])
    )


def listings_from_anchors(
    html: str,
    *,
    source: str,
    base_url: str,
    href_pattern: re.Pattern[str],
    id_pattern: re.Pattern[str],
    title_builder=None,
) -> list[Listing]:
    soup = BeautifulSoup(html, "html.parser")
    found: dict[str, Listing] = {}

    for anchor in soup.find_all("a", href=True):
        href = anchor["href"]
        if not href_pattern.search(href):
            continue
        id_match = id_pattern.search(href)
        if not id_match:
            continue
        listing_id = id_match.group(1)
        if listing_id in found:
            continue

        anchor_text = anchor.get_text(" ", strip=True) or anchor.get("title", "")
        context = _block_text(anchor, href_pattern)
        if title_builder is not None:
            title = title_builder(href, anchor_text, context)
        else:
            title = anchor_text
        # Le titre vient parfois d'un lien image vide : on retombe sur le bloc.
        if len(title) < 8:
            title = context[:120]

        found[listing_id] = Listing(
            source=source,
            listing_id=listing_id,
            title=title,
            url=urljoin(base_url, href.split("?")[0]),
            price=parse_price(context),
            year=parse_year(title) or parse_year(context),
            odometer_km=parse_odometer(context),
            transmission=parse_transmission(context),
        )

    return list(found.values())
