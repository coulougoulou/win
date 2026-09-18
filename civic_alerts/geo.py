"""Filtre de distance maison.

Les parametres de rayon des sites sont peu fiables : une execution reelle a
remonte une annonce de Lethbridge (Alberta, ~3000 km) malgre `radius=1000`.
On recalcule donc la distance nous-memes a partir de la ville, lisible dans
l'URL de l'annonce sur les deux sources.
"""

from __future__ import annotations

import logging
import math
import re
import unicodedata

log = logging.getLogger(__name__)

# Saint-Hubert (Longueuil), QC
ORIGIN = (45.4940, -73.4180)

# Villes canadiennes principales. Une ville absente de la table n'est jamais
# rejetee : mieux vaut une annonce a verifier qu'un village quebecois manque.
CITIES: dict[str, tuple[float, float]] = {
    # Quebec
    "montreal": (45.51, -73.57), "laval": (45.61, -73.71), "longueuil": (45.53, -73.52),
    "brossard": (45.45, -73.47), "saint-hubert": (45.49, -73.42), "st-hubert": (45.49, -73.42),
    "quebec": (46.81, -71.21), "levis": (46.80, -71.18), "gatineau": (45.48, -75.70),
    "sherbrooke": (45.40, -71.89), "trois-rivieres": (46.34, -72.54), "saguenay": (48.43, -71.07),
    "chicoutimi": (48.43, -71.06), "drummondville": (45.88, -72.48), "granby": (45.40, -72.73),
    "saint-jean-sur-richelieu": (45.31, -73.26), "saint-jerome": (45.78, -74.00),
    "repentigny": (45.74, -73.45), "terrebonne": (45.70, -73.65), "blainville": (45.67, -73.88),
    "mirabel": (45.65, -74.08), "shawinigan": (46.57, -72.74), "rimouski": (48.45, -68.52),
    "rouyn-noranda": (48.24, -79.02), "val-dor": (48.10, -77.80), "sept-iles": (50.21, -66.38),
    "gaspe": (48.83, -64.48), "victoriaville": (46.06, -71.96), "saint-hyacinthe": (45.63, -72.96),
    "sorel": (46.04, -73.11), "joliette": (46.02, -73.44), "salaberry": (45.25, -74.13),
    "saint-georges": (46.12, -70.67), "beauce": (46.12, -70.67), "thetford": (46.10, -71.30),
    "magog": (45.27, -72.15), "alma": (48.55, -71.65), "baie-comeau": (49.22, -68.15),
    "matane": (48.84, -67.53), "amos": (48.57, -78.12), "la-tuque": (47.44, -72.78),
    "vaudreuil": (45.40, -74.03), "saint-eustache": (45.57, -73.90), "chateauguay": (45.38, -73.75),
    "boucherville": (45.59, -73.44), "sainte-julie": (45.58, -73.34), "varennes": (45.68, -73.44),
    "rive-sud": (45.50, -73.45), "rive-nord": (45.70, -73.70), "laurentides": (46.05, -74.30),
    "monteregie": (45.40, -73.20), "estrie": (45.40, -71.90), "outaouais": (45.60, -75.80),
    "mauricie": (46.50, -72.80), "lanaudiere": (46.10, -73.50), "abitibi": (48.30, -78.50),
    "bas-saint-laurent": (48.20, -69.00), "cote-nord": (50.00, -66.50),
    # Ontario
    "toronto": (43.65, -79.38), "mississauga": (43.59, -79.64), "brampton": (43.68, -79.76),
    "hamilton": (43.26, -79.87), "ottawa": (45.42, -75.70), "london": (42.98, -81.25),
    "kitchener": (43.45, -80.49), "waterloo": (43.46, -80.52), "cambridge": (43.36, -80.31),
    "windsor": (42.31, -83.04), "oshawa": (43.90, -78.86), "barrie": (44.39, -79.69),
    "kingston": (44.23, -76.48), "guelph": (43.54, -80.25), "sudbury": (46.49, -80.99),
    "thunder-bay": (48.38, -89.25), "peterborough": (44.31, -78.32), "belleville": (44.16, -77.38),
    "niagara": (43.10, -79.07), "st-catharines": (43.16, -79.25), "markham": (43.86, -79.34),
    "vaughan": (43.84, -79.50), "richmond-hill": (43.88, -79.44), "oakville": (43.47, -79.69),
    "burlington": (43.33, -79.80), "ajax": (43.85, -79.02), "whitby": (43.88, -78.94),
    "pickering": (43.84, -79.09), "newmarket": (44.06, -79.46), "sarnia": (42.97, -82.40),
    "timmins": (48.48, -81.33), "sault-ste-marie": (46.52, -84.33), "north-bay": (46.31, -79.46),
    "cornwall": (45.02, -74.73), "brockville": (44.59, -75.68), "orillia": (44.61, -79.42),
    "brantford": (43.14, -80.26), "chatham": (42.40, -82.19), "woodstock": (43.13, -80.75),
    "stratford": (43.37, -80.98), "owen-sound": (44.57, -80.94), "kawartha": (44.35, -78.75),
    "durham": (43.90, -78.90), "peel": (43.65, -79.70), "york-region": (44.00, -79.47),
    "halton": (43.50, -79.85), "muskoka": (45.00, -79.30), "kenora": (49.77, -94.49),
    # Provinces de l'Atlantique
    "halifax": (44.65, -63.58), "dartmouth": (44.67, -63.58), "moncton": (46.09, -64.78),
    "saint-john": (45.28, -66.06), "fredericton": (45.96, -66.64), "charlottetown": (46.24, -63.13),
    "sydney": (46.14, -60.19), "truro": (45.37, -63.27), "bathurst": (47.62, -65.65),
    "edmundston": (47.37, -68.33), "miramichi": (47.03, -65.50), "st-johns": (47.56, -52.71),
    "corner-brook": (48.95, -57.95),
    # Ouest canadien (systematiquement hors rayon, mais present pour le rejet)
    "winnipeg": (49.90, -97.14), "brandon": (49.85, -99.95), "regina": (50.45, -104.62),
    "saskatoon": (52.13, -106.67), "calgary": (51.05, -114.07), "edmonton": (53.55, -113.49),
    "lethbridge": (49.69, -112.84), "red-deer": (52.27, -113.81), "medicine-hat": (50.04, -110.68),
    "vancouver": (49.28, -123.12), "surrey": (49.19, -122.85), "victoria": (48.43, -123.37),
    "kelowna": (49.89, -119.50), "kamloops": (50.67, -120.33), "abbotsford": (49.05, -122.33),
    "nanaimo": (49.17, -123.94), "prince-george": (53.92, -122.75), "whitehorse": (60.72, -135.06),
    "yellowknife": (62.45, -114.37),
}

# Les noms longs d'abord : "saint-jean-sur-richelieu" doit gagner sur "saint-jean".
_ORDERED = sorted(CITIES.items(), key=lambda item: -len(item[0]))


def normalize(text: str) -> str:
    stripped = unicodedata.normalize("NFKD", text)
    stripped = "".join(char for char in stripped if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", "-", stripped.lower()).strip("-")


def haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(h))


def locate(*texts: str | None) -> tuple[str, float] | None:
    """Trouve la premiere ville connue mentionnee et sa distance de l'origine."""
    haystack = normalize(" ".join(text for text in texts if text))
    for name, coords in _ORDERED:
        # Bornes de mots pour eviter que "london" matche "new-london-road".
        if re.search(rf"(?:^|-){re.escape(name)}(?:-|$)", haystack):
            return name, haversine_km(ORIGIN, coords)
    return None


def within_radius(radius_km: int, *texts: str | None) -> tuple[bool, str]:
    found = locate(*texts)
    if found is None:
        return True, "ville inconnue (gardee)"
    name, distance = found
    if distance <= radius_km:
        return True, f"{name} a ~{distance:.0f} km"
    return False, f"{name} a ~{distance:.0f} km, hors rayon de {radius_km} km"
