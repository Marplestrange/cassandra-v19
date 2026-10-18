#!/bin/sh
# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Sécurité pose, À ROOT
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : securite
# ZONE       : CN
# VERSION CN : 0.3.4  #0a7a55
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Sécurité pose, À ROOT : les deux commandes que le courtier peut lancer (relever les mesures ; exécuter UN geste de la table fermée), et rien d'autre.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.3.4 empreinte=0a7a55 ▼▼▼
# Sécurité pose, À ROOT : les deux commandes que le courtier peut lancer (relever les mesures ; exécuter UN geste de la table fermée), et rien d'autre.
set -eu
D="${CASSANDRA_MODULE_DIR:?le dossier du module}"
command -v python3 >/dev/null 2>&1 || { echo "securite : python3 est absent" >&2; exit 3; }
install -d -m 0755 -o root -g root /usr/libexec/cassandra /usr/libexec/cassandra/securite
for c in mesurer agir outils; do
  install -m 0755 -o root -g root "$D/commandes/CN_$c" "/usr/libexec/cassandra/securite/$c"
done
echo "securite : commandes posées (mesurer, agir, outils)"
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : à compléter
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
