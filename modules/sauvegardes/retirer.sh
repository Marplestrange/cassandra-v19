#!/bin/sh
# Sauvegardes retire, À ROOT : les commandes rclone posées par l'installation.
set -eu
for c in copier lister purger; do
  rm -f "/usr/libexec/cassandra/sauvegardes/$c"
done
echo "sauvegardes : commandes rclone retirées"
