"""Tests hors-ligne : parsing, filtres, extraction HTML, etat, formatage."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from civic_alerts import filters, geo, notify, state
from civic_alerts.config import Criteria
from civic_alerts.models import Listing
from civic_alerts.parsing import parse_odometer, parse_price, parse_transmission, parse_year
from civic_alerts.sources._html import listings_from_anchors
from civic_alerts.sources import autohebdo, kijiji

CRITERIA = Criteria()


def check(label: str, got, expected):
    assert got == expected, f"{label}: attendu {expected!r}, obtenu {got!r}"
    print(f"  ok  {label}")


def test_parsing():
    print("parsing")
    check("prix avec espace", parse_price("14 500 $"), 14500)
    check("prix avec virgule", parse_price("$12,995"), 12995)
    check("prix bruit ignore", parse_price("lot 42"), None)
    # Cas reel : sur une carte AutoHebdo, l'annee precede le prix.
    check("annee collee au prix", parse_price("2019 13 995 $"), 13995)
    check("km non avale par l'annee", parse_odometer("2019 96 000 km"), 96000)
    check("prix simple", parse_price("7500 $"), 7500)
    check("km francais", parse_odometer("142 000 km"), 142000)
    check("km anglais", parse_odometer("98,500 KM"), 98500)
    check("km faux positif", parse_odometer("2 km du metro"), None)
    check("annee", parse_year("2018 Honda Civic Sport"), 2018)
    check("transmission auto", parse_transmission("Boite automatique"), "automatic")
    check("transmission cvt", parse_transmission("CVT, 4 portes"), "automatic")
    check("transmission manuelle", parse_transmission("6 vitesses manuelle"), "manual")
    check("transmission absente", parse_transmission("4 portes"), None)


def listing(**kwargs) -> Listing:
    base = dict(
        source="test", listing_id="1", title="2019 Honda Civic Sport", url="https://x/1",
        price=13000, year=2019, odometer_km=90000, transmission="automatic",
    )
    base.update(kwargs)
    return Listing(**base)


def test_filters():
    print("filtres")
    check("annonce conforme", filters.matches(listing(), CRITERIA)[0], True)
    check("trop chere", filters.matches(listing(price=18000), CRITERIA)[0], False)
    check("trop de km", filters.matches(listing(odometer_km=190000), CRITERIA)[0], False)
    check("trop vieille", filters.matches(listing(year=2015, title="2015 Honda Civic Sport"), CRITERIA)[0], False)
    check("manuelle rejetee", filters.matches(listing(transmission="manual"), CRITERIA)[0], False)
    check("transmission inconnue gardee", filters.matches(listing(transmission=None), CRITERIA)[0], True)
    check("prix inconnu garde", filters.matches(listing(price=None), CRITERIA)[0], True)
    check("sans Sport rejetee", filters.matches(listing(title="2019 Honda Civic LX"), CRITERIA)[0], False)
    check("pieces rejetees", filters.matches(listing(title="2019 Honda Civic Sport pour pieces"), CRITERIA)[0], False)
    check("autre modele rejete", filters.matches(listing(title="2019 Honda Accord Sport"), CRITERIA)[0], False)
    check("apply", len(filters.apply([listing(), listing(price=90000)], CRITERIA)), 1)


KIJIJI_HTML = """
<html><body>
<div class="card">
  <a href="/v-autos-camions/longueuil/2018-honda-civic-sport/1701234567">2018 Honda Civic Sport</a>
  <div><span>13 495 $</span><span>112 000 km</span><span>Automatique</span></div>
</div>
<div class="card">
  <a href="/v-autos-camions/laval/2017-honda-civic-sport-manuelle/1709876543">2017 Honda Civic Sport</a>
  <div><span>11 000 $</span><span>155 000 km</span><span>Manuelle</span></div>
</div>
<a href="/b-autos-camions/canada/page-2">Page suivante</a>
</body></html>
"""


def test_html_extraction():
    print("extraction HTML")
    found = listings_from_anchors(
        KIJIJI_HTML, source="kijiji", base_url="https://www.kijiji.ca",
        href_pattern=re.compile(r"/v-autos-camions/"), id_pattern=re.compile(r"/(\d{9,})(?:$|[/?#])"),
    )
    check("nombre d'annonces", len(found), 2)
    first = next(item for item in found if item.listing_id == "1701234567")
    check("titre", first.title, "2018 Honda Civic Sport")
    check("url absolue", first.url, "https://www.kijiji.ca/v-autos-camions/longueuil/2018-honda-civic-sport/1701234567")
    check("prix", first.price, 13495)
    check("km", first.odometer_km, 112000)
    check("annee", first.year, 2018)
    check("transmission", first.transmission, "automatic")
    check("lien de pagination ignore", all(item.listing_id.isdigit() for item in found), True)
    check("manuelle filtree ensuite", len(filters.apply(found, CRITERIA)), 1)


# Forme reelle d'un noeud Kijiji, relevee dans les logs d'une execution.
NEXT_DATA = {
    "props": {"pageProps": {"results": {"items": [
        {"__typename": "AutosListing", "id": "1712345678", "title": "2019 Honda Civic Sport",
         "url": "https://www.kijiji.ca/v-cars-trucks/rive-sud/2019-honda-civic-sport/1712345678",
         "price": {"__typename": "AutosDealerAmountPrice", "amount": 1449500},
         "location": {"name": "Rive-Sud", "address": "Saint-Hubert, QC",
                      "coordinates": {"latitude": 45.4940, "longitude": -73.4180}},
         "attributes": {"__typename": "AutosListingAttributes", "all": [
             {"__typename": "ListingAttributeV2", "canonicalName": "vehicletype",
              "canonicalValues": ["used"]},
             {"__typename": "ListingAttributeV2", "canonicalName": "carmileageinkms",
              "canonicalValues": ["88000"]},
             {"__typename": "ListingAttributeV2", "canonicalName": "cartransmission",
              "canonicalValues": ["automatic"]},
         ]}}
    ]}}}
}


def test_kijiji_next_data():
    print("kijiji __NEXT_DATA__")
    html = f'<script id="__NEXT_DATA__" type="application/json">{json.dumps(NEXT_DATA)}</script>'
    found = kijiji._from_next_data(html)
    check("nombre", len(found), 1)
    item = found[0]
    check("id", item.listing_id, "1712345678")
    check("prix en cents converti", item.price, 14495)
    check("km lu dans les attributs", item.odometer_km, 88000)
    check("transmission lue dans les attributs", item.transmission, "automatic")
    check("latitude", round(item.latitude, 3), 45.494)
    check("distance exacte utilisee", geo.within_radius(1000, coords=(item.latitude, item.longitude))[0], True)
    check("url", item.url.startswith("https://www.kijiji.ca/"), True)
    check("passe les filtres", filters.matches(item, CRITERIA)[0], True)


def test_coordinates_beat_city_table():
    print("coordonnees exactes")
    # L'URL dit "montreal" mais les coordonnees pointent vers Vancouver :
    # ce sont les coordonnees qui doivent trancher.
    far = listing(url="https://www.kijiji.ca/v-cars-trucks/montreal/x/1")
    far.latitude, far.longitude = 49.28, -123.12
    check("coordonnees prioritaires sur l'URL", filters.matches(far, CRITERIA)[0], False)
    near = listing(url="https://www.kijiji.ca/v-cars-trucks/lethbridge/x/1")
    near.latitude, near.longitude = 45.50, -73.45
    check("annonce proche gardee malgre l'URL", filters.matches(near, CRITERIA)[0], True)


def test_geo():
    print("distance")
    # Villes tirees d'une execution reelle du job.
    check("Lethbridge hors rayon", geo.within_radius(1000, "https://www.kijiji.ca/v-cars-trucks/lethbridge/x/1")[0], False)
    check("Dartmouth dans le rayon", geo.within_radius(1000, "https://www.kijiji.ca/v-cars-trucks/dartmouth/x/1")[0], True)
    check("Beauce dans le rayon", geo.within_radius(1000, "https://www.kijiji.ca/v-cars-trucks/st-georges-de-beauce/x/1")[0], True)
    check("Vancouver hors rayon", geo.within_radius(1000, "https://www.kijiji.ca/v-cars-trucks/vancouver/x/1")[0], False)
    check("ville inconnue gardee", geo.within_radius(1000, "https://www.kijiji.ca/v-cars-trucks/ste-bidule-des-bois/x/1")[0], True)
    check("accents normalises", geo.within_radius(1000, None, "Trois-Rivières, QC")[0], True)
    check("pas de faux positif sur sous-chaine", geo.locate("new-londonderry-road"), None)
    lethbridge = listing(url="https://www.kijiji.ca/v-cars-trucks/lethbridge/2018-honda-civic-sport/1")
    check("filtre integre au pipeline", filters.matches(lethbridge, CRITERIA)[0], False)


def test_english_manual():
    print("transmission anglaise")
    # Cas reel passe a travers le filtre lors de la premiere execution.
    manual = listing(title="2018 Honda Civic Sport Turbo 6 Speed Hatchback", transmission=None)
    manual.transmission = parse_transmission(manual.title)
    check("6 Speed detecte", manual.transmission, "manual")
    check("annonce rejetee", filters.matches(manual, CRITERIA)[0], False)
    check("6-Spd detecte", parse_transmission("6-Spd Manual"), "manual")


AUTOHEBDO_HTML = """
<html><body>
<div class="card">
  <a href="/annonces/honda-civic-sport-toit-mags-sieges-chauffants-essence-noir-cat_ma31gr200622va2411tr7208-3c3aa366-12e2-4d81-8297-59b895f42480">Ouvrir les détails de l'annonce</a>
  <div><span>2019</span><span>13 995 $</span><span>96 000 km</span></div>
</div>
</body></html>
"""


def test_autohebdo_parsing():
    print("autohebdo")
    found = autohebdo._parse(AUTOHEBDO_HTML)
    check("une annonce", len(found), 1)
    item = found[0]
    # Le libelle du lien est generique : le titre doit venir du slug de l'URL.
    check("titre reconstruit", "civic" in item.title.lower() and "sport" in item.title.lower(), True)
    check("libelle generique ecarte", "ouvrir les" not in item.title.lower(), True)
    check("annee tiree du bloc", item.year, 2019)
    check("prix", item.price, 13995)
    check("km", item.odometer_km, 96000)
    check("id = uuid", item.listing_id, "3c3aa366-12e2-4d81-8297-59b895f42480")
    check("passe les filtres", filters.matches(item, CRITERIA)[0], True)


def test_dedupe():
    print("doublons inter-sources")
    # Cas reel : la meme Civic 2017 a 14 990 $ / 134 000 km sur les deux sites.
    kijiji_item = listing(source="kijiji", listing_id="1", year=2017, price=14990, odometer_km=134000)
    autohebdo_item = listing(source="autohebdo", listing_id="uuid", year=2017, price=14990, odometer_km=134000)
    merged = filters.dedupe_across_sources([kijiji_item, autohebdo_item])
    check("un seul exemplaire", len(merged), 1)
    check("la premiere source gagne", merged[0].source, "kijiji")
    autres = filters.dedupe_across_sources([kijiji_item, listing(source="autohebdo", listing_id="u2", price=13000)])
    check("voitures differentes conservees", len(autres), 2)
    # Sans les trois champs, la fusion serait un pari : on garde les deux.
    flous = filters.dedupe_across_sources([
        listing(source="kijiji", listing_id="a", odometer_km=None),
        listing(source="autohebdo", listing_id="b", odometer_km=None),
    ])
    check("annonces incompletes non fusionnees", len(flous), 2)


def test_state(tmp: Path):
    print("etat")
    path = tmp / "seen.json"
    state.save(path, {"kijiji:1": "2026-09-18", "kijiji:2": "2000-01-01"}, ttl_days=90)
    loaded = state.load(path)
    check("annonce recente conservee", "kijiji:1" in loaded, True)
    check("annonce expiree purgee", "kijiji:2" in loaded, False)
    check("fichier absent -> vide", state.load(tmp / "nope.json"), {})
    (tmp / "bad.json").write_text("{pas du json")
    check("fichier corrompu -> vide", state.load(tmp / "bad.json"), {})


def test_messages():
    print("formatage Telegram")
    messages = notify.build_messages([listing(listing_id=str(i)) for i in range(3)])
    check("un seul message", len(messages), 1)
    check("entete", "3 nouvelle(s)" in messages[0], True)
    check("lien present", 'href="https://x/1"' in messages[0], True)
    big = notify.build_messages([listing(listing_id=str(i), title="T" * 110) for i in range(60)])
    check("decoupage sous la limite", all(len(m) <= 3900 for m in big), True)
    escaped = notify.build_messages([listing(title="Civic Sport <b>aubaine</b> & propre")])
    check("HTML echappe", "<b>aubaine</b>" not in escaped[0].replace("<b>1", ""), True)


if __name__ == "__main__":
    import tempfile
    test_parsing()
    test_filters()
    test_html_extraction()
    test_kijiji_next_data()
    test_geo()
    test_coordinates_beat_city_table()
    test_autohebdo_parsing()
    test_dedupe()
    test_english_manual()
    with tempfile.TemporaryDirectory() as tmpdir:
        test_state(Path(tmpdir))
    test_messages()
    print("\nTous les tests passent.")
