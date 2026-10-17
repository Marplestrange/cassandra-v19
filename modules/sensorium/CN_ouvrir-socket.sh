#!/bin/sh
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
