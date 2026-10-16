#!/bin/sh
# Voix pose, À ROOT : les trois commandes (écouter, parler, télécharger) que le courtier peut lancer.
set -eu
D="${CASSANDRA_MODULE_DIR:?le dossier du module}"
command -v python3 >/dev/null 2>&1 || { echo "voix : python3 est absent" >&2; exit 3; }
install -d -m 0755 -o root -g root /usr/libexec/cassandra /usr/libexec/cassandra/voix /usr/libexec/cassandra/voix/voix
for c in ecouter parler telecharger; do
  install -m 0755 -o root -g root "$D/commandes/$c" "/usr/libexec/cassandra/voix/$c"
done
echo "voix : commandes posées (les modèles se téléchargent à la demande)"
