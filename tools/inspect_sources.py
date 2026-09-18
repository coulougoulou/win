"""Diagnostic temporaire : inspecte la structure reelle des pages sources.

A executer sur un runner GitHub (le conteneur de developpement n'a pas d'acces
reseau vers ces domaines). Supprime une fois les selecteurs ajustes.
"""

import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bs4 import BeautifulSoup

from civic_alerts import http_client
from civic_alerts.config import CRITERIA
from civic_alerts.sources import autohebdo, kijiji

session = http_client.make_session()


def inspect_autohebdo():
    print("\n=== AUTOHEBDO ===")
    for label, url, params in [
        ("recherche canonique", autohebdo.SEARCH_URL, autohebdo._search_params(CRITERIA)),
        ("recherche simple", autohebdo.SEARCH_URL, {"prx": "1000", "loc": "Saint-Hubert, QC"}),
    ]:
        response = http_client.get(session, url, params=params, attempts=1)
        if response is None:
            print(f"{label}: inaccessible")
            continue
        print(f"{label}: {response.status_code}, {len(response.text)} octets -> {response.url}")
        soup = BeautifulSoup(response.text, "html.parser")
        hrefs = [a["href"] for a in soup.find_all("a", href=True)]
        print("  prefixes de liens les plus frequents :")
        for prefix, count in Counter("/".join(h.split("/")[:3]) for h in hrefs).most_common(12):
            print(f"    {count:4d}  {prefix}")
        candidates = [h for h in hrefs if re.search(r"civic", h, re.I)]
        print(f"  liens contenant 'civic' : {len(candidates)}")
        for href in candidates[:8]:
            print(f"    {href}")
        # Un SPA laisse peu de liens mais souvent un blob JSON.
        for pattern in (r'window\[.([A-Za-z]+).\]\s*=', r'id="([A-Za-z_-]*[Dd]ata[A-Za-z_-]*)"'):
            hits = set(re.findall(pattern, response.text))
            if hits:
                print(f"  blobs JS reperes ({pattern}): {sorted(hits)[:10]}")
        print(f"  mentions de 'srp-list'/'result-item' : "
              f"{len(re.findall(r'srp-list|result-item|listing-item', response.text, re.I))}")


def inspect_kijiji():
    print("\n=== KIJIJI ===")
    response = http_client.get(session, kijiji.SEARCH_URL, params=kijiji._search_params(CRITERIA), attempts=1)
    if response is None:
        print("inaccessible")
        return
    match = kijiji._NEXT_DATA_RE.search(response.text)
    if not match:
        print("pas de __NEXT_DATA__")
        return
    data = json.loads(match.group(1))
    from civic_alerts._compat import deep_find_dicts

    for node in deep_find_dicts(data, required_any=("title", "adTitle")):
        if not str(node.get("id", "")).isdigit():
            continue
        print("  cles du noeud :", sorted(node.keys()))
        print("  extrait :", json.dumps(node, ensure_ascii=False)[:2000])
        break


if __name__ == "__main__":
    inspect_autohebdo()
    inspect_kijiji()
