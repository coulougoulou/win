# Alertes Honda Civic Sport

Cherche chaque jour les nouvelles annonces correspondant a des criteres precis
et envoie les nouveautes sur Telegram. Tourne sur GitHub Actions : aucune
machine a laisser allumee.

## Criteres actuels

| Critere | Valeur |
| --- | --- |
| Modele | Honda Civic, finition **Sport** |
| Annee | 2017 et plus recent |
| Kilometrage | 170 000 km et moins |
| Transmission | automatique (les annonces manuelles sont rejetees) |
| Prix | 15 000 $ et moins |
| Rayon | 1000 km autour de Saint-Hubert (QC) |

Les sources couvertes sont **Kijiji Autos** et **AutoHebdo (autoTrader.ca)**.

> **Facebook Marketplace n'est pas couvert.** Le site exige une session
> connectee et interdit le scraping automatise ; l'automatiser ferait risquer
> une suspension de compte et casserait au premier changement de leur anti-bot.
> Utilise plutot l'alerte native de Marketplace : fais ta recherche dans
> l'application, puis active les notifications sur cette recherche.

## Configuration

1. **Cree un bot Telegram.** Dans Telegram, ecris a [@BotFather](https://t.me/BotFather),
   envoie `/newbot`, suis les instructions. Il te donne un token qui ressemble a
   `123456789:AAF...`.
2. **Ecris un premier message a ton bot** (n'importe quoi, sinon il n'a pas le
   droit de t'ecrire), puis ouvre
   `https://api.telegram.org/bot<TON_TOKEN>/getUpdates` dans un navigateur et
   note le `chat.id`.
3. **Ajoute les deux secrets** dans le depot GitHub, sous
   *Settings > Secrets and variables > Actions > New repository secret* :
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`

Sans ces secrets, le job tourne quand meme mais journalise une erreur au lieu
d'envoyer quoi que ce soit.

## Utilisation

Le job s'execute automatiquement chaque matin. Pour le lancer a la main :
*Actions > Alertes Honda Civic Sport > Run workflow* (coche `dry_run` pour voir
les resultats dans les logs sans envoyer de message).

En local :

```bash
pip install -r civic_alerts/requirements.txt
python -m civic_alerts.main --dry-run            # affiche au lieu d'envoyer
python -m civic_alerts.main --dry-run --verbose  # montre aussi les rejets
python -m civic_alerts.main --sources kijiji     # une seule source
```

## Ajuster les criteres

Sans toucher au code, via des variables d'environnement (ou `env:` dans le
workflow) : `YEAR_MIN`, `PRICE_MAX`, `ODOMETER_MAX`, `RADIUS_KM`, `POSTAL_CODE`.
Pour changer la finition recherchee, modifie `trim_keywords` dans
`civic_alerts/config.py`.

## Fonctionnement

```
sources/ -> annonces brutes -> filters.py -> state.py (deja vues ?) -> notify.py
```

- `data/seen.json` retient les annonces deja notifiees pour ne pas te les
  renvoyer chaque jour ; le job le recommit apres chaque execution. Une entree
  est oubliee apres 90 jours sans reapparaitre.
- Les filtres sont **reappliques en Python** meme quand la source accepte deja
  le filtre dans l'URL : les sites ignorent parfois silencieusement un
  parametre, et une annonce hors criteres passerait.
- Une annonce dont le prix, l'annee ou le kilometrage est illisible est
  **gardee** plutot que jetee (`keep_when_unknown`) : mieux vaut une annonce a
  verifier qu'une aubaine manquee. La transmission manuelle, elle, est un rejet
  ferme quand elle est detectee.
- Si une source tombe, les autres continuent. Si *aucune* annonce n'est
  recuperee, le job echoue volontairement : c'est le signe que le scraping est
  bloque ou que le balisage a change, et un silence serait trompeur.

## Limites a connaitre

Ce sont des sites publics scrapes sans API officielle. Leur balisage change et
leurs protections anti-bot evoluent : le jour ou le job commence a echouer ou a
ne rien remonter, il faudra ajuster les selecteurs. Le test hors-ligne
(`python tests/test_civic_alerts.py`) valide la logique, pas la structure
actuelle des sites.
