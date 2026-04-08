# 🏛️ Ça va Parlement ? — Infrastructure des bots

Bots de transparence parlementaire suivant les **mouvements de collaborateurs** au Sénat, à l'Assemblée nationale et au Parlement européen.

Les changements sont publiés automatiquement sur **Bluesky** et **Telegram** chaque jour.

---

## Comptes

| Chambre | Bluesky | Telegram |
|---|---|---|
| Sénat | [@senat.cavaparlement.eu](https://bsky.app/profile/senat.cavaparlement.eu) | [@cavaparlement](https://t.me/cavaparlement) |
| Assemblée nationale | [@an.cavaparlement.eu](https://bsky.app/profile/an.cavaparlement.eu) | [@cavaparlement](https://t.me/cavaparlement) |
| Parlement européen | [@ep.cavaparlement.eu](https://bsky.app/profile/ep.cavaparlement.eu) | [@cavaparlement](https://t.me/cavaparlement) |

---

## Ce que font les bots

Chaque jour, chaque bot :

1. Récupère la liste des collaborateurs depuis la source officielle
2. Compare avec l'état de la veille (stocké dans `data/`)
3. Publie chaque arrivée, départ ou transfert sur Bluesky et Telegram
4. Sauvegarde le nouvel état dans le repo via un commit automatique

### Types d'événements détectés

| Événement | Description |
|---|---|
| 📥 Arrivée | Un collaborateur rejoint l'équipe d'un parlementaire |
| 📤 Départ | Un collaborateur quitte l'équipe d'un parlementaire |
| 🔁 Transfert | Un collaborateur passe d'un parlementaire à un autre |

---

## Sources de données

| Bot | Source | Format |
|---|---|---|
| Sénat | [senat.fr](https://www.senat.fr/pubagas/liste_senateurs_collaborateurs.pdf) | PDF (pdfplumber) |
| Assemblée nationale | [data.assemblee-nationale.fr](https://data.assemblee-nationale.fr) | CSV open data |
| Parlement européen | [EP Open Data API v2](https://data.europarl.europa.eu/api/v2) + [europarl.europa.eu](https://www.europarl.europa.eu/meps/en/assistants) | API JSON + scraping HTML |

---

## Structure du repo

```
cavaparlement-bot/
├── .github/
│   └── workflows/
│       ├── senat.yml          # Cron quotidien 07h00
│       ├── assemblee.yml      # Cron quotidien 07h30
│       └── europarl.yml       # Cron quotidien 08h00
│
├── bots/
│   ├── senat/
│   │   ├── main.py            # Point d'entrée
│   │   ├── scraper.py         # Téléchargement et parsing PDF
│   │   ├── diff.py            # Réexporte depuis shared/
│   │   ├── publisher.py       # Formatage et publication
│   │   ├── update_history.py  # Réexporte depuis shared/
│   │   ├── senator_lookup.py  # Mapping sénateurs / groupes / handles Bluesky
│   │   └── senator_reply.py   # Reply Bluesky avec @handle du sénateur
│   │
│   ├── assemblee/
│   │   ├── main.py            # Point d'entrée
│   │   ├── scraper.py         # Téléchargement CSV AN
│   │   └── publisher.py       # Formatage et publication
│   │
│   ├── europarl/
│   │   └── bot.py             # Script unique (scraping + diff + publication)
│   │
│   └── telegram/
│       └── bot.py             # Bot conversationnel Telegram (polling)
│
├── shared/
│   ├── __init__.py
│   ├── diff.py                # compute_diff — commun sénat + AN
│   ├── update_history.py      # append_events — historique unifié
│   ├── political_mapping.py   # Groupes / emojis / hashtags (sénat, AN, EP)
│   └── utils.py               # fmt_date, post_telegram, make_session
│
├── data/
│   ├── senat/
│   │   ├── snapshot.json      # État courant des collaborateurs
│   │   ├── senateurs_info.json
│   │   ├── dates.json         # Dates de prise de poste
│   │   └── compteur_ras.json  # Compteur jours sans mouvement
│   ├── assemblee/
│   │   ├── snapshot.json
│   │   ├── deputes_info.json
│   │   ├── dates.json
│   │   └── compteur_ras.json
│   ├── europarl/
│   │   └── state.json
│   └── unified/
│       └── history.json       # Historique consolidé sénat + AN
│
├── tests/
│   └── test_telegram.py       # Test d'envoi Telegram
│
├── requirements.txt
├── .gitignore
└── LICENSE
```

---

## Lancer un bot localement

```bash
# Cloner le repo
git clone https://github.com/cavaparlement/cavaparlement-bot.git
cd cavaparlement-bot

# Installer les dépendances
pip install -r requirements.txt

# Configurer les variables d'environnement
export BLUESKY_SENAT_IDENTIFIER="senat.cavaparlement.eu"
export BLUESKY_SENAT_PASSWORD="..."
export TELEGRAM_BOT_TOKEN="..."

# Lancer le bot Sénat
python -m bots.senat.main

# Lancer le bot Assemblée nationale
python -m bots.assemblee.main

# Lancer le bot Parlement européen
python -m bots.europarl.bot
```

---

## Variables d'environnement

Toutes les variables sont stockées comme **secrets GitHub** et injectées dans les workflows.

| Variable | Usage |
|---|---|
| `BLUESKY_SENAT_IDENTIFIER` | Handle du compte @senat.cavaparlement.eu |
| `BLUESKY_SENAT_PASSWORD` | Mot de passe applicatif Bluesky |
| `BLUESKY_ASSEMBLEE_IDENTIFIER` | Handle du compte @an.cavaparlement.eu |
| `BLUESKY_ASSEMBLEE_PASSWORD` | Mot de passe applicatif Bluesky |
| `BLUESKY_EUROPARL_PASSWORD` | Mot de passe applicatif Bluesky |
| `TELEGRAM_BOT_TOKEN` | Token du bot Telegram |
| `TELEGRAM_CHAT_ID` | ID du canal Telegram (bot conversationnel) |

---

## Automatisation GitHub Actions

Les trois bots tournent sur cron quotidien avec décalage pour éviter les conflits de commit :

```
07h00 UTC — CavaSenat
07h30 UTC — CavaAssemblée
08h00 UTC — CavaEuroparl
```

Chaque workflow :
1. Installe les dépendances
2. Exécute le bot
3. Commite les fichiers `data/` mis à jour avec `[skip ci]`

Les workflows peuvent aussi être déclenchés manuellement depuis l'onglet **Actions** de GitHub.

> **Note :** Si un workflow est inactif plus de 60 jours, GitHub le désactive automatiquement. Il suffit de le réactiver depuis l'onglet Actions.

---

## Bot conversationnel Telegram

`bots/telegram/bot.py` est un bot en polling continu qui répond aux questions en langage naturel dans un chat privé Telegram. Il utilise **GPT-4o-mini** pour analyser les intentions et interroge les snapshots et l'historique stockés dans `data/`.

Commandes disponibles :

```
mouvements pour [nom]     → historique des mouvements d'un parlementaire
collaborateurs de [nom]   → liste des collaborateurs actuels
mouvements du jour        → changements détectés aujourd'hui
derniers mouvements       → 15 derniers événements
stats par groupe          → répartition par groupe politique
```

Le bot est déployé en continu sur **[Render](https://render.com)** (service web always-on).

---

## Licence

© Ça va Parlement ? — Tous droits réservés.

Ce code source est publié à titre de transparence. Il ne peut pas être copié, réutilisé, modifié ou redistribué sans autorisation explicite.

Pour toute demande : [hello@cavaparlement.eu](mailto:hello@cavaparlement.eu)
