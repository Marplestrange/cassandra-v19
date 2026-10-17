#!/bin/sh
# Voix vérifie, À ROOT : les commandes sont-elles posées et exécutables ?
set -eu
for c in ecouter parler telecharger; do
  [ -x "/usr/libexec/cassandra/voix/$c" ] || { echo "voix : $c absent" >&2; exit 1; }
done
echo "voix : commandes présentes"
