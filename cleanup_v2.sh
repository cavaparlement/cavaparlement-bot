#!/usr/bin/env bash
set -e

echo "==> Nettoyage des fichiers parasites"
find . -name ".DS_Store" -delete || true
find . -name "*.log" -delete || true
find . -name "__pycache__" -type d -exec rm -rf {} + || true
find . -name "*.pyc" -delete || true

echo "==> Création des dossiers utiles"
mkdir -p docs
mkdir -p shared
mkdir -p data/europarl
mkdir -p tests

echo "==> Déplacement prudent de certains fichiers Europarl"
if [ -f "bots/europarl/test_post.py" ]; then
  mv bots/europarl/test_post.py tests/test_europarl_post.py
fi

if [ -f "bots/europarl/state.json" ]; then
  mv bots/europarl/state.json data/europarl/state.json
fi

echo "==> Création d'un .gitignore propre"
cat > .gitignore <<'EOF'
__pycache__/
*.pyc
*.pyo
*.log
.DS_Store
.env
.venv/
venv/
dist/
build/
EOF

echo "==> Création d'un README plus propre"
cat > README.md <<'EOF'
# cavaparlement-bot

Infrastructure des bots du projet Ça va Parlement.

## Contenu
- `bots/senat/` : bot Sénat
- `bots/assemblee/` : bot Assemblée nationale
- `bots/europarl/` : bot Parlement européen
- `bots/telegram/` : bot conversationnel Telegram
- `data/` : données persistées et snapshots
- `tests/` : scripts de test

## Objectif
Collecter, enrichir, historiser et publier les mouvements de collaborateurs parlementaires,
puis produire des jeux de données réutilisables pour le site cavaparlement.eu.
EOF

echo "==> Création d'un requirements.txt provisoire un peu plus large"
cat > requirements.txt <<'EOF'
requests
openai
atproto
python-telegram-bot
beautifulsoup4
lxml
EOF

echo "==> Création d'un fichier d'architecture"
cat > docs/architecture.md <<'EOF'
# Architecture

## Bots
- Sénat : collecte PDF, diff, historique, publication
- Assemblée : collecte CSV/source, diff, historique, publication
- Europarl : expérimental
- Telegram : bot conversationnel

## Données
- `data/senat/`
- `data/assemblee/`
- `data/europarl/`
- `data/unified/` pour les futurs jeux consolidés

## Étapes suivantes
1. Corriger les imports Python
2. Vérifier les workflows GitHub Actions
3. Générer des données unifiées pour le site
EOF

echo "==> État final"
find . -maxdepth 3 | sort

echo ""
echo "Cleanup terminé."
echo "Relis vite les changements puis fais :"
echo "  git status"
echo "  git add ."
echo "  git commit -m 'Cleanup repo structure'"
echo "  git push"

