"""Envoi des alertes sur Telegram."""

from __future__ import annotations

import html
import logging
import os

import requests

from .config import MAX_LISTINGS_PER_MESSAGE
from .models import Listing

log = logging.getLogger(__name__)

API_URL = "https://api.telegram.org/bot{token}/sendMessage"
# Telegram coupe a 4096 caracteres ; on garde de la marge.
MAX_CHARS = 3800


def format_listing(listing: Listing) -> str:
    bits = [listing.human_price(), listing.human_odometer()]
    if listing.year:
        bits.insert(0, str(listing.year))
    if listing.location:
        bits.append(listing.location)
    title = html.escape(listing.title[:110])
    return f'• <a href="{html.escape(listing.url)}">{title}</a>\n  {html.escape(" — ".join(bits))}'


def build_messages(listings: list[Listing]) -> list[str]:
    header = f"🚗 <b>{len(listings)} nouvelle(s) Honda Civic Sport</b>"
    blocks = [format_listing(item) for item in listings[:MAX_LISTINGS_PER_MESSAGE]]
    if len(listings) > MAX_LISTINGS_PER_MESSAGE:
        blocks.append(f"… et {len(listings) - MAX_LISTINGS_PER_MESSAGE} autre(s).")

    messages: list[str] = []
    current = header
    for block in blocks:
        if len(current) + len(block) + 2 > MAX_CHARS:
            messages.append(current)
            current = block
        else:
            current = f"{current}\n\n{block}"
    messages.append(current)
    return messages


def send(listings: list[Listing], *, dry_run: bool = False) -> bool:
    messages = build_messages(listings)

    if dry_run:
        for message in messages:
            print(message)
        return True

    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        log.error("TELEGRAM_BOT_TOKEN ou TELEGRAM_CHAT_ID manquant : rien n'a ete envoye.")
        return False

    ok = True
    for message in messages:
        try:
            response = requests.post(
                API_URL.format(token=token),
                json={
                    "chat_id": chat_id,
                    "text": message,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True,
                },
                timeout=30,
            )
        except requests.RequestException as exc:
            log.error("Envoi Telegram echoue : %s", exc)
            return False
        if response.status_code != 200:
            log.error("Telegram a repondu %s : %s", response.status_code, response.text[:300])
            ok = False
    return ok
