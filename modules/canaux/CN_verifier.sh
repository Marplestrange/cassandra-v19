#!/bin/sh
# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Canaux vérifie, À ROOT
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : canaux
# ZONE       : CN
# VERSION CN : 0.1.0  #91e8ad
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Canaux vérifie, À ROOT : la commande de connexion est-elle posée et exécutable ?
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=91e8ad ▼▼▼
# Canaux vérifie, À ROOT : la commande de connexion est-elle posée et exécutable ?
set -eu
[ -x "/usr/libexec/cassandra/canaux/connecter" ] || { echo "canaux : connecter absent" >&2; exit 1; }
echo "canaux : commande de connexion présente"
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : à compléter
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
