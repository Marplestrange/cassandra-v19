#!/bin/sh
# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Voix retire, À ROOT
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : voix
# ZONE       : CN
# VERSION CN : 0.1.0  #a3703c
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Voix retire, À ROOT : les commandes posées par l'installation (les voix téléchargées restent).
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=a3703c ▼▼▼
# Voix retire, À ROOT : les commandes posées par l'installation (les voix téléchargées restent).
set -eu
for c in ecouter parler telecharger; do
  rm -f "/usr/libexec/cassandra/voix/$c"
done
echo "voix : commandes retirées"
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : à compléter
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
