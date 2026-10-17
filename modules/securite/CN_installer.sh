#!/bin/sh
# Sécurité pose, À ROOT : les deux commandes que le courtier peut lancer (relever les mesures ; exécuter UN geste de la table fermée), et rien d'autre.
set -eu
D="${CASSANDRA_MODULE_DIR:?le dossier du module}"
command -v python3 >/dev/null 2>&1 || { echo "securite : python3 est absent" >&2; exit 3; }
install -d -m 0755 -o root -g root /usr/libexec/cassandra /usr/libexec/cassandra/securite
for c in mesurer agir outils; do
  install -m 0755 -o root -g root "$D/commandes/CN_$c" "/usr/libexec/cassandra/securite/$c"
done
echo "securite : commandes posées (mesurer, agir, outils)"
