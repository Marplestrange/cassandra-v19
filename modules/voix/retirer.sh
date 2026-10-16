#!/bin/sh
# Voix retire, À ROOT : les commandes posées par l'installation (les voix téléchargées restent).
set -eu
for c in ecouter parler telecharger; do
  rm -f "/usr/libexec/cassandra/voix/$c"
done
echo "voix : commandes retirées"
