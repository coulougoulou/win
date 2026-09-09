# Connexion MetaTrader 5

Script minimal pour se connecter a un compte MT5 et lire son etat (solde, equity,
marge, positions ouvertes).

## Prerequis

- Un **terminal MetaTrader 5 installe** sur la machine qui execute le script.
  Le paquet Python `MetaTrader5` pilote ce terminal ; il ne parle pas au broker
  tout seul. Il fonctionne sous Windows (ou sous Wine).
- Python 3.9+.
- Dans le terminal MT5 : *Outils > Options > Expert Advisors* > cocher
  **Autoriser le trading automatise** (necessaire pour les appels API).

## Installation

```bash
pip install -r requirements.txt
cp .env.example .env   # puis renseigne login / mot de passe / serveur
```

## Utilisation

```bash
python mt5_connect.py
```

Sortie type :

```
Connecte a MonBroker-Demo (build terminal 5000)
  Compte     : 12345678 — Prenom Nom
  Type       : demo
  Levier     : 1:100
  Solde      : 10000.00 EUR
  ...
```

## Securite

- `.env` est dans `.gitignore` : ne committe jamais tes identifiants.
- Commence sur un **compte demo** avant de pointer vers un compte reel.
- Le mot de passe *investisseur* (lecture seule) suffit si tu ne veux que
  consulter le compte sans passer d'ordres.
