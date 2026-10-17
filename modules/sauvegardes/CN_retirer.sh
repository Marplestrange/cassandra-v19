#!/bin/sh
# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Sauvegardes retire, À ROOT
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : sauvegardes
# ZONE       : CN
# VERSION CN : 0.1.0  #d9540b
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Sauvegardes retire, À ROOT : les commandes rclone posées par l'installation.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=d9540b ▼▼▼
# Sauvegardes retire, À ROOT : les commandes rclone posées par l'installation.
set -eu
for c in copier lister purger; do
  rm -f "/usr/libexec/cassandra/sauvegardes/$c"
done
echo "sauvegardes : commandes rclone retirées"
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : à compléter
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
