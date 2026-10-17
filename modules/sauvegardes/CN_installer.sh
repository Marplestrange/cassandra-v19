#!/bin/sh
# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Sauvegardes pose, À ROOT
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : sauvegardes
# ZONE       : CN
# VERSION CN : 0.1.0  #41503e
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Sauvegardes pose, À ROOT : les trois commandes rclone que le courtier peut lancer (et rien d'autre).
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=41503e ▼▼▼
# Sauvegardes pose, À ROOT : les trois commandes rclone que le courtier peut lancer (et rien d'autre).
set -eu
D="${CASSANDRA_MODULE_DIR:?le dossier du module}"
command -v rclone >/dev/null 2>&1 || { echo "sauvegardes : rclone est absent" >&2; exit 3; }
command -v python3 >/dev/null 2>&1 || { echo "sauvegardes : python3 est absent" >&2; exit 3; }
install -d -m 0755 -o root -g root /usr/libexec/cassandra /usr/libexec/cassandra/sauvegardes
for c in copier lister purger; do
  install -m 0755 -o root -g root "$D/commandes/CN_$c" "/usr/libexec/cassandra/sauvegardes/$c"
done
echo "sauvegardes : commandes rclone posées"
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : à compléter
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
