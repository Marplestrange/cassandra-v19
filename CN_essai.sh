#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Essayer Cassandra V19 en UNE commande, sans rien installer sur la machine
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : (racine)
# ZONE       : CN
# VERSION CN : 0.1.0  #2def94
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Essayer Cassandra V19 en UNE commande, sans rien installer sur la machine : un environnement Python jetable, un serveur d'essai
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=2def94 ▼▼▼
# Essayer Cassandra V19 en UNE commande, sans rien installer sur la machine : un environnement Python jetable, un serveur d'essai
# avec ses propres données fictives (tests-ui/.donnees-dev, ignoré par git), un compte fictif. Rien de réel n'est touché.
#
#   bash CN_essai.sh            puis ouvrir http://127.0.0.1:9005  (compte ui@exemple.test, mot de passe Essai-UI-2026!)
#   bash CN_essai.sh --effacer  supprime l'environnement et les données d'essai
set -euo pipefail
cd "$(dirname "$0")"

if [ "${1:-}" = "--effacer" ]; then
  rm -rf .venv-essai tests-ui/.donnees-dev
  echo "Essai effacé."
  exit 0
fi

command -v python3 >/dev/null || { echo "Python 3.12 ou plus récent est nécessaire (python3 introuvable)." >&2; exit 1; }
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)' || { echo "Python 3.12 ou plus récent est nécessaire." >&2; exit 1; }

if [ ! -d .venv-essai ]; then
  python3 -m venv .venv-essai
  .venv-essai/bin/pip install --quiet cryptography
fi

echo "Cassandra V19 (essai) : http://127.0.0.1:${UI_PORT:-9005}   compte ui@exemple.test   mot de passe Essai-UI-2026!"
exec .venv-essai/bin/python tests-ui/serveur_dev.py
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : à compléter
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
