"""Sources d'annonces. Chaque module expose `fetch(session, criteria) -> list[Listing]`."""

from . import autohebdo, kijiji

ALL_SOURCES = {
    "kijiji": kijiji,
    "autohebdo": autohebdo,
}
