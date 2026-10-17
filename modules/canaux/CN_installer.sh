#!/bin/sh
# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Canaux pose, À ROOT
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : canaux
# ZONE       : CN
# VERSION CN : 0.1.0  #355b76
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Canaux pose, À ROOT : la commande de connexion Telegram que le courtier peut lancer.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=355b76 ▼▼▼
# Canaux pose, À ROOT : la commande de connexion Telegram que le courtier peut lancer.
set -eu
D="${CASSANDRA_MODULE_DIR:?le dossier du module}"
command -v python3 >/dev/null 2>&1 || { echo "canaux : python3 est absent" >&2; exit 3; }
install -d -m 0755 -o root -g root /usr/libexec/cassandra /usr/libexec/cassandra/canaux
install -m 0755 -o root -g root "$D/commandes/CN_connecter" "/usr/libexec/cassandra/canaux/connecter"
echo "canaux : commande de connexion posée"
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : à compléter
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
