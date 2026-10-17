#!/bin/sh
# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Attend le socket du collecteur, puis l'ouvre au groupe du noyau (le collecteur le crée en 
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : sensorium
# ZONE       : CN
# VERSION CN : 0.1.3  #dc12db
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Attend le socket du collecteur, puis l'ouvre au groupe du noyau (le collecteur le crée en 0600, root seul).
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.3 empreinte=dc12db ▼▼▼
# Attend le socket du collecteur, puis l'ouvre au groupe du noyau (le collecteur le crée en 0600, root seul).
# usage : CN_ouvrir-socket.sh DOSSIER_DU_SOCKET GROUPE
dossier="$1"; groupe="$2"; sock="$dossier/knowledge.sock"
i=0
while [ ! -S "$sock" ]; do
  i=$((i + 1))
  [ "$i" -le 100 ] || { echo "ouvrir-socket : le socket $sock n'apparaît pas" >&2; exit 1; }
  sleep 1
done
chgrp "$groupe" "$dossier" "$sock"
chmod 0750 "$dossier"
chmod 0660 "$sock"
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : à compléter
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
