"""Memoire des annonces deja notifiees, persistee en JSON dans le depot."""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta
from pathlib import Path

log = logging.getLogger(__name__)


def load(path: str | Path) -> dict[str, str]:
    file = Path(path)
    if not file.exists():
        return {}
    try:
        data = json.loads(file.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        log.warning("Etat illisible (%s), on repart a zero.", file)
        return {}
    return data.get("seen", {}) if isinstance(data, dict) else {}


def save(path: str | Path, seen: dict[str, str], ttl_days: int) -> None:
    file = Path(path)
    file.parent.mkdir(parents=True, exist_ok=True)
    cutoff = date.today() - timedelta(days=ttl_days)
    pruned = {
        key: seen_on
        for key, seen_on in seen.items()
        if _as_date(seen_on) >= cutoff
    }
    payload = {
        "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "seen": dict(sorted(pruned.items())),
    }
    file.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _as_date(raw: str) -> date:
    try:
        return date.fromisoformat(raw[:10])
    except (ValueError, TypeError):
        return date.today()
