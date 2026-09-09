"""Connexion a un compte MetaTrader 5 et lecture des infos du compte.

Usage:
    cp .env.example .env   # puis remplis .env
    pip install -r requirements.txt
    python mt5_connect.py

Necessite un terminal MetaTrader 5 installe sur la machine (Windows, ou Wine).
"""

from __future__ import annotations

import os
import sys
from contextlib import contextmanager

from dotenv import load_dotenv

try:
    import MetaTrader5 as mt5
except ImportError:  # pragma: no cover - depend de la plateforme
    sys.exit(
        "Le paquet MetaTrader5 n'est pas installe (ou la plateforme n'est pas "
        "supportee : il requiert Windows ou Wine).\n"
        "Installe-le avec : pip install -r requirements.txt"
    )


class MT5Error(RuntimeError):
    """Erreur remontee par le terminal MetaTrader 5."""


def _last_error() -> str:
    code, message = mt5.last_error()
    return f"[{code}] {message}"


@contextmanager
def connect(login: int, password: str, server: str, terminal_path: str | None = None):
    """Ouvre une session MT5 et la referme proprement a la sortie du bloc."""
    init_kwargs = {"login": login, "password": password, "server": server}
    if terminal_path:
        init_kwargs["path"] = terminal_path

    if not mt5.initialize(**init_kwargs):
        raise MT5Error(f"Echec de l'initialisation du terminal : {_last_error()}")

    try:
        # initialize() peut reussir sur une session deja ouverte : on force le login.
        if not mt5.login(login=login, password=password, server=server):
            raise MT5Error(f"Echec du login sur le compte {login} : {_last_error()}")
        yield mt5
    finally:
        mt5.shutdown()


def load_credentials() -> dict:
    load_dotenv()
    missing = [k for k in ("MT5_LOGIN", "MT5_PASSWORD", "MT5_SERVER") if not os.getenv(k)]
    if missing:
        raise SystemExit(
            "Variables manquantes dans l'environnement ou le fichier .env : "
            + ", ".join(missing)
        )
    return {
        "login": int(os.environ["MT5_LOGIN"]),
        "password": os.environ["MT5_PASSWORD"],
        "server": os.environ["MT5_SERVER"],
        "terminal_path": os.getenv("MT5_TERMINAL_PATH") or None,
    }


def main() -> int:
    creds = load_credentials()
    try:
        with connect(**creds) as api:
            account = api.account_info()
            if account is None:
                raise MT5Error(f"Impossible de lire les infos du compte : {_last_error()}")

            print(f"Connecte a {account.server} (build terminal {api.version()[0]})")
            print(f"  Compte     : {account.login} — {account.name}")
            print(f"  Type       : {'demo' if account.trade_mode == 0 else 'reel'}")
            print(f"  Levier     : 1:{account.leverage}")
            print(f"  Solde      : {account.balance:.2f} {account.currency}")
            print(f"  Equity     : {account.equity:.2f} {account.currency}")
            print(f"  Marge libre: {account.margin_free:.2f} {account.currency}")

            positions = api.positions_get() or ()
            print(f"  Positions ouvertes : {len(positions)}")
            for p in positions:
                side = "BUY" if p.type == api.ORDER_TYPE_BUY else "SELL"
                print(f"    {p.symbol:<10} {side:<4} {p.volume:>6.2f} lots  P/L {p.profit:>10.2f}")
    except MT5Error as exc:
        print(f"Erreur MT5 : {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
