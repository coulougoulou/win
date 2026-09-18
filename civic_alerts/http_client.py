"""Client HTTP partage : entetes credibles, retries, delais polis."""

from __future__ import annotations

import logging
import random
import time

import requests

log = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)

BASE_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept-Language": "fr-CA,fr;q=0.9,en-CA;q=0.8,en;q=0.7",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(BASE_HEADERS)
    return session


def get(session: requests.Session, url: str, *, attempts: int = 3, **kwargs) -> requests.Response | None:
    return _request(session, "GET", url, attempts=attempts, **kwargs)


def post(session: requests.Session, url: str, *, attempts: int = 3, **kwargs) -> requests.Response | None:
    return _request(session, "POST", url, attempts=attempts, **kwargs)


def _request(session, method: str, url: str, *, attempts: int, **kwargs):
    kwargs.setdefault("timeout", 30)
    for attempt in range(1, attempts + 1):
        try:
            response = session.request(method, url, **kwargs)
            if response.status_code == 200:
                return response
            log.warning("%s %s -> HTTP %s (essai %s/%s)", method, url, response.status_code, attempt, attempts)
            # 403/429 = on nous a repere : inutile de marteler.
            if response.status_code in (403, 429) and attempt == attempts:
                return None
        except requests.RequestException as exc:
            log.warning("%s %s a echoue : %s (essai %s/%s)", method, url, exc, attempt, attempts)
        if attempt < attempts:
            time.sleep(2 ** attempt + random.uniform(0, 1.5))
    return None
