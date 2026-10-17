#!/bin/sh
# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Canaux retire, À ROOT
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : canaux
# ZONE       : CN
# VERSION CN : 0.1.0  #bc2c92
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Canaux retire, À ROOT : la commande de connexion posée par l'installation.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=bc2c92 ▼▼▼
# Canaux retire, À ROOT : la commande de connexion posée par l'installation.
set -eu
rm -f "/usr/libexec/cassandra/canaux/connecter"
echo "canaux : commande de connexion retirée"
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : à compléter
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
