#!/bin/sh
# Sauvegardes vérifie, À ROOT : les trois commandes rclone sont-elles posées et exécutables ?
set -eu
for c in copier lister purger; do
  [ -x "/usr/libexec/cassandra/sauvegardes/$c" ] || { echo "sauvegardes : $c absent" >&2; exit 1; }
done
echo "sauvegardes : commandes rclone présentes"
