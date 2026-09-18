"""Point d'entree : cherche, filtre, deduplique, notifie.

    python -m civic_alerts.main --dry-run
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date

from . import filters, http_client, notify, state
from .config import CRITERIA, MAX_LISTINGS_PER_MESSAGE, STATE_PATH, STATE_TTL_DAYS
from .models import Listing
from .sources import ALL_SOURCES

log = logging.getLogger("civic_alerts")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Alertes Honda Civic Sport")
    parser.add_argument("--dry-run", action="store_true", help="Affiche au lieu d'envoyer sur Telegram.")
    parser.add_argument("--no-state", action="store_true", help="Ignore et n'ecrit pas l'etat (tout est 'nouveau').")
    parser.add_argument("--sources", default="", help="Sous-ensemble de sources, separees par des virgules.")
    parser.add_argument("--verbose", "-v", action="store_true", help="Journalise aussi les annonces rejetees.")
    return parser.parse_args(argv)


def collect(source_names: list[str]) -> list[Listing]:
    session = http_client.make_session()
    collected: list[Listing] = []
    for name in source_names:
        module = ALL_SOURCES[name]
        try:
            found = module.fetch(session, CRITERIA)
        except Exception:  # une source cassee ne doit pas tuer les autres
            log.exception("Source %s en erreur, on continue.", name)
            continue
        log.info("%s : %s annonces brutes.", name, len(found))
        collected.extend(found)
    return collected


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    requested = [s.strip() for s in args.sources.split(",") if s.strip()] or list(ALL_SOURCES)
    unknown = [name for name in requested if name not in ALL_SOURCES]
    if unknown:
        log.error("Source(s) inconnue(s) : %s. Disponibles : %s", unknown, list(ALL_SOURCES))
        return 2

    raw = collect(requested)
    if not raw:
        # Zero annonce brute = les sites ont bloque ou change de structure.
        # C'est une panne, pas un resultat : on echoue fort pour que ca se voie.
        log.error("Aucune annonce recuperee d'aucune source : scraping probablement bloque ou casse.")
        return 1

    kept = filters.apply(raw, CRITERIA)
    before_dedupe = len(kept)
    kept = filters.dedupe_across_sources(kept)
    log.info(
        "%s annonces correspondent aux criteres (sur %s), %s doublon(s) inter-sources retire(s).",
        len(kept), len(raw), before_dedupe - len(kept),
    )

    seen = {} if args.no_state else state.load(STATE_PATH)
    fresh = [listing for listing in kept if listing.key not in seen]
    log.info("%s nouvelle(s) annonce(s) jamais notifiee(s).", len(fresh))

    if fresh:
        fresh.sort(key=lambda item: (item.price is None, item.price or 0))
        if not notify.send(fresh, dry_run=args.dry_run):
            # On n'enregistre rien : la prochaine execution reessaiera.
            log.error("Notification non livree, l'etat n'est pas mis a jour.")
            return 1
        for listing in fresh:
            seen[listing.key] = date.today().isoformat()
    else:
        log.info("Rien de neuf aujourd'hui.")

    # On rafraichit aussi la date des annonces toujours en ligne pour qu'elles
    # ne soient pas oubliees par le TTL puis re-notifiees a tort.
    for listing in kept:
        seen.setdefault(listing.key, date.today().isoformat())

    if not args.no_state:
        state.save(STATE_PATH, seen, STATE_TTL_DAYS)

    print(f"::notice::{len(fresh)} nouvelle(s) annonce(s), {len(kept)} correspondance(s) au total")
    return 0


if __name__ == "__main__":
    sys.exit(main())
