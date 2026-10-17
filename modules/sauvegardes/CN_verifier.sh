#!/bin/sh
# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Sauvegardes vérifie, À ROOT
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : sauvegardes
# ZONE       : CN
# VERSION CN : 0.1.0  #1d6d98
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Sauvegardes vérifie, À ROOT : les trois commandes rclone sont-elles posées et exécutables ?
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=1d6d98 ▼▼▼
# Sauvegardes vérifie, À ROOT : les trois commandes rclone sont-elles posées et exécutables ?
set -eu
for c in copier lister purger; do
  [ -x "/usr/libexec/cassandra/sauvegardes/$c" ] || { echo "sauvegardes : $c absent" >&2; exit 1; }
done
echo "sauvegardes : commandes rclone présentes"
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : à compléter
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
