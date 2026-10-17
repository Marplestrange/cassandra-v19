#!/bin/sh
# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Voix vérifie, À ROOT
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : voix
# ZONE       : CN
# VERSION CN : 0.1.0  #9700b8
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Voix vérifie, À ROOT : les commandes sont-elles posées et exécutables ?
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=9700b8 ▼▼▼
# Voix vérifie, À ROOT : les commandes sont-elles posées et exécutables ?
set -eu
for c in ecouter parler telecharger; do
  [ -x "/usr/libexec/cassandra/voix/$c" ] || { echo "voix : $c absent" >&2; exit 1; }
done
echo "voix : commandes présentes"
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : à compléter
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
